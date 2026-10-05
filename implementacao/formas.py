"""Valida as formas adotadas (3.1 e 3.2), usando o catalogo existente."""
from datetime import datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
import re

import yaml

CATALOGO = Path(__file__).resolve().parents[1] / "formas/catalogo.yaml"
ADOTADAS = {"contrato", "guarda", "brief", "teste"}
FORMAS_32 = {"ataque", "triagem", "inspecao", "chamada"}
VERSOES = {"3.1", "3.2"}


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


def forma_catalogo(tipo, c=None):
    c = catalogo() if c is None else c
    return next((f for f in c["formas"] if f["id"] == tipo), None)


def tipos_adotados(versao):
    return ADOTADAS | (FORMAS_32 if versao == "3.2" else set())


def validar_verificacao_contrato(dados, versao, regras):
    for regra in regras:
        for criterio in dados["aceite"]:
            for campo in regra.get("campos_opcionais", []):
                if campo in criterio:
                    permitido = versao == regra["versao"] and criterio["tipo"] in regra["valores"]
                    exigir(permitido, f"Campo {campo} nao permitido para {criterio['tipo']} em {versao}")

    if versao == "3.1":
        for criterio in dados["aceite"]:
            verificacao = criterio["verificacao"]
            exigir(all(campo in verificacao for campo in ("comando", "cwd", "caminhos")),
                   "Verificacao 3.1 exige comando, cwd e caminhos")
        return

    for regra in regras:
        if regra["versao"] != versao:
            continue
        for criterio in dados["aceite"]:
            if criterio["tipo"] not in regra["valores"]:
                continue
            verificacao = criterio["verificacao"]
            ausentes = [campo for campo in regra.get("exige", []) if campo not in verificacao]
            exigir(not ausentes,
                   f"Verificacao {criterio['tipo']} exige {', '.join(ausentes)}")
            permitidos = regra.get("produtor_em")
            if permitidos:
                exigir(verificacao["produtor"] in permitidos,
                       f"Produtor de {criterio['tipo']} invalido")


def validar_dados(tipo, dados, schema_versao="3.1"):
    c = catalogo()
    exigir(isinstance(schema_versao, str) and schema_versao in VERSOES,
           "Versao de schema invalida")
    exigir(isinstance(tipo, str), "Forma invalida")
    exigir(tipo in tipos_adotados(schema_versao), "Forma ainda nao adotada nesta versao")
    forma = forma_catalogo(tipo, c)
    exigir(forma is not None, "Forma ausente do catalogo")
    esquema = forma["dados"]
    campos(dados, esquema, c["enums"])
    if tipo == "contrato":
        validar_verificacao_contrato(dados, schema_versao, forma.get("regras_condicionais", []))
    itens = dados.get("aceite", dados.get("criterios", dados.get("checagens", [])))
    ids = [identificador(i["id"]) for i in itens if "id" in i]
    exigir(len(ids) == len(set(ids)), "Criterio duplicado")
    if tipo == "contrato":
        exigir(any(i["obrigatorio"] for i in itens), "Falta criterio obrigatorio")
    if tipo == "guarda":
        for item in itens:
            exigir(item["resultado"] != "nao_aplica" or item.get("motivo"), "Falta motivo de nao_aplica")
    if tipo == "teste":
        exigir(dados["resultado"] != "pass" or dados["exit_code"] == 0, "Pass exige exit 0")
        if "agente_id" in dados:
            identificador(dados["agente_id"])
        origem = dados.get("exit_code_origem")
        if origem is not None:
            exigir(dados["exit_code"] is not None, "Origem sem exit code")
            exigir(origem != "evento_sucesso" or dados["exit_code"] == 0, "Evento de sucesso exige exit 0")
            exigir(origem != "texto_falha" or dados["exit_code"] != 0, "Texto de falha nao comprova exit 0")
    if tipo == "ataque":
        if "agente_id" in dados:
            identificador(dados["agente_id"])
        if dados["veredito"] == "com_achados":
            exigir(bool(dados["achados"]), "com_achados exige ao menos um achado")
        if dados["veredito"] == "nao_quebrei":
            exigir(bool(dados["tentativas"]), "nao_quebrei exige tentativas")
            exigir(bool(dados["cobertura"]), "nao_quebrei exige cobertura")
        for campo in ("tentativas", "achados"):
            ids = [identificador(item["id"]) for item in dados[campo]]
            exigir(len(ids) == len(set(ids)), f"{campo}: identificador duplicado")
        ids = [identificador(item["criterio_id"]) for item in dados["cobertura"]]
        exigir(len(ids) == len(set(ids)), "cobertura: criterio duplicado")
    if tipo == "triagem":
        identificador(dados["achado_id"])
        exigir(bool(dados["responsavel"].strip()), "Triagem exige responsavel")
        if dados["decisao"] == "procedente":
            exigir(bool(dados.get("evidencia_resolucao_ref")),
                   "Achado procedente exige evidencia da resolucao")
        if dados["decisao"] == "descartado":
            exigir(bool(dados.get("motivo_descarte", "").strip()),
                   "Achado descartado exige motivo")
    if tipo == "inspecao":
        identificador(dados["criterio_id"])
        ids = [identificador(item["id"]) for item in dados["checagens"]]
        exigir(len(ids) == len(set(ids)), "Checagem duplicada")
        exigir(re.fullmatch(r"[0-9a-fA-F]{64}", dados["manifesto_sha256"]) is not None,
               "Hash do manifesto invalido")
    if tipo == "chamada":
        identificador(dados["chamada_id"])
        nomes = []
        for item in dados["ids_observados"]:
            exigir(bool(item["nome"].strip()) and bool(item["valor"].strip()),
                   "IDs observados exigem nome e valor")
            nomes.append(item["nome"])
        exigir(len(nomes) == len(set(nomes)), "ID observado duplicado")
        inicio = datetime.fromisoformat(dados["inicio"])
        fim = datetime.fromisoformat(dados["fim"])
        exigir(inicio.utcoffset() is not None and fim.utcoffset() is not None,
               "Data sem fuso")
        exigir(inicio <= fim, "Fim da chamada anterior ao inicio")
    return dados


def validar(evento, raiz, execucao_id, fatia_id):
    c = catalogo()
    nomes = {v["campo"] for v in c["envelope"]}
    exigir(isinstance(evento, dict) and set(evento) == nomes, "Envelope invalido")
    versao = evento["schema_versao"]
    exigir(isinstance(versao, str) and versao in VERSOES and evento["exemplo"] is False,
           "Versao ou exemplo invalido")
    exigir(isinstance(evento["tipo"], str), "Forma invalida")
    exigir(evento["tipo"] in tipos_adotados(versao), "Forma ainda nao adotada nesta versao")
    exigir(evento["execucao_id"] == execucao_id and evento["fatia_id"] == fatia_id, "Evento de outra execucao")
    for nome in ("evento_id", "execucao_id", "fatia_id"):
        identificador(evento[nome])
    exigir(type(evento["tentativa"]) is int and evento["tentativa"] > 0, "Tentativa invalida")
    produtores = c["produtores_permitidos"]
    exigir(isinstance(evento["produtor"], str) and evento["produtor"] in produtores,
           "Produtor invalido")
    forma = forma_catalogo(evento["tipo"], c)
    proprietarios = forma["produtor"]
    if isinstance(proprietarios, str):
        proprietarios = [proprietarios]
    exigir(evento["produtor"] in proprietarios, "Produtor nao corresponde a forma")
    instante = datetime.fromisoformat(evento["registrado_em"])
    exigir(instante.utcoffset() is not None and instante.utcoffset().total_seconds() == 0, "Data deve ser UTC")
    manifesto = dentro(raiz, evento["manifesto_ref"])
    exigir(manifesto.is_file(), "Manifesto ausente")
    validar_dados(evento["tipo"], evento["dados"], versao)
    dados = evento["dados"]
    refs = [dados["log_ref"]] if evento["tipo"] == "teste" else []
    refs += [i["evidencia_ref"] for i in dados.get("criterios", dados.get("checagens", [])) if i.get("evidencia_ref")]
    if evento["tipo"] == "ataque":
        refs += [dados["entrada"][chave] for chave in
                 ("intencao_ref", "aceite_ref", "baseline_ref")]
        refs += dados["entrada"]["provas_refs"]
        refs += [i["evidencia_ref"] for i in dados["tentativas"] if i.get("evidencia_ref")]
        refs += [i["evidencia_ref"] for i in dados["achados"]]
    elif evento["tipo"] == "triagem":
        refs.append(dados["revisao_ref"])
        if dados.get("evidencia_resolucao_ref"):
            refs.append(dados["evidencia_resolucao_ref"])
    elif evento["tipo"] == "inspecao":
        digest = sha256(manifesto.read_bytes()).hexdigest()
        exigir(digest.lower() == dados["manifesto_sha256"].lower(),
               "Hash nao corresponde ao manifesto")
    for ref in refs:
        exigir(dentro(raiz, ref).is_file(), "Evidencia ausente")
    return evento
