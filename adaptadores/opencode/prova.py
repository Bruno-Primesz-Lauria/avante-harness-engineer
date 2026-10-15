"""Traduz os eventos observados do OpenCode em provas da fatia ativa."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re

from formas import exigir
from guarda_cwd import _extrair_prefixo_cwd, avaliar_operacao
from guarda_efeito import observar_resultado_plan
from protocolo import normalizar, traduzir
from provas import Provas, gravar, ler, trava

PAPEIS = {"map", "config", "implement", "test", "refute", "docs", "dab"}
PAPEIS_REGISTRAVEIS = PAPEIS - {"map"}
ESTADO_TAREFA = re.compile(r"<task\b[^>]*\bstate=[\"']([^\"']+)[\"']", re.IGNORECASE)


def _agora():
    return datetime.now(timezone.utc).isoformat()


def _id_hash(*partes):
    return sha256("\0".join(partes).encode("utf-8")).hexdigest()


def _raiz_eventos(politica):
    return Path(politica["registros_raiz"]) / "opencode"


def _arquivo_tarefa(politica, sessao, chamada):
    return _raiz_eventos(politica) / "tarefas" / (_id_hash(sessao, chamada) + ".json")


def _arquivo_filho(politica, sessao):
    return _raiz_eventos(politica) / "sessoes" / (_id_hash(sessao) + ".json")


def _entrada(evento):
    valor = evento.get("input")
    return valor if isinstance(valor, dict) else {}


def _args(evento):
    valor = evento.get("args")
    if isinstance(valor, dict):
        return valor
    valor = _entrada(evento).get("args")
    return valor if isinstance(valor, dict) else {}


def _provas_da_sessao(sessao, politica, raiz):
    if not isinstance(sessao, str) or not sessao:
        return None, None
    filho = _arquivo_filho(politica, sessao)
    if filho.is_file():
        contexto = ler(filho)
        provas = Provas(raiz, politica["registros_raiz"], contexto["raiz_sessao"], runtime="opencode")
        return provas, contexto
    return Provas(raiz, politica["registros_raiz"], sessao, runtime="opencode"), None


def _sessao_input(evento):
    return _entrada(evento).get("sessionID")


def _criterio_declarado(provas, comando):
    pasta = provas.pasta()
    if pasta is None:
        return None
    contrato = ler(pasta / "contrato.yaml")["dados"]
    return next((criterio for criterio in contrato["aceite"]
                 if criterio["verificacao"].get("comando") == comando), None)


def _negar_prova(motivo):
    return {"decisao": "negar", "motivo": "[prova] " + motivo}


def _cwd_verificacao(decisao, argumentos):
    cwd = decisao.cwd or argumentos.get("workdir")
    if not isinstance(cwd, str) or not cwd:
        return None
    caminho = Path(cwd)
    if not caminho.is_absolute():
        return None
    try:
        caminho = caminho.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return str(caminho) if caminho.is_dir() else None


def _bash_antes(evento, politica, raiz):
    entrada = _entrada(evento)
    exigir(entrada.get("tool") == "bash", "Evento de shell diferente do contrato")
    argumentos = _args(evento)
    normalizado = {"evento": "tool.execute.before", "tool": "bash", "args": argumentos}
    operacao = normalizar("opencode", normalizado)
    decisao = avaliar_operacao(operacao, politica)
    if decisao.decisao == "negar":
        return traduzir("opencode", decisao)

    sessao = entrada.get("sessionID")
    chamada = entrada.get("callID")
    comando = argumentos.get("command")
    provas, contexto_filho = _provas_da_sessao(sessao, politica, raiz)
    criterio = _criterio_declarado(provas, comando) if provas is not None else None
    if criterio is None:
        return traduzir("opencode", decisao)
    if contexto_filho and contexto_filho.get("ambiguo"):
        return _negar_prova("A sessão filha não pôde ser vinculada a uma única chamada Task.")
    exigir(isinstance(chamada, str) and chamada, "Chamada Bash sem identificador")
    cwd = _cwd_verificacao(decisao, argumentos)
    if cwd is None:
        return _negar_prova(
            "O cwd da verificação não foi observado. Informe args.workdir absoluto ou use um prefixo literal."
        )
    agente_id = contexto_filho.get("sessao") if contexto_filho else None
    if not provas.antes(chamada, comando, cwd, "nao_informada", agente_id, runtime="opencode"):
        return _negar_prova("A chamada não iniciou uma verificação declarada e atual.")
    return traduzir("opencode", decisao)


def _observar_bash(evento, politica, raiz):
    entrada = _entrada(evento)
    sessao, chamada = entrada.get("sessionID"), entrada.get("callID")
    argumentos = _args(evento)
    comando = argumentos.get("command")
    if not isinstance(sessao, str) or not isinstance(chamada, str) or not isinstance(comando, str):
        return {}
    provas, _ = _provas_da_sessao(sessao, politica, raiz)
    if provas is None:
        return {}
    saida = evento.get("output")
    saida = saida if isinstance(saida, dict) else {}
    metadata = saida.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    codigo = metadata.get("exit")
    if type(codigo) is not int:
        codigo = None
    texto = metadata.get("output")
    if not isinstance(texto, str):
        texto = "Resultado OpenCode sem metadata.output observável."
    resultado = provas.depois(chamada, comando, codigo, texto,
                              "campo_resultado" if codigo is not None else None)
    if resultado and resultado["resultado"] == "pass" and "databricks" in comando.casefold():
        teste = ler(Path(resultado["pasta"]) / resultado["evidencia_ref"])
        observar_resultado_plan(
            politica,
            cwd=teste["dados"]["cwd"],
            comando=_extrair_prefixo_cwd(comando)[1],
        )
    return {}


def _task_antes(evento, politica, raiz):
    entrada = _entrada(evento)
    pai, chamada = entrada.get("sessionID"), entrada.get("callID")
    papel = _args(evento).get("subagent_type")
    if (not isinstance(pai, str) or not pai or not isinstance(chamada, str) or not chamada or
            papel not in PAPEIS_REGISTRAVEIS):
        return {}
    provas, contexto_filho = _provas_da_sessao(pai, politica, raiz)
    if provas is None or contexto_filho is not None:
        return {}
    pasta = provas.pasta()
    if pasta is None:
        return {}
    estado = provas.estado(pasta)
    if not any(c["papel"] == papel for c in estado["chamadas_previstas"]):
        return {}

    arquivo = _arquivo_tarefa(politica, pai, chamada)
    base = _raiz_eventos(politica)
    with trava(base):
        if arquivo.exists():
            return {}
        gravar(arquivo, {"raiz_sessao": pai, "pai": pai, "chamada_id": chamada,
                         "papel": papel, "inicio": _agora(), "sessao_filha": None})
    provas.abrir_chamada(chamada, papel)
    return {}


def _session_created(evento, politica, raiz):
    propriedades = evento.get("properties")
    propriedades = propriedades if isinstance(propriedades, dict) else {}
    info = propriedades.get("info")
    info = info if isinstance(info, dict) else {}
    sessao_filha, pai = info.get("id") or propriedades.get("sessionID"), info.get("parentID")
    if not isinstance(sessao_filha, str) or not sessao_filha or not isinstance(pai, str) or not pai:
        return {}
    provas, contexto = _provas_da_sessao(pai, politica, raiz)
    if provas is None or contexto is not None or provas.pasta() is None:
        return {}

    base = _raiz_eventos(politica)
    arquivo_filho = _arquivo_filho(politica, sessao_filha)
    tarefas = _raiz_eventos(politica) / "tarefas"
    with trava(base):
        if arquivo_filho.exists():
            return {}
        candidatas = []
        if tarefas.is_dir():
            for caminho in tarefas.glob("*.json"):
                item = ler(caminho)
                if item.get("pai") == pai and item.get("sessao_filha") is None:
                    candidatas.append((caminho, item))
        ambiguo = len(candidatas) != 1
        chamada, papel = None, None
        if not ambiguo:
            caminho, item = candidatas[0]
            item["sessao_filha"] = sessao_filha
            gravar(caminho, item, substituir=True)
            chamada, papel = item["chamada_id"], item["papel"]
        gravar(arquivo_filho, {"raiz_sessao": pai, "pai": pai, "sessao": sessao_filha,
                               "chamada_id": chamada, "papel": papel, "ambiguo": ambiguo})
    return {}


def _limpar_tarefa(evento, politica, pai, chamada, tarefa, sessao_filha=None):
    base = _raiz_eventos(politica)
    arquivo = _arquivo_tarefa(politica, pai, chamada)
    with trava(base):
        arquivo.unlink(missing_ok=True)
        filho = sessao_filha or tarefa.get("sessao_filha")
        if isinstance(filho, str) and filho:
            caminho_filho = _arquivo_filho(politica, filho)
            if caminho_filho.is_file():
                vinculo = ler(caminho_filho)
                if vinculo.get("chamada_id") == chamada or vinculo.get("ambiguo"):
                    caminho_filho.unlink(missing_ok=True)


def _task_depois(evento, politica, raiz):
    entrada = _entrada(evento)
    pai, chamada = entrada.get("sessionID"), entrada.get("callID")
    if not isinstance(pai, str) or not isinstance(chamada, str):
        return {}
    arquivo = _arquivo_tarefa(politica, pai, chamada)
    if not arquivo.is_file():
        return {}
    tarefa = ler(arquivo)
    provas = Provas(raiz, politica["registros_raiz"], pai, runtime="opencode")
    saida = evento.get("output")
    saida = saida if isinstance(saida, dict) else {}
    metadata = saida.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    sessao_filha = metadata.get("sessionId")
    vinculo = _arquivo_filho(politica, sessao_filha) if isinstance(sessao_filha, str) else None
    vinculo_valido = (
        isinstance(sessao_filha, str) and bool(sessao_filha) and
        metadata.get("parentSessionId") == pai and
        tarefa.get("sessao_filha") == sessao_filha and
        vinculo is not None and vinculo.is_file() and
        ler(vinculo).get("chamada_id") == chamada and
        ler(vinculo).get("papel") == tarefa.get("papel")
    )
    if not vinculo_valido:
        provas.encerrar_chamada(chamada)
        _limpar_tarefa(evento, politica, pai, chamada, tarefa, sessao_filha)
        return {}

    texto_saida = saida.get("output")
    estado_saida = metadata.get("state")
    if not isinstance(estado_saida, str) and isinstance(texto_saida, str):
        correspondencia = ESTADO_TAREFA.search(texto_saida)
        estado_saida = correspondencia.group(1) if correspondencia else None
    status = {
        "completed": "concluida", "failed": "falhou", "cancelled": "cancelada",
    }.get(estado_saida.casefold(), "inconclusiva") if isinstance(estado_saida, str) else "inconclusiva"

    ids = [
        {"nome": "callID", "valor": chamada},
        {"nome": "agente_id", "valor": sessao_filha},
    ]
    try:
        provas.registrar_chamada(chamada, tarefa["papel"], "opencode", ids,
                                 tarefa["inicio"], _agora(), status)
    except (KeyError, OSError, TypeError, ValueError):
        provas.encerrar_chamada(chamada)
    _limpar_tarefa(evento, politica, pai, chamada, tarefa, sessao_filha)
    return {}


def _idle(evento, politica, raiz):
    propriedades = evento.get("properties")
    propriedades = propriedades if isinstance(propriedades, dict) else {}
    sessao = propriedades.get("sessionID")
    if not isinstance(sessao, str) or not sessao or _arquivo_filho(politica, sessao).is_file():
        return {}
    provas = Provas(raiz, politica["registros_raiz"], sessao, runtime="opencode")
    try:
        estado = provas.conferir()
        if not estado["ativa"] or estado["fecho_valido"]:
            return {}
        motivo = "A fatia ativa não tem fecho válido."
        if estado["pendencias"]:
            motivo += " Pendências: " + ", ".join(estado["pendencias"]) + "."
    except (KeyError, OSError, TypeError, ValueError):
        motivo = "O registro de prova da fatia é inválido."
    return {"followup_message": (
        "[esteira] " + motivo + " Rode `py -3 adaptadores/prova.py estado`, repita as verificações "
        "do contrato e feche a fatia. Se não for possível, feche com BLOCKED, DECIDE ou FAILED "
        "e o motivo. Não escreva DONE sem fecho válido e não repita efeito externo incerto."
    )}


def tratar(evento, politica, raiz):
    """Trata um evento do plugin; só o evento before de Bash pode bloquear a ferramenta."""
    exigir(isinstance(evento, dict), "Evento invalido")
    tipo = evento.get("evento")
    if tipo == "shell.env":
        sessao = _entrada(evento).get("sessionID")
        return {"env": {"ESTEIRA_SESSAO": sessao, "ESTEIRA_RUNTIME": "opencode"}} if sessao else {}
    if tipo == "session.created":
        return _session_created(evento, politica, raiz)
    if tipo == "session.idle":
        return _idle(evento, politica, raiz)
    if tipo not in {"tool.execute.before", "tool.execute.after"}:
        return {}
    ferramenta = _entrada(evento).get("tool")
    if ferramenta == "task":
        return _task_antes(evento, politica, raiz) if tipo == "tool.execute.before" else _task_depois(evento, politica, raiz)
    if ferramenta != "bash":
        return {}
    return _bash_antes(evento, politica, raiz) if tipo == "tool.execute.before" else _observar_bash(evento, politica, raiz)
