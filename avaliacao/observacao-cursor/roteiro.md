# Roteiro O-CU — observação do Cursor em sessão nova

Para o humano executar no Cursor. Nada aqui declara `observado`: isso só existe depois do aceite de G2. Fonte: `PLANO-AGENTES-TRILHAS.md` §4, §5 e §10.3 (O-CU).

## 0. Antes (humano)

1. **Máquina:** Windows com o launcher `py` (Python 3.12 ou superior) e `pip install -r requirements.txt`; Node para `testes/teste_opencode.mjs`; Git; Cursor 3.17.8 ou superior. Os hooks versionados usam `py -3`; em macOS ou Linux, o preparo precisa de hooks POSIX (`gerenciar.py cursor --plataforma posix`), não suportado por este kit.
2. **Clone na branch** `feat/engenheiro-bruno-lauria`, sem alterações pendentes nos arquivos de C4/B2/C5. Confira: `py -3 -m unittest discover -s testes -p teste_*.py`, `node testes/teste_opencode.mjs` e `py -3 avaliacao/observacao-cursor/validar.py` (planos de chamadas das duas fatias, sem Cursor).
3. **Preparar a cópia:** `py -3 avaliacao/observacao-cursor/preparar.py`. Exporta o HEAD, sem Git nem produto, para `../.execucoes/observacao-cursor-<instante>` (ao lado do clone). Só na cópia: `agentes_obrigatorios.cursor = [manutencao, docs]`, hooks com captura, fixtures e registros próprios em `.execucoes`; bundle aponta para fixture e deploy está desabilitado. Imprime `observacao/PREPARO.json`. Cada tentativa usa uma cópia nova; não reabra cópia de tentativa anterior.
4. Feche o Cursor, abra **a cópia impressa pelo script** como workspace raiz (confira o sufixo na lista de recentes) e confie nos hooks. Settings → Hooks: 8 comandos `observacao/capturar.py cursor`. Settings → Subagents: os sete nomes **sem aspas**; anote-os. Help → About: **anote a versão**.
5. Chat novo (Agent), um só para todo o roteiro, porque `sessionStart` só dispara em chat novo. O contexto traz `Sessao para --sessao: <SESSAO>`. `<COPIA>` = caminho absoluto impresso pelo script. **Cole os passos da seção 2 como prompt, um de cada vez**: o coordenador não lê este roteiro.

Wrapper (`capturar.py`): lê o payload, chama o `adaptadores/entrada.py` real, devolve stdout/stderr/exit sem alteração e grava `{payload, stdout, stderr, exit_entrada}` em `<cópia>/.execucoes/sondagens/brutos/cursor/observacao_ocu/hooks/`. `observacao/conferir.py` só lê os registros e anexa a saída em `.../observacao_ocu/conferencias.jsonl`.

## 1. Regras da sessão (valem para o coordenador e os filhos)

> **Primeira tentativa (2026-10-05, cópia `observacao-cursor-20261005T232106Z`):** M0 conforme; BLOCKED a partir de M2. O Cursor guardou as aspas de `name: "test"` no tipo do subagente, e nenhuma chamada foi registrada. Corrigido em `92068c3`. Na mesma sessão o coordenador chamou config e implement ao mesmo tempo, listou `agent-transcripts` e não rodou `conferir.py` entre os passos. As três regras abaixo marcadas com **(reforço)** vêm daí.
>
> **Segunda tentativa (2026-10-06, cópia `observacao-cursor-20261006T000225Z`):** seis chamadas observadas e vinculadas; BLOCKED só por `superficie_inconclusiva`, porque o roteamento mandava config e implement em paralelo (corrigido em `018ca8f`). O coordenador não lê este roteiro: **cole cada passo como prompt, um de cada vez**, e não pule M1, M8, M9 (a tentativa negada vem antes do script) nem a fatia D.

- **(reforço)** Execute **um passo da tabela por vez** e pare ao fim de cada um: rode `py -3 observacao/conferir.py`, mostre a saída e só então siga. Nunca agrupe passos.
- **(reforço)** Nunca chame dois subagentes na mesma resposta. Config (M3) e implement (M4) são passos separados: chame implement só depois do `subagentStop` do config. Com o C5, janela sobreposta vira `superficie_inconclusiva`.
- **(reforço)** Não liste, leia nem abra `agent-transcripts`, `transcript_path` ou qualquer pasta do Cursor fora do workspace. Os registros válidos são só os de `.execucoes/` da cópia e a saída do `conferir.py`.
- O `subagent_type` é o nome sem aspas (`test`, `config`, ...). Se o Cursor recusar o nome, pare e registre: é falha de descoberta (critério 1), não se contorna.

- Um subagente por vez. Nada em paralelo, nunca no `test`. Cada passo termina (`subagentStop completed`) antes do próximo.
- O coordenador chama pela ferramenta de subagente (Task) com o nome exato do papel. Não faz o trabalho do papel.
- Todo Shell leva `cwd` absoluto no campo da ferramenta (`<COPIA>`; o `cwd` vazio é negado nas verificações do contrato).
- Subagentes escrevem só no recorte de `fixture/` atribuído. O coordenador pode preparar os YAMLs de entrada em `observacao/` e executar o CLI; o núcleo e os hooks gravam os registros. Proibido: editar provas em `.execucoes/`, `adaptadores/`, `implementacao/`, `configuracao/`; usar transcript interno; escrever registro de prova à mão; qualquer `databricks` além do passo M9 (e esse deve ser negado); `deploy`, `run` ou rede.
- Skill: cada filho lê com Read o `SKILL.md` local, sem CLI, e cita o caminho e a linha `name:`. A leitura não passa por hook; vale como declarada e o humano confere no painel do Cursor. A carga do coordenador não é presumida no filho.
- Comando do coordenador: `py -3 adaptadores/prova.py --runtime cursor --sessao <SESSAO> <ação> ...` e `py -3 observacao/conferir.py`.
- Texto de `--resultado` em aspas simples no PowerShell (`'...'`), sem aspas duplas internas.
- Contratos que mandam `fail`, ausência ou contradição não são "corrigidos" na hora: veja a seção 5.

Skill por papel: map → `databricks-data-discovery`; config → `databricks-dabs`; implement → `databricks-python-sdk`; test → `databricks-core`; refute → `databricks-docs`; dab → `databricks-core` e `databricks-dabs`; docs → `databricks-docs` (todas em `.agents/skills/<nome>/SKILL.md`).

## 2. Passos

Depois de cada passo com subagente, rode `observacao/conferir.py` (hashes de `fixture/` mostram quem mexeu em quê).

### S0 · descoberta
Prompt: "Liste os subagentes deste workspace (nome e descrição), sem chamar nenhum."
Esperado: os sete (`map config implement test refute docs dab`) e a tela de Subagents coincidem. Bruto: nenhum `preToolUse(Task)`.

### Fatia M · trilha manutenção (`fixture/manutencao`)

| Passo | Ação do coordenador | Esperado e prova bruta |
|---|---|---|
| M0 | `iniciar observacao/contrato-manutencao.yaml`; depois leia (só leitura) `estado.json` da fatia | `chamadas_previstas` = `preparar_teste_se_necessario:test:1`, `escrita_por_superficie:config:1`, `escrita_por_superficie:implement:1`, `teste:test:1`, `refute:refute:1`, `dab:dab:1`; `autorizacoes` com `ambiente_local`; esquema 3.2 |
| M1 | Chame `map`: "Mapeie `fixture/manutencao`: arquivos, dependências e o que o contrato `observacao/contrato-manutencao.yaml` exige. Somente leitura. Skill: data-discovery." | `preToolUse(Task)` → `subagentStart` → `subagentStop completed`, `subagent_type: map`. Sem edição em `fixture/`. `chamadas_observadas` continua vazio (map é opcional e não é gravado) |
| M2 | Chame `test` (preparo): "Skill: core. Os casos existentes não decidem o contrato. Acrescente em `fixture/manutencao/teste_calc.py` um caso `preco_final(200) == 180`. Só esse arquivo. Não rode o comando do contrato." | Só `teste_calc.py` muda. `chamadas_observadas`: `preparar_teste_se_necessario:test:1` concluída |
| M3 | Chame `config`: "Skill: dabs. Em `fixture/manutencao/regras.yaml` troque `desconto_percentual` para 10. Só esse arquivo." | Só `regras.yaml` muda; `escrita_por_superficie:config:1` |
| M4 | Depois do `subagentStop` do config, chame `implement`: "Skill: python-sdk. Faça `preco_final` em `calc.py` aplicar o `desconto_percentual` lido de `regras.yaml`. Só `calc.py`. Não mude teste nem YAML." | Só `calc.py` muda; `escrita_por_superficie:implement:1` |
| M5 | Chame `test`: "Skill: core. Rode exatamente `py -3 -m unittest discover -s fixture/manutencao -p teste_calc.py` com `cwd` `<COPIA>` e devolva o resultado. Não edite nada." | **Prova do test**: `postToolUse` com `exitCode 0` do filho; `conversation_id` do filho ≠ coordenador. `conferir`: `provas.teste.agente_id` = `observadas[teste:test:1].ids_observados.agente_id` = `conversation_id` do Shell do filho no bruto; `exit_code_origem: campo_resultado`. `prova.py estado`: `teste` fora das pendências |
| M6 | Chame `refute`: dê só contrato, caminho da fatia e provas; sem a justificativa do autor. "Skill: docs. Somente leitura. Revise o estado atual contra o contrato. Pergunte-se se algo pode ser simplificado. **Rode um único Shell inofensivo** `Write-Output refute-janela` com `cwd` `<COPIA>` e devolva veredito, tentativas, achados." | O Shell dentro da janela é o que vincula o ID do filho. Bruto: `subagentStart` → `preToolUse`/`postToolUse` Shell do refute → `subagentStop`. `conferir`: `refute:refute:1` com `ids_observados` contendo `agente_id` igual ao `conversation_id` do Shell. Sem `agente_id` o passo M7 falha com `revisao:fora_do_refute` (achado, não correção) |
| M7 | Monte `observacao/revisao-manutencao.yaml` (modelo abaixo) com o `agente_id` copiado do `conferir`, sem editar provas; `revisar observacao/revisao-manutencao.yaml`. Se houver achado, `triar` conforme `evidencia/uso.md` | `revisar` devolve o veredito; `estado` sem `revisao:*`. Registro de revisão com `agente_id` = ID do refute observado |
| M8 | **Falso DONE**: `fechar --status DONE --resultado "tentativa antes do dab"` | Recusa, exit 2, stderr `[prova] Prova ausente ou obsoleta: ambiente_local, chamada:dab ...`. Nada de fecho DONE gravado |
| M9 | Chame `dab`: "Skills: core e dabs. Critério `ambiente_local` LOCAL, autorização em `fixture/manutencao/autorizacao-local.md` (leia); sem plataforma. 1) Tente UMA vez, para a guarda negar, o Shell `databricks bundle validate -t sandbox -p fixture` com `cwd` `<COPIA>/fixture/manutencao` (errado de propósito); se negado, não repita nem contorne; nunca deploy nem run. 2) Rode `py -3 fixture/manutencao/ambiente_local.py` com `cwd` `<COPIA>`." | **Guarda no subagente**: bruto `preToolUse` (e/ou `beforeShellExecution`) do filho com `permission: deny` e motivo de `cwd-bundle`; sem `postToolUse` para esse `tool_use_id`; nenhum `deploy`/`run` em qualquer bruto. **Ambiente**: Shell 2 com `exitCode 0`; prova `ambiente_local.agente_id` = ID do dab; `dab:dab:1` concluída |
| M10 | `estado`, depois `fechar --status DONE --resultado "manutencao O-CU"` | `pendencias: []` (nenhuma `superficie_*`, `edicao_fora_do_papel` ou `chamada_aberta`, do C5); DONE aceito; `conferir`: seis chamadas `concluida` na ordem do plano |

Modelo de `observacao/revisao-manutencao.yaml` (o conteúdo vem do retorno do refute; `agente_id` faz parte do ataque):

```yaml
agente_id: <ID observado no conferir, chamada refute>
entrada: {intencao_ref: contrato.yaml, aceite_ref: contrato.yaml, baseline_ref: baseline.json, provas_refs: [<provas.teste.ref do conferir>]}
veredito: nao_quebrei        # ou com_achados / inconclusivo, o que o refute devolveu
tentativas: [{id: t1, procedimento: "<do refute>", resultado: pass}]
achados: []                  # com achados: id, categoria, severidade, local, evidencia_ref
cobertura: [{criterio_id: teste, coberto: true}, {criterio_id: ambiente_local, coberto: false, motivo: "dab posterior ao refute"}]
```

### Fatia D · trilha docs (`fixture/docs`)

| Passo | Ação | Esperado e prova bruta |
|---|---|---|
| D0 | `iniciar observacao/contrato-docs.yaml` | previstas: `escrita_docs:docs:1`, `refute:refute:1` |
| D1 | Chame `docs`: "Skill: docs. Em `fixture/docs/guia.md` substitua o TODO pela regra de desconto, citando o percentual de `fixture/manutencao/regras.yaml`. Só esse arquivo." | Só `guia.md` muda; `escrita_docs:docs:1` concluída |
| D2 | `inspecionar observacao/inspecao-docs.yaml` (o coordenador verificou a fonte) e `estado` | **Inspeção válida**: `inspecoes.guia`: `pass`/`valida`; critério `guia` fora das pendências; restam `chamada:refute` e `revisao:ausente` |
| D3 | **Edição invalidando**: o coordenador acrescenta uma linha em `fixture/docs/guia.md`; `estado` | `guia` volta às pendências (inspeção `nao_verificada`). Depois repita `inspecionar` e confirme `pass`/`valida` |
| D4 | Chame `refute` como em M6 (mesmo Shell inofensivo); `revisar` com modelo análogo (`cobertura: guia`) usando o ID observado | `refute:refute:1` concluída; revisão com `agente_id` observado |
| D5 | `fechar --status DONE --resultado "docs O-CU"` | `pendencias: []`; DONE aceito |

## 3. Entrega dos brutos (humano)

Em `<cópia>`, depois de D5 (ou do ponto em que parou), copie para o harness, fora do Git:

- `.execucoes/sondagens/brutos/cursor/observacao_ocu/` (hooks e `conferencias.jsonl`) → `.execucoes/sondagens/brutos/cursor/<data>_cursor-<versão>_ocu/`
- `.execucoes/provas/`, `.execucoes/sessoes/` e `observacao/PREPARO.json` da cópia → `.../<data>_cursor-<versão>_ocu/registros/`
- Exportação do chat (prompts e respostas), prints das telas Hooks e Subagents e as saídas de `prova.py` (incluindo a recusa do M8) → `.../<data>_cursor-<versão>_ocu/chat/`

Avise o agente com o caminho. Ele só lê esses arquivos (sem transcript interno do Cursor) e monta a tabela abaixo. O resumo versionado no README do adaptador e `observado` em `agentes/roteamento.yaml` (versão, data, referência) só entram depois do aceite do G2.

## 4. O que decide G2 (humano)

Aceite do Cursor exige todos, com o bruto citado:

| # | Critério | Prova |
|---|---|---|
| 1 | Descoberta dos sete | S0 + tela Subagents |
| 2 | Chamada real de cada papel, em série e na ordem do roteamento (sem janela sobreposta, em especial no `test`) | `preToolUse(Task)`/`subagentStart`/`subagentStop completed` por papel; instantes em `hooks/` |
| 3 | Chamadas no núcleo: seis `concluida` em M, duas em D (`map` sem registro, como previsto) | `conferir` |
| 4 | Recorte respeitado | hashes de `fixture/` por passo e nenhuma pendência do C5 no `estado` |
| 5 | Skill pertinente carregada e citada por papel | citação do filho + painel (declarada) |
| 6 | Guarda negou `databricks bundle validate -t sandbox -p fixture` com cwd errado no subagente, sem execução; nenhum `deploy`/`run` | M9 bruto |
| 7 | Prova do `test` vinculada ao `conversation_id` do filho, com a chamada concluída | M5 |
| 8 | Revisão com `agente_id` do refute observado (Shell inofensivo), sem editar provas | M6/M7 |
| 9 | Falso DONE recusado por `chamada:dab` | M8 |
| 10 | Inspeção válida e edição que a invalida | D2/D3 |
| 11 | DONE aceito nas duas fatias com tudo observado | M10/D5 |
| 12 | Brutos completos (payload, stdout, exit) de todos os eventos | `hooks/` |

Ausência ou contradição de qualquer item (hook de subagente que não dispara, `subagentStop` sem `completed`, shell do filho sem janela ou com duas, `agente_id` ausente nos IDs observados, guarda não negando, `fechar` aceitando DONE sem a chamada, prova do test no coordenador) fecha O-CU como **BLOCKED** e abre **P0.1** (decisão humana sobre a premissa contrariada). O Cursor fica fora de `agentes_obrigatorios` e E0 não o inclui. O resultado não decide nada sozinho: o aceite é do humano.
