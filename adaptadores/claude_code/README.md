# Claude Code

Visão geral e tabela: [adaptadores](../README.md).

- Instruções: `CLAUDE.md` importa `@AGENTS.md`. Confira a carga numa sessão nova.
- Configuração: `.claude/settings.json`, gerada com `py -3 adaptadores/gerenciar.py claude_code --instalar`. Mescla com o que já existe (permissões e outros hooks ficam).
- `PreToolUse` com matcher `^(Bash|PowerShell)$`. No Windows o hook roda em `powershell` e usa `CLAUDE_PROJECT_DIR` para achar `adaptadores/entrada.py`.
- O `cwd` do envelope é da sessão e não vale como prova. Prefixe o comando com `Set-Location -LiteralPath '...' -ErrorAction Stop;` (PowerShell) ou `cd -- '...' &&` (Bash).
- Decisão positiva devolve só contexto. Negação usa `permissionDecision: deny`.
- Não coleta prova nem retoma fecho.
- Até D-CC passar pelo gate G2, o `fechar` não comprova `DONE` no Claude Code. Feche a fatia como `BLOCKED`, com motivo e condição de retomada, ou execute-a no Cursor. Um relato de agente não substitui a prova observada.
- Confira: `/hooks`.
