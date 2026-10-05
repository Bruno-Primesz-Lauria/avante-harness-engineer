# Plano de implementação da memória compartilhada do harness

Data: 2026-10-03. Estado: proposta revisada, não iniciada. Reconferida em 2026-10-05 contra a branch `feat/engenheiro-bruno-lauria` (commit `a0a5604`), depois de A1–A5, C1–C3 e P0.5 do plano de agentes.

## Intenção

Hoje, o conhecimento que um engenheiro e seu agente descobrem durante o trabalho se perde ou fica preso a uma pessoa. Uma causa de falha confirmada, um limite de ferramenta observado ou o motivo de uma decisão ficam na conversa, nos registros locais de `.execucoes/` (fora do Git) ou na memória pessoal do runtime, como a auto memory do Claude Code. Outro engenheiro não recebe esse conhecimento, e a sessão seguinte, até do mesmo engenheiro, tende a redescobri-lo. O harness também não tem lugar para conhecimento que é contexto e não regra: a trilha `destilar` só leva padrões recorrentes para skills e referências, que são instruções.

Este plano cria uma memória do time, versionada no Git do harness, que engenheiros e agentes consultam conforme a tarefa e atualizam pelo fluxo de revisão. Ao final:

1. **O conhecimento verificado passa a ser do time.** Uma descoberta com fonte vira nota em `memoria/` e é revisada por PR. Depois do merge, qualquer engenheiro a recebe ao atualizar o clone, sem depender da conversa original, de arquivos pessoais ou do Obsidian.
2. **O agente encontra a nota quando ela importa.** A consulta é proporcional: no caminho simples, só quando o pedido toca assunto ou caminho com nota; no estruturado, as notas usadas entram nas fontes do contrato. Pedido sem relação com a memória não paga o custo da leitura.
3. **A nota orienta e não manda.** Ela fica abaixo das permissões, do pedido, do `AGENTS.md` e do código vivo. Não concede autorização nem comprova teste. Quando diverge da fonte, vale a fonte, e a nota é corrigida. Procedimento obrigatório continua no arquivo operacional (trilha, guarda, skill ou `AGENTS.md`).
4. **Só o conteúdo revisado conta como base.** O Git identifica a proposta (nota em branch ou alterada localmente), que é citada como proposta. A publicação passa sempre por PR; nenhuma automação publica nota.
5. **A memória continua confiável com o tempo.** Toda nota ativa tem fonte acessível a partir de outro clone e data de verificação. O `validar` recusa estrutura inválida e avisa quando os arquivos relacionados mudaram. A substituição explícita preserva o histórico.
6. **Funciona em qualquer runtime e sem ferramenta extra.** A base é Markdown no Git, e o Obsidian é opcional. O suporte de cada runtime só é declarado depois de observado em sessão real.

Para chegar lá, a Fase 1 entrega a estrutura, a política, as notas iniciais e o `validar`. A Fase 2 acrescenta busca, índice gerado e aviso de revalidação. A Fase 3 comprova o compartilhamento entre dois engenheiros com clones independentes. A Fase 4 automatiza consulta e sinalização por runtime, apoiada no schema 3.2 do plano de agentes. A memória reusa as peças já previstas (`destilar`, `distill` e `docs-distill`) em vez de criar peças paralelas.

O plano não amplia autorização e não altera guardas. Nas primeiras entregas, também não muda o núcleo de provas nem o schema de eventos. A memória do produto fica de fora: será adotada depois, no repositório dele. As memórias nativas dos runtimes continuam pessoais e não são substituídas. A criação deste documento não ativa a memória, não instala ferramentas e não altera as instruções operacionais atuais.

## 1. Objetivo e resultado esperado

Versionar uma memória em Markdown, distribuída pelo Git, consultada conforme a tarefa e atualizada pelo fluxo de revisão do time. O Obsidian será uma interface opcional para ler, navegar e editar os mesmos arquivos.

O processo deve permitir que um engenheiro registre uma descoberta verificada, que outro receba a nota ao atualizar seu clone e que o agente desse engenheiro encontre o conhecimento sem depender da conversa original, de arquivos pessoais ou do Obsidian instalado.

As notas são contexto `advisory`, com o mesmo estatuto de `nucleo/contexto-avante.md`: orientam a investigação e nunca valem como regra, autorização ou prova.

A primeira entrega cobre a memória do harness. A memória específica do produto será adotada depois, no repositório dele, com suas regras e seu fluxo de revisão.

## 2. Estado atual e limites

| Ponto | Estado conferido | Consequência para o plano |
|---|---|---|
| Instruções comuns | `AGENTS.md` é a entrada; `CLAUDE.md` importa `@AGENTS.md`. Leituras sob demanda seguem o padrão "Leia X quando ..." (caso de `contexto-avante.md`). | Uma linha condicional no `AGENTS.md`; a política fica em `memoria/README.md`. |
| Contexto advisory | `nucleo/contexto-avante.md` é advisory: "nunca é fonte de regra nem de decisão". | As notas adotam o mesmo estatuto e a mesma redação. |
| Persistência operacional | `.execucoes/` guarda provas, estado, sessões e diagnósticos e está no `.gitignore`. Hoje só contém diretórios de teste. | Preservar os registros locais e compartilhar notas destiladas em outra pasta. |
| Destilação | `trilhas/destilar.md` limita a superfície a skills e referências do adaptador. Desde o A5, prevê `docs` com `distill` no passo 2, inspeção do coordenador e `refute`, quando a trilha estiver em `agentes_obrigatorios`. | Incluir notas como destino e ajustar o aceite, sem mexer na sequência de papéis. Notas `.md` já cabem na superfície documental do `docs`. |
| Acervo | `distill` (skill) e `docs-distill` (hook que "sinaliza candidato; não exige pergunta nem destilação") são candidatos em `acervo/README.md`. | Reusar essas peças para destilar e sinalizar notas. Não criar peça paralela. |
| Schema de eventos | Schema 3.2 adotado (C1–C3): `contrato`, `guarda`, `brief`, `teste`, `ataque`, `triagem`, `inspecao` e `chamada`. `destilar` continua candidata. | Notas têm metadados próprios e não são apresentadas como eventos adotados. |
| Fecho técnico | O núcleo já aceita critério `inspecao_documental` sem comando (`Provas.inspecionar`, forma `inspecao`), mas `adaptadores/prova.py` ainda não expõe a inspeção: só `iniciar`, `estado` e `fechar`. | A Fase 1 mantém o comando `validar`, que fecha como critério `teste` em qualquer runtime com coleta. A inspeção documental cobre o que o comando não exercita quando houver caminho de CLI para ela. |
| Prova por runtime | Só o Cursor coleta prova. No Claude Code `fechar` recusa `DONE`, porque não há sessão nem coleta (BL2 do plano de agentes). | Fatia estruturada fecha `DONE` só no Cursor; no Claude Code fecha com impedimento declarado (DM-2). |
| Retrato da prova | O controle do manifesto inclui `implementacao/`, `adaptadores/`, `configuracao/`, `formas/catalogo.yaml` e `agentes/roteamento.yaml` (`CONTROLE` em `implementacao/provas.py`). `memoria/` fica fora. | Editar nota não invalida a prova de outra fatia, salvo se o contrato declarar o caminho. Código da memória nessas pastas passa a integrar o retrato de toda fatia. |
| Git e revisão | Branch de referência `main` (`origin/HEAD`). Não há `.github/`, CODEOWNERS nem CI no repositório. | Revisor é decisão do time (DM-1). A validação roda localmente antes do PR, como as suítes. |
| Plano de agentes | P0.6, A5 e C1–C3 concluídos; o texto do A5 já está em `AGENTS.md`, núcleo, trilhas, acervo e adaptadores. A próxima onda (B1, E0a, D-CC, D-CU) mexe em `adaptadores/` e `testes/`. Define a sequência de `destilar`: docs com distill → inspeção documental → refute. | Partir do texto do A5, sequenciar as entregas (DM-3) e manter `trilhas/destilar.md` compatível com essa sequência. |
| Memória nativa dos runtimes | Runtimes podem manter memória própria fora do repositório (por exemplo, a auto memory do Claude Code em `~/.claude/projects/`). | Ela é pessoal e não substitui nem alimenta esta memória. Conhecimento para o time entra em `memoria/` por PR. |
| Fronteira de repositórios | O produto tem Git próprio e está ignorado pelo Git do harness. | Conhecimento do produto acompanha o repositório do produto. |

Referências locais: [AGENTS.md](AGENTS.md), [README](README.md), [política](nucleo/modus-operandi.md), [contexto Avante](nucleo/contexto-avante.md), [destilação](trilhas/destilar.md), [acervo](acervo/README.md), [formas](formas/README.md), [fecho](evidencia/fecho.md), [uso da prova](evidencia/uso.md), [adaptadores](adaptadores/README.md) e [plano de agentes](PLANO-AGENTES-TRILHAS.md).

## 3. Desenho da memória

### 3.1 Localização e distribuição

```text
avante-harness-engineer/             # repositório do harness
  AGENTS.md
  memoria/                           # conteúdo compartilhado por Git
    README.md                        # política, revisores, contribuição e Obsidian
    indice.md                        # assuntos → notas (gerado a partir da Fase 2)
    modelos/nota.md                  # modelo, fora do índice e das buscas
    decisoes/                        # decisões e seu contexto
    aprendizados/                    # causas, correções e limites verificados
    padroes/                         # procedimentos recorrentes com fontes
    .obsidian/                       # configuração local do Obsidian, fora do Git
  .execucoes/                        # registros locais, fora do Git
  prj-avante-analytics-adb/          # clone independente do produto
```

Criar as pastas de notas conforme surgirem conteúdos reais. A primeira entrega precisa dos três documentos de memória e de duas ou três notas iniciais sustentadas por fontes versionadas.

O nome do arquivo é o `id` da nota: minúsculas, hífen, sem espaço nem acento (`aprendizados/claude-code-fechar-recusa-done.md`). É a identidade usada pelos links e pelo Obsidian; um campo independente criaria duas identidades.

A branch `main` é a referência compartilhada. A distribuição ocorre após o merge e a atualização dos clones. Um clone desatualizado mantém a versão de memória que recebeu na última atualização.

Links:

- Entre notas, link Markdown relativo (`[texto](../decisoes/nome.md)`). Wikilink `[[...]]` e caminho absoluto são recusados, para que GitHub, scripts e agentes resolvam o mesmo link.
- Arquivos fora de `memoria/` entram em `fontes` ou `caminhos`, relativos à raiz do harness, como nos contratos. O Obsidian com vault em `memoria/` não abre arquivos fora do vault.

Obsidian: o engenheiro pode abrir apenas `memoria/` como vault. Ignorar `memoria/.obsidian/` inteiro na primeira entrega; assim nenhum arquivo de configuração pessoal entra por engano. O README registra a configuração esperada, que não é versionada: em *Files and links*, *Use [[Wikilinks]]* desligado e *New link format* em *Relative path to file*. Versionar qualquer arquivo de `.obsidian/` exige decisão explícita do time.

### 3.2 Conteúdo e metadados

Cada nota trata um assunto delimitado. O corpo explica o contexto, a descoberta ou decisão, quando aplicá-la, os limites e como conferir a fonte.

Nota não é instrução. Procedimento que o agente deve seguir sempre vira texto no arquivo operacional (trilha, guarda, skill ou `AGENTS.md`) pela trilha `destilar`, e a nota passa a apontar para ele. A regra vale principalmente para `padrao`: sem ela, as notas viram um regulamento paralelo e sem autoridade. Nota que só repete um documento existente não entra; o índice aponta para o documento.

| Campo | Regra |
|---|---|
| `schema_versao` | Versão dos metadados da nota, inicialmente `1`; independente do schema de provas. |
| `id` | Igual ao nome do arquivo sem `.md`. Único na memória e nunca reutilizado. |
| `tipo` | `decisao`, `aprendizado` ou `padrao`, coerente com a pasta. |
| `status` | `ativo` ou `substituido`. Proposta não é status: é o que ainda não está na `main` (seção 4.1). |
| `tags` | Lista curta de assuntos. É a propriedade nativa do Obsidian, com painel e busca por tag. |
| `caminhos` | Arquivos ou pastas relacionados, relativos à raiz do harness; o prefixo `prj-avante-analytics-adb/` indica o produto. Servem à busca e ao aviso de revalidação (Fase 2). |
| `fontes` | Caminho relativo à raiz do harness, hash de commit, URL de PR ou documentação oficial. Ao menos uma acessível a partir de outro clone. |
| `verificado_em` | Data `AAAA-MM-DD` da última conferência das afirmações. Obrigatória. |
| `substituida_por` | `id` da nota sucessora, obrigatório quando houver substituição por outra nota. |

Ficam fora da primeira entrega: `escopo`, porque o repositório onde a nota vive já define o escopo (seção 8); `responsavel`, porque a autoria está no Git e a revisão é definida no README; e o status `candidato`, porque um campo editável não distingue proposta de conteúdo revisado.

Usar YAML simples (escalares, datas e listas), legível por scripts e pelo Obsidian. Modelos e exemplos não entram no índice nem nas buscas.

Uma referência local a `.execucoes/` pode complementar a rastreabilidade, mas não sustenta sozinha a nota em outro clone. A fonte usada precisa estar commitada; um arquivo alterado e não commitado, como o plano de agentes nesta revisão, ainda não serve de fonte. O resumo preserva o contexto necessário e omite credenciais e dados pessoais desnecessários.

### 3.3 Papel da memória

Na seção "Fontes" de `nucleo/modus-operandi.md`, as notas entram no nível do item 4 (README, GUIA, PLANO e testes): abaixo das permissões do runtime, do pedido, do `AGENTS.md` do escopo e do código e da configuração vivos.

Uma decisão registrada explica seu motivo e aponta para a regra vigente. Mudança de política altera os arquivos operacionais correspondentes no PR adequado. Notas não concedem autorização, não comprovam testes de uma nova execução e não restauram autorizações antigas.

Quando fonte e nota divergirem, vale a fonte viva; corrigir ou substituir a nota. Um commit sem alteração relevante nas fontes não torna a memória obsoleta.

## 4. Protocolo de consulta e contribuição

### 4.1 Consulta

A consulta é proporcional ao caminho:

- **Simples**: buscar em `memoria/` só quando o pedido tocar assunto ou caminho com nota. Sem leitura obrigatória do índice.
- **Estruturado**: na entrada, ler o índice e abrir as notas relacionadas antes de fechar o contrato. As notas usadas entram em `fontes` do contrato.

Passos:

1. Selecionar assuntos e caminhos do pedido e buscar em `memoria/`, excluindo `modelos/`. Começar com até cinco resultados relevantes e ampliar se a investigação justificar.
2. Usar notas `ativo` da `main`. É proposta a nota diferente de `origin/main` (`git diff --name-only origin/main -- memoria/`, após `git fetch`) ou não rastreada (`git status --short -- memoria/`); citá-la como proposta.
3. Conferir escopo, fonte e atualidade antes de aplicar uma recomendação.
4. Sem nota útil, seguir pelo código e pelas fontes atuais. Ausência de memória não impede a tarefa.
5. Quando uma nota influenciar a decisão, citar seu `id` e a fonte conferida: no relato, no caminho simples; em `fontes` do contrato, no estruturado.

Na primeira fase, esse comportamento depende das instruções e da atuação do agente. Só declarar consulta observada quando houver leitura ou busca registrada na execução.

### 4.2 Fechamento e contribuição

1. Avaliar se houve descoberta reutilizável: causa de falha verificada, procedimento recorrente, decisão relevante ou limite de ferramenta observado. Tarefa comum não gera nota nem pergunta de confirmação.
2. Sinalizar o candidato no fecho, com assunto e fontes. É o papel do `docs-distill`: sinalizar, sem exigir pergunta nem destilação.
3. Gravar a nota só onde a escrita está autorizada: no caminho simples, quando o pedido inclui registrar a nota; no estruturado, quando a superfície do contrato inclui o arquivo em `memoria/`. Fora disso, a nota vira fatia própria da trilha `destilar`. Escrever fora da superfície viola o contrato da fatia.
4. Procurar nota existente antes de criar outra e atualizá-la quando o assunto já estiver coberto.
5. Rodar `validar` e submeter pelo fluxo normal de PR. Nota em branch ou só no clone local não é conhecimento do time.
6. O revisor confere conteúdo, fonte, utilidade, duplicação e a fronteira entre nota e instrução. A nota chega à `main` já com `status: ativo`.
7. Após o merge, os demais engenheiros recebem a nota ao atualizar seus clones.

O fecho técnico da tarefa e a publicação da memória são resultados distintos. Uma contribuição pendente de revisão é apresentada como proposta e não impede o sucesso de uma tarefa cujo aceite não inclua a publicação.

### 4.3 Manutenção pelo time

- `memoria/README.md` nomeia quem aprova PRs que tocam `memoria/` (DM-1). Sem CI, o autor roda `validar` antes do PR e o revisor confere a saída.
- Cada autor mantém fontes e índice coerentes com sua contribuição.
- Alteração de código que invalide uma nota a atualiza no mesmo PR, quando estiver no mesmo repositório. A partir da Fase 2, `validar` avisa quando um arquivo de `caminhos` mudou depois de `verificado_em`.
- Contribuições entre harness e produto usam PRs separados e referências entre eles.
- Preservar nomes de arquivo e histórico Git; usar substituição explícita para mudança de entendimento.
- Uma nota por assunto. Conflito de conteúdo se resolve pelas fontes. O índice é o único arquivo tocado por toda contribuição: a partir da Fase 2 ele é gerado, e conflito nele se resolve regenerando.
- Manter o índice curto e apontar para documentos existentes quando eles já contêm o fato.

## 5. Etapas de implementação

### Fase 0 — Preparar a fatia

1. Conferir o estado do checkout e preservar alterações preexistentes, inclusive as da onda do plano de agentes em curso.
2. Registrar as decisões DM-1 a DM-3 (seção 9).
3. Selecionar duas ou três notas iniciais com conhecimento que ainda não está em documento operacional, com fontes commitadas. As candidatas da primeira revisão (prefixo `databricks:` das skills no Claude Code e `fechar` recusando `DONE` nesse runtime) já foram absorvidas pelo `AGENTS.md`, pelo README e pelos READMEs dos adaptadores e não entram, porque nota que só repete documento existente não entra. Buscar o porquê de decisões que os documentos registram sem explicar, por exemplo: a atribuição do teste no subagente do Cursor por janela de tempo, e não por ID, e o motivo de o A5 ter sido aplicado antes do E0.
4. Definir a inspeção documental: nenhum comando existente confere metadados e links de notas. Por isso `validar` entra na Fase 1. No contrato, os `caminhos` do critério cobrem toda a superfície (`memoria/` e os documentos alterados), como exige o validador. O que o comando não exercita (precisão factual, coerência entre README e HTML) fica na revisão e é declarado como limite.
5. Preparar o contrato da trilha `docs` e iniciar a fatia antes de editar, conforme `AGENTS.md` e `evidencia/uso.md`, no runtime definido em DM-2.

Aceite: decisões registradas; escopo, arquivos, notas iniciais, fontes e comandos definidos; runtime compatível com o fecho pretendido.

### Fase 1 — Memória versionada, instruções e validação mínima

Dependência: Fase 0.

| Arquivo | Alteração |
|---|---|
| `AGENTS.md` | Uma linha condicional, no padrão de `contexto-avante.md`: consultar `memoria/` quando o pedido tocar assunto ou caminho com nota; notas são advisory. Distinguir registros locais (`.execucoes/`) de conhecimento versionado (`memoria/`). |
| `nucleo/modus-operandi.md` | Em "Fontes", posicionar as notas no nível do item 4. Documentar consulta proporcional, revalidação e sinalização no fecho. |
| `trilhas/destilar.md` | Incluir nota como destino, com a fronteira entre nota e instrução; explicitar que a forma `destilar` segue candidata. |
| `trilhas/README.md` | Ajustar a descrição da trilha `destilar` ao novo destino. |
| `README.md` | Estrutura, estado implementado, fluxo Git, uso no Obsidian e comando `validar`. |
| `user-harness-esteira-v4.html` | Acrescentar um diagrama curto da memória com o que foi implementado; etapas futuras ficam no plano. |
| `.gitignore` | Ignorar `memoria/.obsidian/`. |
| `memoria/README.md` | Política, revisores, ciclo de contribuição, configuração do Obsidian e limites. |
| `memoria/indice.md` | Índice por assunto com as notas iniciais. |
| `memoria/modelos/nota.md` | Modelo com metadados e estrutura de conteúdo. |
| `memoria/<tipo>/*.md` | Duas ou três notas reais. |
| `implementacao/memoria.py` e `adaptadores/memoria.py` | Leitura de metadados e CLI `validar`: campos e enums; `id` igual ao nome e único; `tipo` coerente com a pasta; `substituida_por` existente; nota ativa presente no índice; links relativos e `fontes` locais resolvidos; wikilink e caminho absoluto recusados. Código de saída diferente de zero em erro. |
| `testes/teste_memoria.py` | Estado válido e uma falha real por regra. É descoberto pela suíte do `AGENTS.md`. |

Aceite:

- Notas e índice são rastreáveis pelo Git e funcionam em um clone novo, sem caminhos absolutos da estação do autor.
- Nenhuma nota ativa depende só de fonte em `.execucoes/` ou de arquivo não commitado.
- `validar` passa no estado entregue e falha nos casos de teste; as suítes do `AGENTS.md` passam.
- O agente recebe uma orientação condicional comum e consulta as notas por leitura de arquivo ou busca textual.
- Revisão humana e atualização dos clones distribuem o conhecimento conforme o fluxo documentado.
- README e HTML descrevem o mesmo nível de implementação.
- A criação de notas é proporcional à tarefa; nada depende de Obsidian, plugin, MCP ou serviço externo.

Dimensão estimada: sete arquivos existentes, três documentos novos, as notas iniciais, um módulo com CLI e um arquivo de teste. Não muda o núcleo de provas nem o schema de eventos. Como `implementacao/` e `adaptadores/` integram o controle do manifesto, editar `memoria.py` durante outra fatia no mesmo checkout invalida a prova dela; não rodar o código da Fase 1 em paralelo com uma fatia ativa do plano de agentes no mesmo checkout.

### Fase 2 — Busca, índice gerado e revalidação

Dependência: Fase 1.

Entregas:

- `buscar`: por tag, texto e caminho. Retorna `id`, caminho, fontes e trechos limitados, com ordenação determinística. Exclui modelos; nota substituída aponta para a sucessora. Marca como proposta a nota diferente de `origin/main` ou não rastreada e informa a revisão da `main` consultada.
- `indice`: gera `memoria/indice.md` a partir dos metadados. `validar` recusa índice diferente do gerado.
- `validar` passa a avisar, sem falhar, quando um arquivo de `caminhos` mudou no Git depois de `verificado_em`. Referência ao produto sem o clone presente é reportada como verificação indisponível; arquivo interno ausente é erro. Caminhos são resolvidos dentro das raízes declaradas, e links que escapem delas são recusados.
- Testes das novas garantias em `testes/teste_memoria.py` e instruções atualizadas com os comandos definitivos. CI não existe hoje; criá-lo é decisão separada.

O CLI não executa instruções contidas nas notas, não faz commit ou push, não altera código de produto e não publica contribuições.

Aceite: casos válidos passam, falhas reais são detectadas, uma consulta encontra a nota esperada em outro clone e uma proposta não é apresentada como conteúdo da `main`. A validação estrutural continua separada da revisão factual.

### Fase 3 — Piloto de compartilhamento

Dependência: Fase 1. A Fase 2 amplia a verificação, mas não é pré-condição para observar o processo manual.

1. O engenheiro A contribui com uma descoberta real e suas fontes por PR.
2. Após aprovação e merge, o engenheiro B atualiza um clone separado e inicia uma sessão nova, sem receber a conversa do autor.
3. Pedir uma tarefa relacionada e observar a busca ou leitura da nota e a conferência da fonte atual.
4. Repetir com uma nota em branch não incorporada, uma nota substituída, uma fonte alterada e um pedido simples sem relação com as notas, verificando que não há aplicação indevida nem leitura desnecessária.
5. Registrar a observação por runtime: Cursor, Claude Code, Codex e OpenCode, conforme forem usados pelo time.
6. Medir o custo da consulta (chamadas, tokens e tempo) com as métricas de `avaliacao/README.md`.

Guardar logs e resultados brutos em `.execucoes/`. Versionar um resumo conciso em `avaliacao/memoria.md`, com cenário, versão do runtime, revisão da memória e resultado. Confirmar permissões e fluxo de PR antes das ações externas do piloto.

Aceite: pelo menos dois engenheiros, com clones independentes, demonstram compartilhamento e recuperação útil. Só declarar suporte observado nos runtimes efetivamente exercitados.

### Fase 4 — Automação por runtime

Dependência: piloto concluído e benefício demonstrado. O schema 3.2 (C1–C3) já está adotado; o registro formal no Claude Code depende do adaptador D-CC, e a destilação com papéis depende da trilha `destilar` entrar em `agentes_obrigatorios` (onda 2 do plano de agentes).

1. Conferir a documentação oficial atual e os eventos disponíveis nas versões usadas pelo time.
2. Reutilizar a política e o CLI comuns; cada adaptador traduz somente os eventos do seu runtime.
3. Priorizar consulta orientada à tarefa. No início da sessão, carregar no máximo a orientação ou o índice quando ainda não houver assunto suficiente para selecionar notas.
4. Implementar o `docs-distill` do acervo: no fechamento, sinalizar candidatos com fontes, sem gravar nota nem abrir PR. Atualizar sua situação em `acervo/README.md` só depois de observado.
5. Registrar consultas e candidaturas em `.execucoes/`, com identificação das notas e da revisão usada, sem gravar no vault a cada chamada de ferramenta. Atualizar `evidencia/layout.md`.
6. Ativar gradualmente por runtime e observar sessões reais antes de declarar a integração disponível.

Aceite: contexto relevante é recuperado com volume limitado, os registros identificam o conhecimento usado e falhas da integração não provocam repetição de efeitos externos nem publicação automática.

Eventos formais de memória e a forma `destilar` entram como extensão do schema 3.2 do plano de agentes, não como migração paralela. Registros existentes continuam legíveis. Não é requisito das primeiras entregas.

## 6. Verificação e critérios de conclusão

Executar as verificações obrigatórias do harness após cada pacote implementado e, a partir da Fase 1, a validação da memória:

```powershell
py -3 -m unittest discover -s testes -p teste_*.py -v
node testes/teste_opencode.mjs
py -3 adaptadores/memoria.py validar
```

Não criar testes que apenas reproduzam o texto das instruções.

| Cenário | Resultado esperado |
|---|---|
| Clone atualizado em outra estação | Índice, notas e fontes portáveis estão disponíveis. |
| Consulta relacionada | A nota útil é encontrada e a fonte é conferida. |
| Pedido simples sem relação com notas | Nenhuma leitura de memória. |
| Consulta sem correspondência | O trabalho continua apoiado nas fontes atuais. |
| Nota em branch ou alterada localmente | É identificada como proposta pelo Git; não recebe revisão presumida. |
| Nota substituída | A busca normal leva à sucessora e o histórico é preservado. |
| Fonte alterada | O agente verifica a divergência e propõe atualização; a partir da Fase 2, `validar` avisa pela data. |
| Nota com fonte apenas em `.execucoes/` | `validar` recusa a nota ativa. |
| Wikilink ou caminho absoluto | `validar` recusa. |
| Candidato no fecho de fatia sem `memoria/` na superfície | Sinalizado no fecho; nenhuma escrita fora da superfície. |
| Contribuições concorrentes | O Git preserva ambas; nomes são conferidos e o índice é regenerado. |
| Obsidian ausente | Leitura, busca e contribuição pelo repositório continuam possíveis. |
| Memória nativa do runtime | Não é usada como fonte compartilhada. |
| Nota sobre autorização ou teste anterior | Não concede permissão nem comprova a execução atual. |

A primeira entrega está concluída quando a Fase 1 passa no aceite; o piloto confirma o compartilhamento entre engenheiros. A Fase 2 acrescenta busca, índice gerado e revalidação. A Fase 4 é declarada concluída por runtime, após observação real.

## 7. Sequência de entregas e esforço

| Entrega | Conteúdo | Porte estimado |
|---|---|---|
| 1 | Fases 0 e 1: estrutura, política, modelo, índice, notas iniciais e `validar` mínimo. | Pequeno a médio; documental, com um validador e seus testes. |
| 2 | Fase 2: busca, índice gerado, revalidação e testes. | Médio; código local. |
| 3 | Fase 3: observação entre engenheiros e runtimes, com ajustes na política. | Depende da participação do time e das ferramentas disponíveis. |
| 4 | Fase 4: eventos, registros e ativação por runtime. | Maior; depende do adaptador do Claude Code (D-CC) e da onda 2 do plano de agentes. |

O piloto manual pode começar após a entrega 1 e ser repetido depois da entrega 2. Cada pacote tem um PR com escopo próprio e usa o contrato e a prova exigidos para seu modo de execução. Não estimar prazo das integrações antes de confirmar os eventos e capacidades disponíveis.

## 8. Adoção no produto e evolução posterior

Depois do piloto, ler o `AGENTS.md` e os documentos vigentes do produto, escolher uma pasta compatível com sua organização e adotar o mesmo protocolo de notas. Como o README do harness informa que as instruções do produto não vêm no clone, conferir como distribuir essa orientação aos engenheiros antes de prometer descoberta automática ali.

Conhecimento específico de negócio acompanha o produto. Conhecimento de ferramentas e processo permanece no harness. Referências entre repositórios identificam o projeto e a revisão; o índice aponta para a fonte canônica, evitando cópias divergentes.

Busca semântica, serviço central, integração MCP ou uso da CLI do Obsidian são evoluções possíveis se o piloto revelar uma necessidade concreta. A base Markdown revisada no Git continua sendo a referência compartilhada.

## 9. Decisões pendentes

| ID | Decisão | Proposta |
|---|---|---|
| DM-1 | Quem aprova PRs que tocam `memoria/`. | O mesmo revisor dos PRs do harness, registrado em `memoria/README.md`. CODEOWNERS é opcional. |
| DM-2 | Runtime da fatia da Fase 1. | Cursor, para fechar `DONE` com prova do `validar` e das suítes. No Claude Code, fechar `BLOCKED` com o motivo (sem coleta) e pedir revisão do PR. |
| DM-3 | Ordem em relação ao plano de agentes. | A proposta original (antes de A1/A5) ficou superada: A1–A5 foram concluídos em 2026-10-05. Nova proposta: a parte documental da Entrega 1 pode correr em paralelo com a onda B1/E0a/D-CC/D-CU, porque os arquivos são disjuntos, exceto `README.md` e o HTML; `memoria.py` e seus testes entram depois do G1, para não alterar o controle do manifesto durante a onda. Commits separados, com o ID `MEM-1`. |

Referências externas consultadas para o desenho: [armazenamento de dados do Obsidian](https://obsidian.md/help/Files+and+folders/How+Obsidian+stores+data), [propriedades das notas](https://obsidian.md/help/properties) e [CLI do Obsidian](https://obsidian.md/help/cli). Revalidar requisitos de versão e instalação ao implementar uma integração opcional.
