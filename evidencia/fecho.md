# Evidência e fecho

Uma prova descreve o que foi observado, em qual execução e sobre qual estado. O fecho consolida as provas depois de conferir os critérios obrigatórios. Só o coordenador publica. A forma é `brief` em [`formas/catalogo.yaml`](../formas/catalogo.yaml). Comandos e registros: [`uso.md`](uso.md).

No caminho simples o fecho é prosa curta no chat, com os mesmos campos: status, resultado, prova e limite. A prova cita comando, cwd, exit code e os caminhos lidos ou alterados. Edição relevante depois dela exige rodar o critério de novo.

## Quando a prova vale

| Exigência | O que conferir |
|---|---|
| Identidade | `execucao_id`, `fatia_id`, `tentativa`, `evento_id` e `schema_versao`. |
| Estado | Manifesto com caminhos e hashes de conteúdo, inclusive arquivo não rastreado relevante. Git HEAD sozinho não basta. |
| Dependências | Versão de ferramenta e de configuração. Em dado: recorte, snapshot, versão ou `run_id`. Declare o limite quando o dado não for reproduzível. |
| Execução | Comando, cwd, início, fim, exit code e log obtido pelo executor. Identificador da chamada, quando existir. |
| Base | `direct`: artefato ou execução verificável. `derived`: cálculo com insumos rastreáveis. `reported`: relato sem verificação. |
| Resultado | `pass`, `fail`, `info` ou `inconclusivo`. |
| Validade | Compare o estado atual com o testado. Mudança relevante invalida a prova. Alteração sem relação com o critério exige justificativa explícita para a prova continuar válida. |
| Aceite | O observado confronta o esperado do critério. Exit 0 não cobre requisito que o comando não exercita. |

`pass` recebido de outro agente não prova a execução: o coordenador precisa do log ou artefato verificável e de um manifesto compatível. Prova `derived` fecha paridade quando insumos e cálculo são verificáveis. Prova `reported` sozinha não fecha critério obrigatório.

Não implementado: o campo `base` não existe na forma `teste`. O núcleo registra só prova direta, de comando observado com exit code. Critério sem comando verificável não fecha pelo núcleo.

## Status da tarefa

Review é uma tarefa: pode estar `DONE` mesmo quando o artefato revisado tem bloqueio. O veredito do artefato é outro campo (`aceitavel`, `com_achados`, `inconclusivo`). `DONE` da revisão não aprova o produto.

| Status | Quando usar | Próxima ação |
|---|---|---|
| `DONE` | Todos os critérios obrigatórios fecharam com prova válida. Nenhum achado obrigatório aberto. | Nenhuma ação humana obrigatória. Declare se fechou a fatia ou o objetivo inteiro. |
| `REVIEW` | O aceite técnico fechou e o acordo prevê revisão humana. | Indique exatamente o que revisar. |
| `DECIDE` | Duas opções concretas, ou autorização ou coordenação ausente, dependem de decisão humana. | Uma pergunta suficiente para a dependência. O trabalho independente continua. |
| `BLOCKED` | Acesso, capacidade, conflito concorrente ou estado externo impede continuar ou verificar, depois da recuperação possível. | Nomeie impedimento, evidência e condição de retomada. A negação isolada de um comando não basta. |
| `FAILED` | A verificação rodou e reprovou o aceite, e a trilha não corrige ou esgotou o orçamento. | Resultado negativo localizável. Preserve o trabalho e nomeie o critério. |

## Resultado de checagem

| Resultado | Significado |
|---|---|
| `limpo` | A checagem aplicável rodou e a evidência aprovou. |
| `bloqueio` | A checagem rodou e encontrou condição impeditiva. |
| `nao_aplica` | Critério fora do escopo, com justificativa e referência ao contrato. |
| `nao_verificado` | Critério aplicável sem evidência suficiente. Impede `DONE` quando obrigatório. |

## Apresentação

Quatro linhas bastam para a pessoa:

```text
Status: DONE — fatia T1
Resultado: <o que ficou verdadeiro>
Prova: <o que foi observado e onde>
Limite: <o que esta fatia não cobriu>
```

O bloco é formato, não resultado de execução.
