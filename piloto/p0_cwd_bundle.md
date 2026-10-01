# P0 — primeira fatia: diretório e bundle no Codex

> Registro histórico da primeira entrega. Correção posterior do usuário:
> **Cursor é o adaptador principal**. O núcleo foi desacoplado, com quatro
> traduções. Estado atual em [arquitetura](../adaptadores/arquitetura.md).

Data: 28/09/2026. Escopo autorizado: avançar a implementação conforme a primeira
fatia sugerida. O término desta fatia é disponibilizar e testar a guarda local,
preparar sua instalação e explicitar o aceite de ativação que depende do runtime.
Não representa a conclusão da P0, nem da guarda completa de identidade/destinos.

## Decisões e superfície

- Primeiro adaptador: Codex CLI 0.158.0, Windows/PowerShell, Python 3.14.6.
- Código em `implementacao/`, `adaptadores/codex/` e `testes/`; dependência em
  `requirements.txt`. Documentação de status atualizada nesta árvore.
- Configuração operacional: `.codex/hooks.json` na raiz do workspace, por
  mesclagem que preserva handlers existentes e cria backup quando necessário.
- Diagnósticos: `.execucoes/codex/cwd_bundle/`, fora da árvore de produto.
- Fora: edição de notebooks/configuração de produto, deploy/run, schemas e
  validador das formas 3.0, persistência P0b, novos agentes e skills.
- Executor e verificador local: agente coordenador, com testes objetivos;
  nenhuma revisão independente por subagente foi realizada.

O HTML continua sendo a referência de política. Esta implementação é um recorte
deliberadamente parcial, sem redefinir seus critérios de conclusão. O valor
interno `permitir` não fecha o enum da forma `guarda`: não há consumidor daquela
forma nesta fatia. As quatro decisões de schema seguem em `formas/README.md`.

## Aceite

| Critério | Prova / estado |
|---|---|
| Diretório oficial e busca ascendente para o oficial são negados | Suíte `teste_cwd_bundle.py`, fixtures isoladas |
| Nome igual em outro diretório não autoriza a chamada | Suíte local |
| Diretório local, YAML válido e chamada coberta permitem continuar | Suíte local, sem conceder aprovação Codex |
| Correção do diretório preserva argumentos e não executa automaticamente | Suíte local com prefixo literal e erro terminante |
| Falha de YAML, payload ou registro produz negação | Suíte local e subprocesso real do adaptador |
| Negação antecede o executor | Consumidor simulado com marcador de efeito; não prova sessão Codex |
| Instalação preserva configuração anterior e não duplica handlers | Testes de mesclagem, backup, conflito e idempotência |
| Confiança e interceptação em sessão Codex real | Pendente: `/hooks` e observação do evento real |

Comando de verificação, a partir da raiz clonada do harness:

```powershell
py -3 testes/teste_cwd_bundle.py
```

Não foi executada chamada Databricks pelos testes. O primeiro ensaio foi
impedido por acesso do sandbox à pasta temporária; a execução autorizada fora
do sandbox permite criar e remover as fixtures isoladas.

Resultado final em 28/09/2026: **36 testes passaram**, exit code **0**, Python
3.14.6 / PyYAML 6.0.3. Inclui leituras literais de `databricks.yml` sem bloqueio
indevido e negação de leitura com efeito anexado. Este resultado é a prova
local do código desta fatia, não o aceite de ativação no Codex.

## Próxima transição

Na primeira entrega, a configuração foi instalada na pasta pai do harness;
essa localização foi corrigida para a raiz clonável. A checagem local inicial também leu os arquivos reais do
repositório: o bundle local passou; `bundles/` foi negado como `cwd_incorreto`.
Nenhuma CLI Databricks foi disparada nessa inspeção.

Revisar e confiar na definição pelo `/hooks`. A confiança
é um requisito do runtime documentado em
[Hooks](https://learn.chatgpt.com/docs/hooks), não uma aprovação adicional
inventada pela política do harness. Nenhum hash de confiança é alterado pelo
instalador. Registrar a negação em sessão antes de marcar o adaptador verificado.

Em seguida, ampliar a checagem de identidade e destinos resolvidos, guardas de
efeito e fecho. A prova mínima P0b e os oito cenários P1 vêm depois.
