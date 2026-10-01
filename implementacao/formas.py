"""Valida somente as quatro formas adotadas, usando o catalogo existente."""
from datetime import datetime
from pathlib import Path, PurePosixPath
import re

import yaml

CATALOGO = Path(__file__).resolve().parents[1] / "formas/catalogo.yaml"
ADOTADAS = {"contrato", "guarda", "brief", "teste"}


def exigir(condicao, motivo):
    if not condicao:
        raise ValueError(motivo)


def identificador(valor):
    exigir(isinstance(valor, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", valor),
           "Identificador invalido")
    return valor


def relativo(valor):
    exigir(isinstance(valor, str) and valor and "\\" not in valor and ":" not in valor,
           "Use caminho relativo com barras /")
    partes = valor.split("/")
    exigir(not PurePosixPath(valor).is_absolute() and all(p not in ("", ".", "..") for p in partes),
           "Caminho fora da raiz ou nao canonico")
    return valor


def dentro(raiz, ref):
    caminho = Path(raiz) / relativo(ref)
    exigir(caminho.resolve().is_relative_to(Path(raiz).resolve()), "Referencia fora da raiz")
    return caminho


def catalogo():
    return yaml.safe_load(CATALOGO.read_text(encoding="utf-8"))


def campos(dados, esquema, enums, nome="dados"):
    exigir(isinstance(dados, dict), f"{nome}: esperado objeto")
    exigir(not set(dados) - set(esquema), f"{nome}: campo desconhecido")
    for chave, regra in esquema.items():
        if chave not in dados:
            exigir(not regra.get("obrigatorio"), f"{nome}.{chave}: ausente")
            continue
        valor = dados[chave]
        if valor is None and regra.get("anulavel"):
            continue
        tipo = regra["tipo"]
        tipos = {"string": str, "caminho": str, "timestamp": str, "enum": str,
                 "bool": bool, "int": int, "lista": list, "objeto": dict}
        exigir(type(valor) is tipos[tipo], f"{nome}.{chave}: tipo invalido")
        if tipo == "enum":
            exigir(valor in enums[regra["enum"]], f"{nome}.{chave}: valor invalido")
        elif tipo == "caminho":
            relativo(valor)
        elif tipo == "timestamp":
            exigir(datetime.fromisoformat(valor).utcoffset() is not None, "Data sem fuso")
        elif tipo == "objeto":
            campos(valor, regra["campos"], enums, f"{nome}.{chave}")
        elif tipo == "lista":
            exigir(len(valor) >= regra.get("min", 0), f"{nome}.{chave}: lista vazia")
            item = regra.get("item", "string")
            for v in valor:
                if isinstance(item, dict):
                    campos(v, item, enums, f"{nome}.{chave}[]")
                else:
                    campos({"item": v}, {"item": {"tipo": item}}, enums, nome)


def validar_dados(tipo, dados):
    c = catalogo()
    exigir(tipo in ADOTADAS, "Forma ainda nao adotada")
    esquema = next(f["dados"] for f in c["formas"] if f["id"] == tipo)
    campos(dados, esquema, c["enums"])
    itens = dados.get("aceite", dados.get("criterios", dados.get("checagens", [])))
    ids = [identificador(i["id"]) for i in itens]
    exigir(len(ids) == len(set(ids)), "Criterio duplicado")
    if tipo == "contrato":
        exigir(any(i["obrigatorio"] for i in itens), "Falta criterio obrigatorio")
    if tipo == "guarda":
        for item in itens:
            exigir(item["resultado"] != "nao_aplica" or item.get("motivo"), "Falta motivo de nao_aplica")
    if tipo == "teste":
        exigir(dados["resultado"] != "pass" or dados["exit_code"] == 0, "Pass exige exit 0")
    return dados


def validar(evento, raiz, execucao_id, fatia_id):
    c = catalogo()
    nomes = {v["campo"] for v in c["envelope"]}
    exigir(isinstance(evento, dict) and set(evento) == nomes, "Envelope invalido")
    exigir(evento["schema_versao"] == "3.1" and evento["exemplo"] is False, "Versao ou exemplo invalido")
    exigir(evento["execucao_id"] == execucao_id and evento["fatia_id"] == fatia_id, "Evento de outra execucao")
    for nome in ("evento_id", "execucao_id", "fatia_id"):
        identificador(evento[nome])
    exigir(type(evento["tentativa"]) is int and evento["tentativa"] > 0, "Tentativa invalida")
    exigir(evento["produtor"] in {"coordenador", "hook", "executor_teste"}, "Produtor invalido")
    produtor = {"contrato": "coordenador", "brief": "coordenador", "guarda": "hook", "teste": "executor_teste"}
    exigir(evento["produtor"] == produtor.get(evento["tipo"]), "Produtor nao corresponde a forma")
    instante = datetime.fromisoformat(evento["registrado_em"])
    exigir(instante.utcoffset() is not None and instante.utcoffset().total_seconds() == 0, "Data deve ser UTC")
    exigir(dentro(raiz, evento["manifesto_ref"]).is_file(), "Manifesto ausente")
    validar_dados(evento["tipo"], evento["dados"])
    dados = evento["dados"]
    refs = [dados["log_ref"]] if evento["tipo"] == "teste" else []
    refs += [i["evidencia_ref"] for i in dados.get("criterios", dados.get("checagens", [])) if i.get("evidencia_ref")]
    for ref in refs:
        exigir(dentro(raiz, ref).is_file(), "Evidencia ausente")
    return evento
