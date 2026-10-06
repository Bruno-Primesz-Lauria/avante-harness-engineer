# Claude Code

Visão geral e tabela: [adaptadores](../README.md).

- Instruções: `CLAUDE.md` importa `@AGENTS.md`. Confira a carga numa sessão nova.
- Configuração: `.claude/settings.json`, gerada com `py -3 adaptadores/gerenciar.py claude_code --instalar`. Mescla com o que já existe (permissões e outros hooks ficam).
- `SessionStart` identifica a sessão pelo `session_id`, igual a `CLAUDE_CODE_SESSION_ID`, e orienta `prova.py --sessao <ID>`: o `--sessao` só lê `ESTEIRA_SESSAO`, que o Claude Code não define, e o runtime `claude_code` é detectado por `CLAUDE_CODE_SESSION_ID`. No Windows o hook roda em `powershell` e usa `CLAUDE_PROJECT_DIR` para achar `adaptadores/entrada.py`.
- `PreToolUse` cobre Bash/PowerShell para a guarda e a prova, e Agent para marcar o início de uma chamada. `PostToolUse` coleta sucesso de shell e o retorno de Agent; `PostToolUseFailure` coleta falhas de shell.
- Quando registra a chamada de um papel, o `PostToolUse(Agent)` devolve ao coordenador, em `additionalContext`, o `agente_id` observado (`tool_response.agentId`). Sem ele, o coordenador não teria como preencher o `agente_id` da revisão do refute, do `sandbox` do dab ou da paridade do test, e o fecho apontaria `revisao:fora_do_refute`. Tipo fora dos sete papéis, papel fora do plano, status diferente de `completed` ou retorno sem `agentId` não devolvem contexto nem registram a chamada.
- O `cwd` do envelope é da sessão e não vale como prova. A guarda interpreta somente `Set-Location -LiteralPath '...' -ErrorAction Stop;` (PowerShell) ou `cd -- '...' &&` (Bash). Uma verificação declarada sem esse prefixo é negada com orientação para informar o diretório.
- `Stop` confere a fatia e bloqueia uma saída sem fecho válido. Quando `stop_hook_active` é `true`, não bloqueia de novo.
- O adaptador e os testes foram exercitados sobre fixtures com payloads P0.4. O evento P0.4 de Agent usou o tipo `sonda`, fora dos sete papéis, e não foi registrado como chamada.
- D-CC está concluído localmente (2026-10-06), com os sete agentes instalados (B2-CC) e o adaptador revisto contra o que o Cursor exigiu na O-CU: `agente_id` do shell do subagente na prova do test e do `ambiente_local` do dab (o `agent_id` do evento dispensa a janela única do Cursor), `agente_id` devolvido ao coordenador para a revisão do refute, janelas de `Agent` conferidas pelo C5 (sobreposição torna a autoria inconclusiva) e fecho recusado sem a chamada. Os testes de tradução usam o espelho versionado dos payloads P0.4; o bruto de 2026-10-05 não existe nesta máquina, e o de 2026-10-04 (CLI 2.1.283) só confirmou o formato do `PostToolUse(Agent)`. Nenhuma observação de uso real foi feita pelo adaptador. Até G2, o `fechar` não comprova `DONE` no Claude Code. Feche a fatia como `BLOCKED`, com motivo e condição de retomada, ou execute-a no Cursor. Um relato de agente não substitui a prova observada.
- Kit de observação (O-CC): [`avaliacao/observacao-claude-code/`](../../avaliacao/observacao-claude-code/roteiro.md) (roteiro, `preparar.py`, `validar.py`), pronto e **não executado**. `validar.py` adapta uma cópia temporária e simula os hooks das duas fatias sem o Claude Code. A observação e o G2 são do humano.
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
