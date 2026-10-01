# Correção

Usar quando: bug sustentado por log, observação ou reprodução.

## Passos

1. **Diagnosticar.** Busque a evidência e localize a causa. Leia você mesmo o log a que tem acesso. Feito quando: há causa, ou a próxima investigação está justificada.
2. **Reproduzir.** Use caso existente ou amplie uma suíte local. A preparação pode terminar com a falha esperada, se o contrato a declara. Feito quando: o mesmo critério será verificado depois da correção.
3. **Corrigir.** Aplique a mudança mínima coerente com a causa. Feito quando: o manifesto, ou o escopo no chat, aponta o estado novo.
4. **Validar.** Entre no [laço comum](README.md). Achado de revisão volta à correção e renova a prova. Feito quando: a regressão verificou a correção e os achados obrigatórios fecharam.

## Aceite

Superfície: a causa localizada e os arquivos necessários para corrigi-la.

Reprodução anterior e resultado posterior no mesmo critério. A falha esperada da preparação não é a conclusão da correção.

## Fecho

`DONE` com o bug corrigido e a regressão verificada.
