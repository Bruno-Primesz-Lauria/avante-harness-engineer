"""Traduz hooks Claude Code em provas da fatia ativa."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from formas import exigir
from guarda_cwd import Operacao, avaliar_operacao
from protocolo import mensagem, traduzir
from provas import Provas, gravar, ler

PAPEIS = {"map", "config", "implement", "test", "refute", "docs", "dab"}
PAPEIS_REGISTRAVEIS = PAPEIS - {"map"}
EXIT_CODE = re.compile(r"Exit code (\d+)")


def _agora():
    return datetime.now(timezone.utc).isoformat()


def _resposta_pre(decisao):
    return traduzir("claude_code", decisao)


def _negar_verificacao(motivo):
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "[prova] " + motivo,
    }}


def _criterio_declarado(provas, comando):
    pasta = provas.pasta()
    if pasta is None:
        return None
    estado = provas.estado(pasta)
    contrato = ler(pasta / "contrato.yaml")["dados"]
    return next((criterio for criterio in contrato["aceite"]
                 if criterio["verificacao"].get("comando") == comando), None)


def _cwd_da_guarda(decisao):
    cwd = decisao.cwd
    if not isinstance(cwd, str) or not cwd:
        return None
    caminho = Path(cwd)
    if not caminho.is_absolute():
        return None
    try:
        resolvido = caminho.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return str(resolvido) if resolvido.is_dir() else None


def _arquivo_chamada(provas, chamada_id):
    pasta = provas.pasta()
    if pasta is None:
        return None
    execucao = pasta.parent.name
    chave = sha256((execucao + ":" + chamada_id).encode("utf-8")).hexdigest()
    return provas.indice.parent / ("claude-" + chave + ".json")


def _marcar_inicio(provas, evento):
    entrada = evento.get("tool_input")
    chamada_id = evento.get("tool_use_id")
    papel = entrada.get("subagent_type") if isinstance(entrada, dict) else None
    if (not isinstance(chamada_id, str) or not chamada_id or
            papel not in PAPEIS_REGISTRAVEIS):
        return
    arquivo = _arquivo_chamada(provas, chamada_id)
    if arquivo is None:
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    if arquivo.exists():
        return
    gravar(arquivo, {"chamada_id": chamada_id, "papel": papel, "inicio": _agora()})


def _registrar_fim(provas, evento):
    chamada_id = evento.get("tool_use_id")
    if not isinstance(chamada_id, str) or not chamada_id:
        return
    arquivo = _arquivo_chamada(provas, chamada_id)
    if arquivo is None or not arquivo.is_file():
        return
    inicio = ler(arquivo)
    resposta = evento.get("tool_response")
    if not isinstance(resposta, dict):
        arquivo.unlink(missing_ok=True)
        return
    papel = resposta.get("agentType")
    agente_id = resposta.get("agentId")
    if (papel not in PAPEIS_REGISTRAVEIS or papel != inicio.get("papel") or
            not isinstance(agente_id, str) or not agente_id or
            resposta.get("status") != "completed"):
        arquivo.unlink(missing_ok=True)
        return
    pasta = provas.pasta()
    if pasta is None:
        arquivo.unlink(missing_ok=True)
        return
    estado = provas.estado(pasta)
    if not any(chamada["papel"] == papel for chamada in estado["chamadas_previstas"]):
        arquivo.unlink(missing_ok=True)
        return
    provas.registrar_chamada(
        chamada_id, papel, "claude_code", [{"nome": "agente_id", "valor": agente_id}],
        inicio["inicio"], _agora(), "concluida",
    )
    arquivo.unlink(missing_ok=True)


def _exit_code_falha(erro):
    if not isinstance(erro, str) or not erro:
        return None
    primeira_linha = erro.splitlines()[0]
    correspondencia = EXIT_CODE.fullmatch(primeira_linha)
    if correspondencia is None:
        return None
    codigo = int(correspondencia.group(1))
    return codigo if codigo != 0 else None


def _tratar_shell(evento, provas, politica, raiz):
    entrada = evento.get("tool_input")
    exigir(isinstance(entrada, dict), "tool_input invalido")
    comando = entrada.get("command")
    exigir(isinstance(comando, str), "Comando ausente")
    sessao = evento.get("session_id")
    operacao = Operacao("antes_execucao", "shell", comando, None, "nao_observado")
    decisao = avaliar_operacao(operacao, politica)
    if decisao.decisao == "negar":
        return _resposta_pre(decisao)

    criterio = _criterio_declarado(provas, comando)
    if criterio is None:
        return _resposta_pre(decisao) if decisao.decisao != "nao_aplica" else {}
    cwd = _cwd_da_guarda(decisao)
    if cwd is None:
        return _negar_verificacao(
            "O cwd da sessao nao comprova o diretorio da verificacao. Informe um prefixo literal "
            "Set-Location -LiteralPath '...' -ErrorAction Stop; (PowerShell) ou cd -- '...' && (Bash)."
        )
    if not provas.antes(evento.get("tool_use_id"), comando, cwd, "claude_code",
                       evento.get("agent_id")):
        return {}
    return _resposta_pre(decisao) if decisao.decisao != "nao_aplica" else {}


def _tratar_resultado(evento, provas):
    entrada = evento.get("tool_input")
    exigir(isinstance(entrada, dict), "tool_input invalido")
    comando = entrada.get("command")
    chamada_id = evento.get("tool_use_id")
    exigir(isinstance(comando, str), "Comando ausente")
    exigir(isinstance(chamada_id, str) and chamada_id, "Chamada sem identificador")
    nome = evento.get("hook_event_name")
    if nome == "PostToolUse":
        resposta = evento.get("tool_response")
        exigir(isinstance(resposta, dict), "tool_response invalido")
        saida = "".join(valor for valor in (resposta.get("stdout", ""), resposta.get("stderr", ""))
                        if isinstance(valor, str))
        codigo, origem = 0, "evento_sucesso"
    else:
        codigo = _exit_code_falha(evento.get("error"))
        origem = "texto_falha" if codigo is not None else None
        saida = evento.get("error") if isinstance(evento.get("error"), str) else ""
        if codigo is None:
            saida = "Execucao inconclusiva: formato de error sem Exit code N na primeira linha.\n" + saida
    return provas.depois(chamada_id, comando, codigo, saida, origem)


def tratar(evento, politica, raiz):
    exigir(isinstance(evento, dict), "Evento invalido")
    if "tool_input" in evento:
        exigir(isinstance(evento["tool_input"], dict), "tool_input invalido")
    nome = evento.get("hook_event_name")
    if nome not in {"SessionStart", "PreToolUse", "PostToolUse", "PostToolUseFailure", "Stop"}:
        return {}
    sessao = evento.get("session_id")
    exigir(isinstance(sessao, str) and sessao, "session_id ausente")
    if nome == "SessionStart":
        return {"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ("Sessao Claude Code para a esteira: " + sessao +
                                  ". O comando de prova seleciona esta sessao por CLAUDE_CODE_SESSION_ID."),
        }}

    if nome == "Stop" and evento.get("stop_hook_active") is True:
        return {}

    provas = Provas(raiz, politica["registros_raiz"], sessao, runtime="claude_code")
    if nome == "Stop":
        try:
            estado = provas.conferir()
        except (OSError, ValueError, KeyError, TypeError):
            return {"decision": "block", "reason": "O registro de prova da fatia e invalido."}
        if not estado["ativa"] or estado["fecho_valido"]:
            return {}
        motivo = "A fatia ativa nao tem fecho valido."
        if estado["pendencias"]:
            motivo += " Pendencias: " + ", ".join(estado["pendencias"]) + "."
        return {"decision": "block", "reason": motivo}

    ferramenta = evento.get("tool_name")
    if nome == "PreToolUse" and ferramenta == "Agent":
        _marcar_inicio(provas, evento)
        return {}
    if nome == "PostToolUse" and ferramenta == "Agent":
        _registrar_fim(provas, evento)
        return {}
    if ferramenta not in {"Bash", "PowerShell"}:
        return {}
    if nome == "PreToolUse":
        return _tratar_shell(evento, provas, politica, raiz)
    if nome in {"PostToolUse", "PostToolUseFailure"}:
        _tratar_resultado(evento, provas)
    return {}
