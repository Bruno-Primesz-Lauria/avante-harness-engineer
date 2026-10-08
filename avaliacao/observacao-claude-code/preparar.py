"""Prepara a copia temporaria da observacao O-CC (PLANO-AGENTES-TRILHAS, painel).

Uso, com o HEAD commitado: py -3 avaliacao/observacao-claude-code/preparar.py
A copia fica em ../.execucoes/observacao-claude-code-<instante>, ao lado do clone.
Nao abre o Claude Code, nao altera o repositorio e nao cria branch, worktree ou Git na copia.
"""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import tarfile

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ.parent / ".execucoes"
PAPEIS = ("map", "config", "implement", "test", "refute", "docs", "dab")
TRILHAS_CC = ["manutencao", "docs"]
REMOVER = (".cursor", ".codex", ".opencode", "prj-avante-analytics-adb")
# O coordenador nao deve achar o roteiro na copia; o humano (ou o agente que conduz) le no clone.
KITS = ("avaliacao/observacao-claude-code/", "avaliacao/observacao-cursor/")
# Eventos que a copia precisa capturar. SubagentStart e UserPromptSubmit sao so capturados (o adaptador
# devolve {}); SubagentStop ja vem do gerador, porque registra a chamada de Agent em segundo plano.
EVENTOS_EXTRAS = ("SubagentStart", "SubagentStop", "UserPromptSubmit")
# Skill, leitura e escrita: o payload traz agent_id e o caminho, o que atribui cada edicao a um subagente.
CAPTURA_FERRAMENTAS = "^(Skill|Read|Edit|Write)$"

FIXTURE = {
    "fixture/manutencao/regras.yaml": "desconto_percentual: 0\n",
    "fixture/manutencao/calc.py": "def preco_final(valor):\n    return valor\n",
    "fixture/manutencao/teste_calc.py": (
        "import unittest\n\nfrom calc import preco_final\n\n\n"
        "class PrecoFinal(unittest.TestCase):\n"
        "    def test_zero(self):\n        self.assertEqual(preco_final(0), 0)\n\n\n"
        "if __name__ == \"__main__\":\n    unittest.main()\n"),
    "fixture/manutencao/ambiente_local.py": (
        "import sys\n\nprint(\"ambiente-local-ok python\", sys.version_info[:2])\n"),
    "fixture/manutencao/autorizacao-local.md": (
        "# Autorizacao local (fixture O-CC)\n\n"
        "Autorizado apenas: `py -3 fixture/manutencao/ambiente_local.py`, na maquina local.\n"
        "Sem plataforma Databricks, sem bundle, sem rede, sem deploy e sem run.\n"),
    # Alvo da guarda no M9a: sem ele a guarda nega por bundle_nao_verificado, nao por cwd_incorreto.
    "fixture/bundle-local/databricks.yml": "bundle:\n  name: saneamento_migracao\n",
    "fixture/docs/guia.md": (
        "# Guia do desconto (fixture)\n\nFonte: fixture/manutencao/regras.yaml.\n\n"
        "TODO: descrever a regra de desconto.\n"),
}

CONTRATO_BASE = """\
artefatos_raiz: .execucoes/provas
prazo: null
fora: [prj-avante-analytics-adb, databricks, deploy, run]
orcamento: {ciclos_correcao_max: 3, ciclos_sem_progresso_max: 2, repeticoes_operacao_max: 2}
responsaveis: {coordenador: agente, executor: agente, verificador: suite_local}
"""


def contratos(copia):
    """Contratos da copia. O comando declarado leva o prefixo literal de cwd: no Claude Code o cwd do evento
    e o da sessao e nao vale como prova. Os subagentes test e dab tem a ferramenta Bash, entao o prefixo e `cd --`.
    """
    pre = f"cd -- '{Path(copia).as_posix()}' && "
    return {
        "observacao/contrato-manutencao.yaml": f"""\
objetivo: Aplicar o desconto de fixture/manutencao/regras.yaml em preco_final
termino_fatia: Teste, ambiente local e revisao independente atuais
trilha: manutencao
superficie: [fixture/manutencao/regras.yaml, fixture/manutencao/calc.py, fixture/manutencao/teste_calc.py]
fontes: [fixture/manutencao/regras.yaml]
aceite:
  - id: teste
    tipo: teste
    obrigatorio: true
    esperado: preco_final(200) igual a 180 com desconto_percentual 10; exit 0
    verificacao:
      comando: "{pre}py -3 -m unittest discover -s fixture/manutencao -p teste_calc.py"
      cwd: .
      caminhos: [fixture/manutencao/regras.yaml, fixture/manutencao/calc.py, fixture/manutencao/teste_calc.py]
  - id: ambiente_local
    tipo: ambiente
    obrigatorio: true
    esperado: O script local termina com exit 0
    autorizacao_ref: fixture/manutencao/autorizacao-local.md
    verificacao:
      comando: "{pre}py -3 fixture/manutencao/ambiente_local.py"
      cwd: .
      caminhos: [fixture/manutencao/ambiente_local.py]
""" + CONTRATO_BASE,
        "observacao/contrato-docs.yaml": """\
objetivo: Documentar a regra de desconto em fixture/docs/guia.md
termino_fatia: Guia inspecionado e revisado
trilha: docs
superficie: [fixture/docs/guia.md]
fontes: [fixture/manutencao/regras.yaml]
aceite:
  - id: guia
    tipo: inspecao_documental
    obrigatorio: true
    esperado: O guia afirma o desconto igual ao de regras.yaml
    verificacao:
      caminhos: [fixture/docs/guia.md]
      checagens: [{id: fonte, esperado: O percentual do guia casa com fixture/manutencao/regras.yaml}]
      produtor: coordenador
""" + CONTRATO_BASE,
        "observacao/inspecao-docs.yaml": """\
criterio_id: guia
checagens: [{id: fonte, resultado: pass}]
""",
    }


CAPTURAR = '''\
"""Repassa o payload do hook ao entrada.py real, preserva stdout, stderr e exit e grava o bruto."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

COPIA = Path(__file__).resolve().parents[1]
BASE = COPIA / ".execucoes/sondagens/brutos/claude_code/observacao_occ"
DESTINO = BASE / "hooks"
TRANSCRIPTS = BASE / "transcripts"


def copiar_transcript(payload):
    """Guarda o transcript do subagente como evidencia para quem confere. O adaptador nao o usa."""
    origem, agente = payload.get("agent_transcript_path"), payload.get("agent_id")
    if not isinstance(origem, str) or not isinstance(agente, str) or not agente.isalnum():
        return "sem_transcript"
    try:
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, TRANSCRIPTS / (agente + ".jsonl"))
        return "copiado"
    except OSError as erro:
        return "nao_copiado: " + str(erro)


def principal():
    corpo = sys.stdin.buffer.read()
    r = subprocess.run([sys.executable, str(COPIA / "adaptadores/entrada.py"), *sys.argv[1:]],
                       input=corpo, capture_output=True, cwd=COPIA)
    try:
        agora = datetime.now(timezone.utc)
        nome, transcript = None, None
        try:
            payload = json.loads(corpo.decode("utf-8-sig"))
            nome = payload.get("hook_event_name")
            if nome == "SubagentStop":
                transcript = copiar_transcript(payload)
        except (ValueError, AttributeError):
            payload = {"nao_json": corpo.decode("utf-8", "replace")}
        registro = dict(recebido_em=agora.isoformat(), argv=sys.argv[1:], payload_sha256=sha256(corpo).hexdigest(),
                        payload=payload, stdout=r.stdout.decode("utf-8", "replace"),
                        stderr=r.stderr.decode("utf-8", "replace"), exit_entrada=r.returncode,
                        transcript=transcript)
        DESTINO.mkdir(parents=True, exist_ok=True)
        (DESTINO / f"{agora:%Y-%m-%dT%H%M%S.%f}+0000_{nome or 'desconhecido'}_{uuid4().hex[:6]}.json").write_text(
            json.dumps(registro, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    except OSError as erro:
        print(f"[capturar] bruto nao gravado: {erro}", file=sys.stderr)
    sys.stdout.buffer.write(r.stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(principal())
'''

CONFERIR = '''\
"""Leitura somente dos registros da copia: chamadas, provas, revisoes e fecho. Nao grava provas."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

COPIA = Path(__file__).resolve().parents[1]
REG = COPIA / ".execucoes"
SAIDA = REG / "sondagens/brutos/claude_code/observacao_occ/conferencias.jsonl"


def ler(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def dados(pasta, ref):
    return ler(pasta / ref)["dados"]


def fatia(estado_json):
    pasta = estado_json.parent
    e = ler(estado_json)
    fecho = dados(pasta, e["fecho"]["ref"]) if e["fecho"] else None
    return dict(
        execucao_id=e["execucao_id"], trilha=e["trilha"], runtime=e["runtime"], tentativa=e["tentativa"],
        previstas=[c["id"] for c in e["chamadas_previstas"]],
        observadas=[dict(id=c["id"], **{k: dados(pasta, c["ref"])[k] for k in ("papel", "status", "ids_observados", "inicio", "fim")})
                    for c in e["chamadas_observadas"]],
        provas={k: dict(ref=v["ref"], **{x: dados(pasta, v["ref"]).get(x) for x in ("resultado", "validade", "exit_code", "exit_code_origem", "agente_id")})
                for k, v in e["provas"].items()},
        inspecoes={k: {x: dados(pasta, v["ref"])[x] for x in ("resultado", "validade")} for k, v in e["inspecoes"].items()},
        revisoes=[dict(ref=r["ref"], agente_id=dados(pasta, r["ref"]).get("agente_id"), veredito=dados(pasta, r["ref"])["veredito"]) for r in e["revisoes"]],
        fecho=fecho and dict(status=fecho["status"], pendencias=fecho["pendencias"]))


def principal():
    fixture = {p.relative_to(COPIA).as_posix(): sha256(p.read_bytes()).hexdigest()[:12]
               for p in sorted((COPIA / "fixture").rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    estados = sorted((REG / "provas").glob("*/principal/estado.json"), key=lambda p: p.stat().st_mtime)
    saida = dict(em=datetime.now(timezone.utc).isoformat(), fixture=fixture, fatias=[fatia(p) for p in estados])
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(saida, ensure_ascii=False) + "\\n")
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    principal()
'''


def git(*args, texto=True):
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=texto, encoding="utf-8" if texto else None)
    return r.returncode, r.stdout


def mostrar(caminho):
    codigo, saida = git("show", f"HEAD:{caminho}")
    return saida if codigo == 0 else None


def verificar_head():
    """Lista o que falta para o HEAD ser o final (C4, C5, B2-CC e D-CC commitados)."""
    faltas = []
    codigo, sujo = git("status", "--porcelain", "--untracked-files=no", "--",
                       ".claude", "adaptadores/claude_code", "adaptadores/executar.py", "adaptadores/prova.py",
                       "adaptadores/gerar_agentes.py", "agentes", "implementacao/provas.py",
                       "implementacao/formas.py", "formas/catalogo.yaml", "configuracao/politica.json", "AGENTS.md")
    if codigo != 0 or sujo.strip():
        faltas.append("ha alteracao de C4/B2/D-CC nao commitada: " + " ".join(sujo.split()[:8]))
    for papel in PAPEIS:
        if mostrar(f".claude/agents/{papel}.md") is None:
            faltas.append(f".claude/agents/{papel}.md ausente do HEAD (B2-CC)")
    config = mostrar(".claude/settings.json") or ""
    if not all(n in config for n in ('"PostToolUse"', '"PostToolUseFailure"', '"Stop"', '"SubagentStop"', "Agent")):
        faltas.append(".claude/settings.json do HEAD sem PostToolUse, PostToolUseFailure, Stop, SubagentStop "
                      "e matcher Agent (D-CC)")
    prova = mostrar("adaptadores/prova.py") or ""
    if not all(n in prova for n in ("inspecionar", "revisar", "triar")):
        faltas.append("adaptadores/prova.py do HEAD sem inspecionar/revisar/triar (C4)")
    if "fora_do_refute" not in (mostrar("implementacao/provas.py") or ""):
        faltas.append("implementacao/provas.py do HEAD sem o vinculo do ataque ao refute (C4)")
    if "agente_id=" not in (mostrar("adaptadores/claude_code/prova.py") or ""):
        faltas.append("adaptadores/claude_code/prova.py do HEAD nao devolve o agente_id ao coordenador (D-CC)")
    if "async_launched" not in (mostrar("adaptadores/claude_code/prova.py") or ""):
        faltas.append("adaptadores/claude_code/prova.py do HEAD nao registra Agent em segundo plano")
    rota = mostrar("agentes/roteamento.yaml") or ""
    if len(re.findall(r"claude_code: \{[^}]*instalado: true", rota)) != len(PAPEIS):
        faltas.append("agentes/roteamento.yaml do HEAD sem instalado: true no claude_code para os sete papeis (B2-CC)")
    try:
        json.loads(mostrar("configuracao/politica.json"))["agentes_obrigatorios"]
    except (TypeError, ValueError, KeyError):
        faltas.append("configuracao/politica.json do HEAD ilegivel")
    return faltas


def extrair(destino):
    proc = subprocess.Popen(["git", "-C", str(RAIZ), "archive", "--format=tar", "HEAD"], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
        for membro in tar:
            if membro.name.split("/", 1)[0] not in REMOVER and not any((membro.name + "/").startswith(k) for k in KITS):
                tar.extract(membro, destino, filter="data")
    if proc.wait() != 0:
        raise RuntimeError("git archive falhou")


def adaptar(destino):
    """Aplica as mudancas so da copia: chave, hooks de captura, fixtures e contratos."""
    destino = Path(destino)
    for kit in KITS:
        if (destino / kit).exists():
            raise RuntimeError("a copia nao pode ter o roteiro")
    if (destino / ".git").exists():
        raise RuntimeError("a copia nao pode ter Git")
    arquivo = destino / "configuracao/politica.json"
    politica = json.loads(arquivo.read_text(encoding="utf-8-sig"))
    politica["agentes_obrigatorios"]["claude_code"] = TRILHAS_CC
    politica["registros_raiz"] = "../.execucoes"
    politica["bundle_local"] = "../fixture/bundle-local"
    politica["deploy_sandbox_autorizado"] = False
    arquivo.write_text(json.dumps(politica, indent=2) + "\n", encoding="utf-8")

    ajustes = destino / ".claude/settings.json"
    config = json.loads(ajustes.read_text(encoding="utf-8-sig"))
    trocados = 0
    for grupos in config["hooks"].values():
        for grupo in grupos:
            for gancho in grupo["hooks"]:
                if "adaptadores/entrada.py" not in gancho["command"]:
                    raise RuntimeError("hook inesperado: " + gancho["command"])
                gancho["command"] = gancho["command"].replace("adaptadores/entrada.py", "observacao/capturar.py")
                trocados += 1
    molde = config["hooks"]["SessionStart"][0]["hooks"]
    for evento in EVENTOS_EXTRAS:
        config["hooks"].setdefault(evento, [{"hooks": copy.deepcopy(molde)}])
    for evento in ("PreToolUse", "PostToolUse"):
        config["hooks"][evento].append({"matcher": CAPTURA_FERRAMENTAS, "hooks": copy.deepcopy(molde)})
    ajustes.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    (destino / "observacao").mkdir()
    (destino / "observacao/capturar.py").write_text(CAPTURAR, encoding="utf-8")
    (destino / "observacao/conferir.py").write_text(CONFERIR, encoding="utf-8")
    for ref, conteudo in {**FIXTURE, **contratos(destino)}.items():
        (destino / ref).parent.mkdir(parents=True, exist_ok=True)
        (destino / ref).write_text(conteudo, encoding="utf-8", newline="\n")
    return dict(hooks_trocados=trocados, eventos_extras=list(EVENTOS_EXTRAS), captura_ferramentas=CAPTURA_FERRAMENTAS,
                agentes_obrigatorios_copia=politica["agentes_obrigatorios"])


def versao_claude():
    try:
        r = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def principal():
    faltas = verificar_head()
    if faltas:
        print("[preparar_occ] HEAD ainda nao esta final:\n- " + "\n- ".join(faltas), file=sys.stderr)
        return 2
    politica_original = (RAIZ / "configuracao/politica.json").read_bytes()
    agora = datetime.now(timezone.utc)
    destino = BASE / f"observacao-claude-code-{agora:%Y%m%dT%H%M%SZ}"
    destino.mkdir(parents=True)
    try:
        extrair(destino)
        removidos = [*REMOVER, *KITS]
        ajustes = adaptar(destino)
        preparo = dict(head=git("rev-parse", "HEAD")[1].strip(), criado_em=agora.isoformat(), destino=str(destino),
                       removidos=removidos, python=sys.version.split()[0], claude=versao_claude(),
                       politica_original_sha256=hashlib.sha256(politica_original).hexdigest(), **ajustes)
        (destino / "observacao/PREPARO.json").write_text(json.dumps(preparo, indent=2) + "\n", encoding="utf-8")
        if (RAIZ / "configuracao/politica.json").read_bytes() != politica_original:
            raise RuntimeError("a politica original mudou")
    except BaseException:
        print(f"Copia incompleta preservada em {destino}", file=sys.stderr)
        raise
    print(json.dumps(preparo, indent=2, ensure_ascii=False))
    print("\nEntre nesta pasta e siga, no clone, " + str(RAIZ / KITS[0] / "roteiro.md") + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
