# Cursor

Adaptador principal. Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.cursor/hooks.json`, gerada com `py -3 adaptadores/gerenciar.py cursor --instalar` (`--plataforma posix` no POSIX).
- `beforeShellExecution` e `preToolUse` (matcher `Shell|Task`) têm `failClosed: true`. A guarda usa o `cwd` do evento de shell.
- `sessionStart` (só em chat novo) informa o ID da sessão pelo contexto adicional e por `ESTEIRA_SESSAO`, que vale no ambiente dos hooks, não no shell do agente, e manda ler o `AGENTS.md`.
- `preToolUse` para `Shell`, `postToolUse` e `postToolUseFailure` registram só as verificações declaradas no contrato da fatia ativa. O `preToolUse` exige diretório absoluto em `tool_input.cwd` (Cursor 3.17.8) ou `working_directory` (versões anteriores); o diretório da sessão não serve. Com `cwd` vazio, a verificação declarada é negada com a orientação de preencher o campo; fora das verificações do contrato, a chamada passa sem registro. Comando de terminal digitado à mão não gera evento.
- Sucesso vem do `exitCode` de `postToolUse` (`campo_resultado`). Exit diferente de zero vem do texto `Command failed with exit code N` de `postToolUseFailure` com `failure_type: error` (`texto_falha`). Negação, timeout ou texto inesperado ficam inconclusivos e nunca viram prova de sucesso.
- `stop` pede correção do fecho em até duas continuações (`loop_limit: 2`). Não bloqueia texto já exibido.
- Um `plan` literal declarado no contrato, com exit 0, gera o recibo que a guarda de deploy consulta.
- Confira: Customize, Hooks e o canal de saída Hooks. Abra `user-harness-esteira/` como workspace.

Uso da prova: [evidencia/uso.md](../../evidencia/uso.md).

## Sondagem P0.5 (2026-10-05)

Cursor 3.17.8 (user setup), app interativo, Windows, numa worktree temporária com a guarda real, um hook de registro em todos os eventos de agente e o subagente `sonda`. Bruto em `.execucoes/sondagens/brutos/cursor/2026-10-05_cursor-3.17.8/` e relatório em `.execucoes/sondagens/cursor.json`, ambos fora do Git; este resumo é o registro versionado.

- Frontmatter: `name`, `description` e `model: inherit` funcionam. Na primeira sessão O-CU (2026-10-05, mesma versão), `name: "test"` virou o tipo literal `"test"`, com aspas, e o papel não foi reconhecido; o gerador passou a escrever `name` e `description` sem aspas. `inherit` não preservou a variante do modelo (principal `grok-4.7`, subagente `grok-4.7-high-fast`). `/sonda` vira uma chamada `Task` do principal.
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

## D-CU (aceite local concluído em 2026-10-05)

- `preToolUse(Task)` guarda `tool_use_id` e `subagent_type` no estado da fatia. `subagentStart` abre a janela correspondente; `subagentStop` fecha e registra a chamada quando o papel está previsto.
- O shell do subagente só se associa à fatia do coordenador dentro de uma janela única. A prova usa o `conversation_id` do shell como `agente_id`, também incluído nos IDs observados da chamada. Fora da janela, com janelas sobrepostas ou papel desconhecido, nenhum sucesso é registrado.
- O ID bruto da chamada fica nos IDs observados; `chamada_id` recebe um identificador estável derivado porque o Schema 3.2 não aceita a quebra de linha que o Cursor inclui no ID bruto. O papel opcional `map` não é gravado como chamada obrigatória pelo núcleo.
- A tradução foi testada com payloads derivados dos brutos P0.5. Não usa transcript nem contadores do `subagentStop`; ainda não foi observada em sessão real.

Com G1 aprovado e os sete agentes instalados por B2-CU (`b4669f0`), os cinco testes de `testes.teste_adaptador_cursor_subagente` continuam verdes: janela única, precedência sobre fatia do filho, janelas sobrepostas, shell fora de janela e papel desconhecido. A4 e o gerador passam; a chave real continua vazia. O-CU e o aceite humano de G2 ainda são necessários para ativação.

## O-CU (roteiro preparado; sessão real pendente)

Roteiro local em `.execucoes/sondagens/ocu-roteiro.md`; preparação por `py -3 .execucoes/sondagens/preparar_ocu.py`. Cópia preparada em 2026-10-05 a partir de C4 (`2368b33`), sem Git nem produto, com registros próprios, captura dos payloads dos hooks e a chave preenchida só nessa cópia. O caminho consta no roteiro local. As alterações de D-CC ficam preservadas na árvore original.

Em sessão nova do Cursor, observar os sete papéis em série, recorte e leitura de skills, guarda negando no subagente, prova do test vinculada ao filho, revisão vinculada ao refute e recusa de DONE sem a chamada prevista. O roteiro também exercita inspeção e invalidação por edição. Script, wrappers e contratos conferidos localmente; execução no Cursor e G2 ainda pendentes. Entregar os brutos e a exportação do chat conforme o roteiro; nenhuma observação nova foi registrada nos metadados.
