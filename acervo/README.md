# Acervo

Vinte e seis peças do desenho: 1 regra, 13 skills, 7 papéis de agente e 5 hooks. [`catalogo.yaml`](catalogo.yaml) lista cada uma, com gatilho, critério, trilhas e `estado`. Nenhum código lê o catálogo, e nenhuma contagem liga peça automaticamente.

| `estado` | Peças | Significa |
|---|---|---|
| `politica` | `modus-operandi` | Há texto de política em [`nucleo/modus-operandi.md`](../nucleo/modus-operandi.md). |
| `implementado` | `cwd-bundle`, `target-dev`, `yaml-stop` e `stop-untested` (estes dois são a guarda "Fecho") | Há código que aplica a guarda. Política e limites em [`guardas/README.md`](../guardas/README.md). |
| `coberto` | `tech-guide` | O papel é atendido pelas skills Databricks instaladas. |
| `candidato` | as outras 12 skills, os 7 papéis, `docs-distill` | Não implementado. Não existe como skill, subagente ou hook. |

A skill pessoal `grilling` não é copiada aqui.

As skills de plataforma `databricks-*` (aitools v0.2.10, em `.agents/skills/`) estão instaladas e ficam fora deste catálogo. Qual usar em cada trilha: [`trilhas/README.md`](../trilhas/README.md#skills-databricks).

## Roteamento

O agente principal escolhe a [trilha](../trilhas/README.md) pelo objetivo e coordena pelo [`modus-operandi`](../nucleo/modus-operandi.md). Carregar uma skill não cria agente, arquivo ou etapa.

Quando a ferramenta não tem a capacidade, declare a limitação. Não invente skill, hook ou revisor como se tivessem rodado.

A avaliação ([`avaliacao/`](../avaliacao/README.md)) mede disparo indevido e instrução duplicada. Funda ou remova peça que custa sem dar benefício.
