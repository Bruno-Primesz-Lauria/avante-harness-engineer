"""Prepara uma copia temporaria e isolada para observacao O-OC.

Uso, com o pacote commitado: py -3 avaliacao/observacao-opencode/preparar.py
A copia fica em ../.execucoes/observacao-opencode-<instante>, ao lado do clone.
Nao abre o OpenCode nem le ou altera a configuracao global do usuario.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import yaml

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ.parent / ".execucoes"
PAPEIS = ("map", "config", "implement", "test", "refute", "docs", "dab")
TRILHAS_OPENCODE = ["manutencao", "docs"]
REMOVER = (".claude", ".cursor", ".codex", "prj-avante-analytics-adb")
KITS = ("avaliacao/observacao-claude-code/", "avaliacao/observacao-cursor/",
        "avaliacao/observacao-opencode/")

FIXTURE = {
    "fixture/manutencao/regras.yaml": "desconto_percentual: 0\n",
    "fixture/manutencao/calc.py": (
        "from pathlib import Path\nimport yaml\n\n"
        "REGRAS = Path(__file__).with_name('regras.yaml')\n\n"
        "def preco_final(valor):\n"
        "    regras = yaml.safe_load(REGRAS.read_text(encoding='utf-8'))\n"
        "    desconto = regras['desconto_percentual']\n"
        "    return valor * (100 - desconto) / 100\n"),
    "fixture/manutencao/teste_calc.py": (
        "import unittest\n\nfrom calc import preco_final\n\n\n"
        "class PrecoFinal(unittest.TestCase):\n"
        "    def test_zero(self):\n"
        "        self.assertEqual(preco_final(0), 0)\n\n\n"
        "if __name__ == '__main__':\n    unittest.main()\n"),
    "fixture/manutencao/ambiente_local.py": (
        "import sys\n\nprint('ambiente-local-ok python', sys.version_info[:2])\n"),
    "fixture/manutencao/autorizacao-local.md": (
        "# Autorizacao local da fixture O-OC\n\n"
        "Permitido somente executar o script ambiente_local.py desta fixture.\n"
        "Sem Databricks, sem bundle, sem rede, sem deploy e sem run.\n"),
    "fixture/bundle-local/databricks.yml": "bundle:\n  name: saneamento_migracao\n",
    "fixture/docs/guia.md": (
        "# Guia do desconto\n\nFonte: fixture/manutencao/regras.yaml.\n\n"
        "TODO: documentar a regra de desconto.\n"),
}

CONTRATO_BASE = """\
artefatos_raiz: .execucoes/provas
fora: [prj-avante-analytics-adb, databricks, deploy, run]
responsaveis: {coordenador: agente, executor: agente, verificador: suite_local}
"""


def contratos():
    return {
        "observacao/contrato-manutencao.yaml": """\
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
      comando: py -3 -m unittest discover -s fixture/manutencao -p teste_calc.py
      cwd: .
      caminhos: [fixture/manutencao/regras.yaml, fixture/manutencao/calc.py, fixture/manutencao/teste_calc.py]
  - id: ambiente_local
    tipo: ambiente
    obrigatorio: true
    esperado: O script local termina com exit 0
    autorizacao_ref: fixture/manutencao/autorizacao-local.md
    verificacao:
      comando: py -3 fixture/manutencao/ambiente_local.py
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


PLUGIN_OBSERVADO = '''\
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { criar_ponte_portatil } from "../../adaptadores/opencode/esteira.js";

const DESTINO = resolve(fileURLToPath(new URL("../../.execucoes/sondagens/brutos/opencode/observacao_ooc/eventos.jsonl", import.meta.url)));
const ponte = criar_ponte_portatil();
const COMANDOS_FIXTURE = new Set([
  "databricks bundle validate -t sandbox -p fixture",
  "py -3 -m unittest discover -s fixture/manutencao -p teste_calc.py",
  "py -3 fixture/manutencao/ambiente_local.py",
]);

function registrar(tipo, dados) {
  try {
    mkdirSync(dirname(DESTINO), { recursive: true });
    appendFileSync(DESTINO, JSON.stringify({ em: new Date().toISOString(), tipo, dados }) + "\\n", "utf8");
  } catch {
    // A captura e best-effort; nunca muda a decisao da ponte.
  }
}

function sanitizarComando(comando) {
  if (typeof comando !== "string") return undefined;
  const sanitizado = comando
    .replace(/(--?(?:token|password|secret|api[-_]?key|client[-_]?secret)(?:=|\\s+))("[^"]*"|'[^']*'|\\S+)/gi, "$1[REDACTED]")
    .replace(/\\b((?:token|password|secret|api[-_]?key)\\s*[:=]\\s*)("[^"]*"|'[^']*'|\\S+)/gi, "$1[REDACTED]");
  if (COMANDOS_FIXTURE.has(sanitizado) || sanitizado === "echo --token [REDACTED]") return sanitizado;
  return "[comando omitido]";
}

function argsSeguros(ferramenta, args = {}) {
  if (ferramenta === "bash") {
    return { command: sanitizarComando(args.command), workdir: args.workdir };
  }
  if (ferramenta === "task") return { subagent_type: args.subagent_type };
  if (ferramenta === "skill") return { name: args.name };
  return {};
}

function saidaSegura(ferramenta, output = {}) {
  const metadata = output.metadata ?? {};
  if (ferramenta === "bash") {
    return { metadata: { exit: metadata.exit, state: metadata.state } };
  }
  if (ferramenta === "task") {
    return {
      metadata: {
        state: metadata.state,
        parentSessionId: metadata.parentSessionId,
        sessionId: metadata.sessionId,
      },
    };
  }
  return {};
}

function eventoSeguro(event) {
  const propriedades = event?.properties ?? {};
  const info = propriedades.info ?? {};
  if (event?.type === "session.created") {
    return { info: { id: info.id, parentID: info.parentID } };
  }
  return { sessionID: propriedades.sessionID ?? info.id };
}

export const Esteira = async (contexto) => {
  const hooks = await ponte(contexto);
  return {
    "tool.execute.before": async (input, output) => {
      if (["bash", "task", "skill"].includes(input.tool)) {
        registrar("tool.execute.before", {
          input: { tool: input.tool, sessionID: input.sessionID, callID: input.callID },
          args: argsSeguros(input.tool, output.args),
        });
      }
      try {
        await hooks["tool.execute.before"]?.(input, output);
        if (input.tool === "bash") {
          registrar("tool.execute.before.result", { callID: input.callID, decisao: "permitir_ou_nao_aplica" });
        }
      } catch (erro) {
        if (input.tool === "bash") {
          registrar("tool.execute.before.result", { callID: input.callID, decisao: "negar", erro: String(erro) });
        }
        throw erro;
      }
    },
    "tool.execute.after": async (input, output) => {
      await hooks["tool.execute.after"]?.(input, output);
      if (["bash", "task", "skill"].includes(input.tool)) {
        registrar("tool.execute.after", {
          input: { tool: input.tool, sessionID: input.sessionID, callID: input.callID },
          args: argsSeguros(input.tool, input.args ?? output.args),
          output: saidaSegura(input.tool, output),
        });
      }
    },
    "shell.env": async (input, output) => {
      await hooks["shell.env"]?.(input, output);
      const env = output?.env ?? {};
      registrar("shell.env", {
        input: { sessionID: input.sessionID, cwd: input.cwd },
        env: { ESTEIRA_SESSAO: env.ESTEIRA_SESSAO, ESTEIRA_RUNTIME: env.ESTEIRA_RUNTIME },
      });
    },
    event: async ({ event }) => {
      if (["session.created", "session.idle"].includes(event?.type)) {
        registrar(event.type, eventoSeguro(event));
      }
      return hooks.event?.({ event });
    },
  };
};
'''

CONFERIR = '''\
"""Resume chamadas, vinculos, verificacoes e fechos; nao marca agentes como observados."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

COPIA = Path(__file__).resolve().parents[1]
REG = COPIA / ".execucoes"
BRUTOS = REG / "sondagens/brutos/opencode/observacao_ooc"
SAIDA = BRUTOS / "conferencias.jsonl"


def ler(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def evento(pasta, ref):
    return ler(pasta / ref)["dados"]


def fatia(estado_json):
    pasta = estado_json.parent
    estado = ler(estado_json)
    fecho = evento(pasta, estado["fecho"]["ref"]) if estado["fecho"] else None
    return {
        "execucao_id": estado["execucao_id"],
        "trilha": estado["trilha"],
        "runtime": estado["runtime"],
        "previstas": [c["id"] for c in estado.get("chamadas_previstas", [])],
        "observadas": [
            {**{k: evento(pasta, c["ref"]).get(k) for k in
                ("chamada_id", "papel", "runtime", "status", "ids_observados", "inicio", "fim")}}
            for c in estado.get("chamadas_observadas", [])
        ],
        "provas": {
            k: {**{x: evento(pasta, v["ref"]).get(x) for x in
                    ("resultado", "validade", "exit_code", "exit_code_origem", "agente_id")}}
            for k, v in estado.get("provas", {}).items()
        },
        "inspecoes": {
            k: {x: evento(pasta, v["ref"]).get(x) for x in ("resultado", "validade")}
            for k, v in estado.get("inspecoes", {}).items()
        },
        "revisoes": [
            {"ref": r["ref"], "agente_id": evento(pasta, r["ref"]).get("agente_id"),
             "veredito": evento(pasta, r["ref"]).get("veredito")}
            for r in estado.get("revisoes", [])
        ],
        "fecho": fecho and {"status": fecho["status"], "pendencias": fecho["pendencias"]},
    }


def principal():
    arquivos = sorted((COPIA / "fixture").rglob("*"))
    fixture = {
        p.relative_to(COPIA).as_posix(): sha256(p.read_bytes()).hexdigest()[:12]
        for p in arquivos if p.is_file() and "__pycache__" not in p.parts
    }
    estados = sorted((REG / "provas").glob("*/principal/estado.json"), key=lambda p: p.stat().st_mtime)
    registros = []
    bruto = BRUTOS / "eventos.jsonl"
    if bruto.is_file():
        registros = [json.loads(linha) for linha in bruto.read_text(encoding="utf-8").splitlines() if linha]
    chamadas_task = [r for r in registros if r.get("tipo") == "tool.execute.before"
                     and r.get("dados", {}).get("input", {}).get("tool") == "task"]
    saida = {
        "em": datetime.now(timezone.utc).isoformat(),
        "fixture": fixture,
        "eventos": {
            "total": len(registros),
            "task_before": len(chamadas_task),
            "bash_before": sum(r.get("tipo") == "tool.execute.before" and
                               r.get("dados", {}).get("input", {}).get("tool") == "bash" for r in registros),
            "negacoes_bash": sum(r.get("tipo") == "tool.execute.before.result" and
                                 r.get("dados", {}).get("decisao") == "negar" for r in registros),
            "sessoes_filhas": sum(bool(r.get("tipo") == "session.created" and
                                       r.get("dados", {}).get("info", {}).get("parentID"))
                                  for r in registros),
        },
        "fatias": [fatia(p) for p in estados],
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    with SAIDA.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(saida, ensure_ascii=False) + "\\n")
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    principal()
'''


def git(*args):
    resultado = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True,
                               text=True, encoding="utf-8")
    return resultado.returncode, resultado.stdout


def mostrar(caminho):
    codigo, saida = git("show", f"HEAD:{caminho}")
    return saida if codigo == 0 else None


def verificar_head():
    """Exige D-OC/B2-OC commitados, sem incluir preferencias do usuario."""
    faltas = []
    escopo = (
        ".opencode", "opencode.json", "adaptadores/opencode", "adaptadores/entrada.py",
        "adaptadores/executar.py", "adaptadores/prova.py", "implementacao/provas.py",
        "formas/catalogo.yaml", "configuracao/politica.json", "agentes",
        "avaliacao/README.md", "adaptadores/opencode/README.md", "PLANO-AGENTES-TRILHAS.md",
    )
    codigo, sujo = git("status", "--porcelain", "--untracked-files=no", "--", *escopo)
    if codigo != 0 or sujo.strip():
        faltas.append("ha arquivo operacional do O-OC/B2-OC/D-OC alterado sem commit: " +
                      " ".join(sujo.split()[:10]))

    politica_texto = mostrar("configuracao/politica.json")
    try:
        politica = json.loads(politica_texto)
        if "opencode" in politica["agentes_obrigatorios"]:
            faltas.append("agentes_obrigatorios.opencode ja esta ativa no HEAD; O-OC nao deve preparar E0")
    except (TypeError, ValueError, KeyError):
        faltas.append("configuracao/politica.json do HEAD ilegivel")

    try:
        rota = yaml.safe_load(mostrar("agentes/roteamento.yaml"))
        if rota["runtimes"]["opencode"]["instalacao_agentes"] != ".opencode/agents/":
            faltas.append("roteamento do OpenCode aponta para outro diretorio")
        for papel in PAPEIS:
            metadados = rota["agentes"][papel]["metadados"]["opencode"]
            if metadados.get("instalado") is not False or metadados.get("observado") != "pendente":
                faltas.append(f"metadados OpenCode de {papel} ja nao estao pendentes")
            if mostrar(f".opencode/agents/{papel}.md") is None:
                faltas.append(f".opencode/agents/{papel}.md ausente do HEAD")
    except (TypeError, KeyError, yaml.YAMLError):
        faltas.append("agentes/roteamento.yaml do HEAD ilegivel ou sem OpenCode")

    plugin = mostrar(".opencode/plugins/esteira.js") or ""
    if "criar_ponte_portatil" not in plugin:
        faltas.append("plugin OpenCode do HEAD nao carrega a ponte D-OC")
    config_texto = mostrar("opencode.json")
    try:
        config = json.loads(config_texto)
        if "provider" in config or "model" in config:
            faltas.append("opencode.json do projeto declara provider ou model")
        if config.get("permission", {}).get("bash", {}).get("databricks bundle *") != "ask":
            faltas.append("opencode.json do projeto perdeu a confirmacao de databricks bundle *")
    except (TypeError, ValueError, AttributeError):
        faltas.append("opencode.json do HEAD ilegivel")
    return faltas


def extrair(destino):
    processo = subprocess.Popen(["git", "-C", str(RAIZ), "archive", "--format=tar", "HEAD"],
                                stdout=subprocess.PIPE)
    with tarfile.open(fileobj=processo.stdout, mode="r|") as arquivo:
        for membro in arquivo:
            if membro.name.split("/", 1)[0] not in REMOVER and not any(
                    (membro.name + "/").startswith(k) for k in KITS):
                arquivo.extract(membro, destino, filter="data")
    if processo.wait() != 0:
        raise RuntimeError("git archive falhou")


def adaptar(destino):
    """Aplica politica, fixtures e captura apenas na copia temporaria."""
    destino = Path(destino)
    if (destino / ".git").exists():
        raise RuntimeError("a copia nao pode ter Git")
    for kit in KITS:
        if (destino / kit).exists():
            raise RuntimeError("a copia nao pode conter roteiro de observacao")

    caminho_politica = destino / "configuracao/politica.json"
    politica = json.loads(caminho_politica.read_text(encoding="utf-8-sig"))
    if "opencode" in politica["agentes_obrigatorios"]:
        raise RuntimeError("a chave opencode deve estar ausente da politica original")
    politica["agentes_obrigatorios"]["opencode"] = list(TRILHAS_OPENCODE)
    politica["registros_raiz"] = "../.execucoes"
    politica["bundle_local"] = "../fixture/bundle-local"
    politica["deploy_sandbox_autorizado"] = False
    caminho_politica.write_text(json.dumps(politica, indent=2) + "\n", encoding="utf-8")

    plugin = destino / ".opencode/plugins/esteira.js"
    original = plugin.read_text(encoding="utf-8")
    if "criar_ponte_portatil" not in original:
        raise RuntimeError("plugin do OpenCode inesperado")
    plugin.write_text(PLUGIN_OBSERVADO, encoding="utf-8", newline="\n")

    (destino / "observacao").mkdir()
    (destino / "observacao/conferir.py").write_text(CONFERIR, encoding="utf-8", newline="\n")
    for ref, conteudo in {**FIXTURE, **contratos()}.items():
        caminho = destino / ref
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8", newline="\n")
    return {
        "agentes_obrigatorios_copia": politica["agentes_obrigatorios"],
        "plugin_observado": ".opencode/plugins/esteira.js",
        "eventos_capturados": ["bash", "task", "skill", "shell.env", "session.created", "session.idle"],
        "bundle_fixture": politica["bundle_local"],
        "deploy_sandbox_autorizado": politica["deploy_sandbox_autorizado"],
    }


def versao_opencode():
    """Registra a versao instalada pelo dev; nao exige uma versao fixa."""
    # No Windows o npm instala opencode.cmd, que o subprocess so acha pelo caminho completo.
    executavel = shutil.which("opencode")
    if executavel is None:
        return None
    try:
        resultado = subprocess.run([executavel, "--version"], capture_output=True, text=True, timeout=30)
        return resultado.stdout.strip() or resultado.stderr.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def principal():
    faltas = verificar_head()
    if faltas:
        print("[preparar_ooc] HEAD ainda nao esta final:\n- " + "\n- ".join(faltas), file=sys.stderr)
        return 2
    politica_original = (RAIZ / "configuracao/politica.json").read_bytes()
    agora = datetime.now(timezone.utc)
    destino = BASE / f"observacao-opencode-{agora:%Y%m%dT%H%M%SZ}"
    destino.mkdir(parents=True)
    try:
        extrair(destino)
        ajustes = adaptar(destino)
        preparo = {
            "head": git("rev-parse", "HEAD")[1].strip(),
            "criado_em": agora.isoformat(),
            "destino": str(destino),
            "removidos": [*REMOVER, *KITS],
            "python": sys.version.split()[0],
            "opencode": versao_opencode(),
            "politica_original_sha256": hashlib.sha256(politica_original).hexdigest(),
            **ajustes,
        }
        (destino / "observacao/PREPARO.json").write_text(
            json.dumps(preparo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if (RAIZ / "configuracao/politica.json").read_bytes() != politica_original:
            raise RuntimeError("a politica original mudou")
    except BaseException:
        print(f"Copia incompleta preservada em {destino}", file=sys.stderr)
        raise
    print(json.dumps(preparo, indent=2, ensure_ascii=False))
    print("\nAbra a copia e siga o roteiro em " + str(RAIZ / "avaliacao/observacao-opencode/roteiro.md"))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
