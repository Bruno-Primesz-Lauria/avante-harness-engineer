"""Conversa continua por projeto: log append-only, arvore de resumos e visoes (plano_conversa_continua.md).

Memoria pessoal e local, em .execucoes/conversa/<projeto>/. A visao orienta e nunca e regra,
autorizacao nem prova. Este modulo nao chama modelo: os nos que nao cabem no limite ficam
pendentes para o compactador.
"""
import bisect
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import heapq
import json
import os
from pathlib import Path
import re

LIMITE = 512                      # bytes por linha da arvore
CORTE_ECHO = 20_000               # caracteres de saida de ferramenta (cabeca e cauda)
PEDACO = 20_000                   # texto longo vira varias mensagens deste tamanho
PARALELO = 8                      # folhas prontas: menos de 8 linhas nao construidas antes
TIPOS = ("user", "claude", "tool", "echo", "work", "note")
NAO_RESUMIDA = "(não resumida: use zoom)"

# Cada visao: (arquivo, alto, baixo, medida). A completa mede bytes, a de sessao caracteres,
# porque o hook do Claude Code corta em 10.000 caracteres.
VISOES = {
    "completa": ("view.json", 128_000, 64_000, "bytes"),
    "compactacao": ("view_compactacao.json", 32_000, 16_000, "bytes"),
    "sessao": ("view_sessao.json", 7_400, 5_000, "caracteres"),
}

SEGREDOS = [
    re.compile(r"dapi[0-9a-f]{32}(?:-\d+)?"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/]{16,}=*"),
    re.compile(r"(?i)\b(password|passwd|senha|token|secret|api[_-]?key)(\"?\s*[:=]\s*\"?)[^\s\"',;]{4,}"),
]
SEGREDO = "‹segredo›"


def mascarar(texto):
    for padrao in SEGREDOS:
        if padrao.groups >= 2:
            texto = padrao.sub(lambda m: m.group(1) + m.group(2) + SEGREDO, texto)
        else:
            texto = padrao.sub(SEGREDO, texto)
    return texto


def tamanho(texto):
    return len(texto.encode("utf-8"))


def cortar_bytes(texto, limite):
    """Prefixo de texto com no maximo `limite` bytes, sem partir caractere."""
    return texto.encode("utf-8")[:limite].decode("utf-8", "ignore")


def cortar_meio(texto, limite=CORTE_ECHO):
    """Cabeca e cauda com no maximo `limite` caracteres no total, marcador incluido."""
    if len(texto) <= limite:
        return texto
    metade = (limite - 60) // 2
    omitidos = len(texto) - 2 * metade
    return texto[:metade] + f"\n[… {omitidos} caracteres omitidos …]\n" + texto[-metade:]


def cobertura(l, i):
    """Primeira mensagem e quantidade de mensagens do no (l, i)."""
    return i << l, 1 << l


def rotulo(l, i):
    primeiro, n = cobertura(l, i)
    return f"{primeiro}+{n}"


def devido(total, l, i):
    """Idade do par irmao (l, i), (l, i+1) na escala dele: (T - last) / 2^l, last = ultima mensagem.

    Medir do primeiro id faz linhas antigas mudarem (plano, secao 3.4). A divisao por potencia
    de 2 e exata em float.
    """
    return (total - (((i + 2) << l) - 1)) / (1 << l)


def _agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gravar_json(caminho, dado):
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as arq:
        json.dump(dado, arq, ensure_ascii=False)
        arq.flush()
        os.fsync(arq.fileno())
    os.replace(tmp, caminho)


def _ler_json(caminho, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return padrao


def _acrescentar(caminho, registros, sincronizar=True):
    """Acrescenta e da flush; fsync so no log (no macOS custa milissegundos por chamada)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "a", encoding="utf-8") as arq:
        for registro in registros:
            arq.write(json.dumps(registro, ensure_ascii=False) + "\n")
        arq.flush()
        if sincronizar:
            os.fsync(arq.fileno())


class Visao:
    """Lista de nos [l, i] que cobre 0..T-1 em ordem, com o sawtooth de alto para baixo."""

    def __init__(self, nome, entradas=None, reduzindo=False):
        self.nome = nome
        self.arquivo, self.alto, self.baixo, self.unidade = VISOES[nome]
        self.entradas = [tuple(e) for e in (entradas or [])]
        self.reduzindo = reduzindo
        self._medidas = {}  # so nos construidos: o texto de um no nunca muda
        self._peso = None   # cache do peso total, mantido por acrescentar, construido e reduzir
        self._conjunto = set(self.entradas)
        self._bloqueada = False  # nenhum par fundivel; so muda quando um no e construido

    def medir(self, texto):
        return tamanho(texto) if self.unidade == "bytes" else len(texto)

    def linha(self, arvore, l, i):
        texto = arvore.texto(l, i)
        corpo = NAO_RESUMIDA if texto is None else texto.replace("\n", " ")
        return f"{rotulo(l, i)}|{corpo}"

    def medida(self, arvore, l, i):
        valor = self._medidas.get((l, i))
        if valor is None:
            valor = self.medir(self.linha(arvore, l, i)) + 1
            if arvore.construido(l, i):
                self._medidas[(l, i)] = valor
        return valor

    def peso(self, arvore):
        if self._peso is None:
            self._peso = sum(self.medida(arvore, l, i) for l, i in self.entradas)
        return self._peso

    def acrescentar(self, i, arvore=None):
        self.entradas.append((0, i))
        self._conjunto.add((0, i))
        if self._peso is not None and arvore is not None:
            self._peso += self.medida(arvore, 0, i)
        else:
            self._peso = None

    def construido(self, arvore, l, i):
        """Um no novo pode liberar fusoes; se esta na visao, troca o marcador pelo texto."""
        self._bloqueada = False
        if (l, i) in self._conjunto and self._peso is not None:
            marcador = self.medir(f"{rotulo(l, i)}|{NAO_RESUMIDA}") + 1
            self._peso += self.medida(arvore, l, i) - marcador

    def candidatos(self, construido):
        for k in range(len(self.entradas) - 1):
            (l, i), (l2, i2) = self.entradas[k], self.entradas[k + 1]
            if l == l2 and i % 2 == 0 and i2 == i + 1 and construido(l + 1, i // 2):
                yield k, l, i

    def escolher(self, total, construido):
        """Par mais devido; empate fica com o mais antigo. Referencia simples do lote em `reduzir`."""
        melhor = None
        for k, l, i in self.candidatos(construido):
            valor = devido(total, l, i)
            if melhor is None or valor > melhor[0]:
                melhor = (valor, k)
        return None if melhor is None else melhor[1]

    def fundir(self, k):
        l, i = self.entradas[k]
        self.entradas[k:k + 2] = [(l + 1, i // 2)]
        self._conjunto -= {(l, i), (l, i + 1)}
        self._conjunto.add((l + 1, i // 2))
        self._peso = None

    def reduzir(self, arvore, total):
        """Lote: passou do alto, funde os pares mais devidos ate o baixo (so pais construidos)."""
        peso = self.peso(arvore)
        if peso > self.alto:
            self.reduzindo = True
        mudou = False
        if self.reduzindo and peso > self.baixo and not self._bloqueada:
            peso, mudou = self._lote(arvore, total, peso)
        self._peso = peso
        if peso <= self.baixo:
            self.reduzindo = False
        return mudou

    def _lote(self, arvore, total, peso):
        """Mesma ordem de `escolher`, em O(n log n): heap de pares sobre lista ligada."""
        nos = list(self.entradas)
        anterior = list(range(-1, len(nos) - 1))
        seguinte = list(range(1, len(nos) + 1))
        seguinte[-1] = -1
        heap = []

        def empilhar(k):
            j = seguinte[k] if k >= 0 else -1
            if k < 0 or j < 0:
                return
            (l, i), (l2, i2) = nos[k], nos[j]
            if l == l2 and i % 2 == 0 and i2 == i + 1 and arvore.construido(l + 1, i // 2):
                heapq.heappush(heap, (-devido(total, l, i), i << l, k, nos[k], nos[j]))

        for k in range(len(nos)):
            empilhar(k)
        mudou = False
        while peso > self.baixo:
            if not heap:
                self._bloqueada = True
                break
            _, _, k, a, b = heapq.heappop(heap)
            j = seguinte[k]
            if nos[k] != a or j < 0 or nos[j] != b:
                continue  # par desfeito por uma fusao anterior
            l, i = a
            peso -= self.medida(arvore, *a) + self.medida(arvore, *b)
            nos[k], nos[j] = (l + 1, i // 2), None
            peso += self.medida(arvore, *nos[k])
            seguinte[k] = seguinte[j]
            if seguinte[j] >= 0:
                anterior[seguinte[j]] = k
            empilhar(anterior[k])
            empilhar(k)
            mudou = True
        if mudou:
            self.entradas = [no for no in nos if no is not None]
            self._conjunto = set(self.entradas)
        return peso, mudou

    def dados(self):
        return {"entradas": [list(e) for e in self.entradas], "reduzindo": self.reduzindo}


class Arvore:
    """Nos construidos, lidos dos arquivos tree/*.jsonl de forma incremental."""

    def __init__(self, pasta):
        self.pasta = pasta
        self.nos = {}
        self._offsets = {}

    def atualizar(self):
        """Le so o que foi acrescentado desde a ultima leitura; devolve os nos novos."""
        novos = []
        self.pasta.mkdir(parents=True, exist_ok=True)
        for caminho in sorted(self.pasta.glob("*.jsonl")):
            inicio = self._offsets.get(caminho.name, 0)
            with open(caminho, "rb") as arq:
                arq.seek(inicio)
                bruto = arq.read()
            fim = bruto.rfind(b"\n") + 1
            for linha in bruto[:fim].splitlines():
                if linha.strip():
                    no = json.loads(linha)
                    chave = (no["l"], no["i"])
                    if chave not in self.nos:
                        self.nos[chave] = no["text"]
                        novos.append(chave)
            self._offsets[caminho.name] = inicio + fim
        return novos

    def construido(self, l, i):
        return (l, i) in self.nos

    def texto(self, l, i):
        return self.nos.get((l, i))


class Chat:
    """Estado de um projeto. Toda mutacao acontece dentro de `aberto()`, sob flock."""

    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.arvore = Arvore(self.pasta / "tree")
        self.estado = {}
        self.visoes = {}
        self._folhas = None   # folhas nao construidas, ordenadas (montadas uma vez por processo)
        self._fusoes = None   # pais com as duas metades construidas

    # -- persistencia -------------------------------------------------------------------
    @contextmanager
    def aberto(self):
        self.pasta.mkdir(parents=True, exist_ok=True)
        with open(self.pasta / "trava", "a+") as trava:
            fcntl.flock(trava, fcntl.LOCK_EX)
            try:
                self.carregar()
                yield self
                self.salvar()
            finally:
                fcntl.flock(trava, fcntl.LOCK_UN)

    def carregar(self):
        antes = self.estado.get("T", 0)
        self.estado = _ler_json(self.pasta / "estado.json", {"T": 0, "arquivos": [], "cursores": {}, "ferramentas": {}})
        novos = self.arvore.atualizar()
        if self._folhas is not None:
            for i in range(antes, self.total):
                self._nova_folha(i)
            for no in novos:
                self._no_construido(*no)
        self.visoes = {}
        for nome, (arquivo, *_resto) in VISOES.items():
            dado = _ler_json(self.pasta / arquivo, {})
            self.visoes[nome] = Visao(nome, dado.get("entradas"), dado.get("reduzindo", False))

    def salvar(self):
        _gravar_json(self.pasta / "estado.json", self.estado)
        for visao in self.visoes.values():
            _gravar_json(self.pasta / visao.arquivo, visao.dados())

    @property
    def total(self):
        return self.estado["T"]

    # -- log ------------------------------------------------------------------------------
    def registrar(self, mensagens):
        """Acrescenta mensagens {kind, text, date, sessao}; constroi o que cabe sem modelo."""
        novas = []
        for msg in mensagens:
            assert msg["kind"] in TIPOS, msg["kind"]
            texto = msg["text"]
            pedacos = [texto[k:k + PEDACO] for k in range(0, len(texto), PEDACO)] or [""]
            for pedaco in pedacos:
                i = self.estado["T"]
                novas.append({"i": i, "kind": msg["kind"], "text": pedaco, "size": tamanho(pedaco),
                              "date": msg.get("date") or _agora(), "sessao": msg.get("sessao", ""),
                              **({"linha": msg["linha"]} if msg.get("linha") else {})})
                self.estado["T"] = i + 1
        if not novas:
            return []
        dia = novas[0]["date"][:10]
        nome = f"main/{dia}.jsonl"
        arquivos = self.estado["arquivos"]
        if not arquivos or arquivos[-1][1] != nome:
            arquivos.append([novas[0]["i"], nome])
        _acrescentar(self.pasta / nome, novas)
        for msg in novas:
            for visao in self.visoes.values():
                visao.acrescentar(msg["i"], self.arvore)
            self._nova_folha(msg["i"])
            self._folha_automatica(msg)
        self.reduzir()
        return novas

    def mensagem(self, i):
        """Mensagem i lida do arquivo do dia em que entrou."""
        if not 0 <= i < self.total:
            return None
        arquivo = None
        for primeiro, nome in self.estado["arquivos"]:
            if primeiro <= i:
                arquivo = nome
        with open(self.pasta / arquivo, encoding="utf-8") as arq:
            for linha in arq:
                msg = json.loads(linha)
                if msg["i"] == i:
                    return msg
        return None

    # -- arvore ---------------------------------------------------------------------------
    def _gravar_no(self, l, i, texto):
        if self.arvore.construido(l, i):
            return False
        _acrescentar(self.pasta / "tree" / f"{_agora()[:10]}.jsonl",
                     [{"l": l, "i": i, "text": texto, "size": tamanho(texto)}], sincronizar=False)
        self.arvore.nos[(l, i)] = texto
        self._no_construido(l, i)
        for visao in self.visoes.values():
            visao.construido(self.arvore, l, i)
        return True

    # Filas de nos prontos: montadas uma vez por processo e mantidas a cada no, sem varrer a arvore.
    def _montar_filas(self):
        self._folhas = [i for i in range(self.total) if not self.arvore.construido(0, i)]
        self._fusoes = set()
        for l, i in self.arvore.nos:
            self._ver_pai(l, i)

    def _ver_pai(self, l, i):
        pai = (l + 1, i // 2)
        primeiro, n = cobertura(*pai)
        if (primeiro + n <= self.total and self.arvore.construido(l, i ^ 1)
                and not self.arvore.construido(*pai)):
            self._fusoes.add(pai)

    def _nova_folha(self, i):
        if self._folhas is not None and not self.arvore.construido(0, i):
            bisect.insort(self._folhas, i)

    def _no_construido(self, l, i):
        if self._folhas is None:
            return
        if l == 0:
            k = bisect.bisect_left(self._folhas, i)
            if k < len(self._folhas) and self._folhas[k] == i:
                self._folhas.pop(k)
        self._fusoes.discard((l, i))
        self._ver_pai(l, i)

    def _folha_automatica(self, msg):
        texto = linha_mecanica(msg)
        if texto is not None and tamanho(texto) <= LIMITE:
            self.construir(0, msg["i"], texto)

    def construir(self, l, i, texto):
        """Grava o no e sobe em cascata as fusoes que cabem por juncao, sem modelo."""
        if not self._gravar_no(l, i, texto):
            return
        while True:
            irmao = i ^ 1
            pai_l, pai_i = l + 1, i // 2
            primeiro, n = cobertura(pai_l, pai_i)
            if primeiro + n > self.total or not self.arvore.construido(l, irmao) or self.arvore.construido(pai_l, pai_i):
                return
            juncao = self.arvore.texto(l, pai_i * 2) + "\n" + self.arvore.texto(l, pai_i * 2 + 1)
            if tamanho(juncao) > LIMITE:
                return
            self._gravar_no(pai_l, pai_i, juncao)
            l, i = pai_l, pai_i

    def pendentes(self, em_voo=frozenset()):
        """Folhas e fusoes prontas para o modelo, em ordem.

        Uma folha esta pronta quando ha menos de PARALELO folhas nao construidas antes dela.
        """
        if self._folhas is None:
            self._montar_filas()
        folhas = [(0, i) for i in self._folhas[:PARALELO] if (0, i) not in em_voo]
        fusoes = sorted((no for no in self._fusoes if no not in em_voo), key=lambda no: cobertura(*no))
        return folhas + fusoes

    def reduzir(self):
        for visao in self.visoes.values():
            visao.reduzir(self.arvore, self.total)

    # -- leitura --------------------------------------------------------------------------
    def zoom(self, primeiro, n):
        if n < 1 or n & (n - 1) or primeiro % n:
            raise ValueError("n e potencia de 2 e id e multiplo de n")
        if n == 1:
            return self.mensagem(primeiro)
        l = n.bit_length() - 1
        filhos = []
        for i in (2 * (primeiro >> l), 2 * (primeiro >> l) + 1):
            p, m = cobertura(l - 1, i)
            if p < self.total:
                filhos.append((f"{p}+{m}", self.arvore.texto(l - 1, i)))
        return filhos

    def texto_visao(self, nome, ate=None, so_construidas=False):
        visao = self.visoes[nome]
        linhas = []
        for l, i in visao.entradas:
            primeiro, _ = cobertura(l, i)
            if ate is not None and primeiro > ate:
                break
            if so_construidas and not self.arvore.construido(l, i):
                break
            linhas.append(visao.linha(self.arvore, l, i))
        return "\n".join(linhas)

    def sessao(self, limite=8_000, cabecalho=""):
        """Visao de sessao com no maximo `limite` caracteres, contando o cabecalho."""
        visao = self.visoes["sessao"]
        linhas = [visao.linha(self.arvore, l, i) for l, i in visao.entradas]
        resto = limite - len(cabecalho) - len("<chat>\n\n</chat>") - 1 - 80
        total = sum(len(x) + 1 for x in linhas)
        omitidas = 0
        while omitidas < len(linhas) and total > resto:
            total -= len(linhas[omitidas]) + 1
            omitidas += 1
        linhas = linhas[omitidas:]
        if omitidas:
            primeiro, _ = cobertura(*visao.entradas[omitidas])
            linhas.insert(0, f"0+{primeiro}|(… {primeiro} mensagens anteriores: abra visao.txt)")
        corpo = "\n".join(linhas)
        return f"{cabecalho}<chat>\n{corpo}\n</chat>"

    def validar(self):
        erros = []
        for nome, visao in self.visoes.items():
            esperado = 0
            for l, i in visao.entradas:
                primeiro, n = cobertura(l, i)
                if primeiro != esperado:
                    erros.append(f"visao {nome}: buraco ou sobreposicao em {rotulo(l, i)}")
                    break
                if l and not self.arvore.construido(l, i):
                    erros.append(f"visao {nome}: no {rotulo(l, i)} sem construir")
                esperado = primeiro + n
            if esperado != self.total and not erros:
                erros.append(f"visao {nome}: cobre {esperado} de {self.total} mensagens")
        for (l, i) in self.arvore.nos:
            primeiro, n = cobertura(l, i)
            if primeiro + n > self.total:
                erros.append(f"no {rotulo(l, i)} alem do log")
        return erros


def linha_mecanica(msg):
    """Linha da folha sem modelo: texto curto fica literal; tool e echo viram metadados (DC-2 b)."""
    kind, texto = msg["kind"], msg["text"]
    if kind in ("tool", "echo"):
        # O conteudo fica so no log, aberto por zoom; a arvore e o modelo veem os metadados.
        return cortar_bytes(f"{kind}: {msg.get('linha') or ''}".rstrip(), LIMITE)
    linha = f"{kind}: {texto}"
    return linha if tamanho(linha) <= LIMITE else None
