# Adaptadores

O núcleo define a política ([guardas](../guardas/README.md)). Cada runtime traduz seu evento para a mesma guarda. O Cursor é o adaptador principal. Mapa do código, protocolo e limites: [arquitetura](arquitetura.md).

| Runtime | Evento | O que guarda | Prova coletada | Instalar e conferir |
|---|---|---|---|---|
| [Cursor](cursor/README.md) | `beforeShellExecution` (falha fecha) | Shell: cwd, target, plan e deploy | `sessionStart`, `preToolUse`, `postToolUse`, `postToolUseFailure` e `stop` | `gerenciar.py cursor --instalar`. Customize, Hooks e canal Hooks. |
| [Claude Code](claude_code/README.md) | `PreToolUse` em `Bash` e `PowerShell` | Idem | Nenhuma | `gerenciar.py claude_code --instalar`. `/hooks`. |
| [Codex](codex/README.md) | `PreToolUse` em `Bash` | Idem | Nenhuma | `gerenciar.py codex --instalar`. Revisar e confiar em `/hooks`. |
| [OpenCode](opencode/README.md) | `tool.execute.before` em `bash` | Idem | Nenhuma | `gerenciar.py opencode --instalar`. Nova sessão. |

Sem `--instalar`, `gerenciar.py` só mostra a configuração. Comandos a partir da raiz do harness: `py -3 adaptadores/gerenciar.py <runtime> [--instalar]`.

Instalar não prova ativação. Em cada runtime, observe uma negação real antes do efeito.

Estado atual dos arquivos de configuração: Cursor, Claude Code e OpenCode instalados; Codex não instalado (`.codex/hooks.json` sem handler).

## Versões observadas

| Runtime | Versão |
|---|---|
| Cursor | 3.17.8 |
| Claude Code | 2.1.289 |
| Codex CLI | 0.158.0 |
| OpenCode | 1.18.15 |

## Equivalência entre runtimes

Um hook de um produto não vale como o de outro. Guarda obrigatória indisponível impede a operação que depende dela. Tarefa segura e independente continua.

| Capacidade | Claude Code | Cursor, Codex, OpenCode |
|---|---|---|
| Instruções | `CLAUDE.md`. Confira o que carrega. | `AGENTS.md`. Confira o que carrega. |
| Pergunta | Cartão, se existir. Senão, texto. | Ferramenta de pergunta ou texto. |
| Revisor | Subagente, se existir e estiver autorizado. | Delegação opcional. Sem suporte, verifique por critério objetivo. |
| Persistência | Árvore de [`evidencia/layout.md`](../evidencia/layout.md), sob a raiz configurada. | Idem. |

Não implementado: skills e subagentes.
