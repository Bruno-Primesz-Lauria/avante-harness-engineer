"""Traduz eventos documentados do Cursor; nao interpreta sucesso em prosa."""
import json
from pathlib import Path

from formas import exigir
from guarda_cwd import Operacao, avaliar_operacao
from guarda_efeito import observar_resultado_plan
from protocolo import mensagem
from provas import Provas, ler


def tratar(evento, politica, raiz):
    nome = evento.get("hook_event_name")
    sessao = evento.get("conversation_id") or evento.get("session_id")
    if nome == "sessionStart":
        exigir(isinstance(sessao, str) and sessao, "Sessao ausente")
        return {"env": {"ESTEIRA_SESSAO": sessao}, "additional_context":
                "Leia AGENTS.md. Sessao para --sessao: " + sessao + ". "
                "Em trabalho de varias etapas, use adaptadores/prova.py (iniciar, estado, fechar) "
                "conforme evidencia/uso.md. Pergunta simples nao precisa de registro."}
    if nome == "stop" and evento.get("status") != "completed":
        return {}
    provas = Provas(raiz, politica["registros_raiz"], sessao)
    if nome == "stop":
        try:
            estado = provas.conferir()
            motivo = "A fatia ativa nao tem fecho valido."
            if estado["pendencias"]:
                motivo += " Pendencias: " + ", ".join(estado["pendencias"]) + "."
            recuperar = estado["ativa"] and not estado["fecho_valido"]
        except (ValueError, OSError, KeyError, TypeError):
            recuperar, motivo = True, "O registro de prova da fatia e invalido."
        if recuperar and evento.get("loop_count", 0) < 2:
            return {"followup_message": "[esteira] " + motivo +
                    " Rode `py -3 adaptadores/prova.py estado`, repita as verificacoes do contrato "
                    "e feche a fatia. Se nao for possivel, feche com BLOCKED, DECIDE ou FAILED e o "
                    "motivo. Nao escreva DONE sem fecho valido e nao repita efeito externo incerto."}
        return {}
    exigir(nome in {"preToolUse", "postToolUse", "postToolUseFailure"}, "Evento nao suportado")
    if evento.get("tool_name") != "Shell":
        return {}
    if provas.pasta() is None:
        return {"permission": "allow"} if nome == "preToolUse" else {}
    entrada = evento.get("tool_input", {})
    comando = entrada.get("command")
    exigir(isinstance(comando, str), "Comando ausente")
    chamada = evento.get("tool_use_id")
    if nome == "preToolUse":
        # O diretorio da sessao nao substitui o diretorio explicito da chamada.
        cwd = entrada.get("working_directory")
        if cwd is None:
            pasta = provas.pasta()
            provas.estado(pasta)
            criterios = ler(pasta / "contrato.yaml")["dados"]["aceite"]
            if not any(c["verificacao"].get("comando") == comando for c in criterios):
                # A guarda beforeShellExecution continua cobrindo o efeito de bundle.
                return {"permission": "allow"}
        exigir(isinstance(cwd, str) and Path(cwd).is_absolute(), "Cwd nao observado")
        cwd = str(Path(cwd).resolve())
        decisao = avaliar_operacao(Operacao("antes_execucao", "shell", comando, cwd, "ferramenta"), politica)
        if decisao.decisao == "negar":
            return {"permission": "deny", "user_message": decisao.motivo,
                    "agent_message": mensagem(decisao)}
        provas.antes(chamada, comando, cwd, evento.get("cursor_version", "nao_informada"))
        return {"permission": "allow"}
    codigo = None
    if nome == "postToolUseFailure":
        saida = "Execucao inconclusiva: " + str(evento.get("failure_type", "erro"))
    else:
        try:
            dados = json.loads(evento["tool_output"])
            codigo = dados.get("exitCode")
            exigir(type(codigo) is int, "Exit code ausente")
            saida = dados.get("stdout", "") + dados.get("stderr", "")
            exigir(isinstance(saida, str), "Saida invalida")
        except (ValueError, KeyError, TypeError, AttributeError):
            codigo, saida = None, "Resultado sem exitCode inteiro; nenhuma prova de sucesso."
    resultado = provas.depois(chamada, comando, codigo, saida, "campo_resultado")
    if resultado is None:
        return {}
    if resultado["resultado"] == "pass" and "databricks" in comando.casefold():
        # O recibo sozinho nao libera deploy: identidade e destinos nao sao observados.
        pasta = Path(resultado["pasta"])
        teste = ler(pasta / resultado["evidencia_ref"])
        observar_resultado_plan(politica, cwd=teste["dados"]["cwd"], comando=comando)
    return {"additional_context": "[esteira] Verificacao: " + resultado["resultado"] +
            ". Prova registrada em " + resultado["evidencia_ref"] + "."}
