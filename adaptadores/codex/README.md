# Codex

Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.codex/hooks.json`, gerada com `py -3 adaptadores/gerenciar.py codex --instalar`. Mescla com o que já existe. Sem a instalação, o arquivo não tem handler.
- `PreToolUse` com matcher `^Bash$`.
- O `cwd` do envelope é da sessão e não vale como prova. A guarda aceita `tool_input.workdir` ou o prefixo literal PowerShell/Bash.
- Decisão positiva devolve só contexto, sem aprovação. Negação usa `permissionDecision: deny`.
- Não coleta prova nem retoma fecho.
- Em fatias estruturadas, informe `--runtime codex` em cada comando `adaptadores/prova.py`; Codex não é detectado automaticamente nem pode ser incluído em `agentes_obrigatorios`.
- O runtime exige revisar e confiar na definição em `/hooks`. O instalador não altera confiança nem permissões.
- A política é a de `configuracao/politica.json`. Diagnósticos em `.execucoes/codex/cwd_bundle/`.

Documentação: [Codex Hooks](https://learn.chatgpt.com/docs/hooks).
