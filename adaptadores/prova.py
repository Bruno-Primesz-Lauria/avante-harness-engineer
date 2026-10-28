"""Gerencia provas, continuidade entre sessoes e testes locais declarados."""
import argparse
import json
import os
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))

from executar import carregar_politica
from provas import Provas
from guarda_cwd import YamlSemDuplicatas
import yaml


def exigir_entrada(registros: Path, arquivo: Path):
    """Fora de registros, nada a exigir; dentro, so entradas/<assunto>/<arquivo>."""
    registros = Path(registros).resolve()
    arquivo = Path(arquivo).resolve()
    try:
        partes = arquivo.relative_to(registros).parts
    except ValueError:
        return None
    if (len(partes) == 3 and partes[0] == "entradas" and partes[1] not in (".", "..")
            and not partes[1].startswith(".")):
        return None
    raise ValueError("O arquivo sob registros deve estar em entradas/<assunto>/<arquivo>")


def _ler_objeto(caminho: Path):
    texto = caminho.read_text(encoding="utf-8")
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        dados = yaml.load(texto, Loader=YamlSemDuplicatas)
    if not isinstance(dados, dict):
        raise ValueError(f"Objeto esperado em {caminho.name}")
    return dados


def _status_fatia(principal: Path):
    estado_caminho = principal / "estado.json"
    if not estado_caminho.is_file():
        return "aberta"
    estado = json.loads(estado_caminho.read_text(encoding="utf-8"))
    fecho = estado.get("fecho") if isinstance(estado, dict) else None
    if not isinstance(fecho, dict):
        return "aberta"
    ref = fecho.get("ref")
    if not isinstance(ref, str) or not ref:
        return "aberta"
    dados = _ler_objeto(principal / ref).get("dados")
    if not isinstance(dados, dict) or not isinstance(dados.get("status"), str):
        raise ValueError(f"status ausente em {ref}")
    return dados["status"]


def _fatias(registros: Path):
    provas = registros / "provas"
    if not provas.is_dir():
        return []
    saida = []
    for pasta in sorted((item for item in provas.iterdir() if item.is_dir()), key=lambda item: item.name):
        contrato = pasta / "principal" / "contrato.yaml"
        if not contrato.is_file():
            continue
        try:
            bruto = json.loads(contrato.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        dados = bruto.get("dados") if isinstance(bruto, dict) else None
        if not isinstance(dados, dict):
            continue
        objetivo, trilha = dados.get("objetivo"), dados.get("trilha")
        if not isinstance(objetivo, str) or not isinstance(trilha, str):
            continue
        saida.append((pasta.name, objetivo, trilha, _status_fatia(pasta / "principal")))
    return saida


def atualizar_indice(registros: Path) -> None:
    """Reescreve indice.md com os assuntos e o estado de cada fatia."""
    registros = Path(registros)
    linhas = [
        "# Registros locais",
        "",
        "Rascunho gerado por prova.py. O rascunho entregue ao prova.py fica em entradas/<assunto>/.",
        "",
        "## Entradas",
        "",
    ]
    entradas = registros / "entradas"
    if entradas.is_dir():
        linhas.extend(f"- {nome}" for nome in sorted(
            item.name for item in entradas.iterdir() if item.is_dir()))
    linhas.extend(["", "## Fatias", ""])
    linhas.extend(f"- {identificador}: {objetivo} | {trilha} | {status}"
                  for identificador, objetivo, trilha, status in _fatias(registros))
    (registros / "indice.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessao", default=os.environ.get("ESTEIRA_SESSAO"))
    parser.add_argument("--execucao")
    runtime_detectado = "claude_code" if os.environ.get("CLAUDE_CODE_SESSION_ID") else (
        "opencode" if os.environ.get("ESTEIRA_RUNTIME") == "opencode" else None
    )
    parser.add_argument("--runtime", choices=("claude_code", "cursor", "codex", "opencode"),
                        default=runtime_detectado)
    comandos = parser.add_subparsers(dest="acao", required=True)
    comandos.add_parser("iniciar").add_argument("contrato", type=Path)
    comandos.add_parser("migrar").add_argument("contrato", type=Path)
    for acao in ("checkpoint", "liberar"):
        comandos.add_parser(acao).add_argument("arquivo", type=Path)
    retomar = comandos.add_parser("retomar")
    retomar.add_argument("--motivo", required=True)
    retomar.add_argument("--revisao", type=int)
    retomar.add_argument("--recuperar", action="store_true")
    verificar = comandos.add_parser("verificar")
    verificar.add_argument("criterio")
    verificar.add_argument("--timeout", type=int, default=300)
    recuperar = comandos.add_parser("recuperar-local")
    recuperar.add_argument("chamada")
    recuperar.add_argument("--motivo", required=True)
    resolver = comandos.add_parser("resolver-operacao")
    resolver.add_argument("operacao_id")
    resolver.add_argument("--evidencia", required=True)
    for acao in ("inspecionar", "revisar", "triar", "diagnosticar", "registrar-sandbox", "registrar-paridade"):
        comandos.add_parser(acao).add_argument("arquivo", type=Path)
    comandos.add_parser("estado")
    fechar = comandos.add_parser("fechar")
    fechar.add_argument("--status", choices=("DONE", "REVIEW", "DECIDE", "BLOCKED", "FAILED"), default="DONE")
    fechar.add_argument("--resultado", required=True)
    args = parser.parse_args(argv)
    try:
        politica = carregar_politica(RAIZ / "configuracao/politica.json")
        provas = Provas(RAIZ, politica["registros_raiz"], args.sessao, runtime=args.runtime, execucao=args.execucao)
        if args.acao in ("iniciar", "migrar", "checkpoint", "liberar", "inspecionar", "revisar", "triar",
                         "diagnosticar", "registrar-sandbox", "registrar-paridade"):
            arquivo = getattr(args, "contrato", None) or args.arquivo
            exigir_entrada(Path(politica["registros_raiz"]), arquivo)
            dados = yaml.load(arquivo.read_text(encoding="utf-8-sig"), Loader=YamlSemDuplicatas)
            if not isinstance(dados, dict):
                raise ValueError("O arquivo de entrada deve ser um objeto YAML")
        if args.acao == "iniciar":
            if args.execucao:
                raise ValueError("Use iniciar sem --execucao; para herdar, use migrar")
            resultado = provas.iniciar(dados)
        elif args.acao == "migrar":
            resultado = provas.migrar(dados)
        elif args.acao in ("checkpoint", "liberar"):
            resultado = provas.salvar_checkpoint(dados, liberar=args.acao == "liberar")
        elif args.acao == "retomar":
            resultado = provas.retomar(args.motivo, args.revisao, args.recuperar)
        elif args.acao == "resolver-operacao":
            resultado = provas.resolver_operacao(args.operacao_id, args.evidencia)
        elif args.acao == "verificar":
            from executor_local import verificar as executar_criterio
            resultado = executar_criterio(provas, args.criterio, args.timeout)
        elif args.acao == "recuperar-local":
            from executor_local import recuperar_local
            resultado = recuperar_local(provas, args.chamada, args.motivo)
        elif args.acao == "inspecionar":
            resultado = provas.inspecionar(dados["criterio_id"], dados["checagens"], dados.get("produtor"))
        elif args.acao == "revisar":
            resultado = provas.revisar(dados)
        elif args.acao == "triar":
            resultado = provas.triar(dados)
        elif args.acao == "diagnosticar":
            resultado = provas.diagnosticar({k: v for k, v in dados.items() if k != "produtor"},
                                            dados.get("produtor"))
        elif args.acao == "registrar-sandbox":
            resultado = provas.registrar_sandbox(dados["criterio_id"],
                                                 {k: v for k, v in dados.items() if k != "criterio_id"})
        elif args.acao == "registrar-paridade":
            resultado = provas.registrar_paridade(dados["criterio_id"],
                                                  {k: v for k, v in dados.items() if k != "criterio_id"})
        elif args.acao == "fechar":
            resultado = provas.fechar(args.status, args.resultado)
        else:
            resultado = provas.conferir()
        print(json.dumps(resultado, ensure_ascii=True))
        # Falha ao reescrever o indice nao invalida o comando ja concluido.
        try:
            atualizar_indice(provas.registros)
        except Exception as erro:
            print(f"[prova] indice nao atualizado: {erro}", file=sys.stderr)
        return 0 if args.acao != "verificar" or resultado["resultado"] == "pass" else 2
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as erro:
        print(f"[prova] {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(principal())
