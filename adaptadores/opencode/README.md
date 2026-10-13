# OpenCode

Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.opencode/plugins/esteira.js`, gerada com `py -3 adaptadores/gerenciar.py opencode --instalar`. Importa a ponte `esteira.js` desta pasta por caminho relativo, então o clone pode mudar de diretório. O instalador não sobrescreve um plugin diferente.
- Agentes nativos: sete definições em `.opencode/agents/`, geradas de `agentes/` com `py -3 adaptadores/gerar_agentes.py --instalar opencode`. Para conferir as definições dos três runtimes, rode `py -3 adaptadores/gerar_agentes.py --verificar`.
- O OpenCode carrega essas definições como `mode: subagent`; as permissões por papel derivam de `FERRAMENTAS_CLAUDE` e o modelo é herdado da sessão. Carregue skills pertinentes pela ferramenta nativa `skill`, usando os nomes `databricks-<skill>`.
- `opencode.json` pede confirmação para `databricks bundle *`. É uma camada adicional; a guarda do harness continua decidindo cwd, target, perfil e operação.
- A ponte encaminha `tool.execute.before` e `tool.execute.after` para `bash` e `task`, além de `shell.env`, `session.created` e `session.idle`. Ela chama `adaptadores/entrada.py` sem shell, com timeout de 10 s.
- Só o `before` de `bash` pode bloquear: negação, erro, timeout ou resposta inválida impedem a ferramenta. Os outros eventos são best-effort. Os argumentos originais não são alterados.
- O cwd vem de `args.workdir`, ou do prefixo literal. Para um comando que coincide com a verificação do contrato, o `before` grava o manifesto e o `after` registra o exit e a saída observados; timeout ou metadados ausentes ficam inconclusivos.
- `task` abre a janela da chamada. O vínculo entre `session.created.info.parentID`, `metadata.parentSessionId`/`metadata.sessionId` e o Bash da sessão filha registra o papel e seu `agente_id`. O status vem de `metadata.state` ou de `state` no texto de saída (`completed`, `failed`, `cancelled`); estado ausente ou desconhecido fica inconclusivo. Vínculo ausente ou ambíguo não cria chamada observada.
- `shell.env` injeta `ESTEIRA_SESSAO` e `ESTEIRA_RUNTIME=opencode`. Assim, `prova.py` detecta OpenCode; `--runtime` explícito continua prevalecendo. Fora de uma sessão OpenCode, passe `--runtime opencode` manualmente.
- `session.idle` confere a fatia principal e pede a correção do fecho por no máximo dois follow-ups. A coleta e o limite foram testados localmente; observação integrada dos agentes em sessão real e ativação em trilha aguardam O-OC/G2-OC. OpenCode segue fora da chave de produção `agentes_obrigatorios`.
- Confira: inicie uma sessão nova para carregar o plugin. Testes: `py -3 -m unittest discover -s testes -p teste_adaptador_opencode.py -v` e `node testes/teste_opencode.mjs`.

## Comportamento observado do runtime

Observado em 13/10/2026 no OpenCode CLI/TUI 1.18.35, Windows. Os registros da sonda temporária ficam em `.execucoes/sondagem-opencode/eventos.jsonl`; ela não integra o plugin de produção.

- `tool.execute.before` recebe `input.tool`, `sessionID` e `callID`; `output.args` contém os argumentos. `tool.execute.after` recebe também `args` na entrada e devolve `title`, `output` e `metadata`. Bash concluído com falha teve `metadata.exit: 1`; timeout teve `metadata.exit: null` e a mensagem de timeout em `output`.
- Em `task`, `args.subagent_type` identifica o papel. O retorno observado foi síncrono (`completed`) e trouxe em `metadata` `parentSessionId`, `sessionId` e o modelo. `session.created` do filho trouxe `info.parentID`; o Bash do filho usou o `sessionID` da sessão filha, igual ao `metadata.sessionId` do `task`.
- `session.idle` trouxe `properties.sessionID`. Uma chamada a `client.session.prompt` nesse evento gerou a resposta seguinte no TUI. No `opencode run` headless, a mensagem foi aceita e apareceu no histórico, mas o processo encerrou antes de gerar a resposta; o follow-up foi confirmado no TUI.
- `shell.env` recebeu `cwd`, `sessionID` e `callID`. Na sonda, os valores injetados `ESTEIRA_SESSAO=<sessionID>` e `ESTEIRA_RUNTIME=opencode` chegaram ao Python tanto no agente principal quanto no subagente.
- `.opencode/agents/` carregou um agente Markdown temporário com `description`, `mode: subagent` e `permission`. Sem `model` no agente, `chat.params` mostrou o mesmo modelo escolhido na sessão principal (`db-anthropic-models/claude-haiku-4-5`). A resposta do subagente reproduziu o diretório de bundle de `AGENTS.md`; o prompt de sistema não é exposto pelo hook, então esse ponto é uma observação comportamental.
- O subagente chamou a ferramenta nativa `skill` e carregou `databricks-core` de `.agents/skills/databricks-core/`.
- Um `opencode.json` temporário de projeto, sem `provider` nem `model`, preservou a lista dos cinco modelos de `opencode models`; uma chamada ao modelo selecionado respondeu `OK`. A configuração global e suas credenciais não foram lidas nem alteradas.

Esses resultados descrevem a versão observada. Timeout e erro foram exercitados; o comportamento de outros provedores/modelos não foi sondado.
