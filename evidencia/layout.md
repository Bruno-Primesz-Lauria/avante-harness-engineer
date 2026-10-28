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
  requisitos.json             # requisitos fixados nas novas execuções
  continuidade/<id>.json       # checkpoints, transferências e conferências
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

Nas execuções portáteis, `checkpoint` guarda próximo passo e referências de autorização; `operacoes_pendentes` acumula efeitos sem resultado confirmado. Contrato, baseline, provas, revisões e triagens continuam acessíveis pelos registros. `requisitos.json` fixa autorização, ambiente/paridade, revisão e diagnóstico; o estado guarda seu hash. `participantes` preserva sessões e runtimes e `continuidade/` registra cada transferência, checkpoint e conferência de operação com hash próprio.

## Retomada

Use `--execucao ID estado` para consultar. Na origem, `liberar` salva checkpoint e libera coordenação. No destino, `retomar --motivo ...` compara o estado e assume a execução. Escrita exige a sessão e o runtime coordenadores. Para processo interrompido, `--recuperar --revisao N` e motivo explícito substituem a liberação; confira que o processo terminou. Não há expiração automática. Verificação ou delegação pendente impede transferência. Uma nova sessão na mesma CLI segue o mesmo protocolo.

Eventos portáteis acrescentam `origem` (sessão e runtime) ao envelope; os eventos anteriores não são reescritos. Execução antiga requer `migrar` para uma execução vinculada, com critérios e superfície preservados, baseline novo e provas novas. Os hashes da origem ficam no vínculo. Registros locais precisam acompanhar o workspace para trocar de máquina.

Compare o estado, confira o resultado de operação externa pendente e revalide as provas. Efeito externo já disparado não se repete só porque a sessão caiu. Se não der para saber se o efeito ocorreu, o status é `BLOCKED`.
