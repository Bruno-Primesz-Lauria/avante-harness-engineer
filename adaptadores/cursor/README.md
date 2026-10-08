# Cursor

Adaptador principal. Visão geral e tabela: [adaptadores](../README.md). Estado dos gates e histórico: painel do [plano](../../PLANO-AGENTES-TRILHAS.md#painel).

- Configuração: `.cursor/hooks.json`, gerada com `py -3 adaptadores/gerenciar.py cursor --instalar` (`--plataforma posix` no POSIX). Agentes em `.cursor/agents/`, gerados por `py -3 adaptadores/gerar_agentes.py --instalar cursor`.
- `beforeShellExecution` e `preToolUse` (matcher `Shell|Task`) têm `failClosed: true`. A guarda usa o `cwd` do evento de shell.
- `sessionStart` (só em chat novo) informa o ID da sessão pelo contexto adicional e por `ESTEIRA_SESSAO`, que vale no ambiente dos hooks, não no shell do agente, manda ler o `AGENTS.md` e orienta `prova.py --runtime cursor`.
- `preToolUse` para `Shell`, `postToolUse` e `postToolUseFailure` registram só as verificações declaradas no contrato da fatia ativa. O `preToolUse` exige diretório absoluto em `tool_input.cwd`; o diretório da sessão não serve. Com `cwd` vazio, a verificação declarada é negada com a orientação de preencher o campo; fora das verificações do contrato, a chamada passa sem registro. Comando de terminal digitado à mão não gera evento.
- Sucesso vem do `exitCode` de `postToolUse` (`campo_resultado`). Exit diferente de zero vem do texto `Command failed with exit code N` de `postToolUseFailure` com `failure_type: error` (`texto_falha`). Negação, timeout ou texto inesperado ficam inconclusivos e nunca viram prova de sucesso.
- `stop` pede correção do fecho em até duas continuações (`loop_limit: 2`). Não bloqueia texto já exibido.
- Um `plan` literal declarado no contrato, com exit 0, gera o recibo que a guarda de deploy consulta.
- Confira: Settings → Hooks, Settings → Subagents e o canal de saída Hooks. Abra o clone do harness como workspace raiz.

Uso da prova: [evidencia/uso.md](../../evidencia/uso.md).

## Subagentes

- `preToolUse(Task)` guarda `tool_use_id` e `subagent_type` no estado da fatia. `subagentStart` abre a janela correspondente; `subagentStop` fecha e registra a chamada quando o papel está previsto.
- O shell do subagente só se associa à fatia do coordenador dentro de uma janela única. A prova usa o `conversation_id` do shell como `agente_id`, também incluído nos IDs observados da chamada. Fora da janela, com janelas sobrepostas ou papel desconhecido, nenhum sucesso é registrado. Por isso os papéis rodam um de cada vez.
- O ID bruto da chamada fica nos IDs observados; `chamada_id` recebe um identificador estável derivado, porque o Schema 3.2 não aceita a quebra de linha que o Cursor inclui no ID bruto. O papel opcional `map` não é gravado como chamada obrigatória.
- Papel sem shell (config, implement, docs) só é ligado à chamada pela janela; a autoria das edições vem da vigilância de superfície (C5).
- O refute e o dab precisam rodar ao menos um shell para que o `agente_id` deles seja observado; a revisão e o `ambiente_local` usam esse ID. O refute gerado para o Cursor traz essa instrução (um único `Write-Output refute-janela`), e o coordenador lê o ID em `chamadas` do `prova.py estado`.

## Comportamento observado do runtime

Observado no Cursor 3.17.8 e 3.19.19, Windows, app interativo.

- Frontmatter: `name`, `description` e `model: inherit` funcionam. `name` e `description` vão sem aspas: com aspas, o tipo do subagente vira o literal com aspas e o papel não é reconhecido. `inherit` não preserva a variante do modelo do principal. Não sondados: `tools`, `skills`, `readonly` e `is_background`.
- O subagente recebe o `AGENTS.md` e enxerga as skills de `.agents/skills/` sem prefixo.
- Os hooks de shell (`preToolUse`, `beforeShellExecution`, `postToolUse`, `postToolUseFailure`) disparam no subagente com `conversation_id` próprio, diferente do principal, e sem `subagent_id` ou `parent_conversation_id`.
- `subagentStart` e `subagentStop` chegam na conversa do principal, com `subagent_id` igual ao `tool_use_id` do `preToolUse(Task)`, mas sem o `conversation_id` do subagente. Os contadores `message_count` e `tool_call_count` do `subagentStop` vêm 0 e não servem de prova.
- `cwd` chega vazio em `tool_input` e em `beforeShellExecution` quando o agente não informa o diretório; com o diretório informado, chega absoluto.
- Sucesso: `postToolUse` com `tool_output` `{output, exitCode: 0}`. Saída diferente de zero chega só em `postToolUseFailure`, como texto, sem campo numérico. Negação por hook: `failure_type: permission_denied`.
- `stop` com `followup_message` faz o principal continuar, e o Cursor mostra o followup no chat como mensagem do usuário. Não dispara para o subagente.
- `sessionStart` só dispara em chat novo: o chat que o Cursor abre junto com a janela não dispara.
- A guarda nega no subagente sem executar o comando.
- Em sessão real com os sete papéis: chamadas em série e na ordem do roteamento, recorte respeitado por papel, prova do test, revisão do refute e `ambiente_local` do dab vinculados ao `conversation_id` do filho, DONE recusado sem a chamada prevista e aceito com tudo observado.
- Não sondados: subagente paralelo ou aninhado, interrupção, timeout e leitura de `.claude/agents/` pelo Cursor.
