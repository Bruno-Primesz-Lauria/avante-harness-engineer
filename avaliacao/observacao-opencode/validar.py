"""Valida localmente o kit O-OC em copia temporaria; nao executa OpenCode."""
import hashlib
import json
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory

import yaml

RAIZ = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(RAIZ / "adaptadores"), str(RAIZ / "implementacao")]
from opencode.prova import tratar
from provas import Provas, ler

SESSAO = "validar-ooc-sessao"
SENTINEL_PROMPT = "SENTINEL_PROMPT_NAO_GRAVAR"
SENTINEL_SAIDA = "SENTINEL_SAIDA_NAO_GRAVAR"

DRIVER_NODE = r'''
import { pathToFileURL } from "node:url";

const [pluginPath, modo, sessao, cwd] = process.argv.slice(2);
const plugin = await import(pathToFileURL(pluginPath));
const prompts = [];
const hooks = await plugin.Esteira({
  client: { session: { prompt: async (pedido) => { prompts.push(pedido); } } },
});

if (modo === "base") {
  const saidaEnv = { env: {} };
  await hooks["shell.env"]({ cwd, sessionID: sessao, callID: "env-probe" }, saidaEnv);
  if (saidaEnv.env.ESTEIRA_RUNTIME !== "opencode" || saidaEnv.env.ESTEIRA_SESSAO !== sessao) {
    throw new Error("shell.env nao injetou o runtime e a sessao");
  }

  const argsTask = {
    subagent_type: "map",
    description: "descricao de teste",
    prompt: "SENTINEL_PROMPT_NAO_GRAVAR",
  };
  await hooks["tool.execute.before"](
    { tool: "task", sessionID: sessao, callID: "task-probe" },
    { args: argsTask },
  );
  await hooks["tool.execute.after"](
    { tool: "task", sessionID: sessao, callID: "task-probe", args: argsTask },
    { title: "Task concluida", output: "SENTINEL_SAIDA_NAO_GRAVAR",
      metadata: { state: "completed", parentSessionId: sessao, sessionId: "filha-probe" } },
  );
  await hooks.event({ event: { type: "session.created",
    properties: { info: { id: "filha-probe", parentID: "pai-sem-fatia", title: "privado" } } } });
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: sessao } } });

  await hooks["tool.execute.before"](
    { tool: "bash", sessionID: sessao, callID: "bash-sanitizar" },
    { args: { command: "echo --token SENTINEL_COMMAND_NAO_GRAVAR", workdir: cwd } },
  );
  let negada = "";
  try {
    await hooks["tool.execute.before"](
      { tool: "bash", sessionID: sessao, callID: "bash-negado" },
      { args: { command: "databricks bundle validate -t sandbox -p fixture", workdir: cwd } },
    );
  } catch (erro) {
    negada = String(erro);
  }
  if (!negada.toLowerCase().includes("cwd")) throw new Error("guarda nao negou pelo cwd: " + negada);
  process.stdout.write(JSON.stringify({ runtime: saidaEnv.env.ESTEIRA_RUNTIME, negada }));
} else if (modo === "idle") {
  await hooks.event({ event: { type: "session.idle", properties: { sessionID: sessao } } });
  await new Promise((resolve) => setTimeout(resolve, 10));
  if (!prompts.length || !prompts[0].body?.parts?.[0]?.text?.includes("fatia ativa")) {
    throw new Error("session.idle nao enviou follow-up para o TUI");
  }
  process.stdout.write(JSON.stringify({ followup: prompts[0].body.parts[0].text }));
} else {
  throw new Error("modo desconhecido");
}
'''


def executar_node(copia, plugin, modo, sessao, cwd):
    driver = copia / "observacao/exercitar_plugin.mjs"
    driver.write_text(DRIVER_NODE, encoding="utf-8")
    resultado = subprocess.run(
        ["node", str(driver), str(plugin), modo, sessao, str(cwd)],
        cwd=copia, capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    if resultado.returncode:
        raise AssertionError("driver Node falhou:\n" + resultado.stdout + resultado.stderr)
    return json.loads(resultado.stdout)


def evento(evento, politica, copia):
    return tratar(evento, politica, copia)


def comando_local(comando, copia):
    """Executa somente os dois comandos locais fixos da fixture."""
    partes = shlex.split(comando, posix=False)
    if partes == ["py", "-3", "-m", "unittest", "discover", "-s",
                  "fixture/manutencao", "-p", "teste_calc.py"]:
        argv = partes
    elif partes == ["py", "-3", "fixture/manutencao/ambiente_local.py"]:
        argv = partes
    else:
        raise AssertionError("comando de fixture fora da lista local: " + comando)
    return subprocess.run(argv, cwd=copia, capture_output=True, text=True, encoding="utf-8")


def tarefa(provas, politica, copia, pai, papel, indice, alterar=None, comando=None):
    chamada = f"task-{indice}"
    filha = f"filha-{indice}"
    antes = {
        "evento": "tool.execute.before",
        "input": {"tool": "task", "sessionID": pai, "callID": chamada},
        "args": {"subagent_type": papel},
    }
    evento(antes, politica, copia)
    evento({"evento": "session.created", "properties": {"info": {"id": filha, "parentID": pai}}},
           politica, copia)
    if alterar:
        alterar()
    if comando:
        bash = f"bash-{indice}"
        args = {"command": comando, "workdir": str(copia)}
        resposta = evento({
            "evento": "tool.execute.before",
            "input": {"tool": "bash", "sessionID": filha, "callID": bash},
            "args": args,
        }, politica, copia)
        assert resposta.get("decisao") != "negar", (papel, resposta)
        resultado = comando_local(comando, copia)
        combinado = resultado.stdout + resultado.stderr
        assert resultado.returncode == 0, combinado
        evento({
            "evento": "tool.execute.after",
            "input": {"tool": "bash", "sessionID": filha, "callID": bash, "args": args},
            "output": {"metadata": {"exit": resultado.returncode, "output": combinado}},
        }, politica, copia)
    evento({
        "evento": "tool.execute.after",
        "input": {"tool": "task", "sessionID": pai, "callID": chamada},
        "output": {"metadata": {
            "state": "completed", "parentSessionId": pai, "sessionId": filha,
        }},
    }, politica, copia)
    return filha


def revisao(agente_id, criterio, provas_refs):
    cobertura = [{"criterio_id": criterio, "coberto": True}]
    if criterio == "teste":
        cobertura.append({"criterio_id": "ambiente_local", "coberto": False,
                          "motivo": "criterio dab executado depois da revisao"})
    return {
        "agente_id": agente_id,
        "entrada": {
            "intencao_ref": "contrato.yaml", "aceite_ref": "contrato.yaml",
            "baseline_ref": "baseline.json", "provas_refs": provas_refs,
        },
        "veredito": "nao_quebrei",
        "tentativas": [{"id": "t1", "procedimento": "Conferir a fixture simulada",
                        "resultado": "pass"}],
        "achados": [],
        "cobertura": cobertura,
    }


def principal():
    kit = runpy.run_path(str(Path(__file__).with_name("preparar.py")))
    compile(kit["CONFERIR"], "conferir.py", "exec")
    politica_original = hashlib.sha256((RAIZ / "configuracao/politica.json").read_bytes()).hexdigest()
    (RAIZ / ".execucoes").mkdir(exist_ok=True)

    with TemporaryDirectory(prefix="validar-ooc-", dir=RAIZ / ".execucoes") as pasta:
        copia = Path(pasta)
        kit["extrair"](copia)
        ajustes = kit["adaptar"](copia)
        politica = json.loads((copia / "configuracao/politica.json").read_text(encoding="utf-8"))
        assert ajustes["agentes_obrigatorios_copia"]["opencode"] == ["manutencao", "docs"]
        assert politica["deploy_sandbox_autorizado"] is False
        assert politica["bundle_local"] == "../fixture/bundle-local"
        for campo in ("bundle_local", "registros_raiz"):
            politica[campo] = str((copia / "configuracao" / politica[campo]).resolve())
        assert not (copia / ".git").exists()
        assert not (copia / "prj-avante-analytics-adb").exists()
        assert all(not (copia / nome).exists() for nome in (".claude", ".cursor", ".codex"))
        assert (copia / ".opencode/agents/dab.md").is_file()
        assert hashlib.sha256((RAIZ / "configuracao/politica.json").read_bytes()).hexdigest() == politica_original

        contratos = {nome: yaml.safe_load(texto) for nome, texto in kit["contratos"]().items()}
        manutencao = contratos["observacao/contrato-manutencao.yaml"]
        docs = contratos["observacao/contrato-docs.yaml"]
        comando_teste = manutencao["aceite"][0]["verificacao"]["comando"]
        comando_ambiente = manutencao["aceite"][1]["verificacao"]["comando"]

        # A captura temporaria encaminha eventos a D-OC e nao guarda prompt ou saida.
        ponte = copia / ".opencode/plugins/esteira-validacao.mjs"
        ponte.write_text(kit["PLUGIN_OBSERVADO"].replace(
            "../../adaptadores/opencode/esteira.js",
            "../../adaptadores/opencode/esteira-validacao.mjs",
        ), encoding="utf-8")
        bridge_original = (copia / "adaptadores/opencode/esteira.js").read_text(encoding="utf-8")
        (copia / "adaptadores/opencode/esteira-validacao.mjs").write_text(bridge_original, encoding="utf-8")
        base_plugin = executar_node(copia, ponte, "base", "probe-sem-fatia",
                                    copia / "fixture/manutencao")
        assert base_plugin["runtime"] == "opencode"
        bruto = copia / ".execucoes/sondagens/brutos/opencode/observacao_ooc/eventos.jsonl"
        linhas = [json.loads(linha) for linha in bruto.read_text(encoding="utf-8").splitlines()]
        texto_bruto = bruto.read_text(encoding="utf-8")
        assert "SENTINEL_PROMPT_NAO_GRAVAR" not in texto_bruto
        assert "SENTINEL_SAIDA_NAO_GRAVAR" not in texto_bruto
        assert "SENTINEL_COMMAND_NAO_GRAVAR" not in texto_bruto
        assert "echo --token [REDACTED]" in texto_bruto
        assert any(item["tipo"] == "tool.execute.before.result" and
                   item["dados"]["decisao"] == "negar" and
                   "cwd" in item["dados"]["erro"].lower() for item in linhas), linhas
        assert {item["tipo"] for item in linhas} >= {
            "tool.execute.before", "tool.execute.after", "shell.env",
            "session.created", "session.idle", "tool.execute.before.result",
        }

        m = Provas(copia, copia / ".execucoes", SESSAO, runtime="opencode")
        m.iniciar(manutencao)
        try:
            m.fechar("DONE", "falso DONE")
        except ValueError:
            pass
        else:
            raise AssertionError("o falso DONE deveria ser recusado")
        idle = executar_node(copia, ponte, "idle", SESSAO, copia)
        assert "fatia ativa" in idle["followup"]

        teste_inicial = (
            "import unittest\n\nfrom calc import preco_final\n\n\n"
            "class PrecoFinal(unittest.TestCase):\n"
            "    def test_zero(self):\n        self.assertEqual(preco_final(0), 0)\n\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        )
        teste_corrigido = (
            "import unittest\n\nfrom calc import preco_final\n\n\n"
            "class PrecoFinal(unittest.TestCase):\n"
            "    def test_zero(self):\n        self.assertEqual(preco_final(0), 0)\n\n"
            "    def test_desconto_dez_porcento(self):\n"
            "        self.assertEqual(preco_final(200), 180)\n\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n"
        )
        assert (copia / "fixture/manutencao/teste_calc.py").read_text(encoding="utf-8") == teste_inicial
        tarefa(m, politica, copia, SESSAO, "test", "m-test-prep",
               alterar=lambda: (copia / "fixture/manutencao/teste_calc.py").write_text(
                   teste_corrigido, encoding="utf-8"))
        tarefa(m, politica, copia, SESSAO, "config", "m-config",
               alterar=lambda: (copia / "fixture/manutencao/regras.yaml").write_text(
                   "desconto_percentual: 10\n", encoding="utf-8"))
        codigo_calc = (
            "from pathlib import Path\nimport yaml\n\n"
            "REGRAS = Path(__file__).with_name('regras.yaml')\n\n"
            "def preco_final(valor):\n"
            "    regras = yaml.safe_load(REGRAS.read_text(encoding='utf-8'))\n"
            "    desconto = regras['desconto_percentual']\n"
            "    return valor * (100 - desconto) / 100\n"
        )
        tarefa(m, politica, copia, SESSAO, "implement", "m-implement",
               alterar=lambda: (copia / "fixture/manutencao/calc.py").write_text(
                   codigo_calc, encoding="utf-8"))
        tarefa(m, politica, copia, SESSAO, "test", "m-test-run", comando=comando_teste)
        refute_m = tarefa(m, politica, copia, SESSAO, "refute", "m-refute")
        estado_m = m.estado(m.pasta())
        if "teste" not in estado_m.get("provas", {}):
            raise AssertionError("prova de teste ausente:\n" + json.dumps(estado_m, indent=2))
        m.revisar(revisao(refute_m, "teste", [estado_m["provas"]["teste"]["ref"]]))
        tarefa(m, politica, copia, SESSAO, "dab", "m-dab", comando=comando_ambiente)
        assert m.fechar("DONE", "fatia manutencao simulada")["status"] == "DONE"

        d = Provas(copia, copia / ".execucoes", "validar-ooc-docs", runtime="opencode")
        d.iniciar(docs)
        guia = (
            "# Guia do desconto\n\nFonte: fixture/manutencao/regras.yaml.\n\n"
            "A regra aplica desconto de 10% ao preço informado, conforme "
            "desconto_percentual: 10 em fixture/manutencao/regras.yaml.\n"
        )
        docs_id = tarefa(d, politica, copia, "validar-ooc-docs", "docs", "d-docs",
                         alterar=lambda: (copia / "fixture/docs/guia.md").write_text(
                             guia, encoding="utf-8"))
        assert "10%" in (copia / "fixture/docs/guia.md").read_text(encoding="utf-8")
        d.inspecionar("guia", [{"id": "fonte", "resultado": "pass"}])
        refute_d = tarefa(d, politica, copia, "validar-ooc-docs", "refute", "d-refute")
        d.revisar(revisao(refute_d, "guia", []))
        assert d.fechar("DONE", "fatia docs simulada")["status"] == "DONE"

        conferencia = subprocess.run(
            ["py", "-3", "observacao/conferir.py"], cwd=copia,
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert conferencia.returncode == 0, conferencia.stdout + conferencia.stderr
        resumo = json.loads(conferencia.stdout)
        assert [item["fecho"]["status"] for item in resumo["fatias"]] == ["DONE", "DONE"]
        assert resumo["eventos"]["negacoes_bash"] >= 1
        assert resumo["eventos"]["sessoes_filhas"] >= 1

    assert hashlib.sha256((RAIZ / "configuracao/politica.json").read_bytes()).hexdigest() == politica_original
    print("Kit O-OC validado localmente: copia isolada, captura saneada, guarda, idle, manutencao e docs simulados.")
    print("OpenCode real nao foi executado; G2-OC continua pendente.")


if __name__ == "__main__":
    principal()
