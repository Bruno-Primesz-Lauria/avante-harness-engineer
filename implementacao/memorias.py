"""Memoria versionada do harness: metadados, validacao estrutural e resumo do indice.

As notas sao contexto advisory. Este modulo nao executa instrucoes contidas nelas,
nao faz commit e nao publica contribuicoes.
"""
from datetime import date
from pathlib import Path, PurePosixPath
import re

import yaml

from guarda_cwd import YamlSemDuplicatas

PASTA = "memoria"
TIPOS = {"decisoes": "decisao", "aprendizados": "aprendizado", "padroes": "padrao"}
STATUS = {"ativo", "substituido"}
# modulo, objeto e etapa sao opcionais: chaveiam a nota por objeto da migracao (memoria do produto).
OPCIONAIS = {"substituida_por", "modulo", "objeto", "etapa"}
CAMPOS = {"schema_versao", "id", "tipo", "status", "tags", "caminhos", "fontes",
          "verificado_em"} | OPCIONAIS
OBRIGATORIOS = CAMPOS - OPCIONAIS
FORA_DAS_NOTAS = {"README.md", "indice.md"}
IGNORADAS = {"modelos", ".obsidian"}
PRODUTO = "prj-avante-analytics-adb/"
LOCAL_APENAS = ".execucoes/"

ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
OBJETO = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
ETAPA = re.compile(r"0[1-8]")
COMMIT = re.compile(r"[0-9a-f]{7,40}")
URL = re.compile(r"https?://\S+")
DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
ABSOLUTO = re.compile(r"^(/|\\|[A-Za-z]:|file:)")
CODIGO = re.compile(r"```.*?```|`[^`\n]*`", re.S)

INDICE_MAX_LINHAS = 40
INDICE_MAX_CARACTERES = 4000


def ler_nota(caminho):
    """Separa o frontmatter YAML do corpo. Erro de formato vira ValueError."""
    texto = caminho.read_text(encoding="utf-8")
    if not texto.startswith("---\n"):
        raise ValueError("Frontmatter ausente: a nota deve comecar com ---")
    fim = texto.find("\n---\n", 4)
    if fim < 0:
        raise ValueError("Frontmatter sem fechamento ---")
    try:
        meta = yaml.load(texto[4:fim], Loader=YamlSemDuplicatas)
    except yaml.YAMLError as erro:
        raise ValueError(f"Frontmatter YAML invalido: {erro}") from None
    if not isinstance(meta, dict):
        raise ValueError("Frontmatter deve ser um mapa")
    return meta, texto[fim + 5:]


def notas(raiz, pasta=PASTA):
    """Notas em <pasta>/<tipo>/, em ordem deterministica; modelos e .obsidian ficam fora."""
    base = Path(raiz) / pasta
    encontradas = []
    for caminho in sorted(base.rglob("*.md")):
        relativo = caminho.relative_to(base)
        if relativo.parts[0] in IGNORADAS or str(relativo) in FORA_DAS_NOTAS:
            continue
        encontradas.append(caminho)
    return encontradas


def _relativo_seguro(valor):
    """Caminho relativo a raiz, com /, sem escapar dela."""
    if not isinstance(valor, str) or not valor.strip():
        return False
    if ABSOLUTO.match(valor) or "\\" in valor:
        return False
    return ".." not in PurePosixPath(valor).parts


def _links(texto):
    sem_codigo = CODIGO.sub("", texto)
    return sem_codigo, [alvo for alvo in LINK.findall(sem_codigo)]


def _conferir_links(arquivo, texto, raiz, erros):
    """Links Markdown relativos e resolvidos; wikilink e caminho absoluto sao recusados."""
    nome = arquivo.relative_to(raiz).as_posix()
    sem_codigo, alvos = _links(texto)
    if "[[" in sem_codigo:
        erros.append(f"{nome}: wikilink [[...]] nao e aceito; use link Markdown relativo")
    resolvidos = set()
    for alvo in alvos:
        if URL.fullmatch(alvo) or alvo.startswith(("mailto:", "#")):
            continue
        if ABSOLUTO.match(alvo):
            erros.append(f"{nome}: link absoluto nao e aceito: {alvo}")
            continue
        caminho = alvo.split("#", 1)[0]
        destino = (arquivo.parent / caminho).resolve()
        try:
            destino.relative_to(raiz.resolve())
        except ValueError:
            erros.append(f"{nome}: link sai da raiz: {alvo}")
            continue
        if not destino.exists():
            erros.append(f"{nome}: link quebrado: {alvo}")
            continue
        resolvidos.add(destino)
    return resolvidos


def _conferir_fontes(nome, fontes, status, raiz, erros):
    portavel = False
    for fonte in fontes:
        if isinstance(fonte, (int, float)) and not isinstance(fonte, bool):
            erros.append(f"{nome}: fonte {fonte} virou numero no YAML; coloque o hash do commit entre aspas")
            continue
        if not isinstance(fonte, str) or not fonte.strip():
            erros.append(f"{nome}: fonte vazia ou nao textual")
            continue
        if URL.fullmatch(fonte) or COMMIT.fullmatch(fonte):
            portavel = True
            continue
        if not _relativo_seguro(fonte):
            erros.append(f"{nome}: fonte deve ser URL, commit ou caminho relativo a raiz: {fonte}")
            continue
        if fonte.startswith(PRODUTO):
            # O clone do produto e opcional; a conferencia do arquivo fica para a Fase 2.
            portavel = True
            continue
        if not (raiz / fonte).exists():
            erros.append(f"{nome}: fonte local inexistente: {fonte}")
            continue
        if not fonte.startswith(LOCAL_APENAS):
            portavel = True
    if status == "ativo" and fontes and not portavel:
        erros.append(f"{nome}: nota ativa precisa de ao menos uma fonte acessivel de outro clone "
                     "(fora de .execucoes/)")


def _conferir_objeto(nome, meta, erros):
    """Campos opcionais por objeto: modulo SAP, objeto e etapas 01-08."""
    modulo = meta.get("modulo")
    if "modulo" in meta and (not isinstance(modulo, str) or not modulo.strip()):
        erros.append(f"{nome}: modulo deve ser texto nao vazio")
    objeto = meta.get("objeto")
    if "objeto" in meta and (not isinstance(objeto, str) or not OBJETO.fullmatch(objeto)):
        erros.append(f"{nome}: objeto deve usar minusculas, digitos, hifen ou sublinhado")
    if "etapa" in meta:
        etapas = meta["etapa"] if isinstance(meta["etapa"], list) else [meta["etapa"]]
        if not etapas or not all(isinstance(e, str) and ETAPA.fullmatch(e) for e in etapas):
            erros.append(f"{nome}: etapa deve ser '01' a '08' entre aspas, ou lista delas")


def validar(raiz, pasta=PASTA):
    """Lista erros estruturais da memoria; lista vazia significa memoria valida."""
    raiz = Path(raiz)
    if not _relativo_seguro(pasta):
        return [f"pasta da memoria deve ser relativa a raiz, sem ..: {pasta}"]
    base = raiz / pasta
    if not base.is_dir():
        return [f"{pasta}/ ausente"]
    erros = []
    metas = {}
    for caminho in notas(raiz, pasta):
        nome = caminho.relative_to(raiz).as_posix()
        try:
            meta, corpo = ler_nota(caminho)
        except (OSError, UnicodeDecodeError, ValueError) as erro:
            erros.append(f"{nome}: {erro}")
            continue
        faltam = sorted(OBRIGATORIOS - set(meta))
        sobram = sorted(set(meta) - CAMPOS)
        if faltam:
            erros.append(f"{nome}: campos ausentes: {', '.join(faltam)}")
        if sobram:
            erros.append(f"{nome}: campos desconhecidos: {', '.join(sobram)}")
        if meta.get("schema_versao") != 1:
            erros.append(f"{nome}: schema_versao deve ser 1")
        identificador = meta.get("id")
        if not isinstance(identificador, str) or not ID.fullmatch(identificador):
            erros.append(f"{nome}: id deve usar minusculas, digitos e hifen")
        elif identificador != caminho.stem:
            erros.append(f"{nome}: id {identificador} difere do nome do arquivo")
        elif identificador in metas:
            erros.append(f"{nome}: id {identificador} repetido em {metas[identificador][0]}")
        partes = caminho.relative_to(base).parts
        if len(partes) != 2 or partes[0] not in TIPOS:
            erros.append(f"{nome}: a nota deve ficar direto em {', '.join(sorted(TIPOS))}")
        elif meta.get("tipo") != TIPOS[partes[0]]:
            erros.append(f"{nome}: tipo deve ser {TIPOS[partes[0]]} na pasta {partes[0]}")
        status = meta.get("status")
        if status not in STATUS:
            erros.append(f"{nome}: status deve ser ativo ou substituido")
        if status == "ativo" and "substituida_por" in meta:
            erros.append(f"{nome}: nota ativa nao tem substituida_por")
        tags = meta.get("tags")
        if not isinstance(tags, list) or not tags or not all(isinstance(t, str) and t.strip() for t in tags):
            erros.append(f"{nome}: tags deve ser lista nao vazia de textos")
        caminhos = meta.get("caminhos")
        if not isinstance(caminhos, list) or not all(_relativo_seguro(c) for c in caminhos):
            erros.append(f"{nome}: caminhos deve ser lista de caminhos relativos a raiz, sem ..")
        fontes = meta.get("fontes")
        if not isinstance(fontes, list) or not fontes:
            erros.append(f"{nome}: fontes deve ser lista nao vazia")
        else:
            _conferir_fontes(nome, fontes, status, raiz, erros)
        verificado = meta.get("verificado_em")
        if not isinstance(verificado, date) and not (isinstance(verificado, str) and DATA.fullmatch(verificado)):
            erros.append(f"{nome}: verificado_em deve ser data AAAA-MM-DD")
        _conferir_objeto(nome, meta, erros)
        _conferir_links(caminho, corpo, raiz, erros)
        if isinstance(identificador, str) and identificador not in metas:
            metas[identificador] = (nome, meta, caminho)

    for identificador, (nome, meta, _) in metas.items():
        sucessora = meta.get("substituida_por")
        if sucessora is not None and (sucessora == identificador or sucessora not in metas):
            erros.append(f"{nome}: substituida_por aponta para nota inexistente: {sucessora}")

    for avulso in ("README.md", "indice.md", "modelos/nota.md"):
        arquivo = base / avulso
        if not arquivo.is_file():
            erros.append(f"{pasta}/{avulso} ausente")
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as erro:
            erros.append(f"{pasta}/{avulso}: {erro}")
            continue
        indexadas = _conferir_links(arquivo, texto, raiz, erros)
        if avulso == "indice.md":
            for identificador, (nome, meta, caminho) in metas.items():
                if meta.get("status") == "ativo" and caminho.resolve() not in indexadas:
                    erros.append(f"{nome}: nota ativa ausente de {pasta}/indice.md")
    return erros


def resumo_indice(raiz, pasta=PASTA, max_linhas=INDICE_MAX_LINHAS, max_caracteres=INDICE_MAX_CARACTERES):
    """Itens do indice para o inicio de sessao, com volume limitado; None sem indice."""
    arquivo = Path(raiz) / pasta / "indice.md"
    if not arquivo.is_file():
        return None
    itens = [linha.rstrip() for linha in arquivo.read_text(encoding="utf-8").splitlines()
             if linha.lstrip().startswith("- ")]
    if not itens:
        return None
    cabecalho = (f"Memoria do time em {pasta}/ (advisory: orienta, nunca e regra, autorizacao nem prova). "
                 "Abra uma nota so quando o pedido tocar o assunto ou os caminhos dela e confira a fonte "
                 f"antes de aplicar. Nota diferente da main e proposta. Indice (links relativos a {pasta}/):")
    linhas, total = [], len(cabecalho)
    for item in itens[:max_linhas]:
        if total + len(item) + 1 > max_caracteres:
            break
        linhas.append(item)
        total += len(item) + 1
    if len(linhas) < len(itens):
        linhas.append(f"(indice truncado: {len(linhas)} de {len(itens)} itens; leia {pasta}/indice.md)")
    return "\n".join([cabecalho, *linhas])
