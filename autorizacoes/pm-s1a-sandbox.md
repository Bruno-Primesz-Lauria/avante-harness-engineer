# Autorização — PM S1a, `plan`, `deploy` e `run` em sandbox

- Operações:
  1. `databricks bundle plan -t sandbox -p dtb-ipp-avante-dev --select jobs.job_pm_coswin_snapshot` e `databricks bundle deploy` do mesmo escopo, no bundle local `saneamento_migracao`.
  2. Um único `run` do job `[sandbox] Job_PM_Coswin_Snapshot`, por `databricks jobs run-now`: a guarda nega `bundle run`.
- Base de `plan` e `deploy`: `AGENTS.md` (Databricks) autoriza `plan` e `deploy` com `-t sandbox`, com `plan` atual, `-p` e `--select`.
- Base do `run`: aprovação do usuário em 2026-10-19, "1 - autorizado", em resposta a "é só me dizer 'autorizo o run da S1a no sandbox'". Na mesma mensagem o agente havia dito que o plano pede aviso ao canal antes do `run`.
- Efeito do `run`: liga o cluster all-purpose `0609-183750-1nvf48ct`, lê `coswin.coswin.{t_job,job_job_action,action,t_action_category}` e grava `uc_ipp_avante_raw_dev.saneamento.coswin_<tabela>_snapshot`. Em 2026-10-19 essas quatro tabelas não existiam (`SHOW TABLES ... LIKE 'coswin*'` vazio).
- Coordenação com o canal: o agente não consegue conferi-la. Vale a autorização do usuário; o registro fica `nao_verificado`.
- Fora desta autorização: outro `run`, outro job, `full_refresh` diferente do padrão do job, `-t dev`, qualquer escrita fora das quatro tabelas `coswin_*_snapshot`.
