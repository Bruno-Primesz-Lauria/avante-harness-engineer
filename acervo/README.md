# Acervo

O acervo é inventário das candidatas do desenho; implementar uma delas exige pacote próprio. Os 7 agentes ficam em [`agentes/roteamento.yaml`](../agentes/roteamento.yaml), a fonte única, e as skills `databricks-*` em [`trilhas/README.md`](../trilhas/README.md#skills-databricks).

| candidata | tipo | situação hoje |
|---|---|---|
| `grilling`, `engineer` | skill | Candidata. |
| `esteira`, `novo-objeto` | skill | Embutida no agente `implement`. |
| `distill`, `docs-objeto` | skill | Embutida no agente `docs`. |
| `regras`, `ingestao` | skill | Embutida no agente `config`. |
| `paridade` | skill | Embutida no agente `test`. |
| `diagnostico` | skill | Embutida no `map` e no coordenador. |
| `escada-validacao`, `dab-sandbox` | skill | Embutida no agente `dab`. |
| `tech-guide` | skill | Candidata, atendida pelas skills `databricks-*` instaladas. |
| `modus-operandi` | regra | Existe em [`nucleo/modus-operandi.md`](../nucleo/modus-operandi.md). |
| `cwd-bundle`, `target-dev` | hook | Implementados como guardas ([`guardas/README.md`](../guardas/README.md)). |
| `stop-untested` | hook | Coberto pelo fecho com prova ([`evidencia/fecho.md`](../evidencia/fecho.md)). |
| `yaml-stop` | hook | Candidata. |
| `docs-distill` | hook | Candidata, prevista no [`plano_memoria_harness.md`](../plano_memoria_harness.md) (segunda atividade do projeto). |
