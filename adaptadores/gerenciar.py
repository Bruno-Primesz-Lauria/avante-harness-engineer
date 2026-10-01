"""Gera ou instala um adaptador explicitamente, preservando outras configuracoes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

RAIZ = Path(__file__).resolve().parents[1]
WORKSPACE = RAIZ


def comando(runtime, plataforma=None):
    plataforma = plataforma or ("windows" if os.name == "nt" else "posix")
    if plataforma not in ("windows", "posix"):
        raise ValueError("Plataforma desconhecida")
    python = "py -3" if plataforma == "windows" else "python3"
    script = "adaptadores/entrada.py"
    if runtime == "claude_code":
        script = ('"${CLAUDE_PROJECT_DIR}/adaptadores/entrada.py"' if plataforma == "windows"
                  else '"$CLAUDE_PROJECT_DIR/adaptadores/entrada.py"')
    return f"{python} {script} {runtime}"


def gerar(runtime, plataforma=None):
    plataforma = plataforma or ("windows" if os.name == "nt" else "posix")
    if runtime == "cursor":
        handler = {"command": comando(runtime, plataforma), "timeout": 10}
        return {"version": 1, "hooks": {
            "beforeShellExecution": [dict(handler, failClosed=True)],
            "sessionStart": [dict(handler)],
            "preToolUse": [dict(handler, matcher="Shell", failClosed=True)],
            "postToolUse": [dict(handler, matcher="Shell")],
            "postToolUseFailure": [dict(handler, matcher="Shell")],
            "stop": [dict(handler, loop_limit=2)],
        }}
    if runtime in ("claude_code", "codex"):
        handler = {"type": "command", "command": comando(runtime, plataforma), "timeout": 10}
        if runtime == "claude_code" and plataforma == "windows":
            handler["shell"] = "powershell"
        return {"hooks": {"PreToolUse": [{
            "matcher": "^(Bash|PowerShell)$" if runtime == "claude_code" else "^Bash$",
            "hooks": [handler],
        }]}}
    if runtime == "opencode":
        return ('import { criar_ponte_portatil } from "../../adaptadores/opencode/esteira.js";\n'
                'export const Esteira = criar_ponte_portatil();\n')
    raise ValueError("Runtime desconhecido")


def destino(runtime, workspace=WORKSPACE):
    return workspace / {"cursor": ".cursor/hooks.json", "claude_code": ".claude/settings.json",
                        "codex": ".codex/hooks.json", "opencode": ".opencode/plugins/esteira.js"}[runtime]


def mesclar(atual, candidato):
    resultado = json.loads(json.dumps(atual))
    if "version" in candidato:
        if resultado.get("version", 1) != 1:
            raise ValueError("Versao de hooks Cursor desconhecida")
        resultado["version"] = 1
    for evento, grupos in candidato["hooks"].items():
        lista = resultado.setdefault("hooks", {}).setdefault(evento, [])
        for grupo in grupos:
            if grupo in lista:
                continue
            comandos = {h["command"] for h in grupo.get("hooks", [grupo])}
            for existente in lista:
                if comandos & {h.get("command") for h in existente.get("hooks", [existente])}:
                    raise ValueError("Handler existente difere; revisar sem sobrescrever")
            lista.append(grupo)
    return resultado


def gravar(caminho, conteudo, anterior):
    if anterior == conteudo:
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if anterior is not None:
        sufixo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        with caminho.with_name(f"{caminho.name}.backup.{sufixo}").open("xb") as arquivo:
            arquivo.write(anterior)
    fd, nome = tempfile.mkstemp(prefix="harness_", suffix=".tmp", dir=caminho.parent)
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(conteudo)
        if (caminho.read_bytes() if caminho.exists() else None) != anterior:
            raise RuntimeError("Configuracao mudou durante a gravacao")
        os.replace(nome, caminho)
    finally:
        if Path(nome).exists():
            Path(nome).unlink()


def instalar(runtime, workspace=WORKSPACE, plataforma=None):
    caminho = destino(runtime, workspace)
    anterior = caminho.read_bytes() if caminho.exists() else None
    candidato = gerar(runtime, plataforma)
    if runtime == "opencode":
        conteudo = candidato.encode("utf-8")
        if anterior is not None and anterior != conteudo:
            raise ValueError("Plugin local ja existe e difere; revisar manualmente")
    else:
        atual = json.loads(anterior.decode("utf-8-sig")) if anterior else {}
        preparado = json.loads(json.dumps(atual))
        outra = "posix" if (plataforma or ("windows" if os.name == "nt" else "posix")) == "windows" else "windows"
        # Ao trocar o SO, substituir apenas a definicao exata gerada por nos.
        # Manter as duas faria o lancador indisponivel bloquear a chamada.
        alternativo = gerar(runtime, outra)
        for evento, grupos in alternativo["hooks"].items():
            existentes = preparado.get("hooks", {}).get(evento, [])
            if existentes:
                preparado["hooks"][evento] = [g for g in existentes if g not in grupos]
        resultado = mesclar(preparado, candidato)
        if resultado == atual:
            return caminho
        conteudo = (json.dumps(resultado, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    gravar(caminho, conteudo, anterior)
    return caminho


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("cursor", "claude_code", "codex", "opencode"))
    parser.add_argument("--instalar", action="store_true", help="Sem esta flag, apenas mostra a configuracao")
    parser.add_argument("--plataforma", choices=("windows", "posix"), help="Padrao: sistema atual")
    args = parser.parse_args()
    if args.instalar:
        print(instalar(args.runtime, plataforma=args.plataforma))
    else:
        configuracao = gerar(args.runtime, args.plataforma)
        print(configuracao if isinstance(configuracao, str) else json.dumps(configuracao, indent=2))
