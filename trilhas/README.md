# Trilhas

Escolha a trilha pelo objetivo. Ela roda em um de dois modos, pela chave `agentes_obrigatorios` de [`configuracao/politica.json`](../configuracao/politica.json) para o seu runtime:

- **Com agentes**, se a trilha está na chave: você coordena e os papéis de [`agentes/`](../agentes/) executam, conforme [Agentes](#agentes).
- **Agente único**, fora da chave: você executa a trilha, com verificação objetiva. Não dependa de subagente nem de skill candidata do [acervo](../acervo/README.md).

| id | Use para | Arquivo |
|---|---|---|
| `novo` | criar ou migrar objeto, ou parte dele | [novo.md](novo.md) |
| `manutencao` | mudança pontual com aceite claro | [manutencao.md](manutencao.md) |
| `correcao` | bug sustentado por log, observação ou reprodução | [correcao.md](correcao.md) |
| `entendimento` | responder pergunta sem alterar produto | [entendimento.md](entendimento.md) |
| `docs` | escrever ou atualizar documento | [docs.md](docs.md) |
| `validacao` | verificar até um degrau, sem corrigir código | [validacao.md](validacao.md) |
| `review` | revisar um recorte, sem reescrever | [review.md](review.md) |
| `destilar` | transformar padrão recorrente em instrução com fonte, ou conhecimento verificado em nota de `memoria/` | [destilar.md](destilar.md) |

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
- Com agentes, quem altera não verifica nem revisa: o `test` verifica e o `refute` revisa. Como agente único, registre o modo de revisão e apoie o aceite em prova objetiva.
- Teste em outro agente continua o mesmo teste. O esperado vem do requisito, do dado de referência ou do comportamento contratado.
- O CI do PR não executa as suítes locais. Rode-as antes do PR (degrau 0 do `PLANO-DE-EXECUCAO.md` do bundle). Ampliação local de suíte vai separada no manifesto de entrega.
- Orçamento do laço: [`nucleo/modus-operandi.md`](../nucleo/modus-operandi.md#recuperação).

## Agentes

Vale só para a trilha que está em `agentes_obrigatorios` do seu runtime. A fonte única da ordem e dos gatilhos é [`agentes/roteamento.yaml`](../agentes/roteamento.yaml); cada papel tem sua definição em `agentes/<papel>.md`.

| Trilha | Sequência |
|---|---|
| `novo` | map opcional → coordenador → config/implement → test → refute → dab se aplicável → coordenador |
| `manutencao` | map opcional → coordenador → test prepara se o caso existente não decide → config/implement → test → refute → dab se aplicável → coordenador |
| `correcao` | diagnóstico (map opcional) → coordenador → test reproduz → config/implement → test revalida → refute → dab se aplicável → coordenador |
| `docs` | map opcional → coordenador → docs → inspeção documental pelo coordenador → refute → coordenador |
| `destilar` | map opcional → coordenador → docs com distill → inspeção documental pelo coordenador → refute → coordenador |
| `validacao` | coordenador → test → dab se autorizado → test com paridade se exigida → refute → coordenador |
| `review` | map opcional → coordenador → refute → coordenador |
| `entendimento` | coordenador, com map opcional; sem refute |

- **Um subagente por vez:** chame o próximo papel só depois que o anterior terminar, inclusive `config` e `implement` na mesma etapa. Com janelas sobrepostas, a autoria das edições fica inconclusiva e a fatia não fecha `DONE` (`superficie_inconclusiva`).
- **Escrita por superfície:** YAML de negócio, ingestão ou recurso vai para `config`; notebook, Python ou SQL, para `implement`. Arquivo que nenhum dos dois cobre recusa o início da fatia: declare arquivos atribuíveis ou feche com `DECIDE`.
- **Gatilhos:** `test` entra com critério `teste`, `validacao_dados` ou `paridade`; `dab`, com critério `ambiente` e autorização registrada (sem ela, `DECIDE`); `refute`, em toda trilha estruturada exceto `entendimento`. `map` é sempre opcional.
- **Plano de chamadas:** `iniciar` calcula as chamadas previstas e as grava no `estado.json` da fatia. Não escreva o plano à mão. Só a chamada observada pelo adaptador do runtime conta como execução do papel.
- **Prova do teste:** vale a do comando que o `test` rodou. Teste rodado por você no lugar do `test` não fecha o critério (`teste_fora_do_test`).
- **Entrada do refute:** intenção, aceite, baseline, estado atual e provas. Não envie o racional do autor. Achado procedente volta ao dono da superfície, conta no orçamento e pede novo teste e nova revisão; descarte exige motivo registrado na triagem.
- **Registros do coordenador** ([uso](../evidencia/uso.md#inspeção-revisão-e-triagem)): `revisar` para cada refute chamado e `triar` para cada achado; `diagnosticar` na correção, antes de chamar `config` ou `implement`; `registrar-sandbox` com o retorno do `dab` quando o critério `ambiente` roda `databricks bundle`; `registrar-paridade` com o retorno do `test` no critério `paridade`. O `agente_id` de cada registro é o da chamada observada: no Cursor, o dos `ids_observados` da chamada no `estado`; no Claude Code, o que o hook devolve em `[esteira] Chamada <papel> registrada ... agente_id=`.
- **Edição depois da prova:** invalida teste, inspeção e revisão afetados.
- **Papel ou capacidade obrigatória indisponível:** `BLOCKED` para o trabalho que depende dele; o trabalho independente continua. Falta de decisão ou autorização humana: `DECIDE`.
- O papel não amplia autorização: guardas, permissões do runtime e o `AGENTS.md` prevalecem.

## Skills Databricks

Use a skill para acertar comando e API da plataforma. Ela não muda escopo, autorização nem guarda. Se divergir do harness, vale o harness.

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
