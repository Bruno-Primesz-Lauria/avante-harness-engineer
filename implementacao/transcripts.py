"""Leitura incremental do transcript JSONL do Claude Code para o log da conversa continua.

So o transcript e fonte do log (seu `uuid` torna a importacao idempotente). Pensamentos,
anexos, lembretes do sistema e resultados cifrados nunca entram.
"""
import json
import re

from conversas import cortar_meio, mascarar

LEMBRETE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
AGENTES = {"Agent", "Task"}
CAMPOS_TOOL = ("description", "file_path", "path", "notebook_path", "url", "pattern", "query",
               "skill", "subagent_type", "prompt")
MAX_META = 200
MAX_FERRAMENTAS = 500


def _texto_blocos(conteudo):
    if isinstance(conteudo, str):
        return conteudo
    partes = []
    for bloco in conteudo or []:
        if not isinstance(bloco, dict):
            continue
        if bloco.get("type") == "text":
            partes.append(bloco.get("text", ""))
        elif bloco.get("type") == "image":
            partes.append("[imagem]")
    return "\n".join(partes)


def _meta_tool(nome, entrada):
    detalhes = []
    if isinstance(entrada, dict):
        for campo in CAMPOS_TOOL:
            valor = entrada.get(campo)
            if isinstance(valor, str) and valor.strip():
                detalhes.append(valor.strip().replace("\n", " ")[:120])
                if len(detalhes) == 2:
                    break
    return mascarar(f"{nome} — {' · '.join(detalhes)}" if detalhes else nome)[:MAX_META]


def ler(caminho, cursor, ferramentas, sessao_padrao=""):
    """Le o trecho novo do transcript a partir de `cursor` (offset em bytes).

    Devolve (mensagens, novo_cursor). So linhas completas (terminadas em \\n) sao lidas: o
    transcript e gravado de forma assincrona, e a cauda parcial entra na proxima leitura.
    `ferramentas` mapeia tool_use_id -> nome e e atualizado no lugar.
    """
    with open(caminho, "rb") as arq:
        arq.seek(cursor)
        bruto = arq.read()
    fim = bruto.rfind(b"\n") + 1
    mensagens = []
    for linha in bruto[:fim].splitlines():
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        mensagens.extend(_converter(registro, ferramentas, sessao_padrao))
    while len(ferramentas) > MAX_FERRAMENTAS:
        ferramentas.pop(next(iter(ferramentas)))
    return mensagens, cursor + fim


def _converter(registro, ferramentas, sessao_padrao):
    tipo = registro.get("type")
    if tipo not in ("user", "assistant") or registro.get("isSidechain") or registro.get("isMeta"):
        return []
    data = registro.get("timestamp") or ""
    sessao = (registro.get("sessionId") or sessao_padrao)[:8]
    base = {"date": data, "sessao": sessao}
    conteudo = (registro.get("message") or {}).get("content")
    saida = []
    if tipo == "user":
        if isinstance(conteudo, str):
            texto = LEMBRETE.sub("", conteudo).strip()
            if texto:
                origem = (registro.get("origin") or {}).get("kind", "human")
                if origem == "human":
                    saida.append({**base, "kind": "user", "text": mascarar(texto)})
                else:
                    saida.append({**base, "kind": "work", "text": mascarar(f"[{origem}] {texto}")})
            return saida
        for bloco in conteudo or []:
            if not isinstance(bloco, dict):
                continue
            if bloco.get("type") == "text":
                texto = LEMBRETE.sub("", bloco.get("text", "")).strip()
                if texto:
                    saida.append({**base, "kind": "user", "text": mascarar(texto)})
            elif bloco.get("type") == "tool_result":
                saida.append(_resultado(bloco, ferramentas, base))
        return saida
    for bloco in conteudo or []:
        if not isinstance(bloco, dict):
            continue
        if bloco.get("type") == "text" and bloco.get("text", "").strip():
            saida.append({**base, "kind": "claude", "text": mascarar(bloco["text"].strip())})
        elif bloco.get("type") == "tool_use":
            nome, entrada = bloco.get("name", "?"), bloco.get("input")
            rotulo = nome
            if nome in AGENTES and isinstance(entrada, dict):
                rotulo = entrada.get("subagent_type") or entrada.get("description") or nome
            ferramentas[bloco.get("id", "")] = [nome, rotulo]
            corpo = json.dumps(entrada, ensure_ascii=False)
            saida.append({**base, "kind": "tool", "text": mascarar(cortar_meio(f"{nome} {corpo}")),
                          "linha": _meta_tool(nome, entrada)})
        # thinking, redacted_thinking, server_tool_use e advisor_tool_result nao entram.
    return saida


def _resultado(bloco, ferramentas, base):
    nome, rotulo = ferramentas.get(bloco.get("tool_use_id", ""), ["?", "?"])
    texto = _texto_blocos(bloco.get("content"))
    if nome in AGENTES:
        return {**base, "kind": "work", "text": mascarar(cortar_meio(f"[{rotulo}] {texto}"))}
    estado = "erro" if bloco.get("is_error") else "ok"
    return {**base, "kind": "echo", "text": mascarar(cortar_meio(texto)),
            "linha": f"{nome}: {estado}, {len(texto)} caracteres"}
