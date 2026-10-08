"""Inicia, consulta e fecha uma fatia; nao executa comandos de produto."""
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


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessao", default=os.environ.get("ESTEIRA_SESSAO"))
    runtime_detectado = "claude_code" if os.environ.get("CLAUDE_CODE_SESSION_ID") else None
    parser.add_argument("--runtime", choices=("claude_code", "cursor", "codex", "opencode"),
                        default=runtime_detectado)
    comandos = parser.add_subparsers(dest="acao", required=True)
    comandos.add_parser("iniciar").add_argument("contrato", type=Path)
    for acao in ("inspecionar", "revisar", "triar", "diagnosticar", "registrar-sandbox", "registrar-paridade"):
        comandos.add_parser(acao).add_argument("arquivo", type=Path)
    comandos.add_parser("estado")
    fechar = comandos.add_parser("fechar")
    fechar.add_argument("--status", choices=("DONE", "REVIEW", "DECIDE", "BLOCKED", "FAILED"), default="DONE")
    fechar.add_argument("--resultado", required=True)
    args = parser.parse_args(argv)
    try:
        politica = carregar_politica(RAIZ / "configuracao/politica.json")
        provas = Provas(RAIZ, politica["registros_raiz"], args.sessao, runtime=args.runtime)
        if args.acao not in ("estado", "fechar"):
            dados = yaml.load((getattr(args, "contrato", None) or args.arquivo).read_text(encoding="utf-8-sig"),
                              Loader=YamlSemDuplicatas)
            if not isinstance(dados, dict):
                raise ValueError("O arquivo de entrada deve ser um objeto YAML")
        if args.acao == "iniciar":
            resultado = provas.iniciar(dados)
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
        return 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as erro:
        print(f"[prova] {erro}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(principal())
