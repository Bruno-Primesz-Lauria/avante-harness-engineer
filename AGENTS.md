# Harness da esteira

Regras para todo pedido. Detalhes em `nucleo/modus-operandi.md`.

## Sempre

- Busque o fato no repositório antes de perguntar. Pergunte só o que muda escopo, resultado ou autorização.
- Faça a menor mudança que resolve o pedido. Preserve alterações que já existiam.
- O produto fica em `prj-avante-analytics-adb/`, com Git próprio. Leia o `AGENTS.md` dele antes de trabalhar ali; ele prevalece nesse escopo.
- Registros do harness ficam em `.execucoes/`, nunca nos arquivos do produto.

## Caminho simples ou estruturado

- **Simples**: pergunta delimitada ou mudança pequena e reversível. Responda com fontes ou altere e verifique. Sem contrato.
- **Estruturado**: várias etapas, impacto relevante, ambiguidade ou retomada. Siga a trilha em `trilhas/` e, **antes de editar**, inicie a fatia:
  `py -3 adaptadores/prova.py iniciar <contrato.yaml>` — modelo do contrato em `evidencia/uso.md`.
  Rode as verificações pelo chat, consulte com `estado` e feche com `fechar`.
  Só escreva `DONE` se `fechar` aceitar. Se recusar, verifique de novo ou feche com `BLOCKED`, `FAILED` ou `DECIDE` (`evidencia/fecho.md`).

## Databricks

- Leia `guardas/README.md` antes de qualquer `databricks bundle`.
- Rode um comando literal por vez, sem pipe, `;`, `&&` extra ou variável, no diretório do bundle local `prj-avante-analytics-adb/bundles/src/notebooks/saneamento_migracao`. Se o runtime não informa o diretório, use o prefixo `Set-Location -LiteralPath '<caminho>' -ErrorAction Stop;` (PowerShell) ou `cd -- '<caminho>' &&` (Bash).
- Deploy e `run` exigem autorização explícita. A guarda não concede autorização.
- Uma negação vale para aquela chamada. Corrija e repita; não contorne com outra ferramenta, wrapper ou terminal.

## Mudanças no próprio harness

Verifique com `py -3 -m unittest discover -s testes -p teste_*.py -v` e `node testes/teste_opencode.mjs`.
