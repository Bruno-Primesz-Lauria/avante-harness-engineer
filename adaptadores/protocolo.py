"""Traduz os eventos dos quatro runtimes para uma operacao neutra e a decisao para a resposta nativa."""
from guarda_cwd import Operacao

RUNTIMES = ("cursor", "claude_code", "codex", "opencode")


def normalizar(runtime, evento):
    if runtime not in RUNTIMES or not isinstance(evento, dict):
        raise ValueError("Runtime ou evento invalido")
    if runtime == "cursor":
        if evento.get("hook_event_name") != "beforeShellExecution":
            raise ValueError("Evento Cursor fora do contrato")
        return Operacao("antes_execucao", "shell", evento.get("command"), evento.get("cwd"), "ferramenta")
    if runtime in ("codex", "claude_code"):
        if evento.get("hook_event_name") != "PreToolUse":
            raise ValueError("Esperado PreToolUse")
        ferramentas = {"Bash"} if runtime == "codex" else {"Bash", "PowerShell"}
        if evento.get("tool_name") not in ferramentas:
            return Operacao("antes_execucao", "fora_do_recorte")
        entrada = evento.get("tool_input")
        if not isinstance(entrada, dict):
            raise ValueError("tool_input invalido")
        # Claude nao documenta workdir em Bash; cwd do envelope e de sessao.
        cwd = entrada.get("workdir") if runtime == "codex" else None
        return Operacao("antes_execucao", "shell", entrada.get("command"), cwd,
                        "ferramenta" if cwd is not None else "nao_observado")
    if evento.get("evento") != "tool.execute.before":
        raise ValueError("Evento OpenCode fora do contrato")
    if evento.get("tool") != "bash":
        return Operacao("antes_execucao", "fora_do_recorte")
    entrada = evento.get("args")
    if not isinstance(entrada, dict):
        raise ValueError("args invalido")
    return Operacao("antes_execucao", "shell", entrada.get("command"), entrada.get("workdir"), "ferramenta")


def mensagem(decisao):
    return f"[cwd-bundle/{decisao.codigo}] {decisao.motivo} {decisao.recuperacao}".strip()


def traduzir(runtime, decisao):
    if runtime == "cursor":
        resposta = {"permission": "deny" if decisao.decisao == "negar" else "allow"}
        if decisao.decisao != "nao_aplica":
            resposta["agent_message"] = mensagem(decisao)
        if decisao.decisao == "negar":
            resposta["user_message"] = mensagem(decisao)
        return resposta
    if runtime in ("codex", "claude_code"):
        if decisao.decisao == "nao_aplica":
            return {}
        corpo = {"hookEventName": "PreToolUse"}
        if decisao.decisao == "negar":
            corpo.update(permissionDecision="deny", permissionDecisionReason=mensagem(decisao))
        else:
            corpo["additionalContext"] = mensagem(decisao)
        return {"hookSpecificOutput": corpo}
    if runtime == "opencode":
        return {"decisao": decisao.decisao, "motivo": mensagem(decisao)}
    raise ValueError("Runtime desconhecido")
