# Novo objeto

Usar quando: criar ou migrar um objeto, ou parte dele, dentro da fronteira, com ou sem irmão similar.

## Passos

1. **Delimitar.** Identifique irmão, arquivos, etapas, efeitos e critérios. Feito quando: o contrato tem escopo e orçamento.
2. **Implementar.** Configure o YAML e crie o notebook a partir do template da etapa e de um irmão vivo. Inclua recurso, `include` e task quando o objeto pede. Feito quando: cada responsabilidade tem etapa dona.
3. **Verificar e revisar.** Entre no [laço comum](README.md). Feito quando: cada critério tem prova atual e nenhum achado obrigatório está aberto.
4. **Ambiente**, só se o contrato pede. Execute só o degrau autorizado; `validate` não publica. Comando `databricks bundle` de critério `ambiente` leva o registro `registrar-sandbox` ([uso](../evidencia/uso.md#diagnóstico-ambiente-e-paridade)). Feito quando: há `plan` atual antes de deploy, e coordenação antes de ingestão ou espinha. Se o ambiente falha, feche com `DECIDE`, `BLOCKED` ou `FAILED`.

Com agentes: `map` no passo 1, se a investigação for ampla; `config` e `implement` no 2, por superfície; `test` e `refute` no 3; `dab` no 4, com autorização registrada.

## Aceite

Superfície: notebook e configuração, recurso, `include` e task, conforme o objeto. A etapa 06 é job. BP segue os quatro pipelines vivos (cutover, saneamento, fornecedor, cliente), mais monitoramento e `bp_historico`. Pipeline novo de BP entra no orquestrador do módulo e nos pipelines do `bp_historico`.

- Degrau 0 exigido pelo repositório.
- Spark quando a mudança mexer em coluna ou na etapa 04.
- `validate` local.
- Paridade no mesmo recorte.
- Validação da saída de dados e arquivo 06 no Volume, quando o objeto gera arquivo.

## Fecho

`DONE` da fatia só no término declarado. O objeto completo só fica `DONE` com paridade, validação da saída de dados e, se gera arquivo, o arquivo 06.
