"""Checagem local anterior a bundle validate, plan e deploy.

Nao executa comandos, nao consulta credenciais e nao concede autorizacao.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shlex

import yaml


class YamlSemDuplicatas(yaml.SafeLoader):
    """Configuracao ambigua nao pode produzir uma decisao positiva."""


def _mapa(loader, node):
    pares = loader.construct_pairs(node)
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError("Chave YAML duplicada")
        resultado[chave] = valor
    return resultado


YamlSemDuplicatas.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapa
)


@dataclass(frozen=True)
class Decisao:
    decisao: str
    codigo: str
    motivo: str
    recuperacao: str = ""
    cwd: str | None = None
    bundle_arquivo: str | None = None

    def registro(self):
        return asdict(self)


@dataclass(frozen=True)
class Operacao:
    """Contrato interno independente dos eventos de cada ferramenta."""
    fase: str
    ferramenta: str
    comando: str | None = None
    cwd: str | None = None
    origem_cwd: str = "nao_observado"


def negar(codigo, motivo, recuperacao="", cwd=None, bundle_arquivo=None):
    return Decisao("negar", codigo, motivo, recuperacao, cwd, bundle_arquivo)


def resolver_bundle(cwd: Path) -> Path | None:
    """Reproduz a busca ascendente; nao resolve includes/targets da CLI."""
    for pasta in (cwd, *cwd.parents):
        candidatos = [pasta / nome for nome in ("databricks.yml", "databricks.yaml")]
        existentes = [p for p in candidatos if p.is_file()]
        if len(existentes) > 1:
            raise ValueError("Dois arquivos de bundle no mesmo diretorio")
        if existentes:
            return existentes[0].resolve(strict=True)
    return None


def avaliar_cwd(cwd: str, bundle_local: Path, nome_esperado: str) -> Decisao:
    recuperacao = (
        f"Repita a chamada no diretorio '{bundle_local}', pelo cwd da ferramenta ou com o prefixo "
        "literal do shell. Mantenha target, perfil e argumentos."
    )
    try:
        informado = Path(cwd)
        if not informado.is_absolute():
            return negar("cwd_relativo", "O diretorio deve ser absoluto.", recuperacao)
        local = bundle_local.resolve(strict=True)
        atual = informado.resolve(strict=True)
        if not atual.is_dir():
            raise ValueError("Diretorio inexistente")
        arquivo = resolver_bundle(atual)
        if atual != local:
            return negar("cwd_incorreto", "A chamada nao parte do bundle local.",
                         recuperacao, str(atual), str(arquivo) if arquivo else None)
        if arquivo != local / "databricks.yml":
            return negar("bundle_incorreto", "O diretorio nao tem o databricks.yml do bundle local.",
                         recuperacao, str(atual), str(arquivo) if arquivo else None)
        dados = yaml.load(arquivo.read_text(encoding="utf-8-sig"), Loader=YamlSemDuplicatas)
        if not isinstance(dados, dict) or not isinstance(dados.get("bundle"), dict):
            raise ValueError("Declaracao bundle ausente")
        if dados["bundle"].get("name") != nome_esperado:
            return negar("nome_incorreto", "O nome declarado no bundle difere do esperado.",
                         "Confira a configuracao local. Nao troque o destino.",
                         str(atual), str(arquivo))
        return Decisao("permitir", "cwd_conferido",
                       "Diretorio e nome do bundle conferidos; identidade e destinos "
                       "resolvidos nao.", cwd=str(atual),
                       bundle_arquivo=str(arquivo))
    except (OSError, ValueError, TypeError, yaml.YAMLError):
        return negar("bundle_nao_verificado", "Nao foi possivel ler o bundle local.",
                     "Confira se o arquivo existe, se ha acesso e se o YAML e valido. Repita.")


def _tokens(comando: str) -> list[str]:
    # Subconjunto literal, sem expansao, pipeline, redirecionamento ou subshell.
    if any(c in comando for c in "`;|&<>$(){}\r\n"):
        raise ValueError("Sintaxe fora do subconjunto literal")
    leitor = shlex.shlex(comando, posix=True)
    leitor.whitespace_split = True
    leitor.escape = ""
    leitor.commenters = ""
    return list(leitor)


def _extrair_prefixo_cwd(comando: str) -> tuple[str | None, str]:
    """Extrai somente os prefixos literais de diretório já aceitos pela guarda."""
    prefixo = re.match(
        r"^\s*Set-Location\s+-LiteralPath\s+'([^'\r\n]+)'\s+-ErrorAction\s+Stop\s*;\s*(.*)$",
        comando, flags=re.IGNORECASE | re.DOTALL,
    )
    if prefixo:
        cwd, restante = prefixo.groups()
        return cwd, restante
    prefixo_bash = re.match(r"^\s*cd\s+--\s+'([^'\r\n]+)'\s*&&\s*(.*)$", comando, re.DOTALL)
    if prefixo_bash:
        cwd, restante = prefixo_bash.groups()
        return cwd, restante
    return None, comando


# A CLI como palavra de comando, seguida de flags e do subcomando bundle.
CLI_BUNDLE = re.compile(
    r"(?<![\w.\-])databricks(?:\.exe|\.cmd)?[\"']?\s+(?:-\S+\s+(?:[^-\s]\S*\s+)?)*[\"']?bundle\b",
    re.IGNORECASE)


# SQL ad hoc pela CLI (skills databricks-*): so leitura passa.
CLI_SQL = re.compile(
    r"(?<![\w.\-])databricks(?:\.exe|\.cmd)?[\"']?\s.*?\bexperimental\s+aitools\s+tools\s+query\b",
    re.IGNORECASE | re.DOTALL)
SQL_LEITURA = {"select", "with", "show", "describe", "desc", "explain", "values"}
SQL_ESCRITA = re.compile(
    r"\b(insert|update|delete|merge|create|drop|alter|truncate|grant|revoke|copy|"
    r"optimize|vacuum|refresh|call|msck|restore|analyze|set|reset|execute)\b", re.IGNORECASE)


def avaliar_sql(comando: str) -> Decisao:
    composto = negar("sql_nao_verificavel", "Consulta composta, dinamica ou com comentario.",
                     "Rode uma unica chamada literal: databricks experimental aitools tools query "
                     "\"SELECT ...\" --profile <perfil>. Sem pipe, variavel, crase ou comentario SQL.")
    if any(c in comando for c in "$`\r\n"):
        return composto
    try:
        leitor = shlex.shlex(comando.strip(), posix=True, punctuation_chars=";|&<>(){}")
        leitor.whitespace_split = True
        leitor.commenters = ""
        tokens = list(leitor)
    except ValueError:
        return composto
    if any(t and set(t) <= set(";|&<>(){}") for t in tokens):
        return composto
    posicao = next((i for i, t in enumerate(tokens) if t.casefold() == "query"), None)
    if posicao is None or posicao + 1 >= len(tokens) or tokens[posicao + 1].startswith("-"):
        return composto
    sql = tokens[posicao + 1]
    if "--" in sql or "/*" in sql:
        return composto
    texto = re.sub(r"'(?:[^']|'')*'", "''", sql)
    comandos = [c.strip() for c in texto.split(";") if c.strip()]
    if (not comandos or SQL_ESCRITA.search(texto)
            or any(c.split()[0].casefold() not in SQL_LEITURA for c in comandos)):
        return negar("sql_escrita", "SQL ad hoc so pode ler (SELECT, WITH, SHOW, DESCRIBE, EXPLAIN).",
                     "Escrita em catalogo segue pelo pipeline ou job do bundle. Se for preciso escrever "
                     "agora, peca ao usuario que execute.")
    return Decisao("permitir", "sql_leitura", "Consulta somente leitura.")


def avaliar_operacao(operacao: Operacao, politica: dict) -> Decisao:
    if operacao.fase != "antes_execucao":
        return negar("evento_invalido", "Esperada operacao anterior a execucao.")
    if operacao.ferramenta != "shell":
        return Decisao("nao_aplica", "ferramenta_fora_do_recorte",
                       "Somente chamadas de shell sao verificadas.")
    if not isinstance(operacao.comando, str):
        return negar("entrada_invalida", "Comando ausente ou invalido.")
    comando = operacao.comando
    cwd_prefixo, comando_sem_prefixo = _extrair_prefixo_cwd(comando)
    if CLI_SQL.search(comando) and not CLI_BUNDLE.search(comando):
        resultado = avaliar_sql(comando)
        return Decisao(resultado.decisao, resultado.codigo, resultado.motivo, resultado.recuperacao,
                       cwd=cwd_prefixo, bundle_arquivo=resultado.bundle_arquivo)
    if not CLI_BUNDLE.search(comando):
        return Decisao("nao_aplica", "comando_fora_do_recorte",
                       "Sem chamada de databricks bundle no comando.", cwd=cwd_prefixo)

    # O diretorio da sessao nao comprova o cwd da chamada.
    cwd = operacao.cwd if operacao.origem_cwd == "ferramenta" else None
    if cwd_prefixo is not None:
        cwd, comando = cwd_prefixo, comando_sem_prefixo
    try:
        tokens = _tokens(comando.strip())
    except ValueError:
        return negar("comando_nao_suportado", "Comando composto ou dinamico nao e verificavel.",
                     "Rode uma unica chamada literal, sem ; | & ou variaveis. Fixe o cwd absoluto pela "
                     "ferramenta ou com Set-Location -LiteralPath 'caminho' -ErrorAction Stop; "
                     "(PowerShell) ou cd -- 'caminho' && (Bash).")
    # Mencionar databricks.yml numa leitura literal nao e operar o bundle.
    leituras = {"get-content", "get-childitem", "test-path", "resolve-path", "get-filehash"}
    if tokens and (tokens[0].casefold() in leituras or (
        tokens[0].casefold() in {"rg", "rg.exe"}
        and not any(t == "--pre" or t.startswith("--pre=") for t in tokens[1:])
    )):
        return Decisao("nao_aplica", "leitura_literal", "Leitura literal; nao opera o bundle.")
    from guarda_efeito import avaliar_efeito, separar_ambiente
    try:
        ambiente, invocacao = separar_ambiente(tokens)
    except ValueError:
        return negar("ambiente_nao_suportado",
                     "So DATABRICKS_BUNDLE_TARGET pode vir como prefixo, uma vez.",
                     "Use -t/--target ou um unico prefixo DATABRICKS_BUNDLE_TARGET=valor "
                     "antes do executavel.")
    if (len(invocacao) < 3
            or invocacao[0].casefold() not in {"databricks", "databricks.exe", "databricks.cmd"}):
        return negar("wrapper_opaco", "O executavel nao e a CLI databricks, ou ha wrapper.",
                     "Chame databricks, databricks.exe ou databricks.cmd, sem caminho, "
                     "numa unica chamada literal.")
    if invocacao[1].startswith("-"):
        return negar("argumentos_nao_suportados", "Flag antes do subcomando nao coberta.",
                     "Coloque -t/--target e -p/--profile depois de bundle validate ou plan.")
    if invocacao[1] != "bundle":
        return Decisao("nao_aplica", "fora_de_bundle", "Subcomando fora de bundle.")
    if not isinstance(cwd, str) or not cwd:
        return negar("cwd_nao_observavel", "A ferramenta nao informou o cwd da chamada.",
                     f"Fixe o cwd em '{politica['bundle_local']}' pela ferramenta "
                     "ou com o prefixo literal PowerShell/Bash.")
    resultado = avaliar_cwd(cwd, Path(politica["bundle_local"]), politica["bundle_nome"])
    if resultado.decisao != "permitir":
        return resultado
    return avaliar_efeito(invocacao, ambiente, politica, resultado)
