# Formas

[`implementacao/formas.py`](../implementacao/formas.py) valida as formas adotadas em [`catalogo.yaml`](catalogo.yaml), schema 3.2:

- 3.1 e 3.2: `contrato`, `guarda`, `brief` e `teste`.
- Só 3.2: `ataque`, `triagem`, `inspecao`, `chamada`, `diagnostico`, `sandbox` e `paridade`.

Uma forma é adotada quando o fecho depende dela para aceitar ou recusar DONE. Relato do autor não é prova.

`diagnostico`, `sandbox` (ambiente) e `paridade` foram aprovadas em 2026-10-05 e adotadas no pacote C6; em 3.1 o validador as recusa. `intencao`, `mapa`, `config`, `implement`, `docs`, `destilar` e `resposta` não serão adotadas; o motivo de cada uma está na seção 3.3 do [plano](../PLANO-AGENTES-TRILHAS.md).

Os exemplos usam `exemplo: true`. Servem de ilustração, e o validador rejeita esse registro.

## Envelope

Todo evento carrega `schema_versao`, `tipo`, `exemplo`, `execucao_id`, `fatia_id`, `tentativa`, `evento_id`, `produtor`, `registrado_em`, `manifesto_ref` e `dados`. As regras de cada campo estão no catálogo. Produtor de cada forma:

| Forma | Produtor |
|---|---|
| `contrato`, `brief`, `triagem` | `coordenador` |
| `guarda` | `hook` |
| `teste` | `executor_teste`, observado pelo hook, inclusive no subagente (`agente_id`) |
| `ataque` | `refute` |
| `inspecao` | `coordenador` ou `refute` |
| `chamada` | `adaptador`; nunca o coordenador |
| `diagnostico` | `coordenador` ou `map` |
| `sandbox` | `dab`, ligado à chamada `dab` observada e ao `teste` do comando |
| `paridade` | `test`, ligado ao `teste` do comando de paridade |

O validador rejeita: `exemplo: true`, identidade de outra execução, chave desconhecida, referência que fuja da raiz e manifesto ou evidência ausente.

Validação sintática não atesta verdade. O armazenamento valida cada evento antes de gravar e recusa gravar o mesmo evento duas vezes. O fecho confere critérios do contrato, logs, manifesto e hashes ([uso](../evidencia/uso.md)).

## Campos fechados

- `contrato`: `fontes` é lista de strings; `prazo` é timestamp com fuso ou null. Em 3.2, `teste`, `ambiente`, `validacao_dados` e `paridade` exigem `comando`, `cwd` e `caminhos`; `inspecao_documental` e `analise_codigo` exigem `caminhos`, `checagens` e `produtor`, sem comando.
- `guarda`: a chamada tem decisão `permitir`, `negar` ou `nao_aplica`. A decisão não amplia a autorização do runtime. `negar` impede a chamada dependente, não a tarefa inteira.
- `teste`: log e estado ligados por hash; `agente_id` e `exit_code_origem` são opcionais.
- `inspecao`: edição relevante em qualquer caminho a invalida, como acontece com o teste.
- `diagnostico`: textos não vazios; `criterio_reproducao` é um critério de teste do contrato; `evidencia_ref` fica dentro da fatia.
- `sandbox`: `nao_verificado` vale para o que a CLI não observa (`identidade`, `destinos_resolvidos` como `[nao_verificado]`, `coordenacao`); deploy exige os dois primeiros verificados, run também a coordenação, e `pass` em deploy ou run exige `plan_ref` e plan compatível. `plan_ref` é relativo a `registros_raiz`; `autorizacao_ref`, à raiz do harness.
- `paridade`: valores das contas em decimal, `diferenca` igual a `valor_origem` menos `valor_destino`; diferença sem divergência listada e divergência `pendente` impedem `pass`; divergência `explicada` leva explicação e evidência. O `resultado` de `sandbox` e `paridade` é calculado pelo núcleo a partir do teste observado.
- Baseline, manifesto e estado: versão 1, em [`evidencia/uso.md`](../evidencia/uso.md).

## Dois vereditos

- Tarefa de review, sobre o artefato: `aceitavel`, `com_achados`, `inconclusivo`.
- Forma `ataque`: `com_achados`, `nao_quebrei`, `inconclusivo`.

Os nomes canônicos estão em `catalogo.yaml`.
