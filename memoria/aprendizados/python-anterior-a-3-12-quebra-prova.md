---
schema_versao: 1
id: python-anterior-a-3-12-quebra-prova
tipo: aprendizado
status: ativo
tags: [python, ambiente, prova, macos]
caminhos: [implementacao/provas.py, adaptadores/entrada.py, requirements.txt]
fontes: [implementacao/provas.py, adaptadores/entrada.py, README.md, https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_junction]
verificado_em: 2026-10-06
---

# Python anterior a 3.12 quebra o retrato da prova com `is_junction`

## Contexto

O README exige Python 3.12 ou mais novo, sem dizer o sintoma. O retrato da prova em [`provas.py`](../../implementacao/provas.py) recusa link com `Path.is_junction()`, que só existe a partir do Python 3.12.

## Descoberta

Em 2026-10-06, num Mac em que o `python3` padrão era o 3.11 do Anaconda, a suíte do harness terminou com 80 erros e uma falha em 191 testes. O erro comum foi `AttributeError: 'PosixPath' object has no attribute 'is_junction'`. Com um `.venv` em Python 3.14 e o PyYAML do `requirements.txt`, os 191 testes passaram.

O [`entrada.py`](../../adaptadores/entrada.py) roda o hook com o Python do `.venv` quando ele existe. Sem `.venv`, usa o mesmo Python que iniciou o hook.

## Quando aplicar

Erro com `is_junction`; muitos erros na suíte logo após clonar; Mac com Anaconda ou o Python do sistema (3.9) como `python3`.

## Como resolver

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Use qualquer Python 3.12 ou mais novo disponível. Rode a suíte com `.venv/bin/python`.

## Limites

Só o caminho do erro nas provas foi conferido. Não foi medido o que o hook responde em cada evento quando roda com Python 3.11.

## Como conferir

```bash
.venv/bin/python -m unittest discover -s testes -p 'teste_*.py'
```
