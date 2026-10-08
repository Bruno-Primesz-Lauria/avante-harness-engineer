"""Valida a memoria versionada e entrega o indice no SessionStart; nao altera nem publica notas."""
import argparse
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))

from memorias import PASTA, notas, resumo_indice, validar


def sessao(raiz, pasta):
    """Resposta SessionStart do Claude Code com o indice; falha da memoria nunca bloqueia a sessao."""
    try:
        indice = resumo_indice(raiz, pasta)
    except (OSError, ValueError):
        indice = None
    if not indice:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": indice}}


def principal(argv=None, raiz=RAIZ):
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest="acao", required=True)
    for acao, ajuda in (("validar", "Confere metadados, links, fontes e indice"),
                        ("sessao", "Imprime a resposta SessionStart do Claude Code com o indice")):
        sub = comandos.add_parser(acao, help=ajuda)
        sub.add_argument("--raiz", type=Path, default=raiz,
                         help="Raiz do projeto; caminhos, fontes e links sao relativos a ela")
        sub.add_argument("--pasta", default=PASTA, help="Pasta da memoria, relativa a raiz")
    args = parser.parse_args(argv)
    if args.acao == "sessao":
        # O payload do hook chega no stdin e nao e necessario; nao bloquear a leitura.
        print(json.dumps(sessao(args.raiz, args.pasta), ensure_ascii=True))
        return 0
    erros = validar(args.raiz, args.pasta)
    if erros:
        for erro in erros:
            print(f"[memoria] {erro}", file=sys.stderr)
        print(f"[memoria] {len(erros)} erro(s).", file=sys.stderr)
        return 1
    print(f"[memoria] OK: {len(notas(args.raiz, args.pasta))} nota(s) valida(s) em {args.pasta}/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
