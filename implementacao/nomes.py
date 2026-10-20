"""Nomes legíveis das pastas de prova, sessão e recibo de plan."""
from datetime import datetime, timezone
from pathlib import Path
import re
import unicodedata

_PASTA = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,98}[a-z0-9])?\Z")
_SOBRA = {
    "a", "o", "e", "de", "do", "da", "em", "no", "na", "para", "com",
    "um", "uma", "que", "os", "as", "se", "ao", "aos", "por",
}


def slug(texto, limite=60):
    """Trecho de nome: minúsculas, sem acento, hífen entre palavras."""
    if not isinstance(texto, str):
        texto = ""
    normal = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").lower()
    saida = "-".join(re.findall(r"[a-z0-9]+", normal))
    if len(saida) <= limite:
        return saida or "fatia"
    corte = saida[:limite]
    if "-" in corte:
        corte = corte.rsplit("-", 1)[0]
    partes = [parte for parte in corte.split("-") if parte]
    while len(partes) > 1 and partes[-1] in _SOBRA:
        partes.pop()
    return "-".join(partes) or "fatia"


def nome_de_pasta(valor):
    if isinstance(valor, str) and _PASTA.fullmatch(valor):
        return valor
    return None


def _candidatos(base):
    limpo = slug(base, 90)
    yield limpo
    n = 2
    while n < 1000:
        cauda = f"-{n}"
        yield limpo[:100 - len(cauda)].rstrip("-") + cauda
        n += 1


def reservar_diretorio(diretorio, base):
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    for nome in _candidatos(base):
        try:
            (diretorio / nome).mkdir()
        except FileExistsError:
            continue
        return nome
    raise ValueError("Nome esgotado")


def nome_livre(diretorio, base, atual=None):
    """Primeiro nome livre. Se atual já ocupa um candidato, devolve esse."""
    diretorio = Path(diretorio)
    atual_resolvido = Path(atual).resolve() if atual is not None and Path(atual).exists() else None
    for nome in _candidatos(base):
        caminho = diretorio / nome
        if atual_resolvido is not None and caminho.exists() and caminho.resolve() == atual_resolvido:
            return nome
        if not caminho.exists():
            return nome
    raise ValueError("Nome esgotado")


def nome_arquivo(diretorio, base, extensao):
    if not isinstance(extensao, str) or not extensao.startswith(".") or "/" in extensao or "\\" in extensao:
        raise ValueError("Extensao invalida")
    diretorio = Path(diretorio)
    diretorio.mkdir(parents=True, exist_ok=True)
    for nome in _candidatos(base):
        if not (diretorio / f"{nome}{extensao}").exists():
            return nome
    raise ValueError("Nome esgotado")


def _dia(quando):
    momento = quando or datetime.now(timezone.utc)
    return momento.strftime("%Y-%m-%d")


def nome_fatia(trilha, objetivo, quando=None):
    return f"{_dia(quando)}-{slug(trilha, 24)}-{slug(objetivo, 72)}"


def nome_plan(target, selecao, quando=None):
    itens = selecao if isinstance(selecao, (list, tuple)) else [selecao]
    bruto = "-".join(str(item) for item in itens if item is not None and str(item) != "")
    assunto = slug(bruto, 60) if bruto else "bundle"
    return f"{_dia(quando)}-plan-{slug(str(target), 20)}-{assunto}"
