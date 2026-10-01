# Contrato proporcional

O contrato registra o que será verdadeiro ao fim da fatia. O agente preenche o que descobre no repositório. O usuário não classifica o trabalho nem preenche formulário.

No caminho simples o contrato é o escopo no chat, quando houver escrita. No estruturado, o registro segue a forma `contrato` em [`formas/catalogo.yaml`](../formas/catalogo.yaml). O agente o prepara conforme [`evidencia/uso.md`](../evidencia/uso.md).

## Campos

| Campo | Caminho simples | Caminho estruturado |
|---|---|---|
| Intenção e término | Pedido claro e resposta verificável. | Objetivo completo, término da fatia e aceite enumerado. |
| Superfície | Arquivos necessários, identificados antes da edição. | Lista exata dos arquivos de produto, separada da raiz de artefatos do harness. |
| Fora | Limites inferidos do pedido. Pode ficar vazio. | Exclusões importantes nomeadas. Lista vazia não gera pergunta. |
| Fontes | Caminhos que sustentam a resposta ou a alteração. | Instruções aplicáveis, código, documentos vivos e o irmão da etapa. |
| Aceite | Verificação adequada ao resultado. | Critérios com `tipo` (`teste`, `inspecao_documental`, `analise_codigo`, `ambiente`, `paridade`, `validacao_dados`), `esperado` e `verificacao` (comando, cwd, caminhos). Fatia que publica dado usa `validacao_dados` para conferir schema e conteúdo da saída. |
| Responsabilidades | O agente executa; a prova objetiva valida. | Quem executa, quem verifica e quem coordena. |
| Orçamento e prazo | Limites do runtime. | Ciclos e repetições no registro, ajustando o [orçamento padrão](../nucleo/modus-operandi.md). `prazo` é data com fuso ou `null`. |

O aceite de cada trilha (superfície, critério e fecho) está no arquivo da trilha.

## Fechado quando

- O término da fatia é observável e separado do objetivo completo do objeto.
- Cada critério obrigatório tem tipo permitido e esperado verificável.
- A superfície de produto e a raiz de artefatos estão em campos diferentes.
- Os identificadores de aceite são únicos.
