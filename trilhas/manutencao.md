# Manutenção

Usar quando: mudança pontual, com resultado e vizinhos relevantes nomeados.

## Passos

1. **Mapear.** Veja o que o caso existente cobre. Feito quando: o teste decide o comportamento, ou fica registrado que não decide.
2. **Preparar.** Amplie uma suíte existente se o caso não cobre o corte, ou use verificação de ambiente se for o aceite correto. Feito quando: o esperado vem do requisito.
3. **Alterar.** Mude só os arquivos autorizados e preserve alteração anterior. Feito quando: o estado novo está identificado.
4. **Verificar e revisar.** Entre no [laço comum](README.md). Rode o aceite, trate os achados e repita a prova depois de mudança relevante. Feito quando: os critérios fecharam.

Com agentes: `map` no passo 1, se a investigação for ampla; `test` no 2, só se o caso existente não decide; `config` e `implement` no 3, por superfície; `test` e `refute` no 4; `dab` se o contrato tem critério `ambiente` autorizado.

## Aceite

Superfície: os arquivos exatos do corte e as dependências necessárias.

Caso existente que decide o comportamento. Se não cobre, amplie uma suíte existente como preparação, ou defina a validação de ambiente apropriada.

## Fecho

`DONE` com prova atual e achados obrigatórios resolvidos. Trabalho já autorizado não espera nova aprovação humana.
