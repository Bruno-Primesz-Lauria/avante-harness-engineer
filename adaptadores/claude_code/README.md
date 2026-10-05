# Claude Code

Visão geral e tabela: [adaptadores](../README.md).

- Instruções: `CLAUDE.md` importa `@AGENTS.md`. Confira a carga numa sessão nova.
- Configuração: `.claude/settings.json`, gerada com `py -3 adaptadores/gerenciar.py claude_code --instalar`. Mescla com o que já existe (permissões e outros hooks ficam).
- `SessionStart` identifica a sessão pelo `session_id`, igual a `CLAUDE_CODE_SESSION_ID`. No Windows o hook roda em `powershell` e usa `CLAUDE_PROJECT_DIR` para achar `adaptadores/entrada.py`.
- `PreToolUse` cobre Bash/PowerShell para a guarda e a prova, e Agent para marcar o início de uma chamada. `PostToolUse` coleta sucesso de shell e o retorno de Agent; `PostToolUseFailure` coleta falhas de shell.
- O `cwd` do envelope é da sessão e não vale como prova. A guarda interpreta somente `Set-Location -LiteralPath '...' -ErrorAction Stop;` (PowerShell) ou `cd -- '...' &&` (Bash). Uma verificação declarada sem esse prefixo é negada com orientação para informar o diretório.
- `Stop` confere a fatia e bloqueia uma saída sem fecho válido. Quando `stop_hook_active` é `true`, não bloqueia de novo.
- O adaptador e os testes foram exercitados sobre fixtures com payloads P0.4. O evento P0.4 de Agent usou o tipo `sonda`, fora dos sete papéis, e não foi registrado como chamada.
- D-CC está implementado sobre fixture e conclui depois de G1/B2; nenhuma observação de uso real foi feita pelo adaptador. Até G2, o `fechar` não comprova `DONE` no Claude Code. Feche a fatia como `BLOCKED`, com motivo e condição de retomada, ou execute-a no Cursor. Um relato de agente não substitui a prova observada.
- Confira: `/hooks`.

## Sondagem P0.4 (2026-10-04, refeita em 2026-10-05)

Primeira observação no CLI 2.1.283, em duas sessões. Os brutos dela não foram preservados. Refeita em 2026-10-05 no CLI 2.1.289, headless, Windows, hooks em PowerShell, numa worktree temporária com a guarda real; todos os itens abaixo se repetiram. Bruto em `.execucoes/sondagens/brutos/claude_code/2026-10-05_cli-2.1.289/` e relatório em `.execucoes/sondagens/claude_code.json`, ambos fora do Git; este resumo é o registro versionado.

- Frontmatter: `name`, `description`, `tools`, `model: inherit` e `skills` são efetivos. A skill listada é pré-carregada no subagente, inclusive com escopo de plugin (`databricks:databricks-core`).
- O subagente recebe `CLAUDE.md`/`AGENTS.md` e as skills do plugin (31 `databricks:databricks-*` na 2.1.289). Skills de `.agents/skills/` não aparecem no Claude Code.
- `PreToolUse`, `PostToolUse` e `PostToolUseFailure` disparam dentro do subagente, com o `session_id` da sessão principal e mais `agent_id` e `agent_type`. Nenhuma variável de ambiente distingue o subagente.
- `SubagentStart` não traz `tool_use_id`. A chamada liga ao subagente pelo `PostToolUse(Agent)`, em que `tool_response.agentId` é o `agent_id`.
- `CLAUDE_CODE_SESSION_ID`, no ambiente do hook e no shell, é igual ao `session_id` e serve para `--sessao`.
- Sucesso chega em `PostToolUse`, sem exit code. Saída diferente de zero chega só em `PostToolUseFailure`, e o código vem apenas como texto na primeira linha de `error` (`Exit code N`). O formato é igual no Bash e no PowerShell, no principal e no subagente.
- `Stop` com `decision: block` faz o principal continuar. O `Stop` seguinte vem com `stop_hook_active: true`. O `Stop` não dispara para o subagente, que tem o seu próprio `SubagentStop`.
- A guarda negou dentro do subagente (`cwd-bundle/comando_nao_suportado`), sem executar o comando.
- Não sondados: Desktop 2.1.286, modo interativo, subagente em segundo plano ou aninhado, interrupção e timeout.
