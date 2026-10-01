"""Target efetivo e plan vigente antes de deploy.

Nao executa a CLI, nao le o ambiente do processo e nao grava recibo
antes da execucao. O recibo de plan so entra por observar_resultado_plan,
depois de um exit 0 observado, nunca no gancho que roda antes da execucao.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import uuid4

from guarda_cwd import Decisao, negar


EXECUTAVEIS = {"databricks", "databricks.exe", "databricks.cmd"}
OPERACOES = {"validate", "plan", "deploy"}
VAR_TARGET = "DATABRICKS_BUNDLE_TARGET"
VALOR = re.compile(r"[A-Za-z0-9_.-]+")
ATRIBUICAO = re.compile(r"\A([A-Za-z_][A-Za-z0-9_]*)=([A-Za-z0-9_.-]+)\Z")
HEX64 = re.compile(r"[0-9a-f]{64}")
CHAVES_RECIBO = {
    "versao", "bundle_arquivo", "bundle_nome", "target", "selecao",
    "perfil_sha256", "identidade", "estado", "observado_em",
}
SYNC = "--select nao restringe o sync de arquivos."


@dataclass(frozen=True)
class Chamada:
    operacao: str
    target: str | None
    perfil: str | None
    selecao: tuple[str, ...]


def separar_ambiente(tokens: list[str]) -> tuple[dict, list[str]]:
    ambiente = {}
    indice = 0
    while indice < len(tokens):
        encontrado = ATRIBUICAO.fullmatch(tokens[indice])
        if not encontrado:
            break
        nome, valor = encontrado.group(1), encontrado.group(2)
        if nome != VAR_TARGET or nome in ambiente:
            raise ValueError("ambiente_nao_suportado")
        ambiente[nome] = valor
        indice += 1
    return ambiente, tokens[indice:]


def _valor_simples(texto: str) -> str | None:
    if VALOR.fullmatch(texto) and not texto.startswith("-"):
        return texto
    return None


def _pedacos_select(texto: str) -> tuple[str, ...] | None:
    partes = texto.split(",")
    if not partes:
        return None
    saida = []
    for parte in partes:
        if _valor_simples(parte) is None:
            return None
        saida.append(parte)
    return tuple(saida)


def interpretar(invocacao: list[str], ambiente: dict) -> Decisao | Chamada:
    if len(invocacao) < 3 or invocacao[2] not in OPERACOES:
        return negar("operacao_pendente",
                     "Esta operacao do bundle nao tem guarda completa.",
                     "Rode apenas validate ou plan, com -t e -p. "
                     "Para deploy, run, destroy ou sync, peca ao usuario.")
    flags = {"selecao": []}
    restantes = invocacao[3:]
    while restantes:
        token = restantes.pop(0)
        if not token.startswith("-"):
            return negar("argumentos_nao_suportados", "Argumento sem flag nao e aceito.",
                         "Use somente -t/--target, -p/--profile e --select.")
        chave, separador, valor = token.partition("=")
        canonica = {"-t": "target", "--target": "target", "-p": "perfil",
                    "--profile": "perfil", "--select": "selecao"}.get(chave)
        if canonica is None or (canonica != "selecao" and canonica in flags):
            return negar("argumentos_nao_suportados", "Flag desconhecida ou repetida.",
                         "Use somente -t/--target, -p/--profile e --select, cada uma com um valor.")
        if not separador:
            if not restantes:
                return negar("argumentos_invalidos", "Flag sem valor.", "Passe um valor a cada flag.")
            valor = restantes.pop(0)
        if canonica == "selecao":
            pedacos = _pedacos_select(valor)
            if pedacos is None:
                return negar("argumentos_invalidos", "Valor de --select invalido.",
                             "Use nomes com letras, numeros, _ . -, separados por virgula.")
            flags["selecao"].extend(pedacos)
            continue
        if _valor_simples(valor) is None:
            return negar("argumentos_invalidos", "Valor de flag invalido.",
                         "Use letras, numeros, _ . - e nao comece o valor com -.")
        flags[canonica] = valor
    selecao = tuple(flags["selecao"])
    if len(selecao) != len(set(selecao)):
        return negar("argumentos_invalidos", "Item repetido em --select.",
                     "Informe cada item uma vez.")
    flag_target = flags.get("target")
    env_target = ambiente.get(VAR_TARGET)
    if flag_target and env_target and flag_target != env_target:
        return negar("target_conflitante",
                     "A flag de target e DATABRICKS_BUNDLE_TARGET indicam targets diferentes.",
                     "Use um unico target.")
    return Chamada(invocacao[2], flag_target or env_target, flags.get("perfil"),
                   tuple(sorted(selecao)))


def _dev_autorizado(politica: dict, operacao: str, selecao: tuple[str, ...]) -> bool:
    itens = politica.get("autorizacoes_dev")
    if not isinstance(itens, list):
        return False
    for item in itens:
        if not isinstance(item, dict) or item.get("operacao") != operacao:
            continue
        escopo = item.get("selecao", "*")
        if escopo == "*":
            return True
        if isinstance(escopo, list) and tuple(sorted(str(x) for x in escopo)) == selecao:
            return True
    return False


def _politica_target(chamada: Chamada, politica: dict) -> Decisao | None:
    if not chamada.target:
        return negar("target_nao_observavel",
                     "O comando nao informa o target.",
                     "Acrescente -t sandbox ou o prefixo DATABRICKS_BUNDLE_TARGET=sandbox. "
                     "O ambiente do processo e o default do YAML nao valem.")
    if chamada.target == "dev" and not _dev_autorizado(politica, chamada.operacao, chamada.selecao):
        return negar("target_dev_pendente",
                     "O target dev grava nos catalogos da entrega e esta operacao nao tem autorizacao.",
                     "Peca autorizacao ao usuario. Nao troque o target por conta propria.")
    if chamada.target != "sandbox" and chamada.target != "dev":
        return negar("target_nao_permitido",
                     "So os targets sandbox e dev autorizado sao permitidos.",
                     "Mantenha o target pedido e avise o usuario. Nao o substitua.")
    if not chamada.perfil:
        return negar("target_perfil_pendentes",
                     "O comando nao informa o perfil.",
                     "Acrescente -p ou --profile. O ambiente do processo nao substitui a flag.")
    return None


def _motivo_leitura(operacao: str) -> str:
    base = ("Diretorio, nome do bundle, target e perfil conferidos. "
            "Identidade autenticada e variaveis resolvidas da CLI nao foram conferidas.")
    if operacao == "plan":
        return base + " Plan nao publica e nao autoriza deploy."
    return base


def _pasta_recibos(politica: dict) -> Path | None:
    bruto = politica.get("registros_raiz")
    if not isinstance(bruto, str) or not bruto:
        return None
    pasta = Path(bruto) / "plans"
    if pasta.exists() and not pasta.is_dir():
        return None
    return pasta


def _sha(texto: str) -> str:
    return sha256(texto.encode("utf-8")).hexdigest()


def _hash_arquivo(caminho: Path) -> str:
    return sha256(caminho.read_bytes()).hexdigest()


def _arquivos_do_plan(bundle_dir: Path, bundle_arquivo: Path, caminhos) -> list[Path]:
    if caminhos is None:
        caminhos = []
    if not isinstance(caminhos, (list, tuple)):
        raise ValueError("caminhos")
    raiz = bundle_dir.resolve()
    obrigatorio = bundle_arquivo.resolve()
    lista = []
    for item in caminhos:
        caminho = Path(item)
        if not caminho.is_absolute():
            raise ValueError("relativo")
        lista.append(caminho.resolve(strict=True))
    if obrigatorio not in lista:
        lista.append(obrigatorio.resolve(strict=True))
    saida = []
    for caminho in lista:
        if not caminho.is_file() or not caminho.is_relative_to(raiz):
            raise ValueError("fora_do_bundle")
        saida.append(caminho)
    return sorted(set(saida), key=lambda item: str(item))


def observar_resultado_plan(politica: dict, *, cwd: str, comando: str, caminhos=(),
                            identidade: str = "nao_observada") -> Decisao:
    """Grava recibo somente para um plan que ja passou na guarda.

    O chamador precisa ter visto exit 0. O gancho que roda antes da execucao nao chama esta funcao.
    """
    from guarda_cwd import _tokens, avaliar_cwd

    if identidade != "nao_observada" and not re.fullmatch(r"[A-Za-z0-9_.@+-]{1,200}", identidade):
        return negar("entrada_invalida", "Identidade do recibo invalida.")
    base = avaliar_cwd(cwd, Path(politica["bundle_local"]), politica["bundle_nome"])
    if base.decisao != "permitir":
        return base
    try:
        ambiente, invocacao = separar_ambiente(_tokens(comando.strip()))
    except ValueError:
        return negar("comando_nao_suportado", "Plan composto ou com ambiente nao verificavel.")
    if (len(invocacao) < 3 or invocacao[0].casefold() not in EXECUTAVEIS
            or invocacao[1] != "bundle"):
        return negar("wrapper_opaco", "O recibo exige a chamada literal de bundle plan.")
    chamada = interpretar(invocacao, ambiente)
    if isinstance(chamada, Decisao):
        return chamada
    if chamada.operacao != "plan":
        return negar("plan_nao_observado", "Somente plan gera recibo.")
    negacao = _politica_target(chamada, politica)
    if negacao:
        return negacao
    pasta = _pasta_recibos(politica)
    if pasta is None:
        return negar("plan_nao_verificado", "Pasta de recibos indisponivel.")
    try:
        arquivos = _arquivos_do_plan(Path(base.cwd), Path(base.bundle_arquivo), caminhos)
        pasta.mkdir(parents=True, exist_ok=True)
        recibo = {
            "versao": 1,
            "bundle_arquivo": str(Path(base.bundle_arquivo).resolve()),
            "bundle_nome": politica["bundle_nome"],
            "target": chamada.target,
            "selecao": list(chamada.selecao),
            "perfil_sha256": _sha(chamada.perfil),
            "identidade": identidade,
            "estado": [{"caminho": str(arquivo), "sha256": _hash_arquivo(arquivo)}
                       for arquivo in arquivos],
            "observado_em": datetime.now(timezone.utc).isoformat(),
        }
        destino = pasta / f"{uuid4().hex}.json"
        with destino.open("x", encoding="utf-8") as arquivo:
            json.dump(recibo, arquivo, ensure_ascii=True, indent=2, sort_keys=True)
            arquivo.write("\n")
    except (OSError, ValueError, TypeError):
        return negar("estado_nao_verificado",
                     "Nao foi possivel amarrar o plan aos arquivos do bundle.",
                     "Inclua somente arquivos dentro do diretorio do bundle e repita o plan.")
    return Decisao("permitir", "plan_registrado",
                   "Recibo gravado para este bundle, target, perfil e selecao. "
                   "Um arquivo chamado plan nao substitui o recibo.",
                   cwd=base.cwd, bundle_arquivo=base.bundle_arquivo)


def _ler_recibo(caminho: Path, bundle_dir: Path) -> dict | None:
    try:
        if not caminho.is_file() or caminho.parent.resolve() != caminho.resolve().parent:
            return None
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(dados, dict) or set(dados) != CHAVES_RECIBO or dados.get("versao") != 1:
        return None
    if not isinstance(dados["selecao"], list) or dados["selecao"] != sorted(dados["selecao"]):
        return None
    if any(_valor_simples(item) is None for item in dados["selecao"]):
        return None
    if not HEX64.fullmatch(str(dados["perfil_sha256"])):
        return None
    estado = dados["estado"]
    if not isinstance(estado, list) or not estado:
        return None
    for item in estado:
        if not isinstance(item, dict) or set(item) != {"caminho", "sha256"}:
            return None
        if not HEX64.fullmatch(str(item["sha256"])):
            return None
        if not isinstance(item["caminho"], str) or not Path(item["caminho"]).is_absolute():
            return None
        try:
            arquivo = Path(item["caminho"]).resolve(strict=False)
        except OSError:
            return None
        if not arquivo.is_relative_to(bundle_dir.resolve()):
            return None
    return dados


def _estado_confere(recibo: dict) -> bool:
    try:
        for item in recibo["estado"]:
            if _hash_arquivo(Path(item["caminho"])) != item["sha256"]:
                return False
    except OSError:
        return False
    return True


def _classificar_recibos(politica, base: Decisao, chamada: Chamada) -> str:
    pasta = _pasta_recibos(politica)
    if pasta is None:
        return "nao_verificado"
    if not pasta.exists():
        return "ausente"
    bundle = str(Path(base.bundle_arquivo).resolve())
    raiz = Path(base.cwd).resolve()
    perfil = _sha(chamada.perfil)
    selecao = list(chamada.selecao)
    vigente = False
    obsoleto = False
    incompativel = False
    try:
        arquivos = [item for item in pasta.glob("*.json") if item.is_file()]
    except OSError:
        return "nao_verificado"
    for arquivo in arquivos:
        recibo = _ler_recibo(arquivo, raiz)
        if recibo is None:
            continue
        if (recibo["bundle_arquivo"] != bundle or recibo["bundle_nome"] != politica["bundle_nome"]
                or recibo["target"] != chamada.target or recibo["selecao"] != selecao):
            continue
        if recibo["perfil_sha256"] != perfil or recibo["identidade"] != "nao_observada":
            if _estado_confere(recibo):
                incompativel = True
            else:
                obsoleto = True
            continue
        if _estado_confere(recibo):
            vigente = True
        else:
            obsoleto = True
    if vigente:
        return "vigente"
    if obsoleto:
        return "obsoleto"
    if incompativel:
        return "incompativel"
    return "ausente"


def _conferir_deploy(chamada: Chamada, politica: dict, base: Decisao) -> Decisao:
    if not chamada.selecao and politica.get("intencao_deploy_completo") is not True:
        return negar("deploy_completo_nao_declarado",
                     "Deploy sem --select publica o bundle inteiro e a politica nao declara essa intencao.",
                     "Use --select ou peca ao usuario para declarar o deploy completo. " + SYNC)
    estado = _classificar_recibos(politica, base, chamada)
    if estado == "nao_verificado":
        return negar("plan_nao_verificado", "Nao foi possivel ler os recibos de plan.",
                     "Confira o acesso a pasta de registros e repita.")
    if estado == "obsoleto":
        return negar("plan_obsoleto",
                     "Um arquivo do bundle mudou depois do plan.",
                     "Rode o plan de novo, com o mesmo target, perfil e selecao.")
    if estado == "incompativel":
        return negar("plan_incompativel",
                     "O plan registrado usa outro perfil ou outra identidade.",
                     "Rode o plan de novo com o mesmo perfil do deploy.")
    if estado != "vigente":
        return negar("plan_ausente",
                     "Nao ha plan registrado para este bundle, target, perfil e selecao.",
                     "Rode o plan autorizado por este chat antes do deploy. "
                     "Um arquivo chamado plan nao conta.")
    return negar("identidade_destinos_pendentes",
                 "Ha plan registrado, mas a identidade autenticada e os destinos resolvidos nao sao conferidos.",
                 "Nao rode o deploy nem o contorne. Peca ao usuario para rodar. " + SYNC)


def avaliar_efeito(invocacao: list[str], ambiente: dict, politica: dict, base: Decisao) -> Decisao:
    chamada = interpretar(invocacao, ambiente)
    if isinstance(chamada, Decisao):
        return chamada
    negacao = _politica_target(chamada, politica)
    if negacao:
        return negacao
    if chamada.operacao == "deploy":
        return _conferir_deploy(chamada, politica, base)
    return Decisao("permitir", "plan_conferido" if chamada.operacao == "plan" else "cwd_conferido",
                   _motivo_leitura(chamada.operacao), cwd=base.cwd, bundle_arquivo=base.bundle_arquivo)
