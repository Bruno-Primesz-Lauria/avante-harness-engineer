# Estado e retomada

Layout dos artefatos do harness, separados dos arquivos de produto, do PR e do deploy. O núcleo grava `provas/` e `sessoes/` em `.execucoes/`. `entradas/` é o rascunho e `provas/` é a cópia imutável; `indice.md` é gerado pelo `prova.py`. O conteúdo de cada registro, os schemas e os limites estão em [`uso.md`](uso.md).

```text
.execucoes/entradas/<assunto>/
.execucoes/indice.md
.execucoes/plans/<data>-plan-<target>-<selecao>.json
.execucoes/provas/<data>-<trilha>-<assunto>/principal/
  baseline.json
  contrato.yaml
  estado.json
  tentativas/NNN/
    manifesto.json
    eventos/<evento_id>.yaml
    logs/resultado.txt
  fechos/<fecho_id>.yaml
.execucoes/sessoes/<data>-<trilha>-<assunto>/ativa.json
.execucoes/sessoes/mapa.json
```

O nome da prova, do recibo de plan e da sessão leva a data e o assunto. `sessoes/mapa.json` liga o identificador da sessão do runtime a essa pasta. Cada evento dentro da fatia conserva o identificador da gravação: o `estado.json` confere o arquivo por esse nome.

## Propriedade

Um coordenador publica fechos e atualiza `estado.json`. Hooks e agentes emitem eventos únicos e imutáveis. Ninguém disputa o fecho.

Toda tentativa nova e todo fecho novo preservam os anteriores. A escrita do estado usa troca atômica e controle de revisão; conflito impede sobrescrita silenciosa.

Logs omitem segredo e dado pessoal desnecessário.

## Baseline

O baseline captura o estado anterior relevante, inclusive arquivo não rastreado. Git limpo não é pré-condição. Alteração concorrente que conflite com a edição da fatia interrompe a edição e não é atribuída ao agente.

## Checkpoint

O núcleo grava o estado antes de cada verificação do contrato (chamada pendente) e depois dela (prova). O checkpoint deve também guardar o próximo passo e as autorizações ou coordenações válidas, cada uma com seu escopo.

Não implementado: próximo passo e autorizações não ficam em `estado.json`. Registre-os no fecho ou no chat.

## Retomada

Compare o estado, confira o resultado de operação externa pendente e revalide as provas. Efeito externo já disparado não se repete só porque a sessão caiu. Se não der para saber se o efeito ocorreu, o status é `BLOCKED`.
