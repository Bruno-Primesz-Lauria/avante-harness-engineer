"""Confere o kit O-CC sem o Claude Code: adapta uma copia temporaria e simula, pelo wrapper de captura,
os hooks de duas fatias conformes. Nao e observacao: nada aqui vale como G2."""
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

raiz = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(raiz / "adaptadores"), str(raiz / "implementacao")]
from provas import Provas, ler

SEMEAR = ("adaptadores", "implementacao", "formas", "agentes", "configuracao", ".claude", "AGENTS.md", "CLAUDE.md")
SESSAO = "validar-occ-sessao"

(raiz / ".execucoes").mkdir(exist_ok=True)
kit = runpy.run_path(str(Path(__file__).with_name("preparar.py")))
compile(kit["CAPTURAR"], "capturar.py", "exec")
compile(kit["CONFERIR"], "conferir.py", "exec")


def semear(copia):
    for nome in SEMEAR:
        origem = raiz / nome
        if origem.is_dir():
            shutil.copytree(origem, copia / nome, ignore=shutil.ignore_patterns("__pycache__", ".fixtures"))
        else:
            shutil.copy2(origem, copia / nome)


def hook(copia, evento):
    r = subprocess.run([sys.executable, str(copia / "observacao/capturar.py"), "claude_code"],
                       input=json.dumps(evento).encode("utf-8"), capture_output=True, cwd=copia)
    assert r.returncode == 0, (evento.get("hook_event_name"), r.stderr.decode("utf-8", "replace"))
    return json.loads(r.stdout.decode("utf-8") or "{}")


def agente(copia, papel, agente_id, uso, comando=None, segundo_plano=False):
    """Agent pre, shell do subagente (com agent_id) e Agent pos; devolve o contexto do pos.

    Em segundo plano (CLI 2.1.292), o pos volta async_launched antes do shell e o fim chega no SubagentStop.
    """
    base = dict(session_id=SESSAO, tool_use_id=uso)
    hook(copia, dict(base, hook_event_name="PreToolUse", tool_name="Agent",
                     tool_input=dict(subagent_type=papel, description="O-CC", prompt="validar")))
    if segundo_plano:
        resposta = hook(copia, dict(base, hook_event_name="PostToolUse", tool_name="Agent",
                                    tool_input=dict(subagent_type=papel),
                                    tool_response=dict(isAsync=True, status="async_launched", agentId=agente_id)))
    if comando is not None:
        shell = dict(session_id=SESSAO, agent_id=agente_id, agent_type=papel, tool_name="Bash",
                     tool_use_id=uso + "-sh", tool_input=dict(command=comando))
        resposta_shell = hook(copia, dict(shell, hook_event_name="PreToolUse"))
        assert "permissionDecision" not in resposta_shell.get("hookSpecificOutput", {}), (papel, resposta_shell)
        hook(copia, dict(shell, hook_event_name="PostToolUse", tool_response=dict(
            stdout="ok", stderr="", interrupted=False, isImage=False, noOutputExpected=False)))
    if segundo_plano:
        parada = hook(copia, dict(session_id=SESSAO, hook_event_name="SubagentStop", agent_id=agente_id,
                                  agent_type=papel, stop_hook_active=False))
        assert parada == {}, (papel, parada)
    else:
        resposta = hook(copia, dict(base, hook_event_name="PostToolUse", tool_name="Agent",
                                    tool_input=dict(subagent_type=papel),
                                    tool_response=dict(status="completed", agentId=agente_id, agentType=papel)))
    contexto = resposta["hookSpecificOutput"]["additionalContext"]
    assert "agente_id=" + agente_id in contexto, contexto
    return contexto


def revisao(agente_id, criterio):
    return dict(agente_id=agente_id,
                entrada=dict(intencao_ref="contrato.yaml", aceite_ref="contrato.yaml",
                             baseline_ref="baseline.json", provas_refs=[]),
                veredito="nao_quebrei", tentativas=[dict(id="t1", procedimento="Reproduzir", resultado="pass")],
                achados=[], cobertura=[dict(criterio_id=criterio, coberto=True)])


with TemporaryDirectory(prefix="validar-occ-", dir=raiz / ".execucoes") as pasta:
    copia = Path(pasta)
    semear(copia)
    ajustes = kit["adaptar"](copia)

    config = json.loads((copia / ".claude/settings.json").read_text(encoding="utf-8"))
    comandos = [g["command"] for grupos in config["hooks"].values() for grupo in grupos for g in grupo["hooks"]]
    assert comandos and all("observacao/capturar.py" in c and "entrada.py" not in c for c in comandos), comandos
    assert {"SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop", *kit["EVENTOS_EXTRAS"]} <= set(config["hooks"])
    assert not kit["LIMITE_TEMPORARIO"].search((copia / "AGENTS.md").read_text(encoding="utf-8"))
    assert ajustes["agentes_obrigatorios_copia"]["claude_code"] == ["manutencao", "docs"]

    contratos = {nome: yaml.safe_load(texto) for nome, texto in kit["contratos"](copia).items()}
    comando_teste = contratos["observacao/contrato-manutencao.yaml"]["aceite"][0]["verificacao"]["comando"]
    comando_local = contratos["observacao/contrato-manutencao.yaml"]["aceite"][1]["verificacao"]["comando"]
    assert comando_teste.startswith(f"cd -- '{copia.as_posix()}' && "), comando_teste

    hook(copia, dict(hook_event_name="SessionStart", session_id=SESSAO, source="startup"))
    # M9a: a guarda nega no subagente, pelo prefixo de cwd errado, antes de qualquer fatia.
    negada = hook(copia, dict(hook_event_name="PreToolUse", session_id=SESSAO, agent_id="a-guarda", agent_type="dab",
                              tool_name="Bash", tool_use_id="uso-guarda", tool_input=dict(
                                  command=f"cd -- '{copia.as_posix()}/fixture/manutencao' && "
                                          "databricks bundle validate -t sandbox -p fixture")))
    assert negada["hookSpecificOutput"]["permissionDecision"] == "deny", negada

    # Fatia M: mesmo plano e mesma ordem do roteiro.
    m = Provas(copia, copia / ".execucoes", SESSAO, runtime="claude_code")
    m.iniciar(contratos["observacao/contrato-manutencao.yaml"])
    plano = ler(m.pasta() / "estado.json")["chamadas_previstas"]
    assert [c["papel"] for c in plano] == ["test", "config", "implement", "test", "refute", "dab"]
    print("manutencao", [c["id"] for c in plano])
    try:
        m.fechar("DONE", "tentativa antes das chamadas")
    except ValueError as erro:
        assert "chamada:dab" in str(erro), erro
    else:
        raise AssertionError("o falso DONE deveria ser recusado")
    agente(copia, "test", "a-prep", "uso-prep", segundo_plano=True)
    agente(copia, "config", "a-config", "uso-config", segundo_plano=True)
    agente(copia, "implement", "a-impl", "uso-impl", segundo_plano=True)
    agente(copia, "test", "a-test", "uso-test", comando_teste, segundo_plano=True)
    contexto = agente(copia, "refute", "a-refute", "uso-refute", segundo_plano=True)
    agente(copia, "dab", "a-dab", "uso-dab", comando_local, segundo_plano=True)
    estado = m.estado(m.pasta())
    assert estado["provas"].keys() == {"teste", "ambiente_local"}, estado["provas"].keys()
    agentes = {k: ler(m.pasta() / v["ref"])["dados"]["agente_id"] for k, v in estado["provas"].items()}
    assert agentes == {"teste": "a-test", "ambiente_local": "a-dab"}, agentes
    m.revisar(revisao(contexto.split("agente_id=")[1].split(".")[0], "teste"))
    assert m.pendencias(m.pasta(), m.estado(m.pasta()))[1] == [], m.pendencias(m.pasta(), m.estado(m.pasta()))[1]
    assert m.fechar("DONE", "Fatia M conforme")["status"] == "DONE"

    # Fatia D: inspecao documental com docs e refute.
    d = Provas(copia, copia / ".execucoes", SESSAO, runtime="claude_code")
    d.iniciar(contratos["observacao/contrato-docs.yaml"])
    plano = ler(d.pasta() / "estado.json")["chamadas_previstas"]
    assert [c["papel"] for c in plano] == ["docs", "refute"]
    print("docs", [c["id"] for c in plano])
    agente(copia, "docs", "a-docs", "uso-docs")
    d.inspecionar(**{"criterio_id": "guia", "checagens": [{"id": "fonte", "resultado": "pass"}]})
    contexto = agente(copia, "refute", "a-refute-2", "uso-refute-2")
    d.revisar(revisao(contexto.split("agente_id=")[1].split(".")[0], "guia"))
    assert d.fechar("DONE", "Fatia D conforme")["status"] == "DONE"

    brutos = copia / ".execucoes/sondagens/brutos/claude_code/observacao_occ/hooks"
    nomes = sorted(p.name.split("_")[1] for p in brutos.glob("*.json"))
    # 1 + guarda + 8 Agent x2 + 6 SubagentStop (M em segundo plano) + 2 shells x2
    assert len(nomes) == 28 and nomes.count("SessionStart") == 1 and nomes.count("SubagentStop") == 6, nomes
    saida = subprocess.run([sys.executable, str(copia / "observacao/conferir.py")], capture_output=True, cwd=copia)
    assert saida.returncode == 0, saida.stderr.decode("utf-8", "replace")
    conferido = json.loads(saida.stdout.decode("utf-8"))
    assert [f["fecho"]["status"] for f in conferido["fatias"]] == ["DONE", "DONE"], conferido["fatias"]
print("Kit conferido localmente: adaptacao, wrapper de captura e fatias M e D simuladas; Claude Code nao executado.")
