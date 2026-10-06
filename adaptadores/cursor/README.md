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
- A tradução foi testada com payloads derivados dos brutos P0.5. Não usa transcript nem contadores do `subagentStop`. Foi observada em sessão real na O-CU (abaixo).

Com G1 aprovado e os sete agentes instalados por B2-CU (`b4669f0`), os cinco testes de `testes.teste_adaptador_cursor_subagente` continuam verdes: janela única, precedência sobre fatia do filho, janelas sobrepostas, shell fora de janela e papel desconhecido. A4 e o gerador passam; a chave real continua vazia até o E0.

## O-CU (G2 aceito em 2026-10-06)

Kit versionado em [`avaliacao/observacao-cursor/`](../../avaliacao/observacao-cursor/roteiro.md): roteiro, preparação (`preparar.py`) e conferência local (`validar.py`). A cópia exporta o HEAD, sem Git nem produto, com registros próprios, captura dos payloads dos hooks e a chave preenchida só nela.

Sexta sessão: Cursor 3.19.19, Windows, cópia `observacao-cursor-20261006T183058Z` (HEAD `dbea3cb`), roteiro em turnos. Os brutos (152 eventos), os registros, a exportação do chat e a tabela dos 12 critérios ficam em `.execucoes/sondagens/brutos/cursor/2026-10-06_cursor-3.19.19_ocu/`, fora do Git. Este resumo é o registro versionado. O humano aceitou o G2 com 11 critérios conformes e o critério 5 parcial.

- **Descoberta e ordem:** os sete papéis foram chamados por `Task` com `subagent_type` exato. Os pares `preToolUse(Task)` → `subagentStart` → `subagentStop completed` vieram em série, sem janela sobreposta, na ordem do roteamento.
- **Recorte:** test, config, implement e docs mudaram só o arquivo atribuído; map, dab e refute não mudaram nenhum. Os dois fechos ficaram sem pendência do C5.
- **Guarda:** negou no subagente dab (`cwd-bundle/cwd_incorreto`), sem execução e sem nova tentativa. Nenhum `deploy` ou `run`.
- **Vínculos:** a prova do test, a revisão de cada refute e o `ambiente_local` do dab levam o `conversation_id` do shell do filho como `agente_id`, igual ao dos IDs observados da chamada.
- **Recusa de DONE:** antes das chamadas, o DONE foi recusado com exit 2 e `chamada:dab` nas pendências.
- **Inspeção:** a edição posterior do guia invalidou a inspeção, e a nova inspeção voltou a `valida`.
- **Fechos:** DONE aceito nas duas fatias, manutenção e docs, pelo followup do `stop`. As seis chamadas da manutenção ficaram `concluida`.
- **Limites:**
  - Os contadores do `subagentStop` vêm 0, então a leitura de skill só se comprova pelo retorno do filho, que ficou registrado só para map e dab.
  - Os dois refutes rodaram também um shell de leitura além do `refute-janela` pedido.
  - Houve um `sessionStart` avulso, sem outros eventos.
