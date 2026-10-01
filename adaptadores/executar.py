"""Entrada JSON comum; cada adaptador mantem sua propria semantica de resposta."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))


def carregar_politica(caminho):
    politica = json.loads(caminho.read_text(encoding="utf-8-sig"))
    for campo in ("bundle_local", "registros_raiz"):
        politica[campo] = str((caminho.parent / Path(politica[campo])).resolve())
    return politica


def principal(runtime, caminho=None):
    try:
        from guarda_cwd import avaliar_operacao
        from protocolo import normalizar, traduzir
        politica = carregar_politica(caminho or RAIZ / "configuracao/politica.json")
        evento = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if runtime == "cursor" and isinstance(evento, dict) and evento.get("hook_event_name") != "beforeShellExecution":
            from cursor.prova import tratar
            try:
                resposta = tratar(evento, politica, RAIZ)
            except ValueError as erro:
                if evento.get("hook_event_name") == "preToolUse":
                    resposta = {"permission": "deny", "agent_message": "[prova] " + str(erro),
                                "user_message": "A verificacao precisa de ajuste. Veja o motivo no hook."}
                else:
                    raise
            print(json.dumps(resposta, ensure_ascii=True))
            return 0
        operacao = normalizar(runtime, evento)
        decisao = avaliar_operacao(operacao, politica)
        if decisao.decisao != "nao_aplica":
            pasta = Path(politica["registros_raiz"]) / runtime / "cwd_bundle"
            pasta.mkdir(parents=True, exist_ok=True)
            registro = {
                "versao_diagnostico": 2, "runtime": runtime,
                "registrado_em": datetime.now(timezone.utc).isoformat(),
                "evento_id": uuid4().hex, "decisao": decisao.registro(),
                "origem_cwd": operacao.origem_cwd,
                "entrada_sha256": sha256(json.dumps(evento, sort_keys=True).encode()).hexdigest(),
            }
            with (pasta / f"{registro['evento_id']}.json").open("x", encoding="utf-8") as arquivo:
                json.dump(registro, arquivo, ensure_ascii=False, indent=2)
        print(json.dumps(traduzir(runtime, decisao), ensure_ascii=True))
        return 0
    except Exception:
        # Exit 2 bloqueia nos hooks; OpenCode trata erro do subprocesso.
        print("[cwd-bundle] Guarda indisponivel ou entrada invalida. Peca ao usuario para conferir a instalacao.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or sys.argv[1] not in ("cursor", "claude_code", "codex", "opencode"):
        raise SystemExit(2)
    raise SystemExit(principal(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) == 3 else None))
