---
schema_versao: 1
id: claude-code-hooks-windows-desligam-guarda-no-macos
tipo: aprendizado
status: ativo
tags: [claude-code, hooks, macos, guarda]
caminhos: [.claude/settings.json, adaptadores/gerenciar.py, adaptadores/entrada.py]
fontes: [.claude/settings.json, adaptadores/gerenciar.py, adaptadores/entrada.py, https://code.claude.com/docs/en/hooks]
verificado_em: 2026-10-06
---

# No macOS, os hooks versionados do Claude Code não rodam e a guarda fica desligada sem aviso

## Contexto

O [`.claude/settings.json`](../../.claude/settings.json) versionado é gerado para Windows: `py -3` e `shell: powershell`. O [`entrada.py`](../../adaptadores/entrada.py) converte qualquer falha própria em exit 2, porque os runtimes só bloqueiam com exit 2.

## Descoberta

Em 2026-10-06, num Mac sem `py` e sem `pwsh` (Claude Code no app desktop, macOS com Darwin 25.6), o comando do hook não chega a iniciar o `entrada.py`. A falha acontece antes dele, com código diferente de 2. O Claude Code trata isso como erro não bloqueante, e a chamada de shell segue sem decisão da guarda. Nada no chat avisa que a guarda não rodou.

Depois de instalar os hooks POSIX, a guarda voltou a negar na mesma sessão: um comando composto com `databricks bundle` foi negado com `cwd-bundle/comando_nao_suportado`.

## Quando aplicar

Clone em macOS ou Linux; qualquer pedido de `databricks bundle` pelo Claude Code; suspeita de que a guarda não está respondendo.

## Como resolver

1. Crie o `.venv` com Python 3.12 ou mais novo, conforme o README. Ver [python-anterior-a-3-12-quebra-prova](python-anterior-a-3-12-quebra-prova.md).
2. Gere os hooks POSIX no seu clone:

   ```bash
   python3 adaptadores/gerenciar.py claude_code --instalar --plataforma posix
   ```

3. Não commite o `.claude/settings.json` alterado. O formato versionado é Windows. O [`gerenciar.py`](../../adaptadores/gerenciar.py) substitui só a definição gerada por ele, porque manter as duas faria o lançador ausente bloquear as chamadas.

## Limites

Observado só no app desktop no macOS. Linux e o CLI no terminal não foram exercitados. O efeito de um `pwsh` instalado no Mac não foi testado.

## Como conferir

`/hooks` no terminal do Claude Code, ou envie um evento de teste ao hook:

```bash
echo '{"hook_event_name":"SessionStart","session_id":"teste","source":"startup"}' | python3 adaptadores/entrada.py claude_code
```

A resposta é um JSON com `additionalContext`. Sem `py` no sistema, o comando versionado (`py -3 ...`) falha antes disso.
