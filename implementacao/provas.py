"""Prova minima: estado antes da chamada, resultado observado e fecho atual."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from formas import dentro, exigir, nao_verificados_sandbox, relativo, validar, validar_dados
import yaml

IGNORADOS = {".git", ".venv", ".execucoes", ".fixtures", "__pycache__", ".pytest_cache"}
ROTEAMENTO = Path(__file__).resolve().parents[1] / "agentes/roteamento.yaml"
PAPEIS = {"map", "config", "implement", "test", "refute", "docs", "dab"}
TIPOS_COMANDO = {"teste", "ambiente", "validacao_dados", "paridade"}
TIPOS_TESTE = {"teste", "validacao_dados", "paridade"}
TIPOS_INSPECAO = {"inspecao_documental", "analise_codigo"}
# Etapa de test no roteamento -> tipos de critério que a exigem; None: sempre (test decide se prepara).
CRITERIOS_TESTE = {
    "preparar_teste_se_necessario": None,
    "teste": TIPOS_TESTE,
    "teste_reproduz": TIPOS_TESTE,
    "teste_revalidar": TIPOS_TESTE,
    "teste_inicial": {"teste", "validacao_dados"},
    "teste_paridade": {"paridade"},
}
# A implementacao/configuracao que interpreta a prova tambem faz parte dela.
CONTROLE = ["implementacao", "adaptadores", "configuracao", "formas/catalogo.yaml", "agentes/roteamento.yaml"]
EXTENSOES = {
    "config": {".yaml", ".yml"},
    "implement": {".ipynb", ".py", ".sql"},
    "docs": {".md", ".rst", ".txt"},
}
# Papéis de escrita cuja superfície o núcleo confere por janela de chamada (C5).
ESCRITORES = {"config", "implement", "docs"}


def agora():
    return datetime.now(timezone.utc).isoformat()


def hash_bytes(conteudo):
    return sha256(conteudo).hexdigest()


def hash_arquivo(caminho):
    return hash_bytes(Path(caminho).read_bytes())


def ler(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gravar(caminho, dados, substituir=False):
    """Artefato novo e exclusivo; estado substituido sob lock pelo chamador."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(dados, ensure_ascii=False, indent=2) + "\n"
    if not substituir:
        with caminho.open("x", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        return
    temporario = caminho.with_name(uuid4().hex + ".tmp")
    try:
        with temporario.open("x", encoding="utf-8") as arquivo:
            arquivo.write(texto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        temporario.unlink(missing_ok=True)


@contextmanager
def trava(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    lock = pasta / ".lock"
    try:
        arquivo = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise ValueError("Registro em uso por outra execucao. Confira se ela terminou e repita") from None
    try:
        with arquivo:
            arquivo.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def retrato(raiz, caminhos):
    """Captura arquivos declarados, inclusive novos, removidos e nao rastreados."""
    resultado = {}

    def visitar(caminho, ref):
        exigir(not caminho.is_symlink() and not caminho.is_junction(), "Link nao aceito na prova")
        if caminho.is_dir():
            resultado[ref] = "diretorio"
            for filho in sorted(caminho.iterdir()):
                if filho.name not in IGNORADOS:
                    visitar(filho, ref + "/" + filho.name)
        else:
            resultado[ref] = hash_arquivo(caminho) if caminho.exists() else None

    for ref in sorted(set(caminhos)):
        exigir(not set(Path(relativo(ref)).parts) & IGNORADOS, "Artefato interno fora da superficie")
        visitar(dentro(raiz, ref), ref)
    return resultado


def limpar_log(texto):
    texto = re.sub(r"(?i)(bearer\s+|(?:token|password|secret)\s*[=:]\s*)[^\s,;]+", r"\1[omitido]", texto)
    return re.sub(r"\bdapi[a-zA-Z0-9]{20,}\b", "[omitido]", texto)


def alterados(antes, depois):
    """Arquivos com conteúdo diferente entre dois retratos, inclusive criados e removidos."""
    return sorted(r for r in set(antes) | set(depois)
                  if antes.get(r) != depois.get(r) and "diretorio" not in (antes.get(r), depois.get(r)))


def operacao_bundle(comando):
    """Operação, target, perfil e seleção literais de um `databricks bundle <operação>`; None se não for."""
    achado = re.search(r"\bbundle\s+(validate|plan|deploy|run)\b", comando)
    if achado is None:
        return None
    derivado = dict(operacao=achado.group(1),
                    selecao=sorted(v.strip("'\"") for v in re.findall(r"--select[ =](\S+)", comando)))
    for campo, flags in (("target", "-t|--target"), ("perfil", "-p|--profile")):
        valor = re.search(rf"(?:^|\s)(?:{flags})[ =](\S+)", comando)
        if valor:
            derivado[campo] = valor.group(1).strip("'\"")
    return derivado


def compor(declarado, observado):
    """O que o núcleo observa não é declarado à mão; se vier declarado, precisa coincidir."""
    for campo, valor in observado.items():
        exigir(declarado.get(campo, valor) == valor, f"Campo {campo} diverge do observado")
    return {**declarado, **observado}


def anotar(lista, itens):
    lista.extend(i for i in dict.fromkeys(itens) if i not in lista)


def concluidas(plano, registros):
    """Chamadas previstas cumpridas na ordem observada; repetir uma etapa reabre as seguintes."""
    etapas = list(dict.fromkeys(c["etapa"] for c in plano))
    posicao = {c["id"]: etapas.index(c["etapa"]) for c in plano}
    feitas = set()
    for registro in registros:
        if registro["status"] != "concluida" or registro["id"] not in posicao:
            continue
        if registro["id"] in feitas:
            feitas = {i for i in feitas if posicao[i] <= posicao[registro["id"]]}
        feitas.add(registro["id"])
    return feitas


class Provas:
    def __init__(self, raiz, registros, sessao, runtime=None):
        self.raiz = Path(raiz).resolve(strict=True)
        self.registros = Path(registros).resolve()
        exigir(self.registros.is_relative_to(self.raiz) and self.registros != self.raiz,
               "Registros devem ficar dentro do harness, separados do produto")
        exigir(isinstance(sessao, str) and 0 < len(sessao) <= 300, "Sessao ausente")
        exigir(runtime is None or runtime in {"claude_code", "cursor", "codex", "opencode"},
               "Runtime invalido")
        self.sessao = hash_bytes(sessao.encode())
        self.indice = self.registros / "sessoes" / self.sessao
        self.runtime = runtime
        self.politica_path = self.raiz / "configuracao/politica.json"

    def pasta(self):
        ponteiro = self.indice / "ativa.json"
        if not ponteiro.exists():
            return None
        return dentro(self.registros, ler(ponteiro)["fatia"])

    def cwd(self, ref):
        return self.raiz if ref == "." else dentro(self.raiz, ref).resolve()

    def estado(self, pasta):
        estado = ler(pasta / "estado.json")
        exigir(estado["versao"] == 1 and estado["sessao"] == self.sessao, "Estado de outra sessao")
        exigir(hash_arquivo(pasta / "contrato.yaml") == estado["contrato_sha256"], "O contrato mudou. Abra uma nova fatia")
        return estado

    def atualizar(self, pasta, estado):
        anterior = ler(pasta / "estado.json")
        exigir(anterior["revisao"] == estado["revisao"], "Estado mudou; nao sobrescrever")
        estado["revisao"] += 1
        gravar(pasta / "estado.json", estado, substituir=True)

    def evento(self, pasta, estado, tipo, dados, manifesto, tentativa, destino=None,
               produtor=None, schema_versao=None):
        produtores = {"contrato": "coordenador", "brief": "coordenador",
                      "teste": "executor_teste", "guarda": "hook", "inspecao": "coordenador",
                      "ataque": "refute", "triagem": "coordenador", "chamada": "adaptador",
                      "diagnostico": "coordenador", "sandbox": "dab", "paridade": "test"}
        evento = dict(schema_versao=schema_versao or estado.get("schema_versao", "3.1"),
                      tipo=tipo, exemplo=False,
                      execucao_id=estado["execucao_id"], fatia_id="principal",
                      tentativa=tentativa, evento_id=uuid4().hex,
                      produtor=produtor or produtores[tipo],
                      registrado_em=agora(), manifesto_ref=manifesto, dados=dados)
        validar(evento, pasta, estado["execucao_id"], "principal")
        ref = destino or f"tentativas/{tentativa:03d}/eventos/{evento['evento_id']}.yaml"
        gravar(dentro(pasta, ref), evento)
        return ref

    def papeis_superficie(self, contrato, papeis):
        """Atribui cada item da superfície aos papéis pela extensão; diretório vale pelos seus arquivos."""
        atribuidos, sem_papel = set(), []
        for ref in contrato["superficie"]:
            caminho = dentro(self.raiz, ref)
            arquivos = [f for f in caminho.rglob("*") if f.is_file() and
                        not set(f.relative_to(self.raiz).parts) & IGNORADOS] if caminho.is_dir() else [caminho]
            do_item = {p for p in papeis for f in arquivos if f.suffix.casefold() in EXTENSOES[p]}
            if not do_item:
                sem_papel.append(ref)
            atribuidos |= do_item
        return atribuidos, sem_papel

    def plano_chamadas(self, contrato, autorizacoes=None, exigir_atribuicao=False):
        """Deriva as chamadas obrigatórias na ordem do roteamento.

        Com a trilha ativada, item da superfície sem papel de escrita recusa o início em vez de sumir do plano.
        """
        rota = yaml.safe_load(ROTEAMENTO.read_text(encoding="utf-8"))
        tipos = {c["tipo"] for c in contrato["aceite"]}
        autorizacoes = autorizacoes or {}
        saida = []

        def adicionar(etapa, papel, criterio_id=None):
            ocorrencia = sum(c["etapa"] == etapa and c["papel"] == papel for c in saida) + 1
            saida.append({"id": f"{etapa}:{papel}:{ocorrencia}", "etapa": etapa,
                          "papel": papel, "criterio_id": criterio_id, "obrigatoria": True})

        for passo in rota["trilhas"][contrato["trilha"]]["fluxo"]:
            etapa, papel = passo["id"], passo.get("responsavel")
            escritores = [m["responsavel"] for m in passo.get("membros", [])] or (
                [papel] if papel == "docs" else [])
            if escritores:
                atribuidos, sem_papel = self.papeis_superficie(contrato, escritores)
                if exigir_atribuicao:
                    exigir(not sem_papel, "Superficie sem papel de escrita roteado: " + ", ".join(sem_papel) +
                           ". Declare arquivos atribuiveis ao papel ou feche com DECIDE")
                    sem_escritor = passo.get("se_nenhum_membro_aplicavel", passo.get("se_nao_aplicavel"))
                    exigir(atribuidos or sem_escritor != "DECIDE",
                           "Nenhum papel de escrita se aplica a superficie. Feche com DECIDE")
                for escritor in escritores:
                    if escritor in atribuidos:
                        adicionar(etapa, escritor)
            elif papel == "test":
                exigir(etapa in CRITERIOS_TESTE, f"Etapa de test sem regra no nucleo: {etapa}")
                if CRITERIOS_TESTE[etapa] is None or tipos & CRITERIOS_TESTE[etapa]:
                    adicionar(etapa, papel)
            elif papel == "dab":
                for criterio in contrato["aceite"]:
                    if criterio["tipo"] == "ambiente" and criterio["id"] in autorizacoes:
                        adicionar(etapa, papel, criterio["id"])
            elif papel == "refute":
                adicionar(etapa, papel)
        return saida

    def autorizacao_ref(self, criterio):
        ref = criterio.get("autorizacao_ref")
        if not ref:
            return None
        ref = relativo(ref)
        partes = Path(ref).parts
        ignorados = {nome.casefold() for nome in IGNORADOS}
        exigir(not any(parte.casefold() in ignorados for parte in partes),
               "Referencia de autorizacao em area ignorada")
        caminho = dentro(self.raiz, ref)
        atual = self.raiz
        for parte in partes:
            atual = atual / parte
            exigir(not atual.is_symlink() and not atual.is_junction(),
                   "Link nao aceito na referencia de autorizacao")
        if not caminho.is_file():
            return None
        try:
            caminho.read_bytes()
        except OSError:
            return None
        return ref

    def politica(self):
        if not self.politica_path.is_file():
            return {"agentes_obrigatorios": {"claude_code": [], "cursor": []}}
        dados = ler(self.politica_path)
        ativacao = dados.get("agentes_obrigatorios", {"claude_code": [], "cursor": []})
        exigir(isinstance(ativacao, dict) and set(ativacao) <= {"claude_code", "cursor"},
               "agentes_obrigatorios deve ser configurado por runtime")
        for runtime, trilhas in ativacao.items():
            exigir(isinstance(trilhas, list) and all(t in {"novo", "manutencao", "correcao", "docs",
                       "destilar", "review", "validacao", "entendimento"} for t in trilhas),
                   f"agentes_obrigatorios.{runtime} invalido")
        return {"agentes_obrigatorios": ativacao}

    def ativada(self, trilha, runtime):
        """Trilha com agentes obrigatórios no runtime; fora da chave vale o fluxo atual."""
        ativacao = self.politica()["agentes_obrigatorios"]
        if not any(trilha in trilhas for trilhas in ativacao.values()):
            return False
        exigir(runtime is not None, "Runtime explicito obrigatorio para conferir agentes_obrigatorios")
        return trilha in ativacao.get(runtime, [])

    def iniciar(self, contrato):
        schema_versao = "3.2" if any(
            c.get("tipo") in TIPOS_INSPECAO or
            (c.get("tipo") == "ambiente" and "autorizacao_ref" in c)
            for c in contrato.get("aceite", [])) else "3.1"
        validar_dados("contrato", contrato, schema_versao)
        exigir(contrato["artefatos_raiz"] == ".execucoes/provas", "Use .execucoes/provas para artefatos")
        ativa = self.ativada(contrato["trilha"], self.runtime)
        comandos = set()
        cobertura = []
        autorizacoes = {}
        for criterio in contrato["aceite"]:
            v = criterio["verificacao"]
            if criterio["tipo"] in TIPOS_COMANDO:
                cwd = self.cwd(v["cwd"])
                exigir(cwd.is_dir(), "Cwd da verificacao ausente")
                chave = (v["comando"], str(cwd.resolve()))
                exigir(v["comando"].strip() and chave not in comandos,
                       "Comando vazio ou verificacao duplicada")
                comandos.add(chave)
            cobertura.extend(v["caminhos"])
            if criterio["tipo"] == "ambiente" and criterio.get("autorizacao_ref"):
                ref = relativo(criterio["autorizacao_ref"])
                # rejeita áreas internas até quando o arquivo ainda não existe.
                ignorados = {nome.casefold() for nome in IGNORADOS}
                exigir(not any(parte.casefold() in ignorados for parte in Path(ref).parts),
                       "Referencia de autorizacao em area ignorada")
                validada = self.autorizacao_ref(criterio)
                if validada:
                    autorizacoes[criterio["id"]] = validada
                if validada or not dentro(self.raiz, ref).exists():
                    cobertura.append(ref)
        for ref in contrato["superficie"]:
            exigir(any(ref == c or ref.startswith(c + "/") for c in cobertura), "Superficie sem verificacao")
        baseline = retrato(self.raiz, contrato["superficie"] + cobertura)
        chamadas_previstas = self.plano_chamadas(contrato, autorizacoes, exigir_atribuicao=ativa)
        with trava(self.indice):
            anterior = self.pasta()
            if anterior:
                exigir(self.estado(anterior)["fecho"] is not None, "Feche a fatia ativa antes de iniciar outra")
            execucao = uuid4().hex
            pasta = self.registros / "provas" / execucao / "principal"
            estado = dict(versao=1, schema_versao=schema_versao, sessao=self.sessao, execucao_id=execucao,
                          runtime=self.runtime, trilha=contrato["trilha"],
                          chamadas_previstas=chamadas_previstas, chamadas_observadas=[],
                          autorizacoes=autorizacoes, manifestos_autorizacao={},
                          revisao=0, tentativa=0, pendente=None, chamadas=[], provas={}, inspecoes={},
                          revisoes=[], triagens=[], fecho=None, contrato_sha256="")
            if ativa and ESCRITORES & {c["papel"] for c in chamadas_previstas}:
                estado["vigilancia_superficie"] = dict(
                    retrato=retrato(self.raiz, self.vigiados(contrato)), abertas={}, pendencias=[])
            gravar(pasta / "baseline.json", dict(versao=1, registrado_em=agora(), arquivos=baseline))
            for criterio_id, ref in autorizacoes.items():
                manifesto_ref = f"tentativas/001/autorizacoes/{criterio_id}.json"
                manifesto = dict(versao=1, caminhos=[ref], arquivos=retrato(self.raiz, [ref]),
                                 controle=retrato(self.raiz, CONTROLE))
                gravar(dentro(pasta, manifesto_ref), manifesto)
                estado["manifestos_autorizacao"][criterio_id] = manifesto_ref
            self.evento(pasta, estado, "contrato", contrato, "baseline.json", 1, "contrato.yaml")
            estado["contrato_sha256"] = hash_arquivo(pasta / "contrato.yaml")
            gravar(pasta / "estado.json", estado)
            gravar(self.indice / "ativa.json", {"fatia": pasta.relative_to(self.registros).as_posix()}, substituir=True)
            return {"execucao_id": execucao, "fatia": str(pasta), "revisao": 0}

    def vigiados(self, contrato):
        return sorted(set(contrato["superficie"]) |
                      {p for c in contrato["aceite"] for p in c["verificacao"]["caminhos"]})

    def abrir_chamada(self, chamada_id, papel):
        """Início observado de um subagente: o que mudou desde o último retrato não foi feito por papel (C5)."""
        pasta = self.pasta()
        if pasta is None:
            return False
        with trava(pasta):
            estado = self.estado(pasta)
            vigia = estado.get("vigilancia_superficie")
            if vigia is None or chamada_id in vigia["abertas"]:
                return False
            contrato = ler(pasta / "contrato.yaml")["dados"]
            atual = retrato(self.raiz, self.vigiados(contrato))
            if (papel in {"config", "implement"} and self.exige_diagnostico(estado.get("trilha", contrato["trilha"]))
                    and not self.diagnosticos_validos(pasta, estado)):
                anotar(vigia["pendencias"], [f"escrita_sem_diagnostico:{papel}:{chamada_id}"])
            if vigia["abertas"]:
                for janela in vigia["abertas"].values():
                    janela["sobreposta"] = True
            else:
                anotar(vigia["pendencias"], ["edicao_fora_do_papel:" + r for r in alterados(vigia["retrato"], atual)])
            vigia["abertas"][chamada_id] = dict(papel=papel, retrato=atual, sobreposta=bool(vigia["abertas"]))
            vigia["retrato"] = atual
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return True

    def encerrar_chamada(self, chamada_id):
        """Fim de subagente sem registro de chamada (falha ou papel recusado): a janela ainda é conferida."""
        pasta = self.pasta()
        if pasta is None:
            return False
        with trava(pasta):
            estado = self.estado(pasta)
            vigia = estado.get("vigilancia_superficie")
            if vigia is None or chamada_id not in vigia["abertas"]:
                return False
            self.fechar_janela(vigia, ler(pasta / "contrato.yaml")["dados"], chamada_id, None)
            self.atualizar(pasta, estado)
            return True

    def fechar_janela(self, vigia, contrato, chamada_id, papel):
        atual = retrato(self.raiz, self.vigiados(contrato))
        janela = vigia["abertas"].pop(chamada_id, None)
        if janela is None:
            # Sem início observado, o que mudou desde o último retrato não tem autoria atribuível.
            if papel in ESCRITORES and alterados(vigia["retrato"], atual):
                anotar(vigia["pendencias"], ["superficie_inconclusiva:" + chamada_id])
        else:
            mudou = alterados(janela["retrato"], atual)
            if janela["sobreposta"] and mudou:
                anotar(vigia["pendencias"], ["superficie_inconclusiva:" + chamada_id])
            elif janela["papel"] in ESCRITORES:
                dentro_superficie = lambda r: any(r == s or r.startswith(s + "/") for s in contrato["superficie"])
                anotar(vigia["pendencias"], [
                    f"superficie_violada:{janela['papel']}:{r}" for r in mudou
                    if not dentro_superficie(r) or Path(r).suffix.casefold() not in EXTENSOES[janela["papel"]]])
        if not vigia["abertas"]:
            vigia["retrato"] = atual

    def pendencias_superficie(self, pasta, estado):
        vigia = estado.get("vigilancia_superficie")
        if vigia is None:
            return []
        faltam = list(vigia["pendencias"])
        if vigia["abertas"]:
            anotar(faltam, ["chamada_aberta:" + c for c in vigia["abertas"]])
        else:
            atual = retrato(self.raiz, self.vigiados(ler(pasta / "contrato.yaml")["dados"]))
            anotar(faltam, ["edicao_fora_do_papel:" + r for r in alterados(vigia["retrato"], atual)])
        return faltam

    def registrar_chamada(self, chamada_id, papel, runtime, ids_observados, inicio, fim, status):
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        exigir(papel in PAPEIS and papel != "map", "Papel nao roteado como obrigatorio")
        exigir(runtime in {"claude_code", "cursor"}, "Runtime invalido")
        with trava(pasta):
            estado = self.estado(pasta)
            exigir(estado["runtime"] in (None, runtime), "Chamada observada em outro runtime")
            exigir(not any(c["chamada_id"] == chamada_id for c in estado["chamadas_observadas"]),
                   "Chamada ja registrada")
            plano = estado["chamadas_previstas"]
            feitas = concluidas(plano, estado["chamadas_observadas"])
            do_papel = [c for c in plano if c["papel"] == papel]
            exigir(do_papel, "Chamada de papel nao prevista no plano da fatia")
            esperada = next((c for c in do_papel if c["id"] not in feitas), None)
            if esperada is None:
                # Retorno (achado, reprovação): repetir o papel reabre as etapas seguintes do plano.
                esperada = do_papel[-1]
            else:
                indice = plano.index(esperada)
                anteriores = [c["id"] for c in plano[:indice] if c["etapa"] != esperada["etapa"]]
                exigir(all(i in feitas for i in anteriores), "Chamada fora da ordem prevista")
            dados ={"chamada_id": chamada_id, "papel": papel, "runtime": runtime,
                     "ids_observados": ids_observados, "inicio": inicio, "fim": fim, "status": status}
            manifesto_ref = "baseline.json"
            if papel == "dab":
                criterio_id = esperada["criterio_id"]
                manifesto_ref = estado.get("manifestos_autorizacao", {}).get(criterio_id)
                exigir(manifesto_ref is not None and self.manifesto_atual(pasta, manifesto_ref),
                       "Registro de autorizacao ausente ou obsoleto")
            ref = self.evento(pasta, estado, "chamada", dados, manifesto_ref, max(1, estado["tentativa"]),
                              produtor="adaptador", schema_versao="3.2")
            estado["runtime"] = runtime
            if estado.get("vigilancia_superficie") is not None:
                self.fechar_janela(estado["vigilancia_superficie"], ler(pasta / "contrato.yaml")["dados"],
                                   chamada_id, papel)
            estado["chamadas_observadas"].append({"id": esperada["id"], "etapa": esperada["etapa"],
                                                  "papel": papel, "status": status, "chamada_id": chamada_id,
                                                  "ref": ref,
                                                  "sha256": hash_arquivo(dentro(pasta, ref))})
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"etapa": esperada["etapa"], "papel": papel, "evidencia_ref": ref}

    def inspecionar(self, criterio_id, checagens, produtor=None):
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            criterio = next((c for c in contrato["aceite"] if c["id"] == criterio_id), None)
            exigir(criterio is not None and criterio["tipo"] in TIPOS_INSPECAO, "Criterio de inspecao ausente")
            v = criterio["verificacao"]
            produtor_contratado = v["produtor"]
            produtor = produtor or produtor_contratado
            exigir(produtor == produtor_contratado, "Produtor diferente do criterio contratado")
            exigidos = {c["id"] for c in v["checagens"]}
            exigir(isinstance(checagens, list) and {c.get("id") for c in checagens} == exigidos,
                   "Checagens nao correspondem ao criterio")
            manifesto_ref = f"tentativas/{max(1, estado['tentativa'] + 1):03d}/inspecoes/{uuid4().hex}.json"
            retrato_inspecionado = dict(versao=1, caminhos=v["caminhos"],
                                       arquivos=retrato(self.raiz, v["caminhos"]),
                                       controle=retrato(self.raiz, CONTROLE))
            gravar(dentro(pasta, manifesto_ref), retrato_inspecionado)
            resultado = "pass" if all(c["resultado"] == "pass" for c in checagens) else (
                "fail" if any(c["resultado"] == "fail" for c in checagens) else "inconclusivo")
            dados = dict(criterio_id=criterio_id, caminhos=v["caminhos"],
                         manifesto_sha256=hash_arquivo(dentro(pasta, manifesto_ref)),
                         checagens=checagens, resultado=resultado,
                         validade="valida" if resultado == "pass" else "nao_verificada")
            ref = self.evento(pasta, estado, "inspecao", dados, manifesto_ref,
                              max(1, estado["tentativa"] + 1), produtor=produtor, schema_versao="3.2")
            estado["inspecoes"][criterio_id] = {"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))}
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"resultado": resultado, "evidencia_ref": ref}

    def revisar(self, dados):
        """Registra a revisão do refute sobre o estado atual; edição posterior a torna obsoleta."""
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        validar_dados("ataque", dados, "3.2")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            ids = {c["id"] for c in contrato["aceite"]}
            exigir(all(c["criterio_id"] in ids for c in dados["cobertura"]),
                   "Cobertura da revisao fora dos criterios do contrato")
            # O estado revisado é retratado pelo núcleo, não declarado por quem revisa.
            caminhos = sorted(set(contrato["superficie"]) |
                              {p for c in contrato["aceite"] for p in c["verificacao"]["caminhos"]})
            tentativa = max(1, estado["tentativa"])
            manifesto_ref = f"tentativas/{tentativa:03d}/revisoes/{uuid4().hex}.json"
            gravar(dentro(pasta, manifesto_ref), dict(versao=1, caminhos=caminhos,
                   arquivos=retrato(self.raiz, caminhos), controle=retrato(self.raiz, CONTROLE)))
            ref = self.evento(pasta, estado, "ataque", dados, manifesto_ref, tentativa,
                              produtor="refute", schema_versao="3.2")
            estado.setdefault("revisoes", []).append({"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))})
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"veredito": dados["veredito"], "evidencia_ref": ref}

    def triar(self, dados):
        """Registra a decisão do coordenador sobre um achado de uma revisão desta fatia."""
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        validar_dados("triagem", dados, "3.2")
        with trava(pasta):
            estado = self.estado(pasta)
            registro = next((r for r in estado.get("revisoes", []) if r["ref"] == dados["revisao_ref"]), None)
            ataque = self.registrado(pasta, estado, registro) if registro else None
            exigir(ataque is not None, "Revisao nao registrada nesta fatia")
            exigir(any(a["id"] == dados["achado_id"] for a in ataque["dados"]["achados"]),
                   "Achado ausente da revisao")
            ref = self.evento(pasta, estado, "triagem", dados, ataque["manifesto_ref"],
                              max(1, estado["tentativa"]), produtor="coordenador", schema_versao="3.2")
            estado.setdefault("triagens", []).append({"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))})
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"decisao": dados["decisao"], "evidencia_ref": ref}

    def exige_diagnostico(self, trilha):
        """A trilha roteia o diagnóstico como capacidade obrigatória do coordenador."""
        rota = yaml.safe_load(ROTEAMENTO.read_text(encoding="utf-8"))
        return any(passo.get("capacidade") == "diagnostico" and passo.get("capacidade_obrigatoria")
                   for passo in rota["trilhas"][trilha]["fluxo"])

    def diagnosticos_validos(self, pasta, estado):
        eventos = (self.registrado(pasta, estado, r) for r in estado.get("diagnosticos", []))
        return [e for e in eventos if e is not None and e["tipo"] == "diagnostico"]

    def diagnosticar(self, dados, produtor=None):
        """Registra o diagnóstico da correção; sem ele a escrita de config ou implement não é aceita (C6)."""
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        validar_dados("diagnostico", dados, "3.2")
        produtor = produtor or "coordenador"
        exigir(produtor in {"coordenador", "map"}, "Produtor de diagnostico invalido")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            criterio = next((c for c in contrato["aceite"] if c["id"] == dados["criterio_reproducao"]), None)
            exigir(criterio is not None and criterio["tipo"] in TIPOS_TESTE,
                   "Criterio de reproducao ausente do contrato")
            ref = self.evento(pasta, estado, "diagnostico", dados, "baseline.json",
                              max(1, estado["tentativa"]), produtor=produtor, schema_versao="3.2")
            estado.setdefault("diagnosticos", []).append({"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))})
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"base": dados["base"], "evidencia_ref": ref}

    def teste_do_criterio(self, pasta, estado, contrato, criterio_id, tipo):
        """Critério do tipo e o registro teste atual do comando dele, ao que sandbox e paridade se ligam."""
        criterio = next((c for c in contrato["aceite"] if c["id"] == criterio_id), None)
        exigir(criterio is not None and criterio["tipo"] == tipo, f"Criterio {tipo} ausente do contrato")
        registro = estado["provas"].get(criterio_id)
        teste = self.registrado(pasta, estado, registro) if registro else None
        exigir(teste is not None and teste["tipo"] == "teste",
               "Rode o comando do criterio e confira o resultado antes de registrar")
        return criterio, registro, teste

    def plan_compativel(self, dados):
        """Recibo de plan legível, do mesmo target, perfil e seleção, com os arquivos do plan inalterados."""
        if dados.get("plan_ref") is None:
            return None
        try:
            recibo = ler(dentro(self.registros, dados["plan_ref"]))
            return (recibo["target"] == dados["target"] and recibo["selecao"] == sorted(dados["selecao"]) and
                    recibo["perfil_sha256"] == hash_bytes(dados["perfil"].encode()) and
                    all(hash_arquivo(i["caminho"]) == i["sha256"] for i in recibo["estado"]))
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def registrar_sandbox(self, criterio_id, declarado):
        """Registra o ambiente de um critério `ambiente`, ligado ao teste do comando por ref e hash (C6).

        O agente declara só o que observou (plan_ref, identidade, destinos, coordenação). Operação,
        target, perfil e seleção vêm do comando contratado; cwd, resultado e teste_ref, do teste observado.
        """
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        exigir(isinstance(declarado, dict), "Registro de ambiente invalido")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            criterio, registro, teste = self.teste_do_criterio(pasta, estado, contrato, criterio_id, "ambiente")
            exigir(criterio.get("autorizacao_ref"), "Criterio ambiente sem autorizacao_ref")
            d = teste["dados"]
            operacao = operacao_bundle(d["comando"])
            exigir(operacao is not None, "Comando do criterio nao e uma operacao de bundle conhecida")
            observado = dict(operacao, cwd=d["cwd"], resultado=d["resultado"],
                             autorizacao_ref=criterio["autorizacao_ref"], teste_ref=registro["ref"])
            politica = ler(self.politica_path) if self.politica_path.is_file() else {}
            if politica.get("bundle_nome"):
                observado["bundle"] = politica["bundle_nome"]
            dados = compor(dict(declarado, plan_ref=declarado.get("plan_ref")), observado)
            dados = compor(dados, dict(plan_estado_compativel=self.plan_compativel(dados)))
            ref = self.evento(pasta, estado, "sandbox", dados, teste["manifesto_ref"],
                              max(1, estado["tentativa"]), produtor="dab", schema_versao="3.2")
            estado.setdefault("sandbox", {})[criterio_id] = dict(
                ref=ref, sha256=hash_arquivo(dentro(pasta, ref)),
                teste_ref=registro["ref"], teste_sha256=registro["sha256"])
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"resultado": dados["resultado"], "nao_verificado": nao_verificados_sandbox(dados),
                    "evidencia_ref": ref}

    def registrar_paridade(self, criterio_id, declarado):
        """Registra a paridade de um critério `paridade`, ligada ao teste do comando por ref e hash (C6).

        O resultado é do núcleo: divergência pendente reprova mesmo com exit 0.
        """
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        exigir(isinstance(declarado, dict), "Registro de paridade invalido")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            _, registro, teste = self.teste_do_criterio(pasta, estado, contrato, criterio_id, "paridade")
            divergencias = declarado.get("divergencias")
            pendente = isinstance(divergencias, list) and any(
                isinstance(i, dict) and i.get("estado") == "pendente" for i in divergencias)
            resultado = teste["dados"]["resultado"]
            if resultado == "pass" and pendente:
                resultado = "fail"
            dados = compor(declarado, dict(criterio_id=criterio_id, resultado=resultado,
                                           teste_ref=registro["ref"]))
            ref = self.evento(pasta, estado, "paridade", dados, teste["manifesto_ref"],
                              max(1, estado["tentativa"]), produtor="test", schema_versao="3.2")
            estado.setdefault("paridades", {})[criterio_id] = dict(
                ref=ref, sha256=hash_arquivo(dentro(pasta, ref)),
                teste_ref=registro["ref"], teste_sha256=registro["sha256"])
            estado["fecho"] = None
            self.atualizar(pasta, estado)
            return {"resultado": resultado, "evidencia_ref": ref}

    def antes(self, chamada, comando, cwd, versao_runtime, agente_id=None):
        pasta = self.pasta()
        if pasta is None:
            return False
        exigir(isinstance(chamada, str) and chamada, "Chamada sem identificador")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            criterio = next((c for c in contrato["aceite"] if
                             c["verificacao"].get("comando") == comando and
                             str(self.cwd(c["verificacao"]["cwd"])) == cwd), None)
            if criterio is None:
                return False
            exigir(estado["pendente"] is None, "Ha verificacao sem resultado. Confira o resultado antes de repetir")
            exigir(chamada not in estado["chamadas"], "Chamada ja registrada")
            estado["chamadas"].append(chamada)
            estado["fecho"] = None  # Nova verificacao reabre a fatia; o fecho gravado continua em disco.
            estado["tentativa"] += 1
            tentativa = estado["tentativa"]
            manifesto = f"tentativas/{tentativa:03d}/manifesto.json"
            caminhos = criterio["verificacao"]["caminhos"]
            dados = dict(versao=1, registrado_em=agora(), caminhos=caminhos, arquivos=retrato(self.raiz, caminhos),
                         controle=retrato(self.raiz, CONTROLE + [".cursor/hooks.json"]),
                         runtime=versao_runtime, contrato_sha256=estado["contrato_sha256"])
            gravar(dentro(pasta, manifesto), dados)
            estado["pendente"] = dict(chamada=chamada, comando_sha256=hash_bytes(comando.encode()),
                                      criterio=criterio["id"], cwd=cwd, inicio=agora(), manifesto=manifesto,
                                      manifesto_sha256=hash_arquivo(dentro(pasta, manifesto)),
                                      agente_id=agente_id)
            self.evento(pasta, estado, "guarda", dict(operacao="registrar_verificacao",
                        checagens=[dict(id="estado_anterior", resultado="limpo")],
                        decisao="permitir", recuperacao=""), manifesto, tentativa)
            self.atualizar(pasta, estado)
            return True

    def manifesto_atual(self, pasta, ref):
        m = ler(dentro(pasta, ref))
        return (m["arquivos"] == retrato(self.raiz, m["caminhos"]) and
                m["controle"] == retrato(self.raiz, list(m["controle"])))

    def depois(self, chamada, comando, exit_code, saida, exit_code_origem=None):
        pasta = self.pasta()
        if pasta is None:
            return None
        with trava(pasta):
            estado = self.estado(pasta)
            p = estado["pendente"]
            if p is None or p["chamada"] != chamada:
                return None
            exigir(p["comando_sha256"] == hash_bytes(comando.encode()), "Resultado de outro comando")
            exigir(exit_code is None or type(exit_code) is int, "Exit code invalido")
            exigir(isinstance(saida, str), "Saida invalida")
            tentativa = estado["tentativa"]
            log_ref = f"tentativas/{tentativa:03d}/logs/resultado.txt"
            log = dentro(pasta, log_ref)
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("x", encoding="utf-8") as arquivo:
                arquivo.write(limpar_log(saida))
            atual = (hash_arquivo(dentro(pasta, p["manifesto"])) == p["manifesto_sha256"] and
                     self.manifesto_atual(pasta, p["manifesto"]))
            resultado = "inconclusivo" if exit_code is None or not atual else ("pass" if exit_code == 0 else "fail")
            dados = dict(criterio_id=p["criterio"], chamada_id=chamada, cwd=p["cwd"],
                         comando=limpar_log(comando), inicio=p["inicio"], fim=agora(), exit_code=exit_code,
                         log_ref=log_ref, log_sha256=hash_arquivo(log),
                         estado_testado=p["manifesto_sha256"], resultado=resultado,
                         validade="valida" if atual and exit_code is not None else "nao_verificada")
            if p.get("agente_id"):
                dados["agente_id"] = p["agente_id"]
            if exit_code is not None and exit_code_origem:
                dados["exit_code_origem"] = exit_code_origem
            ref = self.evento(pasta, estado, "teste", dados, p["manifesto"], tentativa)
            estado["provas"][p["criterio"]] = {"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))}
            estado["pendente"] = None
            self.atualizar(pasta, estado)
            return {"resultado": resultado, "evidencia_ref": ref, "pasta": str(pasta)}

    def registrado(self, pasta, estado, registro):
        """Evento da fatia íntegro e válido, ou None se alterado ou ilegível."""
        try:
            arquivo = dentro(pasta, registro["ref"])
            exigir(hash_arquivo(arquivo) == registro["sha256"], "Registro alterado")
            return validar(ler(arquivo), pasta, estado["execucao_id"], "principal")
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def manifesto_valido(self, pasta, ref):
        try:
            return self.manifesto_atual(pasta, ref)
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def prova_atende(self, pasta, criterio, e):
        """Evento do critério com resultado pass sobre um estado que ainda não mudou."""
        d = e["dados"]
        try:
            if criterio["tipo"] in TIPOS_INSPECAO:
                return (e["tipo"] == "inspecao" and d["criterio_id"] == criterio["id"] and
                        d["resultado"] == "pass" and d["validade"] == "valida" and
                        self.manifesto_atual(pasta, e["manifesto_ref"]))
            return (e["tipo"] == "teste" and d["criterio_id"] == criterio["id"] and
                    d["resultado"] == "pass" and d["validade"] == "valida" and
                    hash_arquivo(dentro(pasta, d["log_ref"])) == d["log_sha256"] and
                    hash_arquivo(dentro(pasta, e["manifesto_ref"])) == d["estado_testado"] and
                    self.manifesto_atual(pasta, e["manifesto_ref"]))
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def criterios(self, pasta, estado, contrato, ativa):
        saida, faltam = [], []
        plano = estado.get("chamadas_previstas") or self.plano_chamadas(contrato)
        # Com test no plano ativado, a prova de teste precisa ter rodado num subagente test observado.
        agentes_test = self.agentes_do_papel(pasta, estado, "test") if ativa and any(
            c["papel"] == "test" for c in plano) else None
        for c in contrato["aceite"]:
            registro = estado.get("inspecoes" if c["tipo"] in TIPOS_INSPECAO else "provas", {}).get(c["id"])
            e = self.registrado(pasta, estado, registro) if registro else None
            provado = e is not None and self.prova_atende(pasta, c, e)
            # Com a trilha ativada, o critério ambiente também exige a autorização registrada e atual.
            autorizado = not (ativa and c["tipo"] == "ambiente") or self.manifesto_valido(
                pasta, estado.get("manifestos_autorizacao", {}).get(c["id"]))
            vinculado = (agentes_test is None or c["tipo"] not in TIPOS_TESTE or
                         (e is not None and e["dados"].get("agente_id") in agentes_test))
            extras = self.exigencias_formas(pasta, estado, c, estado["provas"].get(c["id"]), ativa,
                                            plano) if provado and c["tipo"] in {"ambiente", "paridade"} else []
            atendido = provado and autorizado and vinculado and not extras
            item = dict(id=c["id"], atendido=atendido, validade="valida" if atendido else "nao_verificada")
            if e is not None:
                item["evidencia_ref"] = registro["ref"]
            saida.append(item)
            if c["obrigatorio"] and not provado:
                faltam.append(c["id"])
            if c["obrigatorio"] and not autorizado:
                faltam.append("autorizacao_ambiente:" + c["id"])
            if c["obrigatorio"] and provado and not vinculado:
                faltam.append("teste_fora_do_test:" + c["id"])
            if c["obrigatorio"]:
                faltam.extend(extras)
        return saida, faltam

    def exigencias_formas(self, pasta, estado, c, prova, ativa, plano):
        """Ambiente (operação de bundle) e paridade: o registro da forma ligado ao teste atual; exigido com a trilha ativada.

        Registro existente e reprovado, obsoleto ou fora do papel bloqueia também sem a chave.
        """
        sandbox = c["tipo"] == "ambiente"
        if sandbox and operacao_bundle(c["verificacao"]["comando"]) is None:
            return []  # Script local ou outro comando: nao ha bundle, target nem plan a registrar.
        forma, papel = ("sandbox", "dab") if sandbox else ("paridade", "test")
        registro = estado.get("sandbox" if sandbox else "paridades", {}).get(c["id"])
        if registro is None:
            return [f"{forma}_ausente:{c['id']}"] if ativa else []
        e = self.registrado(pasta, estado, registro)
        if e is None or e["tipo"] != forma:
            return [f"{forma}_invalido:{c['id']}"]
        d = e["dados"]
        if (registro["teste_ref"], registro["teste_sha256"], d["teste_ref"]) != (prova["ref"], prova["sha256"], prova["ref"]):
            return [f"{forma}_obsoleto:{c['id']}"]
        faltam = [f"{forma}_reprovado:{c['id']}"] if d["resultado"] != "pass" else []
        if ativa and any(p["papel"] == papel for p in plano) and d.get("agente_id") not in self.agentes_do_papel(
                pasta, estado, papel):
            faltam.append(f"{forma}_fora_do_{papel}:{c['id']}")
        if sandbox:
            faltam += [f"sandbox_nao_verificado:{campo}:{c['id']}" for campo in nao_verificados_sandbox(d)]
            if d["plan_ref"] is not None and not self.plan_compativel(d):
                faltam.append(f"sandbox_plan_obsoleto:{c['id']}")
        return faltam

    def chamadas_validas(self, pasta, estado):
        """Chamadas observadas íntegras, com o evento do adaptador que as sustenta."""
        runtime = estado.get("runtime") or self.runtime
        validas = []
        for registro in estado.get("chamadas_observadas", []):
            e = self.registrado(pasta, estado, registro)
            if e is None:
                continue
            d = e["dados"]
            if (e["tipo"] == "chamada" and e["produtor"] == "adaptador" and d["runtime"] == runtime and
                    d["papel"] == registro["papel"] and d["chamada_id"] == registro["chamada_id"] and
                    d["status"] == registro["status"] and
                    (d["papel"] != "dab" or self.manifesto_valido(pasta, e["manifesto_ref"]))):
                validas.append((registro, e))
        return validas

    def agentes_do_papel(self, pasta, estado, papel):
        """IDs de subagente observados nas chamadas concluídas do papel."""
        return {i["valor"] for registro, e in self.chamadas_validas(pasta, estado)
                if registro["papel"] == papel and registro["status"] == "concluida"
                for i in e["dados"]["ids_observados"] if i["nome"] == "agente_id"}

    def chamadas_faltantes(self, pasta, estado):
        runtime = estado.get("runtime") or self.runtime
        contrato = ler(pasta / "contrato.yaml")["dados"]
        if not self.ativada(estado.get("trilha", contrato["trilha"]), runtime):
            return []
        plano = estado.get("chamadas_previstas") or self.plano_chamadas(contrato)
        feitas = concluidas(plano, [registro for registro, _ in self.chamadas_validas(pasta, estado)])
        return [c["etapa"] for c in plano if c["id"] not in feitas]

    def revisao_faltante(self, pasta, estado, trilha):
        """A última revisão cobre o estado atual e seus achados foram tratados.

        Cada refute observado tem a sua revisão registrada, e achado de revisão anterior tem triagem:
        chamar o refute de novo não descarta o que o anterior achou.
        """
        revisoes = estado.get("revisoes", [])
        if not revisoes:
            return ["revisao:ausente"]
        ataques = [(r["ref"], self.registrado(pasta, estado, r)) for r in revisoes]
        ataque = ataques[-1][1]
        if ataque is None:
            return ["revisao:invalida"]
        if not self.manifesto_valido(pasta, ataque["manifesto_ref"]):
            return ["revisao:obsoleta"]
        if ataque["dados"].get("agente_id") not in self.agentes_do_papel(pasta, estado, "refute"):
            return ["revisao:fora_do_refute"]
        revisados = {a["dados"].get("agente_id") for _, a in ataques if a is not None}
        faltam = [f"revisao:sem_registro:{registro['chamada_id']}"
                  for registro, e in self.chamadas_validas(pasta, estado)
                  if registro["papel"] == "refute" and registro["status"] == "concluida" and
                  not revisados & {i["valor"] for i in e["dados"]["ids_observados"] if i["nome"] == "agente_id"}]
        if trilha == "review":
            return faltam  # O veredito é do artefato; a tarefa de revisar fecha mesmo com achados.
        if ataque["dados"]["veredito"] == "inconclusivo":
            return faltam + ["revisao:inconclusiva"]
        decisoes = {}
        for registro in estado.get("triagens", []):
            t = self.registrado(pasta, estado, registro)
            if t is not None:
                decisoes[(t["dados"]["revisao_ref"], t["dados"]["achado_id"])] = t["dados"]["decisao"]
        for ref, anterior in ataques[:-1]:
            if anterior is not None:
                faltam.extend(f"achado:{a['id']}:sem_triagem" for a in anterior["dados"]["achados"]
                              if (ref, a["id"]) not in decisoes)
        # Procedente sobre o estado atual ainda não foi resolvido: a correção muda o estado e pede nova revisão.
        ultima = revisoes[-1]["ref"]
        return faltam + [f"achado:{a['id']}:{decisoes.get((ultima, a['id']), 'sem_triagem')}"
                         for a in ataque["dados"]["achados"] if decisoes.get((ultima, a["id"])) != "descartado"]

    def pendencias(self, pasta, estado):
        """Critérios e, com a trilha ativada, chamadas previstas, revisão atual e achados tratados."""
        contrato = ler(pasta / "contrato.yaml")["dados"]
        trilha = estado.get("trilha", contrato["trilha"])
        ativa = self.ativada(trilha, estado.get("runtime") or self.runtime)
        criterios, faltam = self.criterios(pasta, estado, contrato, ativa)
        if estado["pendente"]:
            faltam.append("resultado_da_chamada_pendente")
        if ativa:
            faltam.extend("chamada:" + etapa for etapa in self.chamadas_faltantes(pasta, estado))
            plano = estado.get("chamadas_previstas") or self.plano_chamadas(contrato)
            if any(c["papel"] == "refute" for c in plano):
                faltam.extend(self.revisao_faltante(pasta, estado, trilha))
            faltam.extend(self.pendencias_superficie(pasta, estado))
            if self.exige_diagnostico(trilha) and not self.diagnosticos_validos(pasta, estado):
                faltam.append("diagnostico:ausente")
        return criterios, faltam

    def fechar(self, status, resultado):
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        with trava(pasta):
            estado = self.estado(pasta)
            criterios, faltam = self.pendencias(pasta, estado)
            exigir(status not in {"DONE", "REVIEW"} or not faltam, "Prova ausente ou obsoleta: " + ", ".join(faltam) + ". Rode as verificacoes do contrato e feche de novo")
            exigir(isinstance(resultado, str) and resultado.strip(), "Resultado ausente")
            dados = dict(escopo_conclusao=estado["execucao_id"], status=status, outcome=resultado,
                         criterios=criterios, pendencias=faltam,
                         acao_humana=resultado if status in {"DECIDE", "REVIEW"} else None)
            # Baseline sustenta o envelope; cada criterio aponta seu proprio manifesto.
            ref = self.evento(pasta, estado, "brief", dados, "baseline.json",
                              max(1, estado["tentativa"]), f"fechos/{uuid4().hex}.yaml")
            estado["fecho"] = {"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))}
            self.atualizar(pasta, estado)
            return dados

    def conferir(self):
        pasta = self.pasta()
        if pasta is None:
            return {"ativa": False, "pendencias": []}
        estado = self.estado(pasta)
        _, faltam = self.pendencias(pasta, estado)
        status = None
        if estado["fecho"]:
            ref = dentro(pasta, estado["fecho"]["ref"])
            exigir(hash_arquivo(ref) == estado["fecho"]["sha256"], "Fecho alterado")
            status = validar(ler(ref), pasta, estado["execucao_id"], "principal")["dados"]["status"]
        return dict(ativa=True, execucao_id=estado["execucao_id"], revisao=estado["revisao"],
                    status=status, pendencias=faltam, fecho_valido=status is not None and (status not in ("DONE", "REVIEW") or not faltam))
