# Raiz clonável do harness — 28/09/2026

Raiz do workspace: `user-harness-esteira/`. O produto será um clone independente
em `prj-avante-analytics-adb/`, dentro dela. O usuário escolheu preparar esse
clone futuro e preservar o checkout de produto atualmente existente na pasta pai.

## Alterações

- Instalador aponta para a própria raiz do harness, inclusive a entrada legada Codex.
- `.cursor/hooks.json` usa `py -3 adaptadores/entrada.py cursor`, sem caminho de máquina.
- `.codex/hooks.json` foi migrado vazio; instalação Codex continua opcional.
- Claude Code gera `.claude/settings.json` versionável. OpenCode usa import relativo.
- Política aponta apenas para o produto interno; sem busca alternativa na pasta pai.
- Ambiente `.venv`, diagnósticos, fixtures e backups ficam dentro do harness.
- `.gitignore` separa o repositório de produto e artefatos locais do histórico do harness.
- HTML de referência copiado sem alteração de conteúdo; links do README e catálogos corrigidos.
- Arquivos externos anteriores migrados com conferência de hash para `.execucoes/migracao/`.
  Somente as duas pastas externas criadas pelo agente, depois de vazias, foram removidas.

## Evidência

54 testes Python passaram (exit 0). Incluem executar o hook gerado numa cópia em
outro caminho com espaços, ler o bundle sintético interno e gravar o diagnóstico
nessa cópia. Também conferem destinos do instalador, geração Windows/POSIX sem
caminhos absolutos e troca de plataforma sem duplicar o próprio hook.

Os cenários JavaScript da ponte OpenCode passaram. Hash do HTML copiado igual ao
original. O status do checkout de produto existente permaneceu igual ao inicial.
Nenhuma operação Databricks foi executada.

O clone interno de produto ainda não foi criado, conforme escolha do usuário.
A ativação em sessão real dos agentes continua pendente. O harness ainda não
foi inicializado/publicado como repositório Git nesta tarefa; sua estrutura e
arquivos estão preparados para versionamento.
