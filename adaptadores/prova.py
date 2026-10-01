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


def principal():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessao", default=os.environ.get("ESTEIRA_SESSAO"))
    comandos = parser.add_subparsers(dest="acao", required=True)
    comandos.add_parser("iniciar").add_argument("contrato", type=Path)
    comandos.add_parser("estado")
    fechar = comandos.add_parser("fechar")
    fechar.add_argument("--status", choices=("DONE", "REVIEW", "DECIDE", "BLOCKED", "FAILED"), default="DONE")
    fechar.add_argument("--resultado", required=True)
    args = parser.parse_args()
    try:
        politica = carregar_politica(RAIZ / "configuracao/politica.json")
        provas = Provas(RAIZ, politica["registros_raiz"], args.sessao)
        if args.acao == "iniciar":
            resultado = provas.iniciar(yaml.load(args.contrato.read_text(encoding="utf-8-sig"), Loader=YamlSemDuplicatas))
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
