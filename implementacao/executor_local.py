"""Executa testes locais declarados, sem shell, e entrega o resultado ao núcleo."""
import os
from pathlib import Path
import shlex
import subprocess
from uuid import uuid4

from formas import exigir
from provas import TIPOS_TESTE, ler


def argumentos_locais(raiz, cwd, comando):
    """Interface restrita a unittest, pytest e scripts de teste Python/Node locais."""
    exigir(not any(c in comando for c in ("\n", "\r", "|", ";", "&", ">", "<", "`", "$")),
           "Executor local nao aceita shell, encadeamento ou expansao")
    partes = shlex.split(comando, posix=os.name != "nt")
    partes = [p[1:-1] if len(p) > 1 and p[0] == p[-1] and p[0] in "\"'" else p for p in partes]
    exigir(bool(partes), "Comando vazio")
    exigir(not any("databricks" in p.casefold() for p in partes), "Executor local nao executa Databricks")
    executavel = Path(partes[0].replace("\\", "/")).name.casefold()
    python = executavel in {"py", "py.exe", "python", "python.exe", "python3", "python3.exe"}
    node = executavel in {"node", "node.exe"}
    exigir(python or node, "Executor aceita somente testes Python ou Node locais")
    if "/" in partes[0] or "\\" in partes[0]:
        exe = (cwd / partes[0]).resolve()
        exigir(exe.is_relative_to(raiz / ".venv"), "Interpretador deve ser o do PATH ou do .venv local")
    args = partes[1:]
    if executavel in {"py", "py.exe"}:
        exigir(args[:1] == ["-3"], "Use py -3")
        args = args[1:]
    exigir(bool(args), "Teste ausente")
    if python and args[0] == "-m":
        exigir(len(args) > 1 and args[1] in {"unittest", "pytest"}, "Modulo local nao permitido")
        exigir(not any(a in {"--override-ini", "-p"} for a in args[2:]) or args[1] == "unittest",
               "Plugins e configuracao executavel nao sao aceitos pelo executor")
    else:
        resto = args
        while resto and resto[0] == "-B":
            resto = resto[1:]
        exigir(bool(resto), "Teste ausente")
        script = (cwd / resto[0]).resolve()
        exigir(script.is_relative_to(raiz) and script.is_file(), "Script local ausente")
        ref = script.relative_to(raiz)
        exigir(any(p in {"testes", "tests"} for p in ref.parts[:-1]) and
               script.suffix in ({".py"} if python else {".js", ".mjs", ".cjs"}),
               "Declare um script dentro de testes/ ou tests/")
    return partes


def verificar(provas, criterio_id, timeout=300):
    exigir(type(timeout) is int and 1 <= timeout <= 3600, "Timeout deve estar entre 1 e 3600 segundos")
    pasta = provas.pasta()
    exigir(pasta is not None, "Nenhuma fatia ativa")
    provas.estado(pasta)
    contrato = ler(pasta / "contrato.yaml")["dados"]
    criterio = next((c for c in contrato["aceite"] if c["id"] == criterio_id), None)
    exigir(criterio is not None and criterio["tipo"] in TIPOS_TESTE, "Executor aceita apenas criterios de teste locais")
    v = criterio["verificacao"]
    cwd = provas.cwd(v["cwd"])
    args = argumentos_locais(provas.raiz, cwd, v["comando"])
    chamada = "local_" + uuid4().hex
    exigir(provas.antes(chamada, v["comando"], str(cwd), "executor_local", runtime=provas.runtime),
           "Verificacao nao corresponde ao contrato")
    codigo, saida = None, "Execucao interrompida antes do resultado"
    try:
        resultado = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=timeout, check=False)
        codigo = resultado.returncode
        saida = resultado.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as erro:
        saida = (erro.stdout or b"").decode("utf-8", errors="replace") + "\n[executor] Timeout; resultado inconclusivo"
    except OSError as erro:
        saida = "[executor] Nao foi possivel iniciar o teste: " + str(erro)
    finally:
        prova = provas.depois(chamada, v["comando"], codigo, saida, "campo_resultado" if codigo is not None else None)
    return prova


def recuperar_local(provas, chamada, motivo):
    """Após conferir o fim do processo, encerra uma captura local interrompida como inconclusiva."""
    exigir(isinstance(motivo, str) and motivo.strip(), "Informe o motivo e a conferencia do processo encerrado")
    pasta = provas.pasta()
    exigir(pasta is not None, "Nenhuma fatia ativa")
    estado = provas.estado(pasta)
    pendente = estado["pendente"]
    exigir(pendente is not None and pendente["chamada"] == chamada and chamada.startswith("local_"),
           "Chamada local pendente nao encontrada")
    contrato = ler(pasta / "contrato.yaml")["dados"]
    criterio = next(c for c in contrato["aceite"] if c["id"] == pendente["criterio"])
    exigir(criterio["tipo"] in TIPOS_TESTE, "Recuperacao aceita somente testes locais")
    v = criterio["verificacao"]
    argumentos_locais(provas.raiz, provas.cwd(v["cwd"]), v["comando"])
    log = pasta / f"tentativas/{estado['tentativa']:03d}/logs/resultado.txt"
    saida = log.read_text(encoding="utf-8") if log.is_file() else "[executor] Processo encerrado sem resultado: " + motivo
    return provas.depois(chamada, v["comando"], None, saida)
