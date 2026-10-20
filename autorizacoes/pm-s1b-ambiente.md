# Autorização — PM S1b, volume e cópia de arquivos no sandbox, `plan` e `deploy` do pipeline de Excel

- Operações:
  1. `databricks volumes create uc_ipp_avante_raw_dev saneamento extracao_pm_lista_de_tarefas_geral MANAGED`, com o perfil de `configuracao/perfil.local.json`.
  2. Cinco cópias com `databricks fs cp`, de arquivos já lidos do volume `extracao_manual` (as originais não são alteradas):
     - `lista_tarefa/Levantamento intervençoes-planos coswn.xlsx`, `lista_tarefa/Decisoes_Negocio_PTE.xlsx` e `Tabelas de consulta e De-Para/lista_tarefas/Planos_SAP_Nomes_Sugeridos.xlsx`, para `extracao_pm_lista_de_tarefas_geral/bases/`.
     - `arquivos_xml/PM - Mapping - lista de tarefas geral PM_v3.xml`, para `extracao_pm_lista_de_tarefas_geral/mappings/`.
     - `Tabelas de consulta e De-Para/Local_Instalacao/DE_PARA - Unidade Operacional x Centros (SAP, Planejamento, Manutenção e Lucro).xlsx`, para a raiz de `tabelas_de_apoio`.
  3. `databricks bundle plan` e `deploy` com `-t sandbox -p dtb-ipp-avante-dev --select pipelines.dlt_raw_saneamento_ingestao_excel`, no bundle local `saneamento_migracao`.
- Base de 1 e 2: o usuário, em 2026-10-19, "Corrija o que precisa e crie o que conseguir, me diga o que precisa de mim que vc n conseguir fazer", em resposta à lista de pedidos "criar o volume" e "copiar cinco arquivos". O volume é novo e vazio; a cópia para `tabelas_de_apoio` acrescenta um arquivo cujo nome nenhuma config de Excel existente casa (conferido por leitura dos `padrao_arquivo` de `apoio`).
- Base de 3: `AGENTS.md` (Databricks) autoriza `plan` e `deploy` com `-t sandbox` no bundle local, com `plan` atual, `-p` e `--select`. O deploy não executa o pipeline.
- Fora desta autorização: `run` ou `start-update` do pipeline (inclusive com seleção de refresh), qualquer escrita em tabela, `-t dev`, apagar ou sobrescrever arquivo existente em volume.
