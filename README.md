# User harness — Esteira

Regras, guardas e registro de provas para agentes de IA que trabalham na esteira `saneamento_migracao`. O desenho completo está em [`user-harness-esteira-v3.html`](user-harness-esteira-v3.html). Estes arquivos descrevem o que existe hoje.

## Como a IA recebe o harness

| Runtime | Instruções | Guarda (antes do shell) | Prova da fatia |
|---|---|---|---|
| Cursor (principal) | `AGENTS.md` | `.cursor/hooks.json` | Sim: `sessionStart`, `preToolUse`, `postToolUse`, `stop` |
| Claude Code | `CLAUDE.md` → `@AGENTS.md` | `.claude/settings.json` | Não |
| Codex | `AGENTS.md` | Após `gerenciar.py codex --instalar` | Não |
| OpenCode | `AGENTS.md` | `.opencode/plugins/esteira.js` | Não |

`AGENTS.md` é curto e traz as regras que mais importam. O resto é lido sob demanda.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| [`nucleo/`](nucleo/modus-operandi.md) | Política: caminho simples ou estruturado, quando perguntar, fontes, recuperação. |
| [`trilhas/`](trilhas/README.md) | Oito trilhas, cada uma com passos, aceite e fecho. |
| [`contratos/`](contratos/README.md) | Campos do contrato da fatia. |
| [`guardas/`](guardas/README.md) | O que o código nega e as regras de conduta sem código. |
| [`evidencia/`](evidencia/uso.md) | Uso da prova, validade, status de fecho e layout dos registros. |
| [`formas/`](formas/README.md) | Schema dos registros (4 formas adotadas, 11 candidatas). |
| [`acervo/`](acervo/README.md) | 26 peças do desenho e o estado de cada uma. |
| `.agents/skills/` | 10 skills Databricks (aitools v0.2.10) para Cursor, Codex e OpenCode; roteamento em [`trilhas/`](trilhas/README.md#skills-databricks). |
| [`adaptadores/`](adaptadores/README.md) | Tradução dos eventos de cada runtime para a mesma guarda. |
| [`avaliacao/`](avaliacao/README.md) | Oito cenários e métricas para medir a política. |
| `implementacao/`, `configuracao/`, `testes/` | Código da guarda e da prova, política de caminhos e testes. |
| `.execucoes/` | Registros locais: provas, sessões e diagnósticos. Fora do Git. |

## Estado

**Imposto por código** (a IA não contorna pelo shell do chat):

- `databricks bundle` só roda no bundle local, com comando literal, target `sandbox` e perfil explícito.
- SQL ad hoc pela CLI só lê; escrita é negada.
- `run`, `destroy`, `sync` e `deploy` são negados. Target `dev` só passa com autorização registrada na política (hoje não há nenhuma). Deploy segue negado porque identidade e destinos ainda não são conferidos.
- No Cursor, `prova.py fechar` recusa `DONE` sem prova atual; o `stop` pede correção até duas vezes.

**Só instrução** (depende do modelo): escolher o caminho e a trilha, iniciar a fatia antes de editar, perguntar pouco, preservar trabalho prévio, coordenar dados do sandbox, respeitar a fronteira do produto.

**Fora da guarda**: terminal manual, MCP, SDK, REST, edição de arquivo e ferramentas que não são shell.

**Ainda não observado**: nenhuma sessão real de Cursor, Claude Code, Codex ou OpenCode mostrou o hook negando ou a prova sendo coletada. Os testes locais cobrem o código, não a ativação. A avaliação dos oito cenários não foi executada.

**Skills Databricks**: as 10 roteadas pelas trilhas ficam em `.agents/skills/`, lido por Cursor, Codex e OpenCode. O Claude Code recebe as 29 pelo plugin `databricks` do projeto. Ativação a observar em sessão.

**Não implementado**: skills do projeto, subagentes, 11 das 15 formas, guarda de `run`, coordenação de dados, identidade autenticada e `docs-distill`.

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
py -3 adaptadores/gerenciar.py cursor --instalar
```

- Linux/macOS: `python3`, `.venv/bin/python` e `--plataforma posix` no instalador.
- Requisitos: Python 3.12+ e PyYAML (`requirements.txt`).
- Sem o clone do produto, a guarda nega toda chamada `databricks bundle`. Ela não procura outro checkout.
- O `AGENTS.md` e o `CLAUDE.md` do produto não são versionados; um clone novo não os traz.
- Versione mudanças de produto no repositório dele (`git -C prj-avante-analytics-adb ...`).

## Precedência

No escopo do produto, o `AGENTS.md` dele prevalece. Sobre o comportamento da esteira, valem o código e o `AGENTS.md` do produto. Sobre o harness, valem estes arquivos e o código; o HTML é o desenho.

## Onde o HTML diverge da pasta

O HTML não é editado. Nestes pontos, vale o que está aqui:

- **Git do harness**: o HTML diz ausente. A pasta é um repositório Git. Só o clone `prj-avante-analytics-adb/` está ausente.
- **Claude Code**: o HTML diz que a carga do `AGENTS.md` não está integrada. O `CLAUDE.md` importa `@AGENTS.md` ([adaptador](adaptadores/claude_code/README.md)).
- **Layout das provas**: o HTML usa `<execucao_id>/<fatia_id>/`. O código grava uma fatia por execução em `.execucoes/provas/<execucao_id>/principal/`, com `contrato.yaml`, `logs/resultado.txt` e sessões em `.execucoes/sessoes/` ([layout](evidencia/layout.md)).
- **Estrutura**: a tabela do HTML lista só código e configuração. A estrutura completa está acima.

## Verificar mudanças no harness

```powershell
py -3 -m unittest discover -s testes -p teste_*.py -v
node testes/teste_opencode.mjs
```
