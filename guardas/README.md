# Guardas

Cheque o efeito real antes da ferramenta executar: identidade, destino resolvido, argumentos. O nome do recurso confirma, mas não prova. Nenhum selo de ambiente substitui o destino real. A guarda não concede autorização.

Mapa do código: [arquitetura](../adaptadores/arquitetura.md). Comandos dos degraus 0–6: `AGENTS.md` do produto.

## O que o código nega

A guarda vale para chamadas de shell de `databricks bundle` e de SQL ad hoc pela CLI. Roda em `beforeShellExecution` (Cursor), `PreToolUse` (Claude Code, Codex) e `tool.execute.before` (OpenCode). Falha da guarda, entrada inválida ou YAML ambíguo negam a chamada.

| Guarda | O código nega | Limite |
|---|---|---|
| `cwd-bundle` | `bundle` cujo cwd não é exatamente o bundle local, ou cujo `databricks.yml` não declara `saneamento_migracao`. Cwd relativo, bundle ausente, YAML inválido ou com chave duplicada. Cwd só da sessão não vale: use o cwd da ferramenta ou o prefixo literal `Set-Location -LiteralPath '...' -ErrorAction Stop;` (PowerShell) ou `cd -- '...' &&` (Bash). | Claude Code não informa cwd da chamada: só vale o prefixo. |
| Comando literal | Pipe, `;`, `&&` fora do prefixo, redirecionamento, `$`, subshell, wrapper opaco. Só `databricks`, `databricks.exe` e `databricks.cmd` sem caminho. Subcomando `bundle` além de `validate`, `plan` e `deploy` (`run`, `destroy`, `sync`...). Flag desconhecida ou duplicada. | Leitura literal (`Get-Content`, `rg` sem `--pre`...) passa. MCP, SDK e subcomandos fora de `bundle` não são vistos. |
| `target-dev` | Target ausente. Target fora de `sandbox` e `dev`. `dev` sem `autorizacoes_dev` na política para aquela operação e seleção (a política atual não tem nenhuma). Perfil (`-p`/`--profile`) ausente. Flag e prefixo `DATABRICKS_BUNDLE_TARGET=` divergentes. | Só lê flag e prefixo literal. Não lê o ambiente do processo, o default do YAML nem variável da CLI. |
| Plan antes de deploy | Deploy sem `--select` e sem `intencao_deploy_completo` na política. Deploy sem recibo de plan do mesmo bundle, target, perfil e seleção, ou com arquivo do bundle alterado depois do plan. | Deploy continua negado mesmo com recibo: identidade autenticada e destinos resolvidos não são conferidos. O recibo hasheia `databricks.yml` e os arquivos informados dentro do bundle; não cobre código fora dele. `--select` não restringe o sync. |
| SQL ad hoc | `databricks experimental aitools tools query` com escrita (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`...), mais de um comando que não seja leitura, comentário SQL, `$`, crase, pipe ou encadeamento. Só passa `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`, `VALUES`. | Não vê SQL por SDK, REST, notebook ou editor. Identificador com crase não é aceito. |
| Fecho | `adaptadores/prova.py fechar` recusa `DONE` ou `REVIEW` sem prova atual de cada critério obrigatório. Prova perde validade se arquivo relevante mudar (hash). Fecho adulterado é inválido. | O `stop` do Cursor pede correção em até duas continuações. Não bloqueia texto livre já exibido. Uso: [evidencia/uso.md](../evidencia/uso.md). |

O recibo de plan nasce quando o Cursor observa `exitCode` 0 (`postToolUse`) de um `plan` literal declarado como verificação no contrato de uma fatia ativa. A guarda de antes da execução nunca grava sucesso.

Não implementado: guarda de `run`, de identidade autenticada, de coordenação de dados, de fronteira de produto e `docs-distill`.

## Conduta do agente

Estas regras não têm código. Siga-as sempre.

### Bundle e diretório

Confirme: bundle `saneamento_migracao`, cwd no bundle local, identidade esperada. O cabeçalho da CLI mostra o nome e o e-mail. Deploy do bundle oficial é exclusivo do CI.

Se a guarda negar, corrija o diretório e confira de novo que o destino é o local. Negar uma chamada não torna a tarefa `BLOCKED`.

### Target e plan

Confira o target efetivo e as variáveis resolvidas. Não troque de target em silêncio.

O target `dev` do bundle local grava nos catálogos da entrega. Sem autorização explícita do responsável para aquela operação, não use. Com autorização, exija `plan` atual do mesmo target.

Execute o `plan` autorizado antes do deploy. Um arquivo chamado plan não é o sucesso do comando. O plan deixa de valer se mudar bundle, identidade, target, seleção ou estado relevante. Use `--select`; deploy completo só com intenção declarada.

### Dados compartilhados

Sandbox isola recurso, não dado. Desde 24 set 2026 os pipelines de BP do sandbox também leem a raw do dev. Antes de ingestão ou espinha, confira coordenação no canal, escopo, destino e rodada.

Sem coordenação válida, pause a execução dependente e siga com o trabalho independente. Só envie mensagem ao canal com autorização explícita.

### Fronteira e superfície

Mudança de produto segue a fronteira do invariante 1 do `AGENTS.md` do produto: o que o `include:` de `bundles/src/notebooks/saneamento_migracao/databricks.yml` lista, mais `src/shared/saneamento_migracao/**`. O contrato da fatia recorta essa fronteira. Artefato do harness fica em namespace separado, na raiz do adaptador.

Mudança fora do escopo impede o aceite. Preserve o trabalho anterior do usuário.

### Fecho com evidência

Todo critério obrigatório precisa de prova válida depois da última alteração relevante. Todo achado obrigatório precisa estar tratado. Se editou YAML ou código relevante, a prova anterior não vale: rode de novo a verificação autorizada. Não escreva `DONE` se o fecho for recusado.

### Skills Databricks

As skills ensinam comando e API; não autorizam. A guarda vê `databricks bundle` e o SQL ad hoc. Outros comandos que elas sugerem (`jobs`, `pipelines`, SDK, REST) passam sem checagem: `run-now`, `start-update` e execução em compute exigem autorização explícita.

### Schema das formas

Valide chave, tipo, enum, referência e identidade de cada registro antes de consumi-lo. Registro inválido é rejeitado e corrigido. Estar bem formado não dispara ação.

### Sinal de destilação

Candidato (`docs-distill`, sem código): ao mudar documento com padrão recorrente, sinalize o candidato. A edição não espera pergunta nem destilação para fechar.

## Falha de ferramenta

| Evento | Próxima ação | Limite |
|---|---|---|
| Diretório incorreto | Negue a chamada. Resolva o bundle correto, confira a identidade e repita a operação já autorizada. | Não muda target nem amplia escopo. |
| Teste ausente ou prova obsoleta | Impeça `DONE`. Execute de novo a verificação necessária e autorizada. | A execução que o agente pode fazer fica com o agente. |
| Falha transitória de leitura ou operação idempotente | Registre o diagnóstico e repita dentro do orçamento, com os mesmos argumentos e o mesmo destino. | No máximo duas repetições por operação, respeitando prazo e limite externos. |
| Timeout em operação com efeito externo | Consulte o resultado real por ID antes de tentar de novo. | Se não der para confirmar se a ação ocorreu: `BLOCKED`. Evite `run` ou deploy duplicado. |
| Falta de acesso, ferramenta ou decisão externa | Continue o trabalho independente e nomeie a dependência exata. | `DECIDE` quando falta decisão humana. `BLOCKED` quando falta capacidade ou acesso. |
| Avaliação executada e reprovada | Na trilha de escrita, corrija dentro do orçamento. Em validação, emita `FAILED` sem editar produto. | Orçamento esgotado com resultado conclusivo negativo: `FAILED`. |
| Achado de revisão | Confira a evidência. Corrija achado procedente no escopo e revalide. Descarte falso positivo com fundamento. | Mudança de escopo pede decisão. Achado obrigatório aberto impede `DONE`. |

## Degraus de operação

| Degrau | Efeito | Pré-condição |
|---|---|---|
| 0–2 | Suíte e verificação de origem, conforme o documento vivo | Ambiente adequado e acesso autorizado. `teste_configs_reais` exige `pyspark` instalado. |
| 3 | `bundle validate -t sandbox` | Bundle local e identidade conferidos. Sucesso não publica recurso. |
| 4 | `plan`, depois `deploy` com o mesmo escopo | Plan atual. Seleção e dependências revistas. Publicação dentro da autorização. |
| 5 | `run` de um pipeline | Destinos conferidos. Coordenação válida quando houver ingestão ou espinha. |
| 6 | `run` de job | Etapas anteriores aplicáveis verdes. Escopo e custo aceitos. Confira resultado e arquivo quando o objeto gera arquivo. |

Em trilha de validação, pare no primeiro resultado conclusivo negativo.
