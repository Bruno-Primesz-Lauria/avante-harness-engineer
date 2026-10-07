# Harness da esteira

Regras para todo pedido. Detalhes em `nucleo/modus-operandi.md`.
Contexto do projeto Avante (vocabulário, etapas, papéis): `nucleo/contexto-avante.md` — advisory, nunca autoridade.

## Sempre

- Busque o fato no repositório antes de perguntar. Pergunte só o que muda escopo, resultado ou autorização.
- Faça a menor mudança que resolve o pedido. Preserve alterações que já existiam.
- O produto fica em `prj-avante-analytics-adb/`, com Git próprio e sem instruções de agente próprias: as regras para trabalhar nele são as deste harness. A documentação do bundle (`README.md`, `GUIA-DESENVOLVIMENTO.md`, `PLANO-DE-EXECUCAO.md`) é fonte de fato, não de regra.
- Registros do harness ficam em `.execucoes/`, nunca nos arquivos do produto.
- Leia `nucleo/contexto-avante.md` quando o pedido ou a fonte citar Mock, SIT, UAT, etapas do objeto, módulos SAP ou papéis (PO, Key User, etc.).

## Caminho simples ou estruturado

- **Simples**: pergunta delimitada ou mudança pequena e reversível. Responda com fontes ou altere e verifique. Sem contrato.
- **Estruturado**: várias etapas, impacto relevante, ambiguidade ou retomada. Siga a trilha em `trilhas/` e, **antes de editar**, inicie a fatia:
  `py -3 adaptadores/prova.py iniciar <contrato.yaml>` — modelo do contrato em `evidencia/uso.md`.
  Rode as verificações pelo chat, consulte com `estado` e feche com `fechar`.
  Só escreva `DONE` se `fechar` aceitar. Se recusar, verifique de novo ou feche com `BLOCKED`, `FAILED` ou `DECIDE` (`evidencia/fecho.md`).
- **Agentes obrigatórios**: se a trilha estiver em `agentes_obrigatorios` do seu runtime (`configuracao/politica.json`), você coordena e delega aos papéis de `agentes/` na ordem de [`trilhas/README.md`](trilhas/README.md#agentes). Não faça em silêncio o trabalho de um papel obrigatório: papel indisponível fecha `BLOCKED`. Fora da chave, um único agente executa a trilha.
- **Limite temporário no Claude Code**: até o gate G2 do Claude Code, a coleta de provas desse runtime não foi observada em sessão real; portanto, `fechar` não comprova `DONE`. Feche a fatia como `BLOCKED`, registrando o motivo e a condição de retomada, ou execute a fatia no Cursor. Relato de agente não substitui prova.

## Databricks

- Leia `guardas/README.md` antes de qualquer `databricks bundle`.
- Em `databricks bundle`, rode um comando literal por vez, sem pipe, `;`, `&&` extra ou variável, no diretório do bundle local `prj-avante-analytics-adb/bundles/src/notebooks/saneamento_migracao`. Se o runtime não informa o diretório, use o prefixo `Set-Location -LiteralPath '<caminho>' -ErrorAction Stop;` (PowerShell) ou `cd -- '<caminho>' &&` (Bash).
- `validate`, `plan` e `deploy` estão autorizados somente com `-t sandbox`, dentro do bundle local acima. Deploy segue exigindo `plan` atual, `-p` e `--select`. Qualquer outro target (inclusive `dev`) e todo `run` exigem autorização explícita. A guarda não concede autorização.
- Uma negação vale para aquela chamada. Corrija e repita; não contorne com outra ferramenta, wrapper ou terminal.
- Para comando ou API da plataforma, use as skills `databricks-*` indicadas para a trilha em `trilhas/README.md` (comece por `databricks-core`). Elas ensinam; não autorizam. Se a skill e o harness divergirem, vale o harness.
- SQL ad hoc (`databricks experimental aitools tools query`) só lê: `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `EXPLAIN`. A guarda nega escrita; ela segue pelo pipeline ou job do bundle, ou o usuário executa.

## Mudanças no próprio harness

Verifique com `py -3 -m unittest discover -s testes -p teste_*.py -v` e `node testes/teste_opencode.mjs`.
