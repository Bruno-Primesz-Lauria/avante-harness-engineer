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

## Skills Databricks

Use a skill para acertar comando e API da plataforma. Ela não muda escopo, autorização nem guarda. Se divergir do harness ou do `AGENTS.md` do produto, vale o harness.

| Skill | Use quando | Trilhas |
|---|---|---|
| `databricks-core` | CLI, autenticação e perfil. Nunca escolha o perfil sozinho. | todas |
| `databricks-docs` | Dúvida técnica sem skill específica. | todas |
| `databricks-dabs` | `databricks.yml`, `include`, recurso, `validate` e `plan`. | `novo`, `manutencao`, `correcao`, `validacao`, `review` |
| `databricks-pipelines` | Pipeline Lakeflow (cutover, saneamento, fornecedor, cliente). | `novo`, `manutencao`, `correcao`, `validacao` |
| `databricks-jobs` | Job e orquestrador; etapa 06. | `novo`, `manutencao`, `correcao`, `validacao` |
| `databricks-dbsql` | SQL do objeto e leitura da saída de dados. | `novo`, `manutencao`, `correcao`, `entendimento`, `validacao` |
| `databricks-unity-catalog` | Catálogo, schema, volume e permissão. | `novo`, `entendimento`, `validacao`, `review` |
| `databricks-data-discovery` | Achar tabela ou responder pergunta sobre o dado. | `entendimento`, `correcao`, `validacao` |
| `databricks-python-sdk` | Código com SDK, Databricks Connect ou REST. | `novo`, `manutencao`, `correcao` |
| `databricks-execution-compute` | Rodar código em cluster ou serverless, só com autorização. | `correcao`, `validacao` |

Ficam em `.agents/skills/` (aitools v0.2.10), lido por Cursor, Codex e OpenCode; o Claude Code as recebe pelo plugin `databricks`. As outras 19 skills do aitools (apps, ML, Lakebase, vector search...) ficam fora da esteira. Atualizar: `databricks aitools install --path .agents/skills --skills databricks-core,databricks-docs,databricks-dabs,databricks-pipelines,databricks-jobs,databricks-dbsql,databricks-unity-catalog,databricks-data-discovery,databricks-python-sdk,databricks-execution-compute`.
