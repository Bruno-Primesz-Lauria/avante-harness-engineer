# Implementação do fluxo aprovado de agentes

## Intenção

Hoje um único agente executa o trabalho estruturado na esteira `saneamento_migracao`: ele implementa, verifica e revisa o próprio resultado, e a disciplina depende do modelo. Só o Cursor coleta prova da fatia; no Claude Code nenhuma fatia estruturada chega a um DONE comprovado.

Este plano torna executável, no Claude Code e no Cursor, o fluxo de agentes aprovado no desenho ([trilhas e fluxogramas](user-harness-esteira-v4.html#trilhas) e [responsabilidades](user-harness-esteira-v4.html#trilhas)). Ao final:

1. **Papéis certos em cada trilha.** O agente principal coordena, e cada trilha estruturada chama os papéis previstos (`map`, `config`, `implement`, `test`, `refute`, `docs` e `dab`) na ordem aprovada e conforme o contrato da fatia. O principal não substitui um papel obrigatório em silêncio.
2. **Escrita, verificação e revisão separadas.** Quem altera não aprova o próprio trabalho. O teste parte do esperado contratado; a revisão independente recebe intenção e aceite, não o racional do autor; edição posterior invalida as duas.
3. **Execução comprovada por observação.** Chamada, log e artefato registrados pelo adaptador do runtime sustentam que um papel rodou. Relato do agente ou YAML escrito pelo principal não bastam.
4. **Fecho que recusa evidência incompleta.** DONE só é aceito com as chamadas previstas observadas, provas atuais e achados tratados. Sem isso, o fecho é BLOCKED, FAILED ou DECIDE, com motivo e ponto de retomada.
5. **Mesmo comportamento nos dois runtimes**, declarado somente depois de observado em sessão real de cada um.

Para chegar lá, uma fonte única de roteamento gera as definições dos agentes e é conferida contra o desenho; o núcleo de provas passa a registrar chamadas, revisões e inspeções; os adaptadores observam os subagentes; e os agentes obrigatórios são ativados por trilha e por runtime, de forma gradual e reversível. Até essa ativação, as instruções operacionais atuais continuam valendo, para que nenhuma instrução exija um agente ainda não instalado.

O plano não amplia autorização. Guardas, permissões do runtime e as regras de deploy/run do `AGENTS.md` continuam prevalecendo, e nenhum agente libera operação hoje vedada.

## 1. Decisões aprovadas

O agente principal coordena: escolhe o caminho, delimita a fatia, define o aceite, delega, trata retornos, controla orçamento e publica o fecho. Os sete agentes são `map`, `config`, `implement`, `test`, `refute`, `docs` e `dab`. Diagnóstico, inspeção documental e paridade são capacidades; não criar agentes adicionais com esses nomes.

| Trilha estruturada | Sequência aprovada | Condições | Pendência |
|---|---|---|---|
| Novo | map opcional → coordenador → config/implement → test → refute → dab se aplicável → coordenador | Config para YAML, implement para código, um de cada vez (decisão de 2026-10-06, P0.1: com o C5, janela de escrita sobreposta torna a autoria inconclusiva). Dab exige critério `ambiente` e autorização registrada. | DEC-1 a DEC-3 aprovadas |
| Manutenção | map opcional → coordenador → test decide/prepara se necessário → config/implement → test → refute → coordenador | Test prepara somente se os casos existentes não decidirem o comportamento contratado. Selecionar escrita por superfície; dab exige critério `ambiente` e autorização registrada. | DEC-1 a DEC-3 aprovadas |
| Correção | diagnóstico com map opcional → coordenador → test reproduz → config/implement corrige → test revalida → refute → dab se aplicável → coordenador | YAML de negócio/ingestão/recurso → config; notebook/Python/SQL → implement. A reprodução usa o mesmo critério: falha esperada autoriza a escrita; aprovação inesperada vai para DECIDE e resultado inconclusivo para BLOCKED. Falha esperada não conclui a correção. Dab exige critério `ambiente` e autorização registrada. | DEC-1 a DEC-3 aprovadas |
| Documentação | map opcional → coordenador → docs → inspeção documental pelo coordenador → refute → coordenador | Não exigir suíte de produto sem relação com o documento. | — |
| Destilar | map opcional → coordenador → docs com distill → inspeção documental pelo coordenador → refute → coordenador | Destino e fonte autorizados; sem duplicar skills de plataforma. | — |
| Validação | coordenador → test → dab se autorizado → test com paridade se exigida → refute → coordenador | Refute foi incluído para alinhar o fluxo ao catálogo. Parar na reprovação conclusiva; não corrigir produto. | — |
| Review | map opcional → coordenador → refute → coordenador | O veredito do artefato é separado do status da tarefa de revisão; indisponibilidade do refute resulta em BLOCKED. | — |
| Entendimento | principal, com map opcional | Sem refute obrigatório; fontes, inferências e preservação de estado verificáveis. | — |

Chamadas de test e refute são obrigatórias onde previstas no caminho estruturado. Config, implement, docs e dab são obrigatórios quando seu gatilho se aplica. Map continua opcional. O caminho simples conserva execução proporcional pelo principal; a classificação não pode ser usada para evitar obrigações de um trabalho estruturado.

Agente obrigatório indisponível impede sucesso da entrega. Registrar BLOCKED e continuar trabalho independente. Se faltar decisão ou autorização humana, usar DECIDE. Permissões superiores do runtime prevalecem; nunca contornar uma proibição de delegação ou operação.

## 2. Estado de partida

Conferido em 2026-10-03 contra o repositório (commit `3454154`).

- `trilhas/README.md` orienta agente único e informa que os papéis não existem.
- `acervo/catalogo.yaml` é inventário sem consumidor executável; os sete agentes estão como `ativacao: opcional`.
- `.claude/agents/`, `.cursor/agents/` e `agentes/` ainda não existem; `adaptadores/gerenciar.py` gera somente hooks.
- Dez skills Databricks estão em `.agents/skills/`. No Claude Code, o plugin `databricks` aparece na sessão principal com o prefixo `databricks:` (por exemplo, `databricks:databricks-core`): 31 skills `databricks-*`, mais `doctor` e `setup`; o HTML cita 29. A carga dentro de subagente não foi observada.
- `implementacao/formas.py` aceita somente contrato, guarda, brief e teste, com produtores `coordenador`, `hook` e `executor_teste`. A forma ataque, do refute, é recusada.
- `implementacao/provas.py` exige comando em todo critério, usa uma única fatia (`principal`) e não registra execução de agentes nem tratamento de achados.
- Cursor coleta provas Shell e solicita correção no stop. Claude Code tem guarda PreToolUse e não tem sessão, coleta nem fecho equivalente.
- A suíte do `AGENTS.md` passa (105 testes unittest e o teste do OpenCode); nenhum teste cobre agentes.

Textos atuais que contradizem o desenho e serão migrados no pacote A5:

| Arquivo | Orientação atual |
|---|---|
| `trilhas/README.md` | Um único agente executa a trilha; não depender de subagentes. O laço comum aceita revisão "sem agente separado". |
| `nucleo/modus-operandi.md` | No estruturado, delegar só com autorização e benefício concreto. |
| `adaptadores/README.md` | Revisor e delegação opcionais. |
| `trilhas/validacao.md` | Sem o passo de refute que o HTML prevê. |
| `acervo/catalogo.yaml` | Agentes opcionais, com gatilhos diferentes do catálogo embutido no HTML (`PECAS`), que já os marca como obrigatórios. |

O roteamento existe hoje em três cópias manuais: `DADOS` e `PECAS` no HTML e o catálogo YAML.

Não considerar configuração presente como evidência de carregamento ou execução real.

## 3. Achados da conferência

### 3.1 Divergências entre HTML e plano

DEC-1 a DEC-3 foram aprovadas em 2026-10-03 e registradas no plano abaixo; D4 e D5 foram alinhados no HTML pelo pacote A3.

| ID | Ponto | HTML | Plano | Proposta | Tipo |
|---|---|---|---|---|---|
| D1 | Quem corrige configuração na correção | Nó "Corrigir achado" com `config / implement`. | Configuração no recorte do implement. | Selecionar pelo tipo de arquivo, como na manutenção: YAML → config, código → implement. Mantém um dono por superfície e evita implement editando YAML de negócio. | DEC-1 — aprovada |
| D2 | Preparação na manutenção | Nó `preparar` (test) sempre antes de alterar. | Sequência omite o passo. | Test prepara somente quando o caso existente não decide o comportamento, como em `trilhas/manutencao.md`. Acrescentar a decisão "Caso cobre?" ao fluxograma e o passo condicional à sequência. | DEC-2 — aprovada |
| D3 | Ambiente em manutenção e correção | Dab só em novo/validação, mas manutenção aceita validação de ambiente. | Idem. | Dab é previsto quando o contrato tem critério `ambiente`, em qualquer trilha de escrita, somente com autorização válida. O gatilho passa a ser o critério, não a trilha. | DEC-3 — aprovada |
| D4 | Review | Sem nó do coordenador antes do refute e sem saída BLOCKED. | coordenador → refute → coordenador; indisponibilidade → BLOCKED. | Alinhar o fluxograma ao plano. | alinhamento |
| D5 | Hook do Cursor em subagente | Afirma que vale para o shell do subagente. | A conferir. | Rebaixar a afirmação para "a observar" até a sondagem P0.5. | alinhamento |

### 3.2 Bloqueios estruturais

Sem tratamento, estes pontos travam trilhas inteiras mesmo com os agentes instalados.

| ID | Bloqueio | Efeito | Tratamento | Pacotes |
|---|---|---|---|---|
| BL1 | Critério sem comando não fecha: o núcleo exige `verificacao.comando` e só aceita evento `teste` vindo do shell (`evidencia/fecho.md` registra o limite). | Docs, destilar e review nunca chegam a DONE pelo núcleo. | Comando condicional ao tipo do critério; registro de inspeção e forma ataque com manifesto do estado avaliado. | P0.3, C1–C3 |
| BL2 | Claude Code sem sessão (`ESTEIRA_SESSAO`) e sem coleta: `fechar` sempre recusa DONE, enquanto o `AGENTS.md` manda o mesmo fluxo para todos os runtimes. | Toda fatia estruturada no Claude Code termina sem DONE. | Declarar o limite já (P0.6); implementar sessão, coleta e fecho (D-CC). | P0.6, D-CC |
| BL3 | A prova é indexada pelo ID de sessão do evento. Subagente com outro ID não encontra a fatia ativa, e o comando passa sem registro. | Test verde em subagente não sustenta DONE; a prova se perde sem aviso. | Sondar os IDs nos eventos de subagente; associar cada chamada à fatia do coordenador; recusar registro órfão. | P0.4, P0.5, C3, D-CC, D-CU |
| BL4 | Capacidades citadas nos fluxos (diagnóstico, paridade, distill, docs-objeto, esteira, novo-objeto, regras, ingestão) são skills candidatas, fora do escopo deste plano. | Pela regra de skill exigida indisponível, correção, destilar e validação com paridade bloqueiam. | Classificar cada uma como obrigatória ou orientativa; a obrigatória vira seção da definição neutra do agente, sem skill nova. | P0.2, A2 |

### 3.3 Formas do desenho v3 fora do catálogo

O HTML v3 descrevia 15 formas de saída. Uma forma só é adotada quando o fecho depende dela para aceitar ou recusar DONE; o relato do autor não é prova (seção 4.4). Decisões humanas de 2026-10-05:

| Forma v3 | Decisão | Motivo | Pacote |
|---|---|---|---|
| contrato, guarda, teste, brief, ataque | adotadas | Base do aceite, guarda, prova executada, fecho e revisão independente. | C1–C3 |
| diagnostico | aprovada, registro mínimo | A capacidade é obrigatória na correção (4.3); sem registro, a obrigação só era cobrada pela reprodução, e hipótese e próximo experimento se perdiam na retomada. | C6 |
| sandbox (Ambiente) | aprovada | É o ponto de efeito externo. Exit code do deploy não comprova target, identidade, seleção nem destinos (limite em `evidencia/uso.md`). | C6 |
| paridade | aprovada | O produto exige paridade para o DONE do objeto. Exit code não mostra recorte, insumos nem divergências; gap sem explicação comprovada precisa impedir a aprovação. | C6 |
| config, implement, docs | não adotadas | Os campos repetem o relato do autor. O núcleo já calcula manifesto e invalida provas por edição. O que faltava, a superfície por papel, passa a ser conferido pelo núcleo em C5, para config e implement. | C5 |
| mapa | não adotada | `map` é opcional e só lê; nenhum fecho depende do mapa. A `chamada` comprova a execução. | — |
| destilar | não adotada | A trilha fecha por critério `inspecao_documental` (forma `inspecao`); fonte e destino viram checagens. | — |
| intencao | não adotada | O objetivo mora no contrato; `ataque.entrada.intencao_ref` aponta para ele. | — |
| resposta | não adotada | Entendimento fecha pelo brief; preservação de estado já é medida por baseline e manifesto. | — |

Triagem, inspeção e chamada não existiam na v3 e foram criadas pelo plano (BL1, BL3 e achados tratados).

## 4. Contrato comum dos agentes

Manter uma definição neutra por agente em `agentes/<nome>.md`, incluindo responsabilidade, gatilho, entradas, ferramentas permitidas, skills, capacidades, saída e condição de término. Gerar versões nativas em `.claude/agents/<nome>.md` e `.cursor/agents/<nome>.md`, sem duplicar a política manualmente.

### 4.1 Fonte única do roteamento

`agentes/roteamento.yaml` é a única fonte da matriz: papéis por trilha, ordem, gatilhos, skills e capacidades. As definições nativas são geradas a partir dele. O HTML continua editado à mão; um teste confere os fluxos de `DADOS` contra o roteamento (responsável por nó e trilhas). O teste checa estrutura e não espelha prompt.

Cada agente registra três metadados distintos: `politica: aprovada`, `instalado` por runtime e `observado` por runtime (versão, data e referência do registro).

### 4.2 Gatilhos derivados do contrato

O papel é previsto quando a trilha o prevê na matriz e o contrato tem o sinal correspondente. `iniciar` calcula o plano de chamadas, com a ordem da matriz, e o grava no estado da fatia; o principal não o escreve à mão. A chamada observada pelo adaptador é o que conta como execução.

| Sinal no contrato | Papel previsto | Trilhas |
|---|---|---|
| Superfície com YAML de negócio, ingestão ou recurso | config | novo, manutenção; correção se DEC-1 aprovada |
| Superfície com notebook, Python ou SQL | implement | novo, manutenção, correção |
| Superfície documental | docs | docs, destilar |
| Critério `teste`, `validacao_dados` ou `paridade` | test (reprodução e revalidação na correção) | novo, manutenção, correção, validação |
| Critério `ambiente` com autorização registrada | dab | novo, validação; manutenção e correção se DEC-3 aprovada |
| Critério `inspecao_documental` ou `analise_codigo` | coordenador inspeciona | docs, destilar, review |
| Trilha estruturada, exceto entendimento | refute | novo, manutenção, correção, docs, destilar, review, validação |
| Investigação ampla | map, sempre opcional | todas |

### 4.3 Skills e capacidades por agente

Carregar apenas a skill pertinente ao gatilho da tarefa, registrar as referências utilizadas e não presumir que a carga no principal chegou ao subagente. A classificação das capacidades é proposta para o pacote P0.2.

| Agente | Skills Databricks | Capacidade embutida | Classificação aprovada P0.2 |
|---|---|---|---|
| map | data-discovery, unity-catalog, docs | diagnóstico (com o coordenador) | obrigatória na correção, com registro `diagnostico` (C6) |
| config | dabs, pipelines, jobs | regras, ingestão | orientativas |
| implement | pipelines, jobs, dbsql, python-sdk, dabs | novo-objeto, esteira | orientativas |
| test | dbsql, data-discovery, core; execution-compute só autorizado | paridade | obrigatória quando o contrato tem critério `paridade` |
| refute | as do artefato revisado, somente leitura; docs | — | — |
| docs | docs | distill, docs-objeto | distill obrigatória em destilar; docs-objeto orientativa |
| dab | core, dabs; jobs ou pipelines para run autorizado | escada-validacao, dab-sandbox (regras já em `guardas/` e no `AGENTS.md`) | referência obrigatória às guardas |

Nomes por runtime: Claude Code usa `databricks:databricks-<nome>` (observado na sessão principal; no subagente, a observar em P0.4). Cursor, Codex e OpenCode leem `.agents/skills/databricks-<nome>/SKILL.md`. Skill ausente gera limitação visível; capacidade obrigatória ausente gera BLOCKED para o trabalho dependente.

### 4.4 Entradas, saídas e restrições

| Agente | Entradas essenciais | Saída verificável | Restrição |
|---|---|---|---|
| map | pergunta, escopo, fontes e baseline | mapa de fontes, dependências, recorte e incertezas | Sem edição de produto |
| config | contrato, arquivos YAML, template e requisitos | arquivos alterados, vínculos com requisitos e estado | Somente superfície atribuída |
| implement | contrato, template/irmão vivo, dependências e skills | alteração, manifesto e critérios a verificar | Sem mudar o aceite unilateralmente |
| test | critério, esperado, comando/ambiente e estado | logs reais, resultados, cobertura e manifesto | Sem corrigir produto ou enfraquecer o esperado; preparação de suíte só no escopo atribuído |
| refute | intenção, aceite, baseline, estado atual e provas | veredito, tentativas, achados (inclusive simplificação, seção 4.5), evidências e limites | Sem editar produto; não receber racional persuasivo do autor |
| docs | contrato, documentos e fontes vivas | documento/instrução e referências | Somente arquivos atribuídos |
| dab | operação, autorização, target/perfil, seleção e pré-condições | resultado real, IDs, logs e destinos observados | Guarda obrigatória; sem retry cego de efeito externo |

Identificar execução, fatia, tentativa, chamada, papel e estado relevante em cada retorno. Hashes comprovam compatibilidade do conteúdo, não autenticam autoria. A chamada observada pelo adaptador sustenta que o papel foi executado; um YAML escrito pelo principal não basta.

### 4.5 Simplicidade

Vale para todos os agentes, no código, no texto e na fala. A simplificação nunca passa por cima, nesta ordem, das regras do harness e do `AGENTS.md` do produto nem das boas práticas Databricks do contexto, lidas na skill pertinente (seção 4.3).

- Escrever o menor código que cumpre o aceite. Cada trecho novo é justificado por um critério, requisito ou dependência; abstração, parâmetro, validação ou camada sem uso atual não entra.
- Reutilizar o que o repositório já tem (irmão vivo, template, função existente) antes de criar algo paralelo.
- Retornos, documentos e fechos dizem o necessário para decidir, de forma direta, sem repetição nem enchimento.
- O princípio cobre o que acompanha o código: comentários, docstrings, código comentado, logs e prints de depuração, configuração sem uso e documentação duplicada. Comentário que repete o código, está desatualizado ou guarda código morto é removível. Comentário que explica o porquê (regra de negócio, decisão não óbvia, vínculo com requisito) fica.
- Em toda revisão, inclusive na trilha review, o refute pergunta: "Isto pode ser simplificado e chegar ao mesmo resultado?" Se sim, registra um achado `simplificacao` com o trecho removível ou a versão mais simples.
- Nas trilhas de escrita, o achado é procedente quando a versão simples mantém o comportamento e passa nos mesmos critérios do contrato, dentro da superfície. Então simplificar é a saída: o achado volta ao autor e segue o tratamento de qualquer achado procedente (orçamento, novo teste e nova revisão). Preferência de estilo sem ganho de volume ou de clareza não é achado.
- Na trilha review, o refute não edita: o achado entra no veredito com severidade e local, e a tarefa de revisar pode fechar DONE com `com_achados`, como qualquer outro achado.
- Boa prática Databricks não é excesso. Exemplos: expectations de qualidade em pipeline (`databricks-pipelines`); timeout, retry e notificação em job (`databricks-jobs`); `COMMENT` em tabela e coluna, que é metadado de governança e descoberta, não comentário de código (`databricks-dbsql`, `databricks-unity-catalog`); permissões e estrutura do bundle (`databricks-dabs`). Antes de propor simplificação em artefato Databricks, o refute consulta a skill do contexto e cita a referência no achado. Simplificação que contraria a boa prática é descartada com essa referência.

## 5. Fases e pacotes

Cada pacote é uma mudança revisável no Git do harness, com aceite próprio e a suíte do `AGENTS.md`. Pacotes sem dependência entre si rodam em paralelo. "Conclui com X" marca início antecipado: o pacote pode começar sobre fixture, mas só fecha depois de X.

| Roda em paralelo | Depende de ordem |
|---|---|
| Todos os pacotes da Fase 0 (P0.3 conclui com P0.4 e P0.5) | A1 → A2 e A1 → A5; C1 → C2 → C3 |
| Frentes A, C e B na Fase 1; A3 junto com A1 | G1 antes de instalar agentes em qualquer runtime |
| Claude Code e Cursor na Fase 2 | Instalação e adaptador → observação → G2 do runtime |
| Trilhas da onda 2 entre si | E0 → onda 1 → G3a → onda 2 → G3b → Fase 4 |

Caminho crítico: P0.4/P0.5 → P0.3 → C1 → C2 → C3 → G1 → D-xx → O-xx → G2 → E0 → E1 → G3a → E2 → G3b → M1 → M2. A frente C define o prazo; priorizá-la.

### Fase 0 — Decisões e sondagens

| ID | Pacote | Responsável | Depende de | Saída verificável |
|---|---|---|---|---|
| P0.1 | Decidir DEC-1, DEC-2 e DEC-3; registrar D4 e D5 | humano, com a proposta da seção 3.1 | — | Seção 1 sem pendência aberta |
| P0.2 | Classificar capacidades e skills candidatas (BL4) | humano, com a proposta da seção 4.3 | — | Tabela 4.3 aprovada |
| P0.3 | Desenho do schema 3.2 (seção 5, "Schema 3.2") | coordenador e humano | conclui com P0.4 e P0.5 | Campos e compatibilidade aprovados |
| P0.4 | Sondagem Claude Code | agente | — | Relatório com versão, documentação consultada e eventos observados |
| P0.5 | Sondagem Cursor | agente | — | Idem |
| P0.6 | Declarar no `AGENTS.md` e no README do adaptador que, no Claude Code, `fechar` recusa DONE até D-CC; a fatia estruturada fecha com status de impedimento e motivo, ou roda no Cursor | agente | — | Texto revisado e suíte verde; entrega imediata, independente do resto |

Perguntas das sondagens, respondidas com documentação oficial atual e observação na versão instalada:

1. Quais campos de frontmatter a versão aceita (ferramentas, herança de modelo, pré-carga de skills)?
2. O subagente recebe `AGENTS.md`/`CLAUDE.md` e as skills do plugin ou de `.agents/skills/`?
3. Os hooks de shell disparam para ferramentas do subagente? Com quais IDs (sessão, conversa, agente, pai)?
4. Há evento de início e fim de subagente, e ele permite associar a chamada à sessão principal?
5. Claude Code: como obter o ID da sessão para `--sessao`, qual evento coleta o resultado da ferramenta e qual pede correção no fim.
6. A guarda de bundle nega dentro do subagente? Observar uma negação real, sem efeito.

Resultado bruto em `.execucoes/sondagens/`; resumo versionado no README do adaptador, com versão e data.

### Fase 1 — Fundações

| ID | Frente | Pacote | Depende de | Saída verificável |
|---|---|---|---|---|
| A1 | A | `agentes/roteamento.yaml` com matriz, ordem, gatilhos (4.2), skills e capacidades (4.3) e metadados (4.1) | P0.1, P0.2 | Cada nó tem responsável e cada condição tem destino |
| A2 | A | Sete definições neutras `agentes/<nome>.md` | A1 | Campos da seção 4 completos; capacidades obrigatórias embutidas |
| A3 | A | Alinhar o HTML (D1–D5) e os metadados do catálogo (aprovado × instalado × observado) | P0.1 | Desenho e catálogo concordam, sem comportamento novo |
| A4 | A | Teste de consistência entre roteamento e fluxos do HTML | A1, A3 | Falha com divergência real e passa no estado alinhado |
| A5 | A | Migrar o texto operacional (`AGENTS.md`, núcleo, trilhas, acervo, adaptadores), condicionado à chave `agentes_obrigatorios` | A1 | Aplicado antecipadamente em 2026-10-05 (merge `3c16e4f`), por decisão humana; com a chave vazia, o comportamento não muda |
| C1 | C | Schema 3.2 em `formas/catalogo.yaml` | P0.3 | Catálogo versionado; registros 3.1 continuam legíveis |
| C2 | C | `formas.py`: ataque, inspeção, triagem e chamada; produtor por papel | C1 | Testes de aceite e recusa por forma |
| C3 | C | `provas.py`: plano de chamadas, critério sem comando, invalidação por edição, atribuição por fatia e papel, chave de ativação | C2 | Testes dos cenários da seção 8 que não dependem de runtime |
| B1 | B | Gerador e verificador neutro → nativo em `gerenciar.py` ou script próprio: idempotente, preserva configuração existente, detecta divergência | P0.4, P0.5; conclui com A2 | Segunda geração sem diferença; divergência manual detectada |

Chave de ativação (C3): `configuracao/politica.json` ganha `agentes_obrigatorios`, com a lista de trilhas habilitadas por runtime, inicialmente vazia. Com a chave vazia, o fecho se comporta como hoje. Com a trilha habilitada, `fechar` exige as chamadas previstas observadas, provas atuais e achados tratados.

Gate G1: suíte do `AGENTS.md` verde, A4 verde e B1 gera os sete agentes de A2 sem diferença na segunda execução.

### Fase 2 — Integração por runtime

Claude Code e Cursor avançam em paralelo e de forma independente.

| ID | Pacote | Depende de | Saída verificável |
|---|---|---|---|
| B2-CC | Instalar os sete agentes no Claude Code | G1 | `.claude/agents/*.md` gerados e sem divergência |
| B2-CU | Instalar os sete agentes no Cursor | G1 | `.cursor/agents/*.md` gerados e sem divergência |
| D-CC | Adaptador Claude Code: sessão, coleta de prova, chamada de subagente observada e conferência de fecho | G1 | Testes de tradução dos eventos sondados em P0.4 |
| D-CU | Adaptador Cursor: chamada de subagente observada e associação à fatia do coordenador | G1 | Testes de tradução dos eventos sondados em P0.5 |
| O-CC | Observar em sessão nova: descoberta dos sete, chamada real, recorte respeitado, skill pertinente carregada, guarda negando no subagente | B2-CC, D-CC | Registro em `.execucoes/` e resumo no README do adaptador |
| O-CU | Idem no Cursor | B2-CU, D-CU | Idem |

Gate G2, por runtime: observação aceita. O runtime que não passa G2 não é ativado; o outro segue.

### Fase 3 — Ativação controlada por trilha

| ID | Pacote | Depende de | Saída verificável |
|---|---|---|---|
| C5 | Superfície por papel: com a trilha ativada, o núcleo confere que config só altera YAML e implement só altera código, dentro da superfície do contrato, e que o principal não edita produto no lugar deles (seção 3.3) | G1, D-CU (D-CC no Claude Code) | Testes de aceite e recusa por papel; chave vazia sem mudança |
| C6 | Adotar as formas `diagnostico`, `sandbox` e `paridade` (seção 3.3) | G1 | Catálogo, validação e fecho cobertos por testes; registros anteriores legíveis |
| E0 | Habilitar manutenção e correção na chave, para os runtimes aprovados em G2 (o A5 já foi aplicado em 2026-10-05). Antes, `adaptadores/prova.py` precisa informar o runtime ao núcleo: com a chave preenchida, `iniciar` e `fechar` sem runtime são recusados. Correção só entra na chave depois de C6 | G2 de ao menos um runtime, A5, C4, C5 | Política e chave coerentes; esvaziar a chave restaura o comportamento atual |
| E1 | Onda 1: cenários de manutenção e correção | E0 | Registros e métricas da onda |
| E2 | Onda 2, em paralelo: novo e validação (dab só em sandbox), docs e destilar, review, entendimento | G3a; C6 para novo e validação | Registros e métricas por trilha |

Gate G3a: onda 1 sem falso DONE, sem violação de escopo e com chamadas previstas iguais às observadas. Gate G3b: o mesmo critério por trilha da onda 2; a trilha que falhar fica desabilitada e as demais seguem. Runtime aprovado em G2 depois da onda 1 entra pelo seu próprio E0.

### Fase 4 — Medição e publicação

| ID | Pacote | Depende de | Saída verificável |
|---|---|---|---|
| M1 | Métricas por trilha e runtime (seção 8) | G3b | Tabela com chamadas esperadas/observadas, defeitos, falsos positivos, falso DONE, tempo, custo, ciclos e volume de código |
| M2 | Atualizar README, HTML e adaptadores com o implementado e o observado; declarar equivalência só onde observada | M1 | Estado publicado separado do que permanece pendente |

Gate G4: aceite final (seção 8).

### Schema 3.2 (P0.3)

Aprovado em 2026-10-03. Reaberto depois da sondagem P0.4 para decidir o executor do teste, e decidido em 2026-10-05. A P0.5 (2026-10-05) mapeou o lado do Cursor; os ajustes estão no último item da lista.

- Plano de chamadas calculado por `iniciar` a partir de `agentes/roteamento.yaml` e do contrato, gravado no estado, nunca no contrato escrito pelo principal.
- `verificacao.comando` obrigatório para `teste`, `ambiente`, `validacao_dados` e `paridade`. Para `inspecao_documental` e `analise_codigo`, `caminhos` e lista de checagens, com produtor coordenador ou refute.
- Forma `ataque`: estado revisado (manifesto), veredito, tentativas, cobertura e achados com id, categoria (inclusive `simplificacao`), severidade, local e evidência.
- Forma `triagem`: revisão de origem, achado, decisão (procedente ou descartado), responsável, evidência da resolução ou motivo do descarte.
- Forma `inspecao`: critério, caminhos, manifesto, checagens e resultado. Edição relevante a invalida, como acontece com o teste.
- Forma `chamada`: papel, runtime, IDs observados, início, fim e status. Produtor é o adaptador, nunca o principal.
- Produtores: `coordenador`, `hook`, `executor_teste` e os sete papéis.
- Compatibilidade: registros 3.1 seguem legíveis e não recebem revisão independente presumida.
- Triagem, inspeção e chamada são formas próprias; as quatro formas 3.2 ficam adotadas após C2 validar os payloads. Diagnóstico, ambiente (`sandbox`) e paridade foram aprovadas em 2026-10-05 e são adotadas em C6. As demais candidatas não são adotadas; motivo por forma na seção 3.3.
- Executor do teste: a forma `teste` continua produzida por `executor_teste`, observada pelo hook, inclusive quando o comando roda num subagente. Ela ganha `agente_id`, o ID do subagente lido nos eventos do runtime. Com a trilha ativada e `test` no plano, o critério `teste`, `validacao_dados` ou `paridade` só fecha se esse ID casar com um `agente_id` de uma `chamada` concluída do papel `test`; senão a pendência é `teste_fora_do_test`. Um teste rodado pelo principal não substitui o papel.
- Exit code: a forma `teste` ganha `exit_code_origem`, com três valores. `campo_resultado` é o campo numérico do runtime (o `exitCode` do Cursor). `evento_sucesso` é o evento de sucesso sem código, que vale 0 (o `PostToolUse` do Claude Code). `texto_falha` é o código lido no texto do evento de falha, diferente de 0 (o `Exit code N` do `PostToolUseFailure`). Formato inesperado mantém `exit_code: null`, ou seja, resultado inconclusivo. Os dois campos são opcionais e aditivos, e registros anteriores continuam válidos.
- Ajustes depois da P0.5 (decididos em 2026-10-05):
  - **Teste no subagente, no Cursor.** O subagente tem `conversation_id` próprio, e nenhum campo do `subagentStart` o traz. O comando conta como do papel `test` quando vem de uma conversa diferente da do coordenador e acontece entre o `subagentStart` e o `subagentStop` de uma chamada `test` (`subagent_id` = `tool_use_id` do `Task`). Não há paralelismo durante o `test`: se outra chamada de subagente estiver aberta na mesma janela, a prova fica inconclusiva. O transcript interno do Cursor não é usado. Implementação em D-CU.
  - **Exit code no Cursor.** O `exitCode` só vem no sucesso. Exit diferente de zero chega em `postToolUseFailure` como `Command failed with exit code N` e usa `texto_falha`, como no Claude Code. Implementado no adaptador.
  - **Diretório no Cursor.** O diretório vem de `tool_input.cwd`. Vazio não é resolvido pela raiz do workspace, porque o diretório da sessão não comprova onde o comando rodou: a verificação declarada é negada com a orientação de preencher o campo. Implementado no adaptador; o comando com `cwd` informado foi observado no reteste.
  - **Contrato de saída do `test`.** É complementar: interpreta (critério, cobertura, manifesto), mas cada item precisa casar com um registro `teste` observado pelo hook. Item sem registro correspondente impede o DONE.

## 6. Grafo de execução

Retângulo: pacote executado por agente. Cápsula: decisão humana. Hexágono: gate. Seta tracejada para frente: início antecipado ("conclui com"). Seta tracejada para P0.1: retorno de controle quando uma observação contradiz o desenho.

```mermaid
flowchart TB
  subgraph F0["Fase 0 · decisões e sondagens — tudo em paralelo"]
    P01(["P0.1 decidir DEC-1..3 e alinhar D4, D5"])
    P02(["P0.2 classificar capacidades"])
    P03(["P0.3 schema 3.2"])
    P04["P0.4 sondagem Claude Code"]
    P05["P0.5 sondagem Cursor"]
    P06["P0.6 limite do Claude Code no AGENTS.md"]
  end

  subgraph F1["Fase 1 · fundações — frentes A, C e B em paralelo"]
    subgraph FA["Frente A · roteamento e política"]
      A1["A1 agentes/roteamento.yaml"]
      A2["A2 definições neutras"]
      A3["A3 alinhar HTML e catálogo"]
      A4["A4 teste de consistência"]
      A5["A5 migração do texto, preparada"]
    end
    subgraph FC["Frente C · evidência"]
      C1["C1 schema 3.2 no catálogo"]
      C2["C2 formas.py"]
      C3["C3 provas.py e chave de ativação"]
    end
    subgraph FB["Frente B · geração"]
      B1["B1 gerador neutro → nativo"]
    end
  end

  G1{{"G1 · suíte, consistência e geração estável"}}

  subgraph F2["Fase 2 · integração — Claude Code ∥ Cursor"]
    subgraph RCC["Claude Code"]
      B2CC["B2-CC instalar agentes"]
      DCC["D-CC sessão, coleta e fecho"]
      OCC["O-CC observar em sessão nova"]
    end
    subgraph RCU["Cursor"]
      B2CU["B2-CU instalar agentes"]
      DCU["D-CU chamadas de subagente"]
      OCU["O-CU observar em sessão nova"]
    end
  end

  G2CC{{"G2 · Claude Code"}}
  G2CU{{"G2 · Cursor"}}

  subgraph F3["Fase 3 · ativação por trilha"]
    E0["E0 runtime no prova.py e habilitar manutenção e correção"]
    E1["E1 onda 1: manutenção e correção"]
    E2N["E2 novo e validação"]
    E2D["E2 docs e destilar"]
    E2R["E2 review"]
    E2E["E2 entendimento"]
  end

  G3a{{"G3a · onda 1"}}
  G3b{{"G3b · por trilha"}}

  subgraph F4["Fase 4 · medição e publicação"]
    M1["M1 métricas por trilha e runtime"]
    M2["M2 publicar estado observado"]
  end

  G4{{"G4 · aceite final"}}

  P01 --> A1
  P02 --> A1
  P01 --> A3
  P03 --> C1
  P04 --> B1
  P05 --> B1
  P04 -.->|conclui com| P03
  P05 -.->|conclui com| P03

  A1 --> A2
  A1 --> A4
  A3 --> A4
  A1 --> A5
  C1 --> C2 --> C3
  A2 -.->|conclui com| B1

  A2 & A4 & C3 & B1 --> G1
  G1 --> B2CC & DCC & B2CU & DCU
  B2CC & DCC --> OCC --> G2CC
  B2CU & DCU --> OCU --> G2CU

  G2CC -->|ao menos um G2| E0
  G2CU -->|ao menos um G2| E0
  A5 --> E0
  G1 --> C4["C4 entrada de inspeção e revisão"] --> E0
  G1 --> C5["C5 superfície por papel"] --> E0
  G1 --> C6["C6 formas diagnóstico, ambiente e paridade"]
  C6 -.->|antes de correção na chave| E1
  C6 --> E2N
  E0 --> E1 --> G3a
  G3a --> E2N & E2D & E2R & E2E
  E2N & E2D & E2R & E2E --> G3b
  G3b --> M1 --> M2 --> G4

  OCC -.->|contradiz o desenho| P01
  OCU -.->|contradiz o desenho| P01
  E1 -.->|achado de desenho| P01
```

## 7. Controle

### 7.1 Ciclo de cada pacote

```mermaid
flowchart LR
  pend["pendente"] -->|dependências concluídas| curso["em curso"]
  curso --> verif{"aceite do pacote passou?"}
  verif -->|não, há orçamento| curso
  verif -->|não, orçamento esgotado| failed["FAILED"]
  verif -->|sim| rev{"revisão achou problema procedente?"}
  rev -->|sim| curso
  rev -->|não| done["DONE e painel atualizado"]
  curso -->|falta acesso ou capacidade| blocked["BLOCKED"]
  curso -->|falta decisão humana| decide["DECIDE"]
  curso -->|observação contradiz o desenho| replan["replanejar em P0.1"]
  blocked -->|impedimento removido| curso
  decide -->|decisão registrada| curso
  replan -->|só dependentes pausam| pend
  done --> gate{{"gate da fase"}}
  gate -->|critério de saída atendido| prox["libera os pacotes seguintes"]
  gate -->|não atendido| curso
```

### 7.2 Regras

1. Um pacote só inicia com as dependências concluídas. Exceção: início antecipado ("conclui com"), sobre fixture; a conclusão continua dependente.
2. Cada pacote fecha com um status de `evidencia/fecho.md` e referência ao commit ou registro. Até D-CC, o pacote executado no Claude Code declara no fecho que a prova da fatia não é coletada nesse runtime.
3. Orçamento padrão do núcleo por pacote: até 3 ciclos de correção e parada após 2 ciclos sem progresso.
4. Observação que contradiz o desenho (sondagem, observação de runtime ou cenário) volta para P0.1. Pausam só os pacotes dependentes; o trabalho independente continua.
5. A ativação é por trilha e runtime, pela chave `agentes_obrigatorios`. Esvaziar a chave é o rollback e não remove agentes instalados.
6. Até G2, a revisão dos pacotes é humana sobre o diff. Depois de G2, o refute do runtime aprovado pode revisar pacotes do harness, sem substituir a decisão humana dos pacotes P0.
7. O painel abaixo é atualizado a cada mudança de status.

### 7.3 Painel

| Gate | Pacotes | Critério de saída | Status |
|---|---|---|---|
| — | P0.1–P0.6 | Decisões registradas e sondagens com evidência | P0.1–P0.2 aprovados; P0.3 decidido (2026-10-05: executor do teste, origem do exit code e ajustes da P0.5); P0.4 concluído (2026-10-04; refeito em 2026-10-05 no CLI 2.1.289 com brutos preservados em `.execucoes/sondagens/`; resumo no README do adaptador Claude Code); P0.5 concluído (2026-10-05, Cursor 3.17.8; resumo no README do adaptador Cursor), três contradições com o desenho, decididas no mesmo dia (Schema 3.2, "Ajustes depois da P0.5"); exit code e diretório já corrigidos no adaptador do Cursor. Reteste no mesmo dia: `sessionStart` dispara em chat novo e o `cwd` informado chega absoluto; P0.6 concluído |
| G1 | A1–A5, C1–C3, B1 | Suíte e A4 verdes; geração estável | Aprovado pelo humano em 2026-10-05, commits `588273f`, `7fc8fd1` e `3c6de1b`. No commit limpo: suíte verde (161 testes), A4 verde (7 testes) e `--verificar` repetível (14 agentes ausentes, esperado antes de B2). Revisão: LF nos agentes gerados; metadados só no roteamento; Bash para map/refute; remoção de `acervo/catalogo.yaml`; HTML v4 como referência de A4; teto de crescimento na 10.1 e pacote C4 |
| G2 Claude Code | B2-CC, D-CC, O-CC | Observação aceita em sessão nova | B2-CC DONE (2026-10-06): sete agentes instalados em `.claude/agents/`, `instalado: true` do `claude_code` em `agentes/roteamento.yaml`, A4 verde e `--verificar` sem divergência nos dois runtimes; a chave `claude_code` continua vazia. D-CC implementado sobre fixture (`9009797`); atualização de `teste_adaptadores.py` aguarda decisão humana; O-CC e G2 pendentes, nada observado no Claude Code |
| G2 Cursor | B2-CU, D-CU, O-CU | Observação aceita em sessão nova | B2-CU DONE (`b4669f0`, 2026-10-05): sete agentes instalados, A4 verde e duas verificações sem divergência. D-CU DONE local (`0457571`): cinco testes de tradução verdes com os agentes instalados; chave real vazia. Kit O-CU versionado em `avaliacao/observacao-cursor/` (roteiro, `preparar.py`, `validar.py`). Primeira sessão O-CU (2026-10-05): M0 conforme; BLOCKED a partir de M2 porque o Cursor 3.17.8 manteve as aspas de `name: "test"` no tipo do subagente (`"test"`), e nenhuma chamada ou prova foi registrada. Correção no gerador (nome e descrição sem aspas, com teste) e reinstalação no Cursor. Na mesma sessão, config e implement rodaram sobrepostos e o coordenador listou `agent-transcripts`; o roteiro foi reforçado. Segunda sessão (2026-10-06, `92068c3`): seis chamadas `concluida` na ordem; prova do test, revisão e ambiente com o `agente_id` do papel observado; BLOCKED só por `superficie_inconclusiva`, porque o roteamento mandava config e implement em paralelo. P0.1 (2026-10-06): escrita passa a ser em série no roteamento, nas trilhas e no HTML. Faltaram M1, M8, M9 (guarda) e a fatia D. Terceira e quarta sessões (2026-10-06, Cursor 3.19.19, `83ed7e3`): o humano colou só o M0; o `followup_message` do `stop` chegou ao chat como mensagem do usuário, e o coordenador leu o roteiro na cópia e fechou a fatia M em DONE sozinho, com seis chamadas `concluida` na ordem, IDs vinculados e sem pendência do C5. M1, M8 e a guarda do M9 ficaram sem observação. P0.1 (2026-10-06): o `stop` segue como em produção; o roteiro passa a ser em turnos (S0, M1 e M9a antes do `iniciar`, sem followup; M0 e M8 no mesmo turno; o resto da fatia corre pelo followup) e sai da cópia. Quinta sessão (2026-10-06, roteiro em turnos): S0, M1, M8, prova do test, revisões vinculadas e DONE nas duas fatias conformes; guarda negou por `cwd_incorreto` no subagente depois de o kit passar a criar o bundle da fixture (`bb2ecf9`); sem `sessionStart`, porque o chat veio aberto com a janela (roteiro reforçado). Três achados: (1) chamada depois do DONE entra na fatia ativa e anula o fecho; decidido manter, por ser conservador, e documentar em `evidencia/uso.md`; (2) `docs` fora da vigilância do C5 permitiu ao coordenador corrigir o guia sozinho; (3) só a última revisão era conferida, e o refute com achado foi descartado sem registro. P0.1 (2026-10-06): `docs` entra em `ESCRITORES`; cada refute observado exige revisão registrada (`revisao:sem_registro`) e achado de revisão anterior exige triagem. Sexta sessão (2026-10-06, Cursor 3.19.19, `dbea3cb`, roteiro em turnos): os sete papéis chamados em série e na ordem; recorte sem pendência do C5; guarda negou no dab por `cwd_incorreto`, sem execução; prova do test, revisões dos refutes e `ambiente_local` vinculados ao `conversation_id` do filho; falso DONE recusado com `chamada:dab`; inspeção invalidada pela edição e refeita; DONE aceito nas duas fatias. Critério 5 parcial: a citação de skill só ficou registrada para map e dab, e os contadores do `subagentStop` vêm 0. **G2 do Cursor aceito pelo humano em 2026-10-06**; `observado` registrado em `agentes/roteamento.yaml` e resumo em `adaptadores/cursor/README.md` |
| — | C4 | Inspeção pelo CLI fecha com chave vazia; revisão exige refute observado com chave ativada | DONE (`2368b33`, 2026-10-05): subcomandos inspecionar/revisar/triar, aceite e adulteração cobertos por testes; revisão Sonnet sem achados procedentes. P0.1: humano aprovou `agente_id` opcional no ataque e validação em `formas.py`; vínculo protegido pelo hash como no test. Chave real vazia |
| — | C5, C6 | C5 antes de E0; C6 antes de correção na chave e de E2 novo/validação | Aprovados pelo humano em 2026-10-05 (seção 3.3). C5 implementado em 2026-10-05, sem commit: janela por chamada em `provas.py` (`abrir_chamada`, `encerrar_chamada`), classes por extensão já existentes no núcleo (`roteamento.yaml` sem mudança) e uso documentado em `evidencia/uso.md`. Fora do brief, por necessidade: os adaptadores do Cursor (`subagentStart`) e do Claude Code (`PreToolUse(Agent)` e descarte na falha) abrem e fecham a janela. Suíte verde (189 testes) com 9 testes novos; não observado em runtime. **C6 implementado em 2026-10-06** (commit `C6:` desta branch): formas `diagnostico`, `sandbox` e `paridade` adotadas no schema 3.2 (aditivas), subcomandos `diagnosticar`, `registrar-sandbox` e `registrar-paridade` em `adaptadores/prova.py` (decisão humana de 2026-10-06), exigências no fecho só com a trilha ativada, registro existente reprovado ou obsoleto bloqueia em qualquer modo; 21 testes novos e um atualizado (suíte em 219); não observado em runtime, e a chave real continua `cursor: [manutencao]` (correção na chave é E0 futuro) |
| — | RT | Codex e OpenCode iniciam e fecham manutenção sem chamadas obrigatórias; runtime ausente e chave codex na política continuam recusados | DONE nesta branch em 2026-10-06: suporte explícito no CLI e no núcleo, com política, coleta de provas e agentes obrigatórios inalterados |
| G3a | E0, E1 | Onda 1 sem falso DONE e com chamadas previstas = observadas | pendente |
| G3b | E2, por trilha | Mesmo critério, por trilha | pendente |
| G4 | M1, M2 | Aceite final | pendente |

## 8. Cenários e aceite final

Começar pelos cenários de manutenção e correção (onda 1). Depois cobrir novo, validação, docs, destilar, review e entendimento (onda 2). Os cenários sem dependência de runtime entram como testes de C3.

| Cenário | Resultado esperado |
|---|---|
| Manutenção de código correta | implement → test → refute; fecho com evidências atuais |
| Manutenção somente YAML | config → test → refute; sem implementação de código artificial |
| Teste verde, requisito ausente | refute encontra lacuna; correção e nova validação/revisão |
| Correção de bug | reprodução falha como esperado; correção passa no mesmo critério |
| Achado falso positivo | descarte fundamentado sem alteração desnecessária |
| Código correto, porém excessivo | refute aponta a versão mais simples; o autor simplifica; test confirma o mesmo resultado nos mesmos critérios |
| Review com comentário redundante ou código comentado | achado `simplificacao` no veredito, sem edição; comentário que explica o porquê é preservado |
| Simplificação que remove boa prática Databricks (por exemplo, uma expectation) | achado descartado com a referência da skill; artefato mantido |
| Edição depois do aceite/revisão | provas anteriores não fecham DONE |
| Agente/skill exigido indisponível | limitação explícita e BLOCKED para o trabalho dependente |
| Validação reprovada | FAILED sem editar produto |
| Review com achados | DONE da tarefa, veredito com_achados do artefato |
| Documentação/destilação | inspeção documental e refute, sem suíte irrelevante |
| Entendimento/caminho simples | fontes verificadas e preservação de estado, sem delegação obrigatória |
| Duas sessões ou escritores concorrentes | sem mistura de provas, autoria atribuída e estado compatível |
| Test executado em subagente | prova associada à fatia do coordenador; nenhum registro órfão |
| Critério de inspeção documental | fecha com registro de inspeção; edição posterior o invalida |
| Fecho sem chamada prevista observada | DONE recusado nos dois runtimes |
| Chave de ativação vazia | comportamento atual preservado, sem exigir agente |
| Ambiente em manutenção (se DEC-3 aprovada) | dab chamado só com critério `ambiente` e autorização válida |
| Config editando código, ou principal editando produto com papel de escrita previsto | DONE recusado com `superficie_violada` ou `edicao_fora_do_papel` (C5) |
| Correção sem diagnóstico registrado | escrita não aceita até o registro `diagnostico` (C6) |
| Deploy com destino não verificado | critério `ambiente` obrigatório não fecha DONE (C6) |
| Paridade com gap sem explicação e exit 0 | registro `paridade` com `fail`; DONE recusado (C6) |

Rodar os checks exigidos pelo `AGENTS.md` e testes focados nas novas garantias. Não adicionar testes que apenas espelhem prompts. Executar os cenários de ativação no chat de Claude Code e Cursor, preservando registros sob `.execucoes/` sem segredos.

Medir por trilha e runtime: chamadas esperadas/observadas, defeitos encontrados por refute, falsos positivos, falso DONE, tempo, custo, ciclos de correção, linhas adicionadas e removidas por fatia e achados de simplificação.

Aceite final (G4): matriz e gatilhos exercitados nos dois runtimes; fecho recusa evidência incompleta; revisão independente ocorre onde prevista; guardas existentes passam suas regressões; README e HTML separam o observado do pendente.

## 9. Limites

Fora deste plano: implementar todos os candidatos do acervo de uma vez, recriar a receita perdida da esteira, mudar regras do produto, autorizar deploy/run, escolher modelos específicos ou prometer independência apenas por trocar de modelo. Herança de modelo continua sendo o padrão nas definições nativas.

Referências técnicas para a implementação: [subagentes Claude Code](https://code.claude.com/docs/en/sub-agents), [subagentes Cursor](https://cursor.com/docs/subagents) e documentação oficial de hooks/skills de cada runtime. Conferir novamente nas sondagens P0.4 e P0.5, pois os recursos e campos variam por versão.

## 10. Próximas fases: briefs para execução por subagentes

Estado em 2026-10-05: Fase 0 concluída; na Fase 1, A1–A5 e C1–C3 concluídos. B1 e E0a implementados; G1 aprovado em 2026-10-05. C4 precisa fechar antes de E0. Por decisão humana no mesmo dia, Cursor vem primeiro; E0 habilitará somente `manutencao` no Cursor depois de G2 aceito. Correção e Claude Code vêm depois. Cada brief abaixo é autocontido: o subagente lê este plano (seções 4 e 5 e o próprio brief), o `AGENTS.md` e os arquivos listados, sem precisar do histórico da conversa.

### 10.1 Regras para todo subagente

- Trabalhar direto na branch `feat/engenheiro-bruno-lauria`, sem branch ou worktree paralela no Git do harness. Sondagem em sessão real pode usar cópia temporária fora do Git, como em P0.4 e P0.5.
- Editar só os arquivos listados no brief. Dois pacotes em paralelo nunca editam o mesmo bloco; em `adaptadores/gerenciar.py` e `adaptadores/executar.py`, cada pacote toca só o ramo do seu runtime.
- Commitar com `git add` explícito dos próprios arquivos, nunca `git add -A`. Mensagem em português, iniciada pelo ID do pacote (por exemplo, `B1: ...`).
- Antes do commit, rodar `py -3 -m unittest discover -s testes -p teste_*.py -v` e `node testes/teste_opencode.mjs`. Suíte vermelha não é commitada.
- Ao concluir, atualizar a linha do painel (7.3) e os metadados afetados (`agentes/roteamento.yaml`; o HTML só nos fluxos), sem declarar observado o que só foi testado localmente.
- Nenhum pacote cria forma, catálogo ou documento novo fora do seu brief. O núcleo (`implementacao/`) só cresce o necessário para o aceite, e a revisão do pacote confere as linhas adicionadas e removidas.
- Fechar com um status de `evidencia/fecho.md`: `DONE` com hash do commit; `BLOCKED`, `FAILED` ou `DECIDE` com motivo e ponto de retomada. Contradição com o desenho volta ao humano (P0.1), sem improvisar.
- Não executar `databricks bundle deploy`/`run`, não editar `prj-avante-analytics-adb/` e não preencher `agentes_obrigatorios` fora do pacote E0.

### 10.2 Ordem e paralelismo

| Onda | Pacotes em paralelo | Libera |
|---|---|---|
| 1 | B1 ∥ E0a | G1 (humano confere) |
| 2 | Claude Code: B2-CC → D-CC → O-CC ∥ Cursor: B2-CU → D-CU → O-CU ∥ C4 ∥ C5 ∥ C6 | G2 por runtime (humano); C4 e C5 liberam E0; C6 libera correção na chave e E2 novo/validação |
| 3 | E0 → E1 | G3a (humano) |
| 4 | E2, por trilha | G3b (humano) |
| 5 | M1 → M2 | G4 (humano) |

D-CC e D-CU podem começar sobre os brutos das sondagens (`.execucoes/sondagens/brutos/`) antes de G1, mas só fecham depois dele.

### 10.3 Briefs

**B1 · gerador neutro → nativo** (agente; libera G1)
- Objetivo: gerar `.claude/agents/<nome>.md` e `.cursor/agents/<nome>.md` dos sete papéis a partir de `agentes/<nome>.md` e `agentes/roteamento.yaml`.
- Ler: seção 4; `agentes/*.md`; `agentes/roteamento.yaml`; os resumos de sondagem em `adaptadores/claude_code/README.md` e `adaptadores/cursor/README.md`; `adaptadores/gerenciar.py` como referência de gravação segura.
- Arquivos: novo `adaptadores/gerar_agentes.py` e novo `testes/teste_gerar_agentes.py`. Não editar `gerenciar.py`.
- Frontmatter só com campos observados. Claude Code: `name`, `description`, `tools`, `model: inherit` e `skills` com os nomes `databricks:databricks-<nome>` das skills fixas do papel. Cursor: `name`, `description` e `model: inherit`; `tools`, `skills` e `readonly` não foram sondados e ficam de fora; o corpo cita `.agents/skills/databricks-<nome>/SKILL.md`. O corpo é a definição neutra.
- Modos: sem flag, mostra; `--verificar` sai com erro quando o instalado diverge do gerado; `--instalar <runtime>` grava com backup e não sobrescreve arquivo editado à mão (divergência detectada por cabeçalho com o hash da fonte).
- Aceite: segunda geração sem diferença; edição manual detectada; teste falha se a definição neutra perder um campo da seção 4. Não instalar nos runtimes: isso é B2.

**E0a · runtime explícito no `prova.py`** (agente; pré-requisito de E0, pode rodar já)
- Objetivo: `adaptadores/prova.py` passa o runtime ao núcleo (`Provas(..., runtime=...)`), por `--runtime` ou por detecção (`CLAUDE_CODE_SESSION_ID` → `claude_code`). Com a chave preenchida para a trilha, `iniciar` e `fechar` sem runtime são recusados, como `Provas.ativada` já exige. RT também aceita `codex` e `opencode` explicitamente; eles ficam fora da chave e continuam sem coleta de provas de shell.
- Arquivos: `adaptadores/prova.py`, `evidencia/uso.md` e testes em `testes/teste_provas.py`.
- Aceite: com a chave vazia, comportamento idêntico ao atual; com a chave preenchida numa fixture, a recusa sem runtime e o aceite com runtime estão cobertos por teste.

**G1 · gate** (humano): suíte verde, A4 verde e `gerar_agentes.py --verificar` estável em duas execuções.

**B2-CC / B2-CU · instalar os agentes** (agente; depois de G1; um por runtime)
- Rodar `py -3 adaptadores/gerar_agentes.py --instalar claude_code` (ou `cursor`) e commitar os sete arquivos gerados.
- Atualizar `instalado: true` do runtime em `agentes/roteamento.yaml` (fonte única), o chip "Ausente" de `#estacao-cursor` ou `#estacao-claude` e a frase de `adaptadores/README.md` sobre as versões nativas.
- Aceite: A4 verde e `--verificar` sem divergência. Instalar não ativa nada: a chave segue vazia.

**D-CC · adaptador Claude Code** (agente; o maior pacote)
- Objetivo: sessão, coleta de prova, chamada de subagente observada e fecho no Claude Code, traduzindo os eventos registrados em P0.4.
- Ler: `adaptadores/claude_code/README.md` (sondagem), `adaptadores/cursor/prova.py` (modelo), `implementacao/provas.py` (`antes`, `depois`, `registrar_chamada`, `conferir`), Schema 3.2 (seção 5) e os brutos em `.execucoes/sondagens/brutos/claude_code/`.
- Arquivos: novo `adaptadores/claude_code/prova.py`; o ramo `claude_code` de `adaptadores/executar.py` e de `adaptadores/gerenciar.py`; `.claude/settings.json` regenerado; README do adaptador; testes de tradução com payloads dos brutos.
- Tradução esperada:
  - Sessão: `session_id` (igual a `CLAUDE_CODE_SESSION_ID`). O shell do subagente chega com o mesmo `session_id` e mais `agent_id`, que vira o `agente_id` da forma `teste`.
  - Prova: `PreToolUse` (Bash/PowerShell) chama `antes`; `PostToolUse` chama `depois` com exit 0 e `exit_code_origem: evento_sucesso`; `PostToolUseFailure` lê `Exit code N` na primeira linha de `error` (`texto_falha`); outro formato fica inconclusivo.
  - Diretório: o `cwd` do envelope é da sessão e não vale. Usar o diretório do prefixo `Set-Location -LiteralPath` / `cd --` já interpretado pela guarda; sem prefixo, negar a verificação declarada com a orientação de informá-lo.
  - Chamada: `PreToolUse(Agent)` marca o início; `PostToolUse(Agent)` traz `tool_response.agentId` e o tipo do subagente, e vira `registrar_chamada` (papel, `ids_observados` com `agente_id`, início, fim, status). Tipo fora dos sete papéis não é registrado.
  - Fecho: `Stop` confere a fatia e devolve `decision: block` com o motivo; com `stop_hook_active: true`, não bloqueia de novo.
- Aceite: testes de tradução para cada evento acima, inclusive teste no subagente casando com a chamada `test` e o cenário "teste rodado pelo principal" gerando `teste_fora_do_test` com a chave ativada numa fixture. O limite temporário do `AGENTS.md` só sai depois de G2.

**D-CU · chamadas de subagente no Cursor** (agente)
- Objetivo: observar as chamadas de subagente e associar ao coordenador o shell que roda no subagente (BL3), conforme "Ajustes depois da P0.5" (seção 5).
- Ler: `adaptadores/cursor/README.md` (sondagem), `adaptadores/cursor/prova.py`, Schema 3.2 e os brutos em `.execucoes/sondagens/brutos/cursor/`.
- Arquivos: `adaptadores/cursor/prova.py`; o ramo `cursor` de `gerenciar.py` (acrescentar `subagentStart`, `subagentStop` e `preToolUse` com matcher `Task`); `.cursor/hooks.json` regenerado; README do adaptador; testes.
- Tradução esperada:
  - `preToolUse(Task)` na conversa do coordenador: guardar `tool_use_id` e `subagent_type` (o papel) no estado da fatia.
  - `subagentStart` abre a janela da chamada (`subagent_id` = `tool_use_id`); `subagentStop` fecha a janela e chama `registrar_chamada`.
  - Shell com `conversation_id` diferente do coordenador, dentro de uma janela aberta: a prova vai para a fatia do coordenador, com `agente_id` igual a esse `conversation_id`, também incluído nos `ids_observados` da chamada. Fora de janela, ou com duas janelas abertas, a prova fica inconclusiva e nada é registrado como sucesso.
  - Não usar o transcript interno nem os contadores do `subagentStop`.
- Aceite: testes com payloads dos brutos para janela única, janelas sobrepostas, shell fora de janela e papel fora dos sete.

**O-CC / O-CU · observação em sessão nova** (humano no Cursor; no Claude Code, um agente pode conduzir em modo headless numa cópia temporária, como em P0.4)
- O-CU: seguir [`avaliacao/observacao-cursor/roteiro.md`](avaliacao/observacao-cursor/roteiro.md). Retomada noutra máquina na seção 10.4.
- Roteiro: com os agentes instalados, abrir sessão nova; chamar cada papel uma vez numa fatia de fixture; conferir descoberta dos sete, recorte respeitado, skill pertinente carregada, guarda negando no subagente, prova do `test` atribuída à fatia do coordenador e `fechar` recusando DONE quando falta uma chamada prevista (chave preenchida só na cópia temporária).
- Saída: brutos em `.execucoes/sondagens/`, resumo versionado no README do adaptador e `observado` preenchido (versão, data, referência) em `agentes/roteamento.yaml`.

**G2 · gate por runtime** (humano): aceita a observação. Runtime que não passa fica fora da chave.

**C4 · entrada de inspeção, revisão e triagem** (agente; depois de G1, antes de E0)
- Problema: `Provas.inspecionar`, `revisar` e `triar` existem no núcleo, mas nenhum CLI ou adaptador os chama. Critério de inspeção nunca fecha DONE (BL1 segue aberto na prática) e, com a trilha ativada, `revisao:ausente` não se resolve. O `ataque` também não está ligado a uma chamada `refute` observada, então o principal poderia registrá-lo.
- Objetivo: três subcomandos em `adaptadores/prova.py` que leem um YAML e chamam o núcleo; com a trilha ativada, o `ataque` só vale se vier de uma chamada `refute` observada, pela mesma regra de `agente_id` do `test`.
- Arquivos: `adaptadores/prova.py`, `implementacao/provas.py` (só o vínculo do `ataque`), `evidencia/uso.md` e testes.
- Extensão aprovada pelo humano em P0.1 (2026-10-05): `agente_id` opcional no ataque de `formas/catalogo.yaml`, validado em `implementacao/formas.py`, para proteger a atribuição pelo hash do evento, como no `test`.
- Aceite: critério de inspeção fecha DONE com a chave vazia; com a chave preenchida numa fixture, `ataque` sem chamada `refute` observada fica pendente.

**C5 · superfície por papel** (agente; depois de G1 e D-CU, antes de E0; no Claude Code, também depois de D-CC)
- Problema: nada comprova que cada papel de escrita ficou na sua superfície. Config poderia editar Python, implement poderia editar YAML de negócio e o principal poderia editar produto em silêncio (seção 3.3).
- Regra: com a trilha ativada, o núcleo compara o manifesto no início e no fim de cada chamada `config` ou `implement` observada. Arquivo alterado na janela precisa estar na superfície do contrato e na classe do papel: YAML de negócio, ingestão ou recurso para config; notebook, Python ou SQL para implement. Fora disso, pendência `superficie_violada`. Alteração de produto fora de qualquer janela de config ou implement, com o papel no plano de chamadas, gera `edicao_fora_do_papel`. Janelas de escrita sobrepostas tornam a atribuição inconclusiva, e nada é aceito como sucesso.
- Arquivos: `implementacao/provas.py` (só a conferência), `agentes/roteamento.yaml` (as `superficies` de config e implement já existem; falta o mapa de cada superfície para padrões de caminho), `evidencia/uso.md` e testes.
- Não usa eventos de edição do runtime, que não foram sondados. Se a sondagem futura os confirmar, eles refinam a atribuição sem mudar a regra.
- Aceite: com a chave vazia, nenhuma mudança; numa fixture com a chave preenchida, os testes cobrem config editando código, implement editando YAML, edição pelo principal, janelas sobrepostas e o caso correto.

**C6 · formas diagnóstico, ambiente e paridade** (agente; depois de G1; antes de correção na chave e de E2 novo/validação)
- Objetivo: adotar em `formas/catalogo.yaml` (schema 3.2, aditivo) e validar em `implementacao/formas.py` as três formas aprovadas na seção 3.3, e fazer o fecho exigi-las onde se aplicam.
- `diagnostico` (registro mínimo; produtor coordenador ou map): `sintoma`, `hipotese_causa`, `base` (`direct`, `derived` ou `reported`), `evidencia_ref`, `criterio_reproducao` e `proximo_passo`. Na correção ativada, a escrita de config ou implement exige um diagnóstico registrado na tentativa, e `criterio_reproducao` precisa existir no contrato.
- `sandbox` (ambiente; produtor `dab`, vinculado à chamada `dab` observada e ao registro `teste` do comando): `operacao`, `cwd`, `bundle`, `target`, `perfil`, `selecao`, `plan_ref`, `plan_estado_compativel`, `autorizacao_ref`, `identidade`, `destinos_resolvidos`, `coordenacao`, `resultado` e `teste_ref`. Campo sem observação integrada (hoje identidade, destinos e coordenação, conforme `evidencia/uso.md`) vale `nao_verificado`, e `nao_verificado` não aprova critério `ambiente` obrigatório.
- `paridade` (produtor `test`, vinculado ao registro `teste` do comando de paridade por `teste_ref` e hash do artefato): `criterio_id`, `recorte`, `insumos`, `contas`, `divergencias` (cada uma com explicação e evidência, ou `pendente`) e `resultado`. Divergência pendente impede `pass`, mesmo com exit 0.
- Arquivos: `formas/catalogo.yaml`, `formas/README.md`, `implementacao/formas.py`, `implementacao/provas.py` (só as exigências no fecho), `evidencia/uso.md` e testes.
- Aceite: testes de aceite e recusa por forma; diagnóstico ausente bloqueia a escrita na correção ativada; deploy com destino `nao_verificado` não fecha critério `ambiente` obrigatório; paridade com gap pendente e exit 0 fica `fail`; registros 3.1 e 3.2 anteriores continuam legíveis.
- **Implementado em 2026-10-06**, com a decisão humana de incluir os subcomandos de registro. O agente declara só o que observou; o núcleo deriva operação, target, perfil, seleção, `cwd`, `resultado`, `autorizacao_ref` e `teste_ref` (campo declarado que divirja é recusado) e calcula `plan_estado_compativel` relendo o recibo de plan. Interpretações a confirmar: (1) `nao_verificado` aprova `validate` e `plan`, que não têm efeito externo, e reprova `deploy` (identidade e destinos) e `run` (também coordenação); como a CLI não observa identidade nem destinos, um deploy contratado só fecha depois dessa integração; (2) "bloqueia a escrita" vale como pendência persistente `escrita_sem_diagnostico:<papel>:<chamada>`, aberta pelo `abrir_chamada` do núcleo, sem negar o `subagentStart` nos adaptadores (fora do brief); (3) `evidencia_ref` do diagnóstico e das divergências fica dentro da fatia, como no ataque; (4) `diagnostico` com produtor `map` é declarado, sem vínculo a chamada, porque `map` não é papel de chamada obrigatória; (5) as definições dos papéis em `agentes/` ainda não instruem o registro pela CLI.

**E0 · ativação da onda 1** (agente, depois do aceite humano de G2): pela decisão de 2026-10-05, preencher primeiro apenas `agentes_obrigatorios.cursor` com `manutencao`. Correção e Claude Code ficam para depois, cada runtime aprovado em G2. Aceite: esvaziar a chave restaura o comportamento atual (teste). **Aplicado em 2026-10-06:** chave `cursor: [manutencao]`; teste `test_e0_chave_real_ativa_so_manutencao_no_cursor_e_esvaziar_restaura` confere a chave real, a recusa sem runtime, o Claude Code fora e o rollback; o `sessionStart` do Cursor passa a indicar `--runtime cursor`; `preparar.py` aceita chave do HEAD contida nas trilhas observadas. Limite atualizado pelo RT: Codex e OpenCode aceitam runtime explícito para abrir e fechar fatias, mas ficam fora da chave e não coletam provas de shell.

**E1 · onda 1** (humano escolhe as tarefas; agente coordena em sessão real): rodar no produto os cenários de manutenção e correção da seção 8. As tarefas e a autorização de ambiente são decisão humana (`DECIDE` até lá). Saída: registros em `.execucoes/` e tabela da onda com chamadas previstas × observadas, falso DONE e violações de escopo. **G3a** (humano).

**E2 · onda 2** (em paralelo por trilha, no formato de E1): novo e validação (dab só em sandbox), docs e destilar, review, entendimento. Cada trilha entra na chave só depois de passar. **G3b** (humano, por trilha).

**M1 · métricas** (agente): consolidar a tabela da seção 8 a partir dos registros de E1 e E2. **M2 · publicação** (agente): README, HTML e READMEs dos adaptadores separando o observado do pendente; declarar equivalência só onde observada. **G4** (humano): aceite final da seção 8.

### 10.4 Retomada noutra máquina

Estado em 2026-10-06, HEAD da branch `feat/engenheiro-bruno-lauria`: G1 aprovado; B2-CU, D-CU, C4 e C5 commitados; P0.1 de escrita em série aplicado; P0.1 do roteiro O-CU em turnos aplicado; P0.1 de `docs` na vigilância e de revisão por refute aplicado. G2 do Cursor aceito na sexta sessão O-CU; E0 aplicado (`agentes_obrigatorios.cursor = [manutencao]`); RT estende a seleção explícita de runtime a Codex e OpenCode, que permanecem fora da chave e sem coleta de provas de shell. C6 implementado (formas diagnóstico, sandbox e paridade, com subcomandos de registro em `adaptadores/prova.py`; chave real inalterada). Próximo passo desta execução: B2-CC e fechamento local de D-CC; depois, entregar o kit O-CC sem executar observação. E1 e G2 do Claude Code continuam decisões humanas.

1. Pré-requisitos: Windows com `py` (Python 3.12+), `pip install -r requirements.txt`, Node, Git e Cursor 3.17.8 ou superior (as sessões de 2026-10-06 à tarde rodaram no 3.19.19).
2. `git clone` e `git checkout feat/engenheiro-bruno-lauria`. Abra o clone no Cursor só para conferir; a observação roda na cópia.
3. Conferência: `py -3 -m unittest discover -s testes -p teste_*.py -v`, `node testes/teste_opencode.mjs`, `py -3 adaptadores/gerar_agentes.py --verificar` (sete `OK` no Cursor; os do Claude Code aparecem `AUSENTE` até B2-CC) e `py -3 avaliacao/observacao-cursor/validar.py`.
4. `py -3 avaliacao/observacao-cursor/preparar.py` e siga [`avaliacao/observacao-cursor/roteiro.md`](avaliacao/observacao-cursor/roteiro.md), lido no clone, a partir da seção 0, item 4. Cole os turnos um a um, no mesmo chat: S0, M1, M9a, M0 + M8 e D0–D3; M2–M10 e D4–D5 correm pelo followup do `stop`.
5. Entrega: brutos, registros e chat da cópia conforme a seção 3 do roteiro. A validação lê só esses arquivos.

Os brutos das cinco primeiras tentativas O-CU e das sondagens P0.4/P0.5 ficam em `.execucoes/` da máquina original, fora do Git; os resumos versionados estão neste painel e nos READMEs dos adaptadores.
