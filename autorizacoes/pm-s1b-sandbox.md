# Autorização — PM S1b, `validate`, `plan` e `deploy` em sandbox

- Operações: `databricks bundle validate -t sandbox -p dtb-ipp-avante-dev` e, depois, `plan` e `deploy` do mesmo escopo (`--select`), no bundle local `saneamento_migracao`.
- Base: `AGENTS.md` (Databricks) autoriza `validate`, `plan` e `deploy` com `-t sandbox` dentro do bundle local, com `plan` atual, `-p` e `--select`; perfil de `configuracao/perfil.local.json`.
- Efeito do `deploy`: acrescenta o alias de volume `pm_lista_de_tarefas_geral` ao recurso do pipeline `dlt_raw_saneamento_ingestao_excel`. Não executa o pipeline. O bundle local não inclui `resources/schemas/`, então o deploy **não cria** o volume `extracao_pm_lista_de_tarefas_geral`: ele precisa existir em `uc_ipp_avante_raw_dev.saneamento` por outro caminho, que depende de autorização explícita do usuário.
- Fora desta autorização: `run` ou `start-update` do pipeline, criação do volume, cópia de arquivo para qualquer volume, `-t dev`, qualquer escrita em tabela.
