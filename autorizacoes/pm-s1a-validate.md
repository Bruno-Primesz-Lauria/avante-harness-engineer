# Autorização — PM S1a, `bundle validate`

- Operação: `databricks bundle validate -t sandbox -p dtb-ipp-avante-dev`, no bundle local `saneamento_migracao`.
- Base: `AGENTS.md` (Databricks) autoriza `validate` com `-t sandbox` dentro do bundle local; perfil de `configuracao/perfil.local.json`.
- Aprovação do usuário: "sim" em 2026-10-16, ao pedido de abrir a S1a (trilha `novo`).
- Fora desta autorização: `plan`, `deploy`, `run`, qualquer target diferente de `sandbox`.
