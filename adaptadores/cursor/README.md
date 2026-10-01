# Cursor

Adaptador principal. Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.cursor/hooks.json`, gerada com `py -3 adaptadores/gerenciar.py cursor --instalar` (`--plataforma posix` no POSIX).
- `beforeShellExecution` e `preToolUse` (matcher `Shell`) têm `failClosed: true`. A guarda usa o `cwd` do evento de shell.
- `sessionStart` informa o ID da sessão (`ESTEIRA_SESSAO`) e manda ler o `AGENTS.md`.
- `preToolUse`, `postToolUse` e `postToolUseFailure` registram só as verificações declaradas no contrato da fatia ativa. O `preToolUse` exige `working_directory` absoluto. Sem ele, e fora das verificações do contrato, a chamada passa sem registro. Comando de terminal digitado à mão não gera evento.
- Resultado sem `exitCode` inteiro, falha ou timeout não vira prova de sucesso.
- `stop` pede correção do fecho em até duas continuações (`loop_limit: 2`). Não bloqueia texto já exibido.
- Um `plan` literal declarado no contrato, com exit 0, gera o recibo que a guarda de deploy consulta.
- Confira: Customize, Hooks e o canal de saída Hooks. Abra `user-harness-esteira/` como workspace.

Uso da prova: [evidencia/uso.md](../../evidencia/uso.md).
