"""Prova minima: estado antes da chamada, resultado observado e fecho atual."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from formas import dentro, exigir, relativo, validar, validar_dados

IGNORADOS = {".git", ".venv", ".execucoes", "__pycache__", ".pytest_cache"}


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


class Provas:
    def __init__(self, raiz, registros, sessao):
        self.raiz = Path(raiz).resolve(strict=True)
        self.registros = Path(registros).resolve()
        exigir(self.registros.is_relative_to(self.raiz) and self.registros != self.raiz,
               "Registros devem ficar dentro do harness, separados do produto")
        exigir(isinstance(sessao, str) and 0 < len(sessao) <= 300, "Sessao ausente")
        self.sessao = hash_bytes(sessao.encode())
        self.indice = self.registros / "sessoes" / self.sessao

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

    def evento(self, pasta, estado, tipo, dados, manifesto, tentativa, destino=None):
        evento = dict(schema_versao="3.1", tipo=tipo, exemplo=False,
                      execucao_id=estado["execucao_id"], fatia_id="principal",
                      tentativa=tentativa, evento_id=uuid4().hex,
                      produtor={"contrato": "coordenador", "brief": "coordenador",
                                "teste": "executor_teste", "guarda": "hook"}[tipo],
                      registrado_em=agora(), manifesto_ref=manifesto, dados=dados)
        validar(evento, pasta, estado["execucao_id"], "principal")
        ref = destino or f"tentativas/{tentativa:03d}/eventos/{evento['evento_id']}.yaml"
        gravar(dentro(pasta, ref), evento)
        return ref

    def iniciar(self, contrato):
        validar_dados("contrato", contrato)
        exigir(contrato["artefatos_raiz"] == ".execucoes/provas", "Use .execucoes/provas para artefatos")
        comandos = set()
        cobertura = []
        for criterio in contrato["aceite"]:
            v = criterio["verificacao"]
            cwd = self.cwd(v["cwd"])
            exigir(cwd.is_dir(), "Cwd da verificacao ausente")
            chave = (v["comando"], str(cwd.resolve()))
            exigir(v["comando"].strip() and chave not in comandos, "Comando vazio ou verificacao duplicada")
            comandos.add(chave)
            cobertura.extend(v["caminhos"])
        for ref in contrato["superficie"]:
            exigir(any(ref == c or ref.startswith(c + "/") for c in cobertura), "Superficie sem verificacao")
        baseline = retrato(self.raiz, contrato["superficie"] + cobertura)
        with trava(self.indice):
            anterior = self.pasta()
            if anterior:
                exigir(self.estado(anterior)["fecho"] is not None, "Feche a fatia ativa antes de iniciar outra")
            execucao = uuid4().hex
            pasta = self.registros / "provas" / execucao / "principal"
            estado = dict(versao=1, sessao=self.sessao, execucao_id=execucao, revisao=0,
                          tentativa=0, pendente=None, chamadas=[], provas={}, fecho=None, contrato_sha256="")
            gravar(pasta / "baseline.json", dict(versao=1, registrado_em=agora(), arquivos=baseline))
            self.evento(pasta, estado, "contrato", contrato, "baseline.json", 1, "contrato.yaml")
            estado["contrato_sha256"] = hash_arquivo(pasta / "contrato.yaml")
            gravar(pasta / "estado.json", estado)
            gravar(self.indice / "ativa.json", {"fatia": pasta.relative_to(self.registros).as_posix()}, substituir=True)
            return {"execucao_id": execucao, "fatia": str(pasta), "revisao": 0}

    def antes(self, chamada, comando, cwd, versao_runtime):
        pasta = self.pasta()
        if pasta is None:
            return False
        exigir(isinstance(chamada, str) and chamada, "Chamada sem identificador")
        with trava(pasta):
            estado = self.estado(pasta)
            contrato = ler(pasta / "contrato.yaml")["dados"]
            criterio = next((c for c in contrato["aceite"] if
                             c["verificacao"]["comando"] == comando and
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
            # A implementacao/configuracao que interpreta a prova tambem faz parte dela.
            controle = ["implementacao", "adaptadores", "configuracao", "formas/catalogo.yaml", ".cursor/hooks.json"]
            dados = dict(versao=1, registrado_em=agora(), caminhos=caminhos,
                         arquivos=retrato(self.raiz, caminhos), controle=retrato(self.raiz, controle),
                         runtime=versao_runtime, contrato_sha256=estado["contrato_sha256"])
            gravar(dentro(pasta, manifesto), dados)
            estado["pendente"] = dict(chamada=chamada, comando_sha256=hash_bytes(comando.encode()),
                                      criterio=criterio["id"], cwd=cwd, inicio=agora(), manifesto=manifesto,
                                      manifesto_sha256=hash_arquivo(dentro(pasta, manifesto)))
            self.evento(pasta, estado, "guarda", dict(operacao="registrar_verificacao",
                        checagens=[dict(id="estado_anterior", resultado="limpo")],
                        decisao="permitir", recuperacao=""), manifesto, tentativa)
            self.atualizar(pasta, estado)
            return True

    def manifesto_atual(self, pasta, ref):
        m = ler(dentro(pasta, ref))
        return (m["arquivos"] == retrato(self.raiz, m["caminhos"]) and
                m["controle"] == retrato(self.raiz, list(m["controle"])))

    def depois(self, chamada, comando, exit_code, saida):
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
            ref = self.evento(pasta, estado, "teste", dados, p["manifesto"], tentativa)
            estado["provas"][p["criterio"]] = {"ref": ref, "sha256": hash_arquivo(dentro(pasta, ref))}
            estado["pendente"] = None
            self.atualizar(pasta, estado)
            return {"resultado": resultado, "evidencia_ref": ref, "pasta": str(pasta)}

    def criterios(self, pasta, estado):
        contrato = ler(pasta / "contrato.yaml")["dados"]
        saida = []
        for c in contrato["aceite"]:
            prova = estado["provas"].get(c["id"])
            valido = False
            referencia = None
            if prova:
                try:
                    arquivo = dentro(pasta, prova["ref"])
                    if arquivo.is_file():
                        referencia = prova["ref"]
                    exigir(hash_arquivo(arquivo) == prova["sha256"], "Prova alterada")
                    e = validar(ler(arquivo), pasta, estado["execucao_id"], "principal")
                    d = e["dados"]
                    valido = (e["tipo"] == "teste" and d["criterio_id"] == c["id"] and
                              d["resultado"] == "pass" and d["validade"] == "valida" and
                              hash_arquivo(dentro(pasta, d["log_ref"])) == d["log_sha256"] and
                              hash_arquivo(dentro(pasta, e["manifesto_ref"])) == d["estado_testado"] and
                              self.manifesto_atual(pasta, e["manifesto_ref"]))
                except (OSError, ValueError, KeyError, TypeError):
                    valido = False
            item = dict(id=c["id"], atendido=valido, validade="valida" if valido else "nao_verificada")
            if referencia:
                item["evidencia_ref"] = referencia
            saida.append(item)
        faltam = [c["id"] for c, r in zip(contrato["aceite"], saida) if c["obrigatorio"] and not r["atendido"]]
        if estado["pendente"]:
            faltam.append("resultado_da_chamada_pendente")
        return saida, faltam

    def fechar(self, status, resultado):
        pasta = self.pasta()
        exigir(pasta is not None, "Nenhuma fatia ativa")
        with trava(pasta):
            estado = self.estado(pasta)
            criterios, faltam = self.criterios(pasta, estado)
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
        _, faltam = self.criterios(pasta, estado)
        status = None
        if estado["fecho"]:
            ref = dentro(pasta, estado["fecho"]["ref"])
            exigir(hash_arquivo(ref) == estado["fecho"]["sha256"], "Fecho alterado")
            status = validar(ler(ref), pasta, estado["execucao_id"], "principal")["dados"]["status"]
        return dict(ativa=True, execucao_id=estado["execucao_id"], revisao=estado["revisao"],
                    status=status, pendencias=faltam, fecho_valido=status is not None and (status not in ("DONE", "REVIEW") or not faltam))
