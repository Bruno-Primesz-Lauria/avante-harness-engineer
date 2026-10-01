"""Entrada portatil: resolve tudo a partir do checkout do harness, nao do cwd."""
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]


def principal():
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("cursor", "claude_code", "codex", "opencode"):
        return 2
    candidato = RAIZ / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    python = str(candidato) if candidato.is_file() else sys.executable
    try:
        # stdin/stdout herdados; o payload nao passa por interpolacao de shell.
        codigo = subprocess.run([python, str(RAIZ / "adaptadores/executar.py"), *sys.argv[1:]],
                                cwd=RAIZ, shell=False).returncode
        # Os runtimes so bloqueiam com exit 2; qualquer outra saida de erro deixaria a chamada passar.
        return 0 if codigo == 0 else 2
    except OSError:
        print("[cwd-bundle] Python do harness indisponivel.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(principal())
