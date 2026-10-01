# User harness — Esteira

Regras, guardas e registro de provas para agentes de IA que trabalham na esteira `saneamento_migracao`. O desenho completo está em [`user-harness-esteira-v3.html`](user-harness-esteira-v3.html). Estes arquivos descrevem o que existe hoje.

## Como a IA recebe o harness

| Runtime | Instruções | Guarda antes do shell | Prova da fatia |
|---|---|---|---|
| Cursor (principal) | `AGENTS.md` | `.cursor/hooks.json` | Sim: `sessionStart`, `preToolUse`, `postToolUse`, `postToolUseFailure`, `stop` |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` | Não |
| Codex | `AGENTS.md` | Só após `gerenciar.py codex --instalar` | Não |
| OpenCode | `AGENTS.md` | `.opencode/plugins/esteira.js` | Não |

`AGENTS.md` é curto e traz as regras que mais importam. O resto é lido sob demanda. Detalhes por runtime: [adaptadores](adaptadores/README.md).

## Estrutura

| Pasta | Conteúdo |
|---|---|
| [`nucleo/`](nucleo/modus-operandi.md) | Política (`modus-operandi.md`) e contexto do projeto Avante (`contexto-avante.md`, advisory). |
| [`trilhas/`](trilhas/README.md) | Oito trilhas, cada uma com passos, aceite e fecho. |
| [`contratos/`](contratos/README.md) | Campos do contrato da fatia. |
| [`guardas/`](guardas/README.md) | O que o código nega e as regras de conduta sem código. |
| [`evidencia/`](evidencia/uso.md) | Uso da prova, validade, status de fecho e layout dos registros. |
| [`formas/`](formas/README.md) | Schema dos registros (4 formas adotadas, 11 candidatas). |
| [`acervo/`](acervo/README.md) | 26 peças do desenho e o estado de cada uma. |
| `.agents/skills/` | 10 skills Databricks (aitools v0.2.10); roteamento em [`trilhas/`](trilhas/README.md#skills-databricks). |
| [`adaptadores/`](adaptadores/README.md) | Tradução dos eventos de cada runtime para a mesma guarda. |
| [`avaliacao/`](avaliacao/README.md) | Oito cenários e métricas para medir a política. |
| `implementacao/`, `configuracao/`, `testes/` | Código da guarda e da prova, política de caminhos e testes. |
| `.execucoes/` | Registros locais: provas, sessões e diagnósticos. Fora do Git. |

## Estado

**Imposto por código** (vale para o shell do chat, quando o hook dispara):

- `databricks bundle` só roda no bundle local, com comando literal, target `sandbox` e perfil explícito.
- Só `validate` e `plan` passam. `deploy`, `run`, `destroy` e `sync` são negados; o deploy segue negado mesmo com plan, porque identidade e destinos não são conferidos.
- Target `dev` só passa com autorização registrada na política. Hoje não há nenhuma.
- SQL ad hoc pela CLI só lê; escrita é negada.
- No Cursor, `prova.py fechar` recusa `DONE` sem prova atual; o `stop` pede correção até duas vezes.

**Só instrução** (depende do modelo): escolher o caminho e a trilha, iniciar a fatia antes de editar, perguntar pouco, preservar trabalho prévio, coordenar dados do sandbox, respeitar a fronteira do produto.

**Fora da guarda**: terminal manual, MCP, SDK, REST, edição de arquivo e ferramentas que não são shell.

**Skills Databricks**: as 10 de `.agents/skills/` valem para Cursor, Codex e OpenCode. O Claude Code recebe as 29 pelo plugin `databricks` do projeto.

**Não implementado**: skills do projeto, subagentes, 11 das 15 formas, conferência de identidade e destinos, coordenação de dados e `docs-distill`.

**Não observado**: nenhuma sessão real mostrou o hook negando, a prova sendo coletada ou as skills carregando. Os testes locais cobrem o código, não a ativação. Os oito cenários não foram executados.

## Preparar um clone

Abra sempre `user-harness-esteira/` como raiz da IDE, também para trabalhar no produto. O produto é um repositório Git separado, dentro dela e ignorado pelo Git do harness:

```text
user-harness-esteira/          # raiz aberta na IDE
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
- O `AGENTS.md` e o `CLAUDE.md` do produto não são versionados; um clone novo não os traz.
- Versione mudanças de produto no repositório dele (`git -C prj-avante-analytics-adb ...`).

## Primeiro teste no Cursor

Mostra se o hook dispara e se a guarda nega antes do efeito. Um comando digitado no seu terminal não passa pelo hook.

1. Em Customize → Hooks, habilite o hook do projeto se o Cursor pedir.
2. No chat, peça `databricks bundle validate -t sandbox -p SEU_PERFIL`, literal e sozinho, com diretório absoluto em `prj-avante-analytics-adb\bundles`. Esperado: negação antes da CLI.
3. Repita no diretório `prj-avante-analytics-adb\bundles\src\notebooks\saneamento_migracao`. Esperado: a guarda deixa seguir. O validate consulta a Databricks e não publica.
4. Anote a versão do Cursor e se o canal Hooks mostrou as duas decisões.

Se o hook não disparar, interrompa e não peça plan, deploy nem run.

## Precedência

No escopo do produto, o `AGENTS.md` dele prevalece. Sobre o comportamento da esteira, valem o código e o `AGENTS.md` do produto. Sobre o harness, valem estes arquivos e o código; o HTML é o desenho.

## Manter README e HTML consistentes

O HTML reúne o desenho proposto e seções sobre o estado atual. Ao mudar a implementação, atualize as afirmações de estado atual no README e no HTML. Funcionalidades ainda propostas devem continuar identificadas como propostas.

O layout implementado está em [`evidencia/layout.md`](evidencia/layout.md) e na seção “Layout implementado” do HTML. A árvore genérica e os exemplos de formas no desenho são ilustrativos. A tabela “Estrutura” do HTML detalha código e configuração dos runtimes; a estrutura completa está neste README.

## Verificar mudanças no harness

```powershell
py -3 -m unittest discover -s testes -p teste_*.py -v
node testes/teste_opencode.mjs
```
