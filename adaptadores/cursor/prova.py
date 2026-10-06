"""Traduz eventos documentados do Cursor; nao interpreta sucesso em prosa."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from formas import dentro, exigir
from guarda_cwd import Operacao, avaliar_operacao
from guarda_efeito import observar_resultado_plan
from protocolo import mensagem
from provas import PAPEIS, Provas, ler, trava

FALHA = re.compile(r"Command failed with exit code (-?\d+)")
PAPEIS_REGISTRAVEIS = PAPEIS - {"map"}


def _agora():
    return datetime.now(timezone.utc).isoformat()


def _editar_estado(provas, alterar):
    pasta = provas.pasta()
    if pasta is None:
        return None, None
    with trava(pasta):
        estado = provas.estado(pasta)
        resultado, mudou = alterar(estado)
        if mudou:
            provas.atualizar(pasta, estado)
        return pasta, resultado


def _rastreamento(estado, sessao):
    rastreio = estado.setdefault("cursor_subagentes", {
        "coordenador_id": sessao, "pendentes": {}, "janelas": {},
    })
    exigir(rastreio.get("coordenador_id") == sessao, "Estado de subagentes pertence a outra conversa")
    return rastreio


def _guardar_task(provas, evento):
    chamada = evento.get("tool_use_id")
    papel = evento.get("tool_input", {}).get("subagent_type")
    exigir(isinstance(chamada, str) and chamada, "tool_use_id ausente na chamada Task")
    exigir(isinstance(papel, str) and papel, "subagent_type ausente na chamada Task")

    def alterar(estado):
        rastreio = _rastreamento(estado, evento["conversation_id"])
        exigir(chamada not in rastreio["pendentes"] and chamada not in rastreio["janelas"],
               "Chamada Task ja observada")
        rastreio["pendentes"][chamada] = {"papel": papel}
        return None, True

    _editar_estado(provas, alterar)


def _abrir_janela(provas, evento):
    chamada = evento.get("subagent_id")
    exigir(isinstance(chamada, str) and chamada, "subagent_id ausente")

    def alterar(estado):
        rastreio = estado.get("cursor_subagentes")
        if rastreio is None or rastreio.get("coordenador_id") != evento.get("conversation_id"):
            return None, False
        pendente = rastreio["pendentes"].get(chamada)
        if pendente is None or pendente["papel"] != evento.get("subagent_type"):
            return None, False
        del rastreio["pendentes"][chamada]
        rastreio["janelas"][chamada] = {
            "papel": pendente["papel"], "inicio": _agora(), "agente_id": None,
        }
        previsto = any(c["papel"] == pendente["papel"] for c in estado["chamadas_previstas"])
        return pendente["papel"] if previsto else None, True

    _, papel = _editar_estado(provas, alterar)
    if papel in PAPEIS_REGISTRAVEIS:
        # Retrato de superficie no inicio do subagente (C5); o fim e conferido em registrar_chamada.
        provas.abrir_chamada(_chamada_id(chamada), papel)


def _fechar_janela(provas, evento):
    chamada = evento.get("subagent_id")
    if not isinstance(chamada, str) or not chamada:
        return None
    fechada = None

    def alterar(estado):
        nonlocal fechada
        rastreio = estado.get("cursor_subagentes")
        if rastreio is None or rastreio.get("coordenador_id") != evento.get("conversation_id"):
            return None, False
        fechada = rastreio["janelas"].pop(chamada, None)
        return None, fechada is not None

    pasta, _ = _editar_estado(provas, alterar)
    if pasta is None or fechada is None:
        return None
    return pasta, chamada, fechada


def _chamada_id(tool_use_id):
    # Cursor inclui LF no ID observado; chamada_id aceita apenas identificadores simples.
    return "cursor_" + sha256(tool_use_id.encode("utf-8")).hexdigest()


def _registrar_subagente(provas, evento):
    fechada = _fechar_janela(provas, evento)
    if fechada is None:
        return
    pasta, tool_use_id, janela = fechada
    papel = janela["papel"]
    if papel not in PAPEIS_REGISTRAVEIS:
        return
    estado = provas.estado(pasta)
    if not any(chamada["papel"] == papel for chamada in estado["chamadas_previstas"]):
        return
    ids = [{"nome": "tool_use_id", "valor": tool_use_id}]
    if janela["agente_id"]:
        ids.append({"nome": "agente_id", "valor": janela["agente_id"]})
    status = "concluida" if evento.get("status") == "completed" else "inconclusiva"
    provas.registrar_chamada(_chamada_id(tool_use_id), papel, "cursor", ids,
                             janela["inicio"], _agora(), status)


def _janelas_ativas(raiz, politica):
    registros = Path(politica["registros_raiz"])
    sessoes = registros / "sessoes"
    abertas = []
    if not sessoes.exists():
        return abertas
    for indice in sessoes.iterdir():
        ponteiro = indice / "ativa.json"
        if not ponteiro.is_file():
            continue
        dados = ler(ponteiro)
        pasta = dentro(registros, dados["fatia"])
        estado_bruto = ler(pasta / "estado.json")
        rastreio = estado_bruto.get("cursor_subagentes")
        if not rastreio or not rastreio.get("janelas"):
            continue
        coordenador_id = rastreio.get("coordenador_id")
        if not isinstance(coordenador_id, str) or not coordenador_id:
            continue
        coordenador = Provas(raiz, registros, coordenador_id, runtime="cursor")
        if coordenador.indice.resolve() != indice.resolve() or coordenador.pasta() != pasta:
            continue
        estado = coordenador.estado(pasta)
        rastreio = estado.get("cursor_subagentes", {})
        abertas.extend((coordenador, coordenador_id, chamada, janela)
                       for chamada, janela in rastreio.get("janelas", {}).items())
    return abertas


def _prova_do_subagente(evento, politica, raiz):
    conversa = evento.get("conversation_id")
    if not isinstance(conversa, str) or not conversa:
        return None
    abertas = _janelas_ativas(raiz, politica)
    if not abertas or any(coordenador_id == conversa
                          for _, coordenador_id, _, _ in abertas):
        return None
    if len(abertas) != 1:
        return False
    provas, coordenador_id, tool_use_id, janela = abertas[0]
    if coordenador_id == conversa or janela["papel"] not in PAPEIS or provas.pasta() is None:
        return False

    def alterar(estado_atual):
        rastreio_atual = estado_atual.get("cursor_subagentes", {})
        atual = rastreio_atual.get("janelas", {}).get(tool_use_id)
        if atual is None or atual["papel"] not in PAPEIS:
            return False, False
        if atual["agente_id"] not in (None, conversa):
            return False, False
        atual["agente_id"] = conversa
        return True, True

    pasta, vinculado = _editar_estado(provas, alterar)
    return (provas, janela["papel"]) if pasta is not None and vinculado else False


def tratar(evento, politica, raiz):
    nome = evento.get("hook_event_name")
    sessao = evento.get("conversation_id") or evento.get("session_id")
    if nome == "sessionStart":
        exigir(isinstance(sessao, str) and sessao, "Sessao ausente")
        return {"env": {"ESTEIRA_SESSAO": sessao}, "additional_context":
                "Leia AGENTS.md. Sessao para --sessao: " + sessao + ". "
                "Em trabalho de varias etapas, use adaptadores/prova.py --runtime cursor (iniciar, estado, fechar) "
                "conforme evidencia/uso.md. Pergunta simples nao precisa de registro."}
    if nome == "stop" and evento.get("status") != "completed":
        return {}
    provas = Provas(raiz, politica["registros_raiz"], sessao, runtime="cursor")
    if nome == "preToolUse" and evento.get("tool_name") == "Task":
        if provas.pasta() is not None:
            _guardar_task(provas, evento)
        return {"permission": "allow"}
    if nome == "subagentStart":
        _abrir_janela(provas, evento)
        return {}
    if nome == "subagentStop":
        _registrar_subagente(provas, evento)
        return {}
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
    agente_id = None
    associado = _prova_do_subagente(evento, politica, raiz)
    if associado is False:
        return {"permission": "allow"} if nome == "preToolUse" else {}
    if associado is not None:
        provas, _ = associado
        agente_id = evento["conversation_id"]
    elif provas.pasta() is None:
        return {"permission": "allow"} if nome == "preToolUse" else {}
    entrada = evento.get("tool_input", {})
    comando = entrada.get("command")
    exigir(isinstance(comando, str), "Comando ausente")
    chamada = evento.get("tool_use_id")
    if nome == "preToolUse":
        # O diretorio da sessao nao substitui o diretorio explicito da chamada.
        # Cursor 3.17.8 envia tool_input.cwd ('' quando o agente nao informa); versoes anteriores, working_directory.
        cwd = entrada.get("working_directory") or entrada.get("cwd") or None
        if cwd is None:
            pasta = provas.pasta()
            provas.estado(pasta)
            criterios = ler(pasta / "contrato.yaml")["dados"]["aceite"]
            if not any(c["verificacao"].get("comando") == comando for c in criterios):
                # A guarda beforeShellExecution continua cobrindo o efeito de bundle.
                return {"permission": "allow"}
        exigir(isinstance(cwd, str) and Path(cwd).is_absolute(),
               "Cwd nao observado. Informe o diretorio absoluto no campo cwd da ferramenta Shell")
        cwd = str(Path(cwd).resolve())
        decisao = avaliar_operacao(Operacao("antes_execucao", "shell", comando, cwd, "ferramenta"), politica)
        if decisao.decisao == "negar":
            return {"permission": "deny", "user_message": decisao.motivo,
                    "agent_message": mensagem(decisao)}
        provas.antes(chamada, comando, cwd, evento.get("cursor_version", "nao_informada"), agente_id)
        return {"permission": "allow"}
    codigo, origem = None, "campo_resultado"
    if nome == "postToolUseFailure":
        erro = evento.get("error_message")
        # Exit diferente de zero chega so como texto (sondagem P0.5); timeout ou negacao seguem inconclusivos.
        lido = FALHA.fullmatch(erro.strip()) if evento.get("failure_type") == "error" and isinstance(erro, str) else None
        if lido and int(lido.group(1)) != 0:
            codigo, origem, saida = int(lido.group(1)), "texto_falha", erro
        else:
            saida = "Execucao inconclusiva: " + str(evento.get("failure_type", "erro"))
    else:
        try:
            dados = json.loads(evento["tool_output"])
            codigo = dados.get("exitCode")
            exigir(type(codigo) is int, "Exit code ausente")
            saida = dados["output"] if "output" in dados else dados.get("stdout", "") + dados.get("stderr", "")
            exigir(isinstance(saida, str), "Saida invalida")
        except (ValueError, KeyError, TypeError, AttributeError):
            codigo, saida = None, "Resultado sem exitCode inteiro; nenhuma prova de sucesso."
    resultado = provas.depois(chamada, comando, codigo, saida, origem)
    if resultado is None:
        return {}
    if resultado["resultado"] == "pass" and "databricks" in comando.casefold():
        # O recibo sozinho nao libera deploy: identidade e destinos nao sao observados.
        pasta = Path(resultado["pasta"])
        teste = ler(pasta / resultado["evidencia_ref"])
        observar_resultado_plan(politica, cwd=teste["dados"]["cwd"], comando=comando)
    return {"additional_context": "[esteira] Verificacao: " + resultado["resultado"] +
            ". Prova registrada em " + resultado["evidencia_ref"] + "."}
