# Prontidão para o piloto — 01/10/2026

> Diagnóstico anterior à implementação. A continuação está em
> [entrega P0b](p0b_prova_minima.md); os estados abaixo preservam o ponto de partida.

O trabalho parou entre a **P0 operacional e a P0b**. Na numeração da página
Construção do HTML: fase 1 concluída, fases 2 e 3 com código testado localmente,
fase 4 por implementar. O harness ainda não está pronto para o piloto completo
da fase 5. A próxima entrega é a prova mínima e sua integração às guardas,
acompanhada do carregamento das instruções no chat.

Este documento registra uma inspeção da pasta e a repetição das suítes locais.
Não constitui prova de ativação no Cursor, execução do piloto ou conclusão de
uma fase operacional. As fases 6 e 7 não são pré-requisitos para iniciar o piloto.

## Estado confirmado

| Fase do HTML | Estado em 01/10 | Pendência para fechar |
|---|---|---|
| 1 — P0, especificação | Concluída; política, trilhas, contratos e catálogos presentes. | Preservar coerência entre desenho e implementação. |
| 2 — P0, diretório | Guarda e configuração Cursor presentes; testes locais verdes. | Preparar o clone interno e observar, no chat do Cursor, negação do oficial e continuidade do validate local. |
| 3 — P0, outras guardas | Target e exigência de plan ligados ao gancho anterior ao shell; fecho estruturado disponível como função. | Integrar resultado de execução e fecho; verificar em sessão real. Código testado não significa fase fechada. |
| 4 — P0b, prova mínima | Layout e requisitos escritos. | Implementar baseline, manifesto, registro de execução, validação, concorrência e invalidação de provas. |
| 5 — P1, piloto | Oito cenários e métricas descritos. | Preparar casos reproduzíveis e executar após o aceite das fases 2–4. |
| 6 — P2, especialização | Catálogo de candidatos. | Adotar skills/agentes quando houver ganho demonstrado. |
| 7 — P3, ampliação | Planejada. | Formas restantes, retomada prolongada e cobertura adicional, mantendo a regressão do piloto. |

Fontes: [Construção no HTML](../user-harness-esteira-v3.html#construcao),
[fases e cenários](README.md), [arquitetura](../adaptadores/arquitetura.md).

## Verificação realizada

Diretório dos comandos: `D:\repos_analytics_avante\user-harness-esteira`.

| Verificação | Resultado |
|---|---|
| `py -3 -m unittest discover -s testes -p teste_*.py -v` | 70 testes passaram, exit 0; Python 3.14.6 e PyYAML 6.0.3. |
| `node testes/teste_opencode.mjs` | Cenários de continuidade, negação, falha e preservação de argumentos passaram, exit 0. |
| Comparação dos dois HTMLs, antes da atualização documental | Conteúdo idêntico por SHA-256. |
| `.cursor/hooks.json` | Contém somente `beforeShellExecution`, com `failClosed: true`. |
| `.execucoes/` | Na inspeção, continha migração e testes; sem evidência operacional de sessão Cursor. |
| Preparo da raiz | Ausentes `.git`, `.venv` e `prj-avante-analytics-adb/` interno. |
| Carregamento de instruções | Ausentes `AGENTS.md`, `CLAUDE.md` e `.cursor/rules/` na raiz do harness. |

A primeira tentativa Python falhou por `PermissionError/WinError 5` nas fixtures
temporárias dentro do sandbox. A repetição autorizada fora dele passou. Não foi
necessário alterar o código para obter o resultado verde. As suítes usam fixtures;
nenhuma chamada Databricks, deploy ou run foi executada nesta inspeção.

## Ajustes em ordem de execução

### 1. Tornar a política carregável no Cursor

Adicionar uma entrada curta de instruções na raiz do harness, apontando para
`nucleo/modus-operandi.md` e carregando trilha, guardas e fecho conforme a tarefa.
Preservar a precedência do `AGENTS.md` do produto no seu escopo. O aceite é uma
sessão nova demonstrar que essas instruções foram carregadas; existir markdown
na pasta não comprova isso. Cursor continua sendo o primeiro adaptador.

### 2. Fechar os contratos necessários à P0b

Resolver as quatro lacunas explicitadas em [Formas](../formas/README.md): campos
de fontes/prazo do contrato, decisão de chamada permitida, tipos da forma `teste`
e schemas de baseline/manifesto/estado. Implementar a validação das formas
`contrato`, `guarda`, `brief` e `teste`. Rejeitar exemplos, referências fora da
execução, identidades incompatíveis, eventos duplicados e campos desconhecidos.

Os diagnósticos atuais são versão 2; não devem ser tratados como eventos das
formas 3.0 sem tradução e validação explícitas.

### 3. Implementar a prova mínima e conectar o plan

Implementar o [layout de evidência](../evidencia/layout.md), incluindo arquivos
relevantes não rastreados e alterações anteriores à tarefa. O executor precisa
registrar comando, cwd, início/fim, exit code, log e estado testado. Preservar
tentativas e eventos anteriores, com atualização atômica e controle de revisão.

Ligar `observar_resultado_plan` ao resultado real de uma execução autorizada.
Hoje somente os testes chamam essa função; o gancho anterior ao shell não
observa exit code nem gera recibo de sucesso. Não liberar deploy apenas porque
o comando `plan` foi solicitado.

Antes de usar o recibo para liberar deploy, completar a conferência da identidade
autenticada e dos destinos resolvidos. O nome do perfil não prova a identidade.
O recibo atual usa `nao_observada`; seu hash inclui obrigatoriamente
`databricks.yml` e os arquivos explicitamente fornecidos, limitados ao diretório
do bundle. É necessário definir a cobertura das dependências relevantes,
inclusive código compartilhado fora desse diretório, para não conservar um plan
após uma alteração que ele deveria invalidar.

Aceite: teste/plan observado gera prova; alteração relevante a invalida;
alteração documental sem relação não exige reteste sem motivo; trabalho prévio
e concorrente permanece distinguível da alteração da tarefa.

### 4. Conectar o fecho ao fluxo real

`avaliar_fecho` já rejeita propostas estruturadas insuficientes. Entretanto,
nenhum adaptador normaliza um evento de fecho, e o Cursor só tem o gancho de
shell. A função não intercepta uma resposta `DONE` em texto livre.

Integrar o fecho ao mecanismo suportado pelo runtime e fazê-lo consultar as
provas persistidas e seus hashes. Hoje `prova_posterior` e as referências vêm da
proposta recebida; não há comparação automática com o conteúdo testado.
Aceite: uma edição relevante depois do teste impede o `DONE` operacional até
nova verificação, sem bloquear uma resposta factual simples.

### 5. Preparar a estação e executar o ensaio conjunto

Preparar `.venv` com `requirements.txt` e o clone independente do produto dentro
do harness. Abrir `user-harness-esteira/` como raiz do Cursor. O checkout do
produto na pasta pai não é substituto: a política aponta apenas para o interno.

Executar no chat o ensaio descrito em Construção e registrar versão, evento,
decisão e ausência/presença do efeito esperado. Incluir diretório incorreto,
validate local permitido, target sem autorização, deploy sem plan, prova
obsoleta e shell comum. Um comando digitado diretamente no terminal não prova
a interceptação do shell do agente.

Preparar também o versionamento do harness para fixar o snapshot do piloto e
permitir clonagem pela equipe. A ausência de Git não impede a suíte unitária,
mas a distribuição reproduzível ainda está por preparar.

### 6. Preparar os oito cenários completos

Transformar cada linha do piloto em entrada, estado inicial, resultado esperado
e registro de métricas. São pelo menos **48 execuções**: oito cenários, duas
configurações, três repetições. Alternar a ordem e manter snapshot, modelo,
ferramentas e controles obrigatórios equivalentes.

Antes de executar os cenários de timeout de run e sandbox compartilhado, definir
o mecanismo de consulta por ID, o registro de coordenação e a cobertura das
ferramentas que produzem o efeito. `bundle run` literal é negado hoje; subcomandos
fora de `bundle`, wrappers sem texto identificável, MCP e SDK não são cobertos
por essa guarda. Uma simulação deve ser registrada como simulação, com o limite
explícito; não comprova execução externa real.

Aceite do piloto: resultados revisados, nenhum falso `DONE` e nenhuma ação fora
da autorização nos casos críticos, conforme [Piloto](README.md).

## Ponto de retomada

Começar pelos itens 1–4 como próxima entrega de implementação. Depois preparar
a estação e observar as fases 2–4 juntas no Cursor. Só então iniciar o piloto.
Skills, subagentes e as outras onze formas continuam nas fases posteriores.

Nesta revisão foram registrados o diagnóstico e os critérios de prontidão e
corrigida uma frase desatualizada na página Implantação dos dois HTMLs. Não houve
mudança de guardas, instalação de adaptadores ou ativação de runtime.
