# Implementação do fluxo aprovado de agentes

Data: 2026-10-02. Estado: planejamento aprovado; implementação dos agentes pendente.

Referência do desenho: [Trilhas e fluxogramas](user-harness-esteira-v3.html#fluxo-trilha) e [responsabilidades](user-harness-esteira-v3.html#agentes-aprovados).

Esta entrega altera o HTML e cria este plano. Não instala agentes, não muda a política executável nem concede autorização para deploy/run. O fluxo aprovado passa a ser a referência para as próximas entregas; as instruções operacionais atuais ainda precisam ser migradas.

## 1. Decisões aprovadas

O agente principal coordena: escolhe o caminho, delimita a fatia, define o aceite, delega, trata retornos, controla orçamento e publica o fecho. Os sete agentes são `map`, `config`, `implement`, `test`, `refute`, `docs` e `dab`. Diagnóstico, inspeção documental e paridade são capacidades; não criar agentes adicionais com esses nomes.

| Trilha estruturada | Sequência aprovada | Condições |
|---|---|---|
| Novo | map opcional → coordenador → config + implement → test → refute → dab se aplicável → coordenador | Config para YAML, implement para código; dependências determinam sequência. Ambiente somente no escopo autorizado. |
| Manutenção | map opcional → coordenador → config/implement → test → refute → coordenador | Selecionar pelo tipo de arquivo; usar ambos quando necessário. |
| Correção | diagnóstico com map opcional → coordenador → test reproduz → implement corrige → test revalida → refute → coordenador | Falha esperada da reprodução não conclui a correção. Configuração associada deve ter dono explícito no recorte do implement; não ampliar o gatilho de config sem atualizar o desenho. |
| Documentação | map opcional → coordenador → docs → inspeção documental pelo coordenador → refute → coordenador | Não exigir suíte de produto sem relação com o documento. |
| Destilar | map opcional → coordenador → docs com distill → inspeção documental pelo coordenador → refute → coordenador | Destino e fonte autorizados; sem duplicar skills de plataforma. |
| Validação | coordenador → test → dab se autorizado → test com paridade se exigida → refute → coordenador | Refute foi incluído para alinhar o fluxo ao catálogo. Parar na reprovação conclusiva; não corrigir produto. |
| Review | map opcional → coordenador → refute → coordenador | O veredito do artefato é separado do status da tarefa de revisão. |
| Entendimento | principal, com map opcional | Sem refute obrigatório; fontes, inferências e preservação de estado verificáveis. |

Chamadas de test e refute são obrigatórias onde previstas no caminho estruturado. Config, implement, docs e dab são obrigatórios quando seu gatilho se aplica. Map continua opcional. O caminho simples conserva execução proporcional pelo principal; a classificação não pode ser usada para evitar obrigações de um trabalho estruturado.

Agente obrigatório indisponível impede sucesso da entrega. Registrar BLOCKED e continuar trabalho independente. Se faltar decisão ou autorização humana, usar DECIDE. Permissões superiores do runtime prevalecem; nunca contornar uma proibição de delegação ou operação.

## 2. Estado de partida

- `trilhas/README.md` orienta agente único e informa que os papéis não existem.
- `acervo/catalogo.yaml` é inventário sem consumidor executável; agentes são candidatos opcionais.
- `.claude/agents/` e `.cursor/agents/` ainda não existem no projeto.
- Dez skills Databricks estão em `.agents/skills/`; Claude Code tem plugin Databricks habilitado na configuração, cuja disponibilidade precisa ser observada na sessão.
- `implementacao/formas.py` aceita somente contrato, guarda, brief e teste. A forma ataque, do refute, é recusada.
- `implementacao/provas.py` exige provas de critérios, mas não execução de agentes nem tratamento de achados.
- Cursor coleta provas Shell e solicita correção no stop. Claude Code tem guarda PreToolUse e não tem coleta/fecho equivalente.

Não considerar configuração presente como evidência de carregamento ou execução real.

## 3. Contrato comum dos agentes

Manter uma definição neutra por agente em `agentes/<nome>.md`, incluindo responsabilidade, gatilho, entradas, ferramentas permitidas, skills, saída e condição de término. Gerar versões nativas em `.claude/agents/<nome>.md` e `.cursor/agents/<nome>.md`, sem duplicar a política manualmente. Usar um roteamento legível por código em `agentes/roteamento.yaml`; o catálogo e as trilhas devem refletir essa mesma fonte.

| Agente | Entradas essenciais | Saída verificável | Restrição |
|---|---|---|---|
| map | pergunta, escopo, fontes e baseline | mapa de fontes, dependências, recorte e incertezas | Sem edição de produto |
| config | contrato, arquivos YAML, template e requisitos | arquivos alterados, vínculos com requisitos e estado | Somente superfície atribuída |
| implement | contrato, template/irmão vivo, dependências e skills | alteração, manifesto e critérios a verificar | Sem mudar o aceite unilateralmente |
| test | critério, esperado, comando/ambiente e estado | logs reais, resultados, cobertura e manifesto | Sem corrigir produto ou enfraquecer o esperado; preparação de suíte só no escopo atribuído |
| refute | intenção, aceite, baseline, estado atual e provas | veredito, tentativas, achados, evidências e limites | Sem editar produto; não receber racional persuasivo do autor |
| docs | contrato, documentos e fontes vivas | documento/instrução e referências | Somente arquivos atribuídos |
| dab | operação, autorização, target/perfil, seleção e pré-condições | resultado real, IDs, logs e destinos observados | Guarda obrigatória; sem retry cego de efeito externo |

Identificar execução, fatia, tentativa, chamada, papel e estado relevante em cada retorno. Hashes comprovam compatibilidade do conteúdo, não autenticam autoria. A chamada observada pelo adaptador sustenta que o papel foi executado; um YAML escrito pelo principal não basta.

Skills por tarefa: pipelines para pipeline, jobs para job/etapa 06, dabs para recurso/bundle, dbsql para SQL, unity-catalog para catálogo/volume/permissões, data-discovery para descoberta/perguntas sobre dados, python-sdk para SDK/Connect/REST, execution-compute para execução, core para CLI/auth/perfil e docs para lacunas técnicas. Carregar apenas as pertinentes, registrar referências utilizadas e não presumir que a carga no principal chegou ao subagente.

## 4. Etapas de implementação

### Etapa A — Unificar política e roteamento

Arquivos: `AGENTS.md`, `nucleo/modus-operandi.md`, `trilhas/*.md`, `acervo/catalogo.yaml`, `acervo/README.md`, `adaptadores/README.md`, `agentes/roteamento.yaml` e definições neutras.

1. Traduzir a matriz aprovada em gatilhos obrigatórios/condicionais, preservando entendimento e caminho simples.
2. Remover orientações conflitantes sobre agente único e fallback silencioso para papéis obrigatórios.
3. Definir como o coordenador registra a superfície de cada escritor e a ordem das dependências.
4. Config e implement não editam o mesmo arquivo simultaneamente. Test e refute recebem um estado estável; mudanças durante a verificação invalidam seu resultado.
5. Manter a aprovação de delegação no escopo do fluxo e os limites superiores do runtime; não pedir confirmação repetida para cada chamada prevista.

Aceite: HTML, catálogo, matriz executável e trilhas concordam; cada nó tem responsável e cada condição tem destino. Metadados distinguem política aprovada de agente instalado e observado.

### Etapa B — Instalar agentes e resolver skills nos dois runtimes

Arquivos: definições neutras, `.claude/agents/*.md`, `.cursor/agents/*.md`, `adaptadores/gerenciar.py`, READMEs dos runtimes e scripts de geração/verificação necessários.

1. Ler novamente as documentações oficiais e validar campos contra as versões instaladas antes de gerar frontmatter.
2. Gerar as sete definições por runtime, preservando configurações existentes; geração idempotente e detecção de divergência.
3. Usar herança de modelo por padrão, sem introduzir modelos fixos; permissões compatíveis com a responsabilidade.
4. Claude Code: resolver nomes reais das skills do plugin e campos de preloading disponíveis. Cursor: definir leitura explícita das skills por caminho/gatilho suportado. Skill ausente gera limitação visível.
5. Observar descoberta e chamada real em sessão nova de cada runtime. Não aceitar apenas inspeção de diretório como ativação.

Aceite: os sete agentes são descobertos; cada papel respeita o recorte; implement demonstra leitura da skill Databricks pertinente; ausência da skill exigida não é ocultada.

### Etapa C — Evidências de delegação e revisão

Arquivos: `formas/catalogo.yaml`, `implementacao/formas.py`, `implementacao/provas.py`, `adaptadores/prova.py`, `evidencia/*.md` e adaptadores dos runtimes.

1. Versionar o schema para incluir plano de chamadas/responsabilidades por trilha e registros observáveis de início/retorno. Decidir campos e compatibilidade antes de codificar; não marcar as quinze formas como adotadas automaticamente.
2. Adotar a forma ataque com veredito, tentativas, cobertura, estado revisado e achados identificáveis. Acrescentar triagem com tratamento, responsável e evidência de resolução/descarte.
3. Registrar inspeção documental/analítica sem exigir que uma afirmação textual com exit zero seja tratada como prova. Definir produtor e validade desses resultados.
4. Vincular teste e revisão ao contrato, estado, dependências e critérios pertinentes. Edição relevante invalida as duas evidências; rever o trecho afetado após correção.
5. Isolar sessões e atribuições; definir serialização de operações que usam o mesmo estado de prova e impedir resultados de outra fatia.

Aceite: relato de agente sem chamada/log/artefato observável não comprova execução. Ataque válido é aceito; revisão obsoleta, adulterada ou de outra fatia é recusada. Registros antigos permanecem consultáveis e não recebem revisão independente presumida.

### Etapa D — Fecho e equivalência dos adaptadores

Arquivos: núcleo de provas, adaptadores Claude Code/Cursor, configurações geradas, guardas e documentação.

1. Exigir chamadas previstas, provas atuais e tratamento de achados no fecho de entregas. Um test aprovado sem refute obrigatório não fecha DONE.
2. Review pode concluir DONE com veredito com_achados; isso não aprova o artefato. Verificação essencial não executada por indisponibilidade resulta em BLOCKED. Revisão executada pode ter veredito inconclusivo com limites explícitos.
3. Validação não corrige produto: reprovação conclusiva encerra FAILED; impossibilidade de verificar encerra BLOCKED. Refute antecede sucesso, não obriga continuar depois da primeira reprovação conclusiva.
4. Implementar coleta de provas e conferência de fecho no Claude Code com os eventos oficialmente suportados; conferir se os eventos incluem chamadas de subagentes e como elas se associam à sessão principal.
5. Conferir o comportamento real dos hooks do Cursor em subagentes. Stop continua sendo mecanismo de solicitação de correção, não garantia de ocultar texto já exibido.
6. Manter cwd, target, perfil, plan e demais guardas existentes. A chamada de dab não amplia autorização nem libera run atualmente vedado pelo código.

Aceite: ausência de papel obrigatório impede sucesso nos dois runtimes; resultado pendente não é promovido a pass; falha de capacidade não é simulada como execução. Só declarar equivalência após observação em sessões reais.

### Etapa E — Exercitar e publicar o estado real

Começar pelos cenários de manutenção e correção. Depois cobrir novo, validação, docs, destilar, review e entendimento. Instalar as definições antes de habilitar a política obrigatória em uso; fazer a transição conjuntamente para evitar instruções exigindo agentes ausentes.

| Cenário | Resultado esperado |
|---|---|
| Manutenção de código correta | implement → test → refute; fecho com evidências atuais |
| Manutenção somente YAML | config → test → refute; sem implementação de código artificial |
| Teste verde, requisito ausente | refute encontra lacuna; correção e nova validação/revisão |
| Correção de bug | reprodução falha como esperado; correção passa no mesmo critério |
| Achado falso positivo | descarte fundamentado sem alteração desnecessária |
| Edição depois do aceite/revisão | provas anteriores não fecham DONE |
| Agente/skill exigido indisponível | limitação explícita e BLOCKED para o trabalho dependente |
| Validação reprovada | FAILED sem editar produto |
| Review com achados | DONE da tarefa, veredito com_achados do artefato |
| Documentação/destilação | inspeção documental e refute, sem suíte irrelevante |
| Entendimento/caminho simples | fontes verificadas e preservação de estado, sem delegação obrigatória |
| Duas sessões ou escritores concorrentes | sem mistura de provas, autoria atribuída e estado compatível |

Rodar os checks exigidos pelo AGENTS.md e testes focados nas novas garantias. Não adicionar testes que apenas espelhem prompts. Executar os cenários de ativação no chat de Claude Code e Cursor, preservando registros sob `.execucoes/` sem segredos.

Medir por trilha: chamadas esperadas/observadas, defeitos encontrados por refute, falsos positivos, falso DONE, tempo, custo e ciclos de correção. Atualizar README, HTML e adaptadores com o que foi implementado e observado, separando o que permanece pendente.

Aceite final: matriz e gatilhos exercitados nos dois runtimes; fecho recusa evidência incompleta; revisão independente ocorre onde prevista; guardas existentes passam suas regressões.

## 5. Ordem e limites da entrega

Ordem: A → B → C → D → E. Preparar definições e schemas antes de ativar a política operacional obrigatória. Cada etapa deve produzir uma mudança revisável com evidências e limitações explícitas.

Fora deste plano: implementar todos os candidatos do acervo de uma vez, recriar a receita perdida da esteira, mudar regras do produto, autorizar deploy/run, escolher modelos específicos ou prometer independência apenas por trocar de modelo.

Referências técnicas para a implementação: [subagentes Claude Code](https://code.claude.com/docs/en/sub-agents), [subagentes Cursor](https://cursor.com/docs/subagents) e documentação oficial de hooks/skills de cada runtime. Conferir novamente antes da implementação, pois os recursos e campos variam por versão.
