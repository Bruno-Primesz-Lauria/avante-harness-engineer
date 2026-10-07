# Claude Code

Visão geral e tabela: [adaptadores](../README.md). Estado dos gates e histórico: painel do [plano](../../PLANO-AGENTES-TRILHAS.md#painel).

- Instruções: `CLAUDE.md` importa `@AGENTS.md`. Confira a carga numa sessão nova.
- Configuração: `.claude/settings.json`, gerada com `py -3 adaptadores/gerenciar.py claude_code --instalar`. Mescla com o que já existe (permissões e outros hooks ficam). Agentes em `.claude/agents/`, gerados por `py -3 adaptadores/gerar_agentes.py --instalar claude_code`.
- `SessionStart` identifica a sessão pelo `session_id`, igual a `CLAUDE_CODE_SESSION_ID`, e orienta `prova.py --sessao <ID>`: o `--sessao` só lê `ESTEIRA_SESSAO`, que o Claude Code não define, e o runtime `claude_code` é detectado por `CLAUDE_CODE_SESSION_ID`. No Windows o hook roda em `powershell` e usa `CLAUDE_PROJECT_DIR` para achar `adaptadores/entrada.py`.
- `PreToolUse` cobre Bash/PowerShell para a guarda e a prova, e Agent para marcar o início de uma chamada. `PostToolUse` coleta sucesso de shell e o retorno de Agent; `PostToolUseFailure` coleta falhas de shell. `SubagentStop` fecha a chamada de Agent lançada em segundo plano.
- Quando registra a chamada de um papel, o `PostToolUse(Agent)` devolve ao coordenador, em `additionalContext`, o `agente_id` observado (`tool_response.agentId`). É o ID que a revisão do refute, o `sandbox` do dab e a paridade do test citam. Tipo fora dos sete papéis, papel fora do plano, status diferente de `completed` ou `async_launched` ou retorno sem `agentId` não devolvem contexto nem registram a chamada.
- Agent em segundo plano (`status: async_launched`, sem `agentType`): o `PostToolUse(Agent)` já devolve o `agente_id` ao coordenador, mas a janela de superfície continua aberta. O registro da chamada vem no `SubagentStop` do mesmo `agent_id`, com `agent_type` igual ao papel lançado. `SubagentStop` de agente interno (`agent_type` vazio) é ignorado. Se o registro falha (fora da ordem, por exemplo), o hook não bloqueia o subagente: fecha a janela e avisa em `systemMessage`.
- O shell do subagente chega com o `session_id` do principal e mais `agent_id`, que vira o `agente_id` da prova; não depende de janela única. As janelas de `Agent` alimentam a vigilância de superfície (C5): sobreposição torna a autoria inconclusiva.
- O `cwd` do envelope é da sessão e não vale como prova. A guarda interpreta somente `Set-Location -LiteralPath '...' -ErrorAction Stop;` (PowerShell) ou `cd -- '...' &&` (Bash). Uma verificação declarada sem esse prefixo é negada com orientação para informar o diretório.
- Um `plan` literal declarado no contrato e concluído com sucesso grava o recibo de plan, como no Cursor; o prefixo de diretório é retirado antes de interpretar o comando.
- `Stop` confere a fatia e bloqueia uma saída sem fecho válido. Quando `stop_hook_active` é `true`, ou quando `background_tasks` traz um subagente `running`, não bloqueia.
- Papéis obrigatórios nas trilhas de `agentes_obrigatorios.claude_code` (hoje `manutencao`, `correcao`, `novo`, `docs` e `review`). Relato de agente não substitui prova observada.
- Observação (O-CC): kit em [`avaliacao/observacao-claude-code/`](../../avaliacao/observacao-claude-code/roteiro.md).
- Confira: `/hooks` e `/agents`.

## Comportamento observado do runtime

Observado no CLI 2.1.283 e 2.1.289 (headless) e 2.1.292 (interativo), Windows, hooks em PowerShell.

- Frontmatter: `name`, `description`, `tools`, `model: inherit` e `skills` são efetivos. A skill listada é pré-carregada no subagente, inclusive com escopo de plugin (`databricks:databricks-core`).
- O subagente recebe `CLAUDE.md`/`AGENTS.md` e as skills do plugin `databricks:databricks-*`. Skills de `.agents/skills/` não aparecem no Claude Code.
- `PreToolUse`, `PostToolUse` e `PostToolUseFailure` disparam dentro do subagente, com o `session_id` da sessão principal e mais `agent_id` e `agent_type`. Nenhuma variável de ambiente distingue o subagente.
- `SubagentStart` não traz `tool_use_id`. A chamada liga ao subagente pelo `PostToolUse(Agent)`, em que `tool_response.agentId` é o `agent_id`.
- No 2.1.292, o `Agent` roda em segundo plano mesmo sem `run_in_background`. O `PostToolUse(Agent)` chega logo depois do `SubagentStart`, com `isAsync: true`, `status: async_launched` e `agentId`, sem `agentType` e sem o conteúdo. O fim chega só no `SubagentStop`, com `agent_id` e `agent_type` e sem status de conclusão.
- O `Stop` e o `SubagentStop` trazem `background_tasks` (`id`, `type: subagent`, `status`, `agent_type`). O `Stop` do principal dispara enquanto o subagente ainda roda.
- Agentes internos do Claude Code disparam `SubagentStop` com `agent_type` vazio, sem `SubagentStart` nem `Agent`.
- `CLAUDE_CODE_SESSION_ID`, no ambiente do hook e no shell, é igual ao `session_id` e serve para `--sessao`.
- Sucesso chega em `PostToolUse`, sem exit code. Saída diferente de zero chega só em `PostToolUseFailure`, e o código vem apenas como texto na primeira linha de `error` (`Exit code N`). O formato é igual no Bash e no PowerShell, no principal e no subagente.
- `Stop` com `decision: block` faz o principal continuar. O `Stop` seguinte vem com `stop_hook_active: true`. O `Stop` não dispara para o subagente, que tem o seu próprio `SubagentStop`.
- A guarda nega dentro do subagente sem executar o comando.
- Não sondados: Desktop, subagente aninhado, interrupção e timeout.
