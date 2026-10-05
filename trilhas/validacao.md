# Validação

Usar quando: verificar até o degrau contratado, sem corrigir código de produto. Não usa o laço comum: reprovação conclusiva encerra em `FAILED`.

## Passos

1. **Delimitar.** Escolha o degrau seguro aplicável. Em pedido genérico, comece pelo degrau local. Publicação e `run` exigem autorização. Feito quando: o alvo está registrado.
2. **Verificar.** Rode as suítes aplicáveis, em ordem. Pare na primeira reprovação. Feito quando: a base passou, ou o aceite reprovou.
3. **Ambiente.** Degrau 3 `validate`; 4 `plan` e `deploy`; 5 pipeline; 6 job. Só os que o contrato autoriza, com as [guardas](../guardas/README.md). Feito quando: o efeito autorizado ocorreu e as guardas foram satisfeitas, ou a verificação parou num resultado conclusivo.
4. **Paridade**, quando obrigatória. Compare o mesmo recorte e explique a divergência. Feito quando: nenhum gap aberto recebe `limpo`.
5. **Revisar.** Confira se as provas sustentam cada critério: estado testado, cobertura e degrau. Achado procedente encerra em `FAILED`, sem corrigir produto. Feito quando: nenhum achado procedente está aberto.

Com agentes: `test` nos passos 2 e 4 (com a capacidade `paridade`); `dab` no 3, com autorização registrada; `refute` no 5.

## Aceite

Superfície: sem alteração de código de produto. Log é artefato de execução. Efeito externo precisa estar autorizado.

Degraus e verificações do escopo, em ordem. Confira schema e conteúdo da saída de dados do alvo. Pare no primeiro resultado conclusivo negativo.

## Fecho

`DONE` se o alvo contratado passou e a revisão não achou problema procedente. `FAILED` se reprovou. `BLOCKED` se não foi possível verificar.
