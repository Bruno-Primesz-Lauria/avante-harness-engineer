"""Gera e verifica as definições nativas dos sete agentes do harness."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import yaml


RAIZ = Path(__file__).resolve().parents[1]
PAPEIS = {"map", "config", "implement", "test", "refute", "docs", "dab"}
DESTINOS = {"claude_code": ".claude/agents", "cursor": ".cursor/agents"}
SECOES_OBRIGATORIAS = (
    "Responsabilidade",
    "Gatilho",
    "Entradas",
    "Ferramentas permitidas",
    "Skills",
    "Capacidades",
    "Saída",
    "Término",
)
FERRAMENTAS_CLAUDE = {
    "map": ("Read", "Grep", "Glob", "Bash"),
    "config": ("Read", "Grep", "Glob", "Edit", "Write", "Bash"),
    "implement": ("Read", "Grep", "Glob", "Edit", "Write", "Bash"),
    "test": ("Read", "Grep", "Glob", "Edit", "Write", "Bash"),
    "refute": ("Read", "Grep", "Glob", "Bash"),
    "docs": ("Read", "Grep", "Glob", "Edit", "Write"),
    "dab": ("Read", "Grep", "Glob", "Bash"),
}
# No Cursor o ID do subagente só aparece no Shell que ele roda na própria janela.
# Test e dab já rodam Shell; o refute, só leitura, precisa de um inofensivo.
VINCULO_CURSOR = {
    "refute": (
        "## Vínculo da chamada no Cursor\n\n"
        "O Cursor só associa esta chamada ao seu ID quando você roda um Shell dentro dela. Rode uma única vez "
        "`Write-Output refute-janela`, com o diretório absoluto no campo `cwd`, e nenhum outro Shell; leia "
        "arquivos pela ferramenta de leitura. Sem isso, a revisão registrada fica `revisao:fora_do_refute`."
    ),
}
MARCADOR = re.compile(
    rb"(?m)^<!-- esteira-agentes source=([0-9a-f]{64}) "
    rb"payload=([0-9a-f]{64}) -->\r?\n"
)


def _sha256(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def _nomes_skills(valor):
    """Extrai apenas IDs explícitos; não transforma texto de seleção em skill."""
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, list):
        return [nome for item in valor for nome in _nomes_skills(item)]
    if isinstance(valor, dict):
        nomes = []
        for chave, item in valor.items():
            if chave == "skill":
                nomes.extend(_nomes_skills(item))
            elif chave == "skills":
                nomes.extend(_nomes_skills(item))
        return nomes
    return []


def _carregar_fontes(raiz):
    raiz = Path(raiz)
    rota_path = raiz / "agentes" / "roteamento.yaml"
    try:
        rota = yaml.safe_load(rota_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as erro:
        raise ValueError(f"Roteamento YAML inválido: {erro}") from erro
    agentes = rota.get("agentes") if isinstance(rota, dict) else None
    if not isinstance(agentes, dict) or set(agentes) != PAPEIS:
        raise ValueError("O roteamento deve definir exatamente os sete agentes aprovados")

    definicoes = {}
    for papel in sorted(PAPEIS):
        caminho = raiz / "agentes" / f"{papel}.md"
        texto = caminho.read_text(encoding="utf-8")
        secoes = set(re.findall(r"(?m)^##\s+(.+?)\s*$", texto))
        faltantes = [secao for secao in SECOES_OBRIGATORIAS if secao not in secoes]
        if faltantes:
            raise ValueError(
                f"{caminho.relative_to(raiz)} sem campos da seção 4: "
                + ", ".join(faltantes)
            )
        definicoes[papel] = texto.rstrip() + "\n"
    runtimes = rota.get("runtimes", {})
    if any(runtime not in runtimes for runtime in DESTINOS):
        raise ValueError("O roteamento deve declarar Claude Code e Cursor")
    return rota, definicoes


def _hash_fonte(rota, papel, runtime, definicao):
    dados_agente = {
        chave: valor
        for chave, valor in rota["agentes"][papel].items()
        if chave != "metadados"
    }
    envelope = {
        "definicao": definicao,
        "agente": dados_agente,
        "skill_ref": rota["runtimes"][runtime]["skill_ref"],
    }
    serializado = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256(serializado)


def _skills_fixos(agente):
    return sorted(set(_nomes_skills(agente.get("skills_databricks", []))))


def _skills_cursor(agente):
    valores = _skills_fixos(agente)
    valores.extend(_nomes_skills(agente.get("skills_condicionais", [])))
    return sorted(set(valores))


def _yaml_string(valor):
    return json.dumps(str(valor), ensure_ascii=False)


def _yaml_simples(valor):
    """Escalar sem aspas: o Cursor guarda as aspas no nome do subagente."""
    valor = str(valor)
    seguro = (valor == valor.strip() and not re.match(r"[-?:,\[\]{}#&*!|>'\"%@`]", valor) and
              ": " not in valor and " #" not in valor)
    if not seguro or yaml.safe_load(valor) != valor:
        raise ValueError(f"Valor exige aspas no frontmatter e nao e aceito pelo Cursor: {valor!r}")
    return valor


def _frontmatter(rota, papel, runtime):
    agente = rota["agentes"][papel]
    linhas = [
        "---",
        f"name: {_yaml_simples(papel)}",
        f"description: {_yaml_simples(agente['responsabilidade'])}",
    ]
    if runtime == "claude_code":
        linhas.append("tools: [" + ", ".join(FERRAMENTAS_CLAUDE[papel]) + "]")
        linhas.append("model: inherit")
        skills = _skills_fixos(agente)
        linhas.append("skills:")
        linhas.extend(f"  - {_yaml_string('databricks:databricks-' + skill)}" for skill in skills)
    else:
        linhas.append("model: inherit")
    linhas.append("---\n")
    return "\n".join(linhas)


def _corpo(rota, papel, runtime, definicao):
    if runtime == "claude_code":
        return definicao
    skills = _skills_cursor(rota["agentes"][papel])
    linhas = [definicao.rstrip(), ""]
    if papel in VINCULO_CURSOR:
        linhas.extend([VINCULO_CURSOR[papel], ""])
    linhas += [
        "## Referências de skills no Cursor",
        "",
        "Leia somente as skills pertinentes ao gatilho, a partir do workspace:",
    ]
    linhas.extend(f"- `.agents/skills/databricks-{skill}/SKILL.md`" for skill in skills)
    linhas.append(
        "- Skills variáveis ficam em `.agents/skills/databricks-<nome>/SKILL.md`."
    )
    return "\n".join(linhas) + "\n"


def gerar(raiz=RAIZ, runtime=None):
    """Retorna caminhos relativos e conteúdos, sem gravar arquivos."""
    if runtime is not None and runtime not in DESTINOS:
        raise ValueError(f"Runtime desconhecido: {runtime}")
    raiz = Path(raiz)
    rota, definicoes = _carregar_fontes(raiz)
    runtimes = (runtime,) if runtime else tuple(DESTINOS)
    resultado = {}
    for nome_runtime in runtimes:
        for papel in sorted(PAPEIS):
            fonte = _hash_fonte(rota, papel, nome_runtime, definicoes[papel])
            cabecalho = _frontmatter(rota, papel, nome_runtime)
            corpo = _corpo(rota, papel, nome_runtime, definicoes[papel])
            payload = (cabecalho + corpo).encode("utf-8")
            marcador = (
                f"<!-- esteira-agentes source={fonte} "
                f"payload={_sha256(payload)} -->\n"
            )
            caminho = Path(DESTINOS[nome_runtime]) / f"{papel}.md"
            resultado[caminho.as_posix()] = (cabecalho + marcador + corpo)
    return resultado


def _integridade_gerado(conteudo):
    correspondencia = MARCADOR.search(conteudo)
    if not correspondencia:
        return None
    payload = conteudo[: correspondencia.start()] + conteudo[correspondencia.end() :]
    if _sha256(payload) != correspondencia.group(2).decode("ascii"):
        return None
    return correspondencia.group(1).decode("ascii")


def verificar(raiz=RAIZ):
    """Compara todos os arquivos nativos existentes com a geração atual."""
    raiz = Path(raiz)
    resultados = []
    divergencias = []
    for relativo, esperado in gerar(raiz).items():
        caminho = raiz / Path(relativo)
        if not caminho.exists():
            resultados.append(f"AUSENTE: {relativo}")
            continue
        atual = caminho.read_bytes()
        if atual == esperado.encode("utf-8"):
            resultados.append(f"OK: {relativo}")
        else:
            resultados.append(f"DIVERGENTE: {relativo}")
            divergencias.append(relativo)
    return not divergencias, resultados


def _gravar_com_backup(caminho, anterior, novo):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if (caminho.read_bytes() if caminho.exists() else None) != anterior:
        raise RuntimeError(f"Arquivo mudou durante a instalação: {caminho}")
    if anterior is not None:
        sufixo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = caminho.with_name(f"{caminho.name}.backup.{sufixo}")
        with backup.open("xb") as arquivo:
            arquivo.write(anterior)
    descritor, temporario = tempfile.mkstemp(
        prefix="agente_", suffix=".tmp", dir=caminho.parent
    )
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(novo)
        if (caminho.read_bytes() if caminho.exists() else None) != anterior:
            raise RuntimeError(f"Arquivo mudou durante a instalação: {caminho}")
        os.replace(temporario, caminho)
    finally:
        if Path(temporario).exists():
            Path(temporario).unlink()


def instalar(runtime, raiz=RAIZ):
    """Instala os sete arquivos de um runtime, protegendo conteúdo manual."""
    if runtime not in DESTINOS:
        raise ValueError(f"Runtime desconhecido: {runtime}")
    raiz = Path(raiz)
    candidatos = gerar(raiz, runtime)
    anteriores = {}
    for relativo, texto in candidatos.items():
        caminho = raiz / Path(relativo)
        anterior = caminho.read_bytes() if caminho.exists() else None
        novo = texto.encode("utf-8")
        if anterior is not None and anterior != novo and _integridade_gerado(anterior) is None:
            raise ValueError(
                f"Divergência manual detectada; arquivo preservado: {caminho}"
            )
        anteriores[caminho] = anterior

    instalados = []
    for relativo, texto in candidatos.items():
        caminho = raiz / Path(relativo)
        novo = texto.encode("utf-8")
        anterior = anteriores[caminho]
        if (caminho.read_bytes() if caminho.exists() else None) != anterior:
            raise RuntimeError(f"Arquivo mudou durante a instalação: {caminho}")
        if anterior == novo:
            instalados.append(caminho)
            continue
        _gravar_com_backup(caminho, anterior, novo)
        instalados.append(caminho)
    return instalados


def mostrar(raiz=RAIZ):
    blocos = []
    for relativo, conteudo in gerar(raiz).items():
        blocos.append(f"# {relativo}\n{conteudo.rstrip()}")
    return "\n\n".join(blocos) + "\n"


def main(argv=None, raiz=RAIZ):
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--verificar", action="store_true", help="Confere os arquivos nativos existentes")
    grupo.add_argument("--instalar", choices=tuple(DESTINOS), metavar="RUNTIME")
    args = parser.parse_args(argv)
    try:
        if args.verificar:
            ok, resultados = verificar(raiz)
            print("\n".join(resultados))
            return 0 if ok else 1
        if args.instalar:
            destinos = instalar(args.instalar, raiz)
            for caminho in destinos:
                print(caminho)
            return 0
        print(mostrar(raiz), end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError, RuntimeError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
