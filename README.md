# User harness — Esteira

Regras, guardas e registro de provas para agentes de IA que trabalham na esteira `saneamento_migracao`. O apoio visual (princípio, estrutura e fluxos) está em [`user-harness-esteira-v4.html`](user-harness-esteira-v4.html). Estes arquivos descrevem o que existe hoje.

## Como a IA recebe o harness

| Runtime | Instruções | Guarda antes do shell | Prova da fatia | Papéis (`agentes/`) |
|---|---|---|---|---|
| Cursor (principal) | `AGENTS.md` | `.cursor/hooks.json` | Sim, observada em sessão real | `.cursor/agents/`, obrigatórios em `manutencao` |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` | Coletada, mas ainda não comprova `DONE` (limite no `AGENTS.md`) | `.claude/agents/`, opcionais |
| Codex | `AGENTS.md` | Só após `gerenciar.py codex --instalar` | Não | Agente único |
| OpenCode | `AGENTS.md` | `.opencode/plugins/esteira.js` | Não | Agente único |

`AGENTS.md` é curto e traz as regras que mais importam. O resto é lido sob demanda. Detalhes por runtime: [adaptadores](adaptadores/README.md).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| [`nucleo/`](nucleo/modus-operandi.md) | Política (`modus-operandi.md`) e contexto do projeto Avante (`contexto-avante.md`, advisory). |
| [`trilhas/`](trilhas/README.md) | Oito trilhas, cada uma com passos, aceite e fecho. |
| [`contratos/`](contratos/README.md) | Campos do contrato da fatia. |
| [`guardas/`](guardas/README.md) | O que o código nega e as regras de conduta sem código. |
| [`evidencia/`](evidencia/uso.md) | Uso da prova, validade, status de fecho e layout dos registros. |
| [`formas/`](formas/README.md) | Schema dos registros (11 formas adotadas). |
| [`acervo/`](acervo/README.md) | Inventário das candidatas do desenho e a situação de cada uma. |
| `.agents/skills/` | 10 skills Databricks (aitools v0.2.10); roteamento em [`trilhas/`](trilhas/README.md#skills-databricks). |
| [`adaptadores/`](adaptadores/README.md) | Tradução dos eventos de cada runtime para a mesma guarda. |
| [`avaliacao/`](avaliacao/README.md) | Cenários, métricas e kits de observação dos agentes por runtime. |
| [`agentes/`](agentes/roteamento.yaml) | Sete papéis (map, config, implement, test, refute, docs, dab) e o roteamento por trilha. |
| `implementacao/`, `configuracao/`, `testes/` | Código da guarda e da prova, política de caminhos e testes. |
| `.execucoes/` | Registros locais: provas, sessões e diagnósticos. Fora do Git; pode ser apagada entre ciclos de teste. |
| [`PLANO-AGENTES-TRILHAS.md`](PLANO-AGENTES-TRILHAS.md) | Plano, gates e histórico. É o único lugar com estado e histórico do harness. |

## Estado

O que existe hoje. Gates, pendências e histórico: [painel do plano](PLANO-AGENTES-TRILHAS.md#painel).

**Imposto por código** (vale para o shell do chat, quando o hook dispara):

- `databricks bundle` só roda no bundle local, com comando literal, target `sandbox` e perfil explícito.
- `validate` e `plan` passam em `sandbox` (e em `dev` só com autorização na política). `deploy` passa só em `sandbox`, com plan vigente, `-p` e `--select`; identidade e destinos não são conferidos. `run`, `destroy` e `sync` são negados.
- Target `dev` só passa com autorização registrada na política. Hoje não há nenhuma.
- SQL ad hoc pela CLI só lê; escrita é negada.
- No Cursor, `prova.py fechar` recusa `DONE` sem prova atual; o `stop` pede correção até duas vezes.
- Na trilha `manutencao` no Cursor (`agentes_obrigatorios.cursor`), `fechar` também exige as chamadas previstas dos papéis observadas, a revisão do refute e cada papel escrevendo só na sua superfície.

**Só instrução** (depende do modelo): escolher o caminho e a trilha, iniciar a fatia antes de editar, perguntar pouco, preservar trabalho prévio, coordenar dados do sandbox, respeitar a fronteira do produto.

**Fora da guarda**: terminal manual, MCP, SDK, REST, edição de arquivo e ferramentas que não são shell.

**Skills Databricks**: as 10 de `.agents/skills/` valem para Cursor, Codex e OpenCode. O Claude Code recebe as `databricks:databricks-*` pelo plugin `databricks` do projeto, inclusive no subagente.

**Observado em sessão real**: no Cursor, os sete papéis em série, guarda negando no subagente e fatias de manutenção e docs fechando `DONE` com prova. No Claude Code, só as sondagens de eventos e da guarda; os papéis ainda não.

**Não implementado**: skills do projeto, conferência de identidade e destinos no deploy, coordenação de dados e `docs-distill`.

## Preparar um clone

Abra sempre `avante-harness-engineer/` como raiz da IDE, também para trabalhar no produto. O produto é um repositório Git separado, dentro dela e ignorado pelo Git do harness:

```text
avante-harness-engineer/       # raiz aberta na IDE
  AGENTS.md, CLAUDE.md
  .cursor/ .claude/ .codex/ .opencode/
  prj-avante-analytics-adb/     # clone do produto, Git próprio
```

```powershell
git clone <URL_DO_REPOSITORIO_DE_PRODUTO> prj-avante-analytics-adb
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

- Requisitos: Python 3.12+ com PyYAML (`requirements.txt`) e Node para o teste do OpenCode. O hook usa o Python do `.venv` quando ele existe.
- Os hooks de Cursor, Claude Code e OpenCode já vêm no clone, no formato Windows (`py -3`). Em Linux/macOS, gere de novo com `python3 adaptadores/gerenciar.py <runtime> --instalar`.
- Sem o clone do produto, a guarda nega toda chamada `databricks bundle`. Ela não procura outro checkout.
- O produto não tem instruções de agente próprias: as regras ficam todas neste harness.
- No Windows, se o checkout do produto falhar com `Filename too long`, rode `git -C prj-avante-analytics-adb config core.longpaths true` e `git -C prj-avante-analytics-adb restore .`.
- Versione mudanças de produto no repositório dele (`git -C prj-avante-analytics-adb ...`).

## Primeiro teste no Cursor

Mostra se o hook dispara e se a guarda nega antes do efeito. Um comando digitado no seu terminal não passa pelo hook.

1. Em Customize → Hooks, habilite o hook do projeto se o Cursor pedir.
2. No chat, peça `databricks bundle validate -t sandbox -p SEU_PERFIL`, literal e sozinho, com diretório absoluto em `prj-avante-analytics-adb\bundles`. Esperado: negação antes da CLI.
3. Repita no diretório `prj-avante-analytics-adb\bundles\src\notebooks\saneamento_migracao`. Esperado: a guarda deixa seguir. O validate consulta a Databricks e não publica.
4. Anote a versão do Cursor e se o canal Hooks mostrou as duas decisões.

Se o hook não disparar, interrompa e não peça plan, deploy nem run.

## Uso pelo time

Prepare o clone (acima) uma vez. Depois:

**Cursor** (runtime completo)

1. Abra `avante-harness-engineer/` como raiz e confie nos hooks. Em Settings → Hooks aparecem os comandos de `adaptadores/entrada.py`; em Settings → Subagents, os sete papéis.
2. Cada tarefa começa em **chat novo** (Ctrl+N). O contexto inicial traz `Sessao para --sessao: <ID>`. Sem essa linha, os hooks não estão ativos: pare e confira.
3. Pergunta ou mudança pequena: peça direto. Trabalho de várias etapas: o agente escreve o contrato ([modelo](evidencia/uso.md)), roda `py -3 adaptadores/prova.py --runtime cursor --sessao <ID> iniciar <contrato.yaml>` antes de editar e fecha com `fechar`.
4. Na trilha `manutencao`, o agente coordena e delega aos papéis (test, config, implement, refute, dab) um de cada vez. Se o chat mostrar `[esteira] A fatia ativa nao tem fecho valido...`, é o hook pedindo para terminar a trilha.
5. Só conta como pronto o `DONE` aceito pelo `fechar`. Recusa vira nova verificação ou fecho `BLOCKED`, `FAILED` ou `DECIDE`, com motivo.

**Claude Code** (guarda completa, prova ainda sem valor de `DONE`)

1. Rode `claude` na raiz do clone. Confira `/hooks` e `/agents` (sete papéis).
2. Use para perguntas, mudanças pequenas e trabalho em que a guarda do bundle importa.
3. Em trabalho estruturado, siga o limite do `AGENTS.md`: feche como `BLOCKED` com motivo, ou leve a fatia para o Cursor.

**Codex e OpenCode**: guarda do shell apenas; agente único e sem prova de fatia.

Em todos: nunca peça `deploy` ou `run` sem autorização explícita, e não contorne uma negação da guarda com outra ferramenta.

## Precedência

As regras do harness valem também no produto, que não tem instruções de agente próprias. Sobre o comportamento da esteira, valem o código do produto e a documentação do bundle (`README.md`, `GUIA-DESENVOLVIMENTO.md`, `PLANO-DE-EXECUCAO.md`) como fonte de fato. Sobre o harness, valem estes arquivos e o código; o HTML é o desenho.

## Manter README e HTML consistentes

O HTML reúne o desenho e as seções de estado ("Estado" e o roteiro). Ao mudar a implementação, atualize as afirmações de estado no README, no HTML e no painel do plano. Funcionalidades ainda propostas continuam identificadas como propostas.

O layout dos registros está em [`evidencia/layout.md`](evidencia/layout.md). Os exemplos de formas no HTML são ilustrativos. A seção "Estrutura de pastas" do HTML resume a árvore; a estrutura completa está neste README.

## Verificar mudanças no harness

```powershell
py -3 -m unittest discover -s testes -p teste_*.py -v
node testes/teste_opencode.mjs
```
