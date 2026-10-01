# Trilhas

Escolha a trilha pelo objetivo. Um único agente executa a trilha, com verificação objetiva. Subagente e skill do [acervo](../acervo/README.md) são candidatos e não existem: não dependa deles.

| id | Use para | Arquivo |
|---|---|---|
| `novo` | criar ou migrar objeto, ou parte dele | [novo.md](novo.md) |
| `manutencao` | mudança pontual com aceite claro | [manutencao.md](manutencao.md) |
| `correcao` | bug sustentado por log, observação ou reprodução | [correcao.md](correcao.md) |
| `entendimento` | responder pergunta sem alterar produto | [entendimento.md](entendimento.md) |
| `docs` | escrever ou atualizar documento | [docs.md](docs.md) |
| `validacao` | verificar até um degrau, sem corrigir código | [validacao.md](validacao.md) |
| `review` | revisar um recorte, sem reescrever | [review.md](review.md) |
| `destilar` | transformar padrão recorrente em instrução com fonte | [destilar.md](destilar.md) |

## Formato de cada trilha

Usar quando, passos (cada um com "Feito quando"), aceite, fecho. Superfície é o conjunto de arquivos que a trilha pode tocar. Os status de fecho (`DONE`, `REVIEW`, `DECIDE`, `BLOCKED`, `FAILED`) estão em [`evidencia/fecho.md`](../evidencia/fecho.md).

Falha de ferramenta vale em qualquer passo: siga a tabela de [`guardas/README.md`](../guardas/README.md#falha-de-ferramenta). Negar uma chamada não bloqueia a tarefa inteira.

## Laço comum

`novo`, `manutencao`, `correcao`, `docs` e `destilar` entram neste laço depois do trabalho próprio. `novo` ainda passa pelo ambiente, se o contrato o pede. `entendimento`, `validacao` e `review` não usam o laço.

```text
verificar → aceite passou?
  falhou → pode corrigir?
  passou → revisar → achado procedente?
    sim → pode corrigir?
    não → fechar                        (DONE / REVIEW)

pode corrigir?
  sim → corrigir achado → verificar    (revalidar)
  não → pendência                      (DECIDE / BLOCKED / FAILED)
```

- O revisor recebe intenção, critérios de aceite, identificadores da execução e a referência da base ou do estado. Ele descobre os arquivos pelo diff. Não envie a justificativa do autor.
- Workspace com alteração prévia exige atribuir a mudança: `git diff` sozinho não delimita a fatia.
- Sem agente separado, registre o modo de revisão e apoie o aceite em prova objetiva.
- Teste em outro agente continua o mesmo teste. O esperado vem do requisito, do dado de referência ou do comportamento contratado.
- O CI do PR não executa as suítes locais. Rode-as antes do PR (regra do `AGENTS.md` do produto). Ampliação local de suíte vai separada no manifesto de entrega.
- Orçamento do laço: [`nucleo/modus-operandi.md`](../nucleo/modus-operandi.md#recuperação).
