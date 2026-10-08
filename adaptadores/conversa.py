"""Conversa continua por projeto (plano_conversa_continua.md): hooks do Claude Code, zoom e validacao.

Memoria pessoal em .execucoes/conversa/<projeto>/, fora do Git. A visao orienta e nunca e
regra, autorizacao nem prova. Os hooks nunca bloqueiam a sessao: erro vai para erros.jsonl.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))

from compactador import TETO_PADRAO, canal_padrao, compactar, desligado, erro
from conversas import Chat
import transcripts

DADOS = RAIZ / ".execucoes" / "conversa"
LIMITE_HOOK = 8_000

CABECALHO = """Conversa do projeto {projeto} (memória pessoal, advisory): {total} mensagens de todas as sessões, inclusive anteriores. Cada linha id+n|texto resume as n mensagens a partir de id; recentes finas, antigas grossas. Tipos: user, claude, tool, echo, work, note. Orienta, nunca é regra, autorização nem prova: código vivo, AGENTS.md e memoria/ prevalecem. Quando uma linha tocar o pedido e for vaga, abra antes de agir ou perguntar:
  {py} {cli} zoom <id> <n> --projeto {projeto}   (n=1 dá a mensagem inteira; date <id> dá a hora)
Visão completa: {visao}
"""


def projeto_de(cwd):
    """Nome da raiz Git do cwd: sessoes na raiz ou em subpastas caem no mesmo chat (DC-1)."""
    if not cwd:
        return None
    feito = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=5)
    raiz = feito.stdout.strip()
    if feito.returncode != 0 or not raiz:
        return None
    # Worktree que o app desktop cria para a sessao (<projeto>/.claude/worktrees/<nome>) e o mesmo projeto.
    principal, separador, _ = raiz.partition("/.claude/worktrees/")
    return Path(principal if separador else raiz).name


def abrir(dados, projeto):
    return Chat(Path(dados) / projeto)


def importar(chat, caminhos, sessao=""):
    """Importa o trecho novo de cada transcript, sob a trava do chat."""
    total = 0
    with chat.aberto():
        cursores = chat.estado.setdefault("cursores", {})
        ferramentas = chat.estado.setdefault("ferramentas", {})
        for caminho in caminhos:
            caminho = str(caminho)
            if not caminho or not os.path.exists(caminho):
                continue
            cursor = cursores.get(caminho, 0)
            mensagens, novo = transcripts.ler(caminho, cursor, ferramentas, sessao)
            total += len(chat.registrar(mensagens))
            cursores[caminho] = novo
    return total


def escrever_visao(chat):
    caminho = chat.pasta / "visao.txt"
    with chat.aberto():
        texto = chat.texto_visao("completa")
    caminho.write_text(f"<chat>\n{texto}\n</chat>\n", encoding="utf-8")
    return caminho


def texto_sessao(chat, projeto):
    with chat.aberto():
        cabecalho = CABECALHO.format(projeto=projeto, total=chat.total, py=sys.executable,
                                     cli=Path(__file__).resolve(), visao=chat.pasta / "visao.txt")
        return chat.sessao(LIMITE_HOOK, cabecalho)


def disparar_compactador(dados, projeto):
    """Processo desanexado: nova sessao e sem pipes, para o hook nao esperar."""
    if os.environ.get("CONVERSA_FILHA") or desligado(Path(dados) / projeto):
        return
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "compactar", "--projeto", projeto,
                      "--dados", str(dados)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)


def hook(evento, dados=DADOS):
    """Trata SessionStart, Stop e SessionEnd. Devolve o JSON de saida (ou {})."""
    if os.environ.get("CONVERSA_FILHA"):
        return {}
    projeto = projeto_de(evento.get("cwd"))
    if not projeto:
        return {}
    chat = abrir(dados, projeto)
    nome = evento.get("hook_event_name")
    transcript = evento.get("transcript_path") or ""
    sessao = evento.get("session_id") or ""
    try:
        if nome == "SessionStart":
            with chat.aberto():
                conhecidos = list(chat.estado.get("cursores", {}))
            importar(chat, conhecidos + ([transcript] if transcript not in conhecidos else []), sessao)
            escrever_visao(chat)
            texto = texto_sessao(chat, projeto)
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": texto}}
        if nome in ("Stop", "SessionEnd"):
            importar(chat, [transcript], sessao)
            if nome == "Stop":
                disparar_compactador(dados, projeto)
    except Exception as exc:  # noqa: BLE001 - hook nunca derruba a sessao
        erro(chat.pasta, None, f"{nome}: {type(exc).__name__}: {exc}")
    return {}


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest="acao", required=True)
    sub = {}
    for acao, ajuda in (("hook", "Evento do Claude Code no stdin (SessionStart, Stop, SessionEnd)"),
                        ("registrar", "Importa o trecho novo de transcripts"),
                        ("compactar", "Constroi os nos pendentes com o modelo"),
                        ("sessao", "Imprime a visao de sessao"),
                        ("visao", "Regenera visao.txt e imprime o caminho"),
                        ("zoom", "Abre a linha id+n"),
                        ("date", "Data, hora e sessao da mensagem id"),
                        ("validar", "Confere as invariantes do log, da arvore e das visoes")):
        sub[acao] = comandos.add_parser(acao, help=ajuda)
        sub[acao].add_argument("--dados", type=Path, default=DADOS)
        if acao != "hook":
            sub[acao].add_argument("--projeto", required=True)
    sub["registrar"].add_argument("transcripts", nargs="+")
    sub["compactar"].add_argument("--teto", type=int, default=TETO_PADRAO)
    sub["zoom"].add_argument("id", type=int)
    sub["zoom"].add_argument("n", type=int)
    sub["zoom"].add_argument("--pagina", type=int, default=1)
    sub["date"].add_argument("id", type=int)
    args = parser.parse_args(argv)

    if args.acao == "hook":
        try:
            evento = json.load(sys.stdin)
            saida = hook(evento, args.dados)
        except Exception:  # noqa: BLE001 - nem payload invalido derruba a sessao
            saida = {}
        if saida:
            print(json.dumps(saida, ensure_ascii=True))
        return 0

    chat = abrir(args.dados, args.projeto)
    if args.acao == "registrar":
        print(f"[conversa] {importar(chat, args.transcripts)} mensagem(ns) nova(s).")
    elif args.acao == "compactar":
        if desligado(chat.pasta):
            return 0
        trava = chat.pasta / "compactador.pid"
        chat.pasta.mkdir(parents=True, exist_ok=True)
        import fcntl
        with open(trava, "a+") as arq:
            try:
                fcntl.flock(arq, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0  # outro compactador ja esta rodando e pega a fila nova
            arq.seek(0)
            arq.truncate()
            arq.write(str(os.getpid()))
            arq.flush()
            try:
                feitos, falhas = compactar(chat, canal_padrao(chat.pasta), teto=args.teto)
            except Exception as exc:  # noqa: BLE001
                erro(chat.pasta, None, f"compactar: {exc}")
                return 1
            escrever_visao(chat)
        print(f"[conversa] {feitos} no(s) construido(s), {falhas} falha(s).")
    elif args.acao == "sessao":
        print(texto_sessao(chat, args.projeto))
    elif args.acao == "visao":
        print(escrever_visao(chat))
    elif args.acao == "zoom":
        with chat.aberto():
            resultado = chat.zoom(args.id, args.n)
        if args.n == 1:
            if resultado is None:
                print("[conversa] mensagem inexistente.", file=sys.stderr)
                return 1
            texto, pagina = resultado["text"], 10_000
            paginas = max(1, -(-len(texto) // pagina))
            trecho = texto[(args.pagina - 1) * pagina: args.pagina * pagina]
            print(f"{resultado['i']}|{resultado['kind']}|{resultado['date']}|sessao {resultado['sessao']}"
                  f"|pagina {args.pagina}/{paginas}\n{trecho}")
        else:
            for rotulo_no, texto in resultado:
                print(f"{rotulo_no}|{texto.replace(chr(10), ' ') if texto else '(não resumida: use zoom)'}")
    elif args.acao == "date":
        with chat.aberto():
            msg = chat.mensagem(args.id)
        if msg is None:
            return 1
        print(f"{msg['date']} sessao {msg['sessao']}")
    elif args.acao == "validar":
        with chat.aberto():
            erros = chat.validar()
            total = chat.total
        for item in erros:
            print(f"[conversa] {item}", file=sys.stderr)
        if erros:
            return 1
        print(f"[conversa] OK: {total} mensagem(ns), visoes contiguas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
