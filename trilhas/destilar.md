# Destilar docs

Usar quando: transformar padrão recorrente em instrução acionável, com fonte, ou registrar conhecimento verificado como nota da [memória do time](../memoria/README.md). O sinal `docs-distill` (não implementado) só apontaria candidato; ele não abre esta trilha sozinho. A forma `destilar` segue candidata.

Instrução ou nota: o que o agente deve seguir sempre vai para o arquivo operacional (trilha, guarda, skill ou `AGENTS.md`). Contexto, motivo de decisão ou limite observado vai para nota em `memoria/`, que aponta para o arquivo operacional quando ele existir. Nota que só repete documento existente não entra.

## Passos

1. **Ler.** Confira as fontes vivas e resolva divergência relevante. Separe instrução recorrente de fato que fica na fonte. Feito quando: as fontes são rastreáveis e o padrão cabe numa instrução.
2. **Escrever.** Use o arquivo exato do contrato. Gatilho claro, instrução acionável, fonte rastreável. O núcleo usa caminho neutro de runtime; o adaptador escolhido entra no campo da forma `destilar`. Feito quando: o texto está fiel e a fonte continua sendo o lugar do fato.
3. **Inspecionar.** Cheque fato, link, exemplo e duplicação contra o documento de origem. Feito quando: o aceite da destilação está registrado.
4. **Revisar.** Entre no [laço comum](README.md). Feito quando: não há achado obrigatório aberto.

Com agentes: `docs`, com a capacidade `distill`, escreve no passo 2; sem `distill`, `BLOCKED`; sem fonte e destino autorizados, `DECIDE`. A inspeção do passo 3 é sua; `refute` revisa no 4.

## Aceite

Superfície: a skill e as referências do adaptador, ou a nota e o índice em `memoria/`, só se o contrato os autoriza. Escreva só nos arquivos autorizados.

Gatilho claro, instrução acionável, fonte rastreável, sem duplicação desnecessária. Link funcional e exemplo consistente com a fonte. Para nota: metadados completos, fonte acessível a partir de outro clone, nota ativa no índice e `python3 adaptadores/memoria.py validar` com exit 0 (no Windows, `py -3`).

## Fecho

`DONE` no aceite da destilação. `REVIEW` só se houver revisão humana prevista. Produto fora do contrato fica intocado.
