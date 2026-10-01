# Formas

O desenho tem quinze formas. [`implementacao/formas.py`](../implementacao/formas.py) valida quatro: `contrato`, `guarda`, `brief` e `teste`, na versão 3.1 de [`catalogo.yaml`](catalogo.yaml). As outras onze (`intencao`, `mapa`, `config`, `implement`, `docs`, `destilar`, `ataque`, `diagnostico`, `sandbox`, `paridade`, `resposta`) são candidatas: o validador as recusa ("forma ainda não adotada") e nenhuma trilha grava registro delas.

Os exemplos do HTML usam `exemplo: true`. Servem de ilustração. O validador rejeita esse registro.

## Envelope

Todo evento carrega `schema_versao`, `tipo`, `exemplo`, `execucao_id`, `fatia_id`, `tentativa`, `evento_id`, `produtor`, `registrado_em`, `manifesto_ref` e `dados`. As regras de cada campo estão no catálogo. Cada forma tem um produtor fixo: `coordenador` (`contrato`, `brief`), `hook` (`guarda`), `executor_teste` (`teste`).

O validador rejeita: `exemplo: true`, identidade de outra execução, chave desconhecida, referência que fuja da raiz e manifesto ou evidência ausente.

Validação sintática não atesta verdade. O armazenamento valida cada evento antes de gravar e recusa gravar o mesmo evento duas vezes. O fecho confere critérios do contrato, logs, manifesto e hashes ([uso](../evidencia/uso.md)).

`intencao` não é obrigatória: o objetivo já mora no `contrato`.

## Campos fechados

- `contrato`: `fontes` é lista de strings; `prazo` é timestamp com fuso ou null.
- `guarda`: a chamada tem decisão `permitir`, `negar` ou `nao_aplica`. A decisão não amplia a autorização do runtime. `negar` impede a chamada dependente, não a tarefa inteira.
- `teste`: campos, tipos e enums no catálogo; log e estado ligados por hash.
- Baseline, manifesto e estado: versão 1, em [`evidencia/uso.md`](../evidencia/uso.md).

## Dois vereditos

- Tarefa de review, sobre o artefato: `aceitavel`, `com_achados`, `inconclusivo`.
- Forma `ataque` (candidata): `com_achados`, `nao_quebrei`, `inconclusivo`.

Os nomes canônicos estão em `catalogo.yaml`.
