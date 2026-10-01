# P0b — prova mínima, 01/10/2026

O núcleo da fase 4 e sua integração com os eventos do Cursor estão implementados.
O aceite operacional das fases 2–4 ainda depende de uma sessão real. O piloto
completo não foi executado.

## Entrega

- `AGENTS.md` como entrada curta para a política existente.
- Validação das quatro formas adotadas, versão 3.1, pelo catálogo existente.
- Baseline, manifesto, log, resultados e fechos preservados por execução.
- Separação de sessões, escrita exclusiva de eventos, lock e revisão do estado.
- Comparação de hashes antes/depois da verificação e no fecho. Criação, edição
  ou remoção relevante invalida a prova; documento fora do critério não invalida.
- Coleta Cursor ligada ao ID da chamada e ao `exitCode` observado. Resultado
  ausente, timeout ou mudança durante a chamada não vira sucesso.
- Recibo de plan após sucesso observado. Deploy continua negado até conferir
  identidade autenticada e destinos; a nova coleta não abre essa permissão.
- Fecho persistido conferido e `stop` com até duas solicitações de correção.
- `.venv` local preparado com PyYAML 6.0.3. Nenhuma dependência nova acrescentada.

Uso, formato dos registros e exemplo de contrato: [prova mínima](../evidencia/uso.md).

## Revisão e testes

A revisão foi feita pelo mesmo agente, com testes objetivos; não houve
delegação. As suítes Python e OpenCode verificam código local e protocolos
simulados. Incluem subprocessos reais do adaptador em uma cópia com espaços no
caminho. Nenhuma operação Databricks foi executada.

```powershell
py -3 -m unittest discover -s testes -p teste_*.py -v
node testes/teste_opencode.mjs
```

O sandbox Windows impede acesso a algumas fixtures; a execução autorizada fora
dele é necessária nesta estação. Resultado final: **102 testes Python passaram**,
e a ponte OpenCode passou, ambos com exit 0. O próprio núcleo registrou essa
validação com eventos explicitamente simulados, logs, hashes e fecho válido.
Resumo local: [resultado P0b](../.execucoes/revisao/resultado_p0b.json).

Execução da prova: `790382f95d1d44f3932911e23ff78c3e`. Os arquivos ficam em
`.execucoes/provas/790382f95d1d44f3932911e23ff78c3e/principal/`.
Também foram conferidos sintaxe Python, links locais, IDs do HTML e igualdade
das duas cópias do guia.

## Pendências para o piloto

1. Preparar o clone interno do produto com as instruções corretas. O checkout
   da pasta pai contém `AGENTS.md` e `CLAUDE.md` não versionados; um clone Git
   simples não leva esses arquivos. Esse checkout foi apenas inspecionado.
2. Abrir uma sessão nova no Cursor e observar carregamento, diretório real da
   chamada, eventos de resultado, invalidação após edição e retomada do fecho.
3. Completar identidade/destinos, run e coordenação para os cenários que exigem
   efeito externo. Não representar simulação como operação real.
4. Fixar o snapshot do harness e executar as 48 repetições do piloto. O harness
   ainda não foi inicializado/publicado como repositório Git nesta entrega.

O `stop` do Cursor não impede uma resposta já exibida. Portanto o bloqueio
garantido nesta fase é o de `DONE` no registro persistido; a disciplina do chat
e a taxa de falso `DONE` precisam ser verificadas no piloto. Não se declara
100% de prontidão com base apenas na suíte local.
