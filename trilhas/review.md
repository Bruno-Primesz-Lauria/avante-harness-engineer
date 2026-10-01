# Review

Usar quando: revisar um recorte identificado, sem reescrever o produto. Não usa o laço comum. Achado volta para quem tem a trilha de escrita, se houver acordo.

## Passos

1. **Recorte.** Separe a mudança da tarefa das alterações anteriores. Feito quando: há manifesto ou diff delimitado.
2. **Revisão.** Confira invariantes e cenários relevantes. Cobertura ausente fica `nao_verificado`. Feito quando: cada achado é localizável.
3. **Veredito.** Declare `aceitavel`, `com_achados` ou `inconclusivo`. Se falta prova essencial, é `inconclusivo`, com o motivo. Feito quando: o veredito está sustentado e não aprova o produto por autoridade.

## Aceite

Superfície: o recorte declarado (base, head e o estado local relevante). Sem corrigir o produto.

Veredito sustentado por achados, severidade, caminhos, tentativas e limites de cobertura.

## Fecho

`DONE` mesmo com achados: o status é da tarefa de revisar, o veredito é do artefato. `DONE` com `com_achados` não torna o artefato aceitável.
