# Cursor

Adaptador principal. Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.cursor/hooks.json`, gerada com `py -3 adaptadores/gerenciar.py cursor --instalar` (`--plataforma posix` no POSIX).
- `beforeShellExecution` e `preToolUse` (matcher `Shell`) têm `failClosed: true`. A guarda usa o `cwd` do evento de shell.
- `sessionStart` (só em chat novo) informa o ID da sessão pelo contexto adicional e por `ESTEIRA_SESSAO`, que vale no ambiente dos hooks, não no shell do agente, e manda ler o `AGENTS.md`.
- `preToolUse`, `postToolUse` e `postToolUseFailure` registram só as verificações declaradas no contrato da fatia ativa. O `preToolUse` exige diretório absoluto em `tool_input.cwd` (Cursor 3.17.8) ou `working_directory` (versões anteriores); o diretório da sessão não serve. Com `cwd` vazio, a verificação declarada é negada com a orientação de preencher o campo; fora das verificações do contrato, a chamada passa sem registro. Comando de terminal digitado à mão não gera evento.
- Sucesso vem do `exitCode` de `postToolUse` (`campo_resultado`). Exit diferente de zero vem do texto `Command failed with exit code N` de `postToolUseFailure` com `failure_type: error` (`texto_falha`). Negação, timeout ou texto inesperado ficam inconclusivos e nunca viram prova de sucesso.
- `stop` pede correção do fecho em até duas continuações (`loop_limit: 2`). Não bloqueia texto já exibido.
- Um `plan` literal declarado no contrato, com exit 0, gera o recibo que a guarda de deploy consulta.
- Confira: Customize, Hooks e o canal de saída Hooks. Abra `user-harness-esteira/` como workspace.

Uso da prova: [evidencia/uso.md](../../evidencia/uso.md).

## Sondagem P0.5 (2026-10-05)

Cursor 3.17.8 (user setup), app interativo, Windows, numa worktree temporária com a guarda real, um hook de registro em todos os eventos de agente e o subagente `sonda`. Bruto em `.execucoes/sondagens/brutos/cursor/2026-10-05_cursor-3.17.8/` e relatório em `.execucoes/sondagens/cursor.json`, ambos fora do Git; este resumo é o registro versionado.

- Frontmatter: `name`, `description` e `model: inherit` funcionam. `inherit` não preservou a variante do modelo (principal `grok-4.7`, subagente `grok-4.7-high-fast`). `/sonda` vira uma chamada `Task` do principal.
- O subagente recebe o `AGENTS.md` e enxerga as skills `databricks-*` sem prefixo.
- Os hooks de shell (`preToolUse`, `beforeShellExecution`, `postToolUse`, `postToolUseFailure`) disparam no subagente com `conversation_id` próprio, diferente do principal, e sem `subagent_id` ou `parent_conversation_id`.
- `subagentStart` e `subagentStop` chegam na conversa do principal, com `subagent_id` igual ao `tool_use_id` do `preToolUse(Task)`, mas sem o `conversation_id` do subagente. A única ligação observável é o transcript do principal (`transcript_path`), que guarda `subagents/<conversation_id do subagente>.jsonl`. Os contadores `message_count` e `tool_call_count` do `subagentStop` vieram 0 e não são confiáveis.
- `cwd` chega vazio em `tool_input` e em `beforeShellExecution` quando o agente não informa o diretório. Não há `working_directory`; o adaptador passou a ler `tool_input.cwd`.
- Sucesso: `postToolUse` com `tool_output` `{output, exitCode: 0}`; a saída vem em `output`, não em `stdout`/`stderr`. Saída diferente de zero chega só em `postToolUseFailure`, como texto (`Command failed with exit code N`), sem campo numérico. Negação por hook: `failure_type: permission_denied`.
- `stop` com `followup_message` faz o principal continuar (`loop_count` 1). Não dispara para o subagente.
- `sessionStart` só dispara em chat novo (no chat reaproveitado não disparou). O `ESTEIRA_SESSAO` que ele devolve chega ao ambiente dos hooks seguintes, não ao shell do agente; o agente recebe o ID da sessão pelo contexto adicional.
- Com o diretório informado pelo agente, `tool_input.cwd` e `beforeShellExecution.cwd` chegam com o caminho absoluto.
- A guarda negou no subagente (`cwd-bundle/comando_nao_suportado`), sem executar.
- Não sondados: `tools`, `skills`, `readonly` e `is_background` no frontmatter, subagente paralelo ou aninhado, interrupção, timeout e leitura de `.claude/agents/` pelo Cursor.
