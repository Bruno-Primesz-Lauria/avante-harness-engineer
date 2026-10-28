# Adaptadores

O núcleo define a política ([guardas](../guardas/README.md)). Cada runtime traduz seu evento para a mesma guarda. O Cursor é o adaptador principal. Mapa do código, protocolo e limites: [arquitetura](arquitetura.md).

## Núcleo portátil

Todos os runtimes podem usar `prova.py verificar` para testes locais e `--execucao ID retomar` para continuidade. Hooks acrescentam observação e controle nas chamadas cobertas. Nas novas execuções, os papéis são delegações opcionais; autorização, ambiente/paridade, diagnóstico, revisão e superfície são requisitos próprios da execução. Veja [o fluxo comum](../evidencia/uso.md#execução-portátil).

A tabela descreve a coleta automática dos hooks. O Codex produz provas pelo executor comum mesmo sem coleta automática. As referências abaixo a agentes obrigatórios são do fluxo legado: a política atual conserva essas listas em `agentes_legados` para execuções antigas, enquanto novas execuções usam `execucao_portatil: true` e `agentes_obrigatorios: {}`. Testes locais de continuidade não substituem observação real em cada IDE.

| Runtime | Evento | O que guarda | Prova coletada | Instalar e conferir |
|---|---|---|---|---|
| [Cursor](cursor/README.md) | `beforeShellExecution` (falha fecha) | Shell: cwd, target, plan e deploy | `sessionStart`, `preToolUse`, `postToolUse`, `postToolUseFailure` e `stop` | `gerenciar.py cursor --instalar`. Customize, Hooks e canal Hooks. |
| [Claude Code](claude_code/README.md) | `PreToolUse` em `Bash` e `PowerShell` | Idem | `SessionStart`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop` e `SubagentStop` | `gerenciar.py claude_code --instalar`. `/hooks`. |
| [Codex](codex/README.md) | `PreToolUse` em `Bash` | Idem | Nenhuma | `gerenciar.py codex --instalar`. Revisar e confiar em `/hooks`. |
| [OpenCode](opencode/README.md) | `tool.execute.before` em `bash` (falha fecha) | Idem | Bash/Task, `session.created`, `shell.env` e `session.idle`; testes locais, observação integrada pendente | `gerenciar.py opencode --instalar`. Nova sessão. |

Sem `--instalar`, `gerenciar.py` só mostra a configuração. Comandos a partir da raiz do harness: `py -3 adaptadores/gerenciar.py <runtime> [--instalar]`.

Instalar não prova ativação. Em cada runtime, observe uma negação real antes do efeito.

Estado atual dos arquivos de configuração: Cursor, Claude Code e OpenCode instalados; Codex não instalado (`.codex/hooks.json` sem handler).

## Versões observadas

| Runtime | Versão |
|---|---|
| Cursor | 3.17.8, 3.19.19 |
| Claude Code | 2.1.283, 2.1.289, 2.1.292 |
| Codex CLI | 0.158.0 |
| OpenCode | 1.18.35 (2026-10-13) |

## Equivalência entre runtimes

Um hook de um produto não vale como o de outro. Guarda obrigatória indisponível impede a operação que depende dela. Tarefa segura e independente continua.

| Capacidade | Claude Code | Cursor, Codex, OpenCode |
|---|---|---|
| Instruções | `CLAUDE.md`. Confira o que carrega. | `AGENTS.md`. Confira o que carrega. |
| Pergunta | Cartão, se existir. Senão, texto. | Ferramenta de pergunta ou texto. |
| Agentes do fluxo | Sete papéis em `.claude/agents/`, gerados de [`agentes/`](../agentes/), observados em sessão real. Obrigatórios nas trilhas de `agentes_obrigatorios.claude_code`, hoje `manutencao`, `correcao`, `novo`, `docs` e `review`; o runtime vem de `CLAUDE_CODE_SESSION_ID`. | Cursor: sete papéis em `.cursor/agents/`, observados em sessão real e obrigatórios nas trilhas de `agentes_obrigatorios.cursor`, hoje `manutencao`, `correcao`, `novo`, `docs` e `review`; passe `--runtime cursor` ao `prova.py`. Codex continua agente único. OpenCode tem sete definições geradas em `.opencode/agents/`; a coleta de shell e subagentes está implementada e testada localmente, mas a observação integrada e o gate G2 seguem pendentes. O plugin injeta `ESTEIRA_RUNTIME=opencode`; `prova.py` detecta esse runtime e ainda aceita `--runtime opencode` explícito. Codex e OpenCode continuam fora da chave de produção. |
| Persistência | Árvore de [`evidencia/layout.md`](../evidencia/layout.md), sob a raiz configurada. | Idem. |

Subagentes: definição neutra em [`agentes/`](../agentes/); as versões nativas ficam em `.cursor/agents/`, `.claude/agents/` e `.opencode/agents/`. Não inclua trilha em `agentes_obrigatorios` de um runtime antes de seus agentes estarem instalados e observados (G2). Instalação e observação por runtime ficam nos metadados de [`agentes/roteamento.yaml`](../agentes/roteamento.yaml); gates e histórico, no painel do [plano](../PLANO-AGENTES-TRILHAS.md#painel). OpenCode 1.18.35 carregou `.agents/skills/databricks-core/` pela ferramenta nativa `skill`, inclusive no subagente.
