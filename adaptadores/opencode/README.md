# OpenCode

Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.opencode/plugins/esteira.js`, gerada com `py -3 adaptadores/gerenciar.py opencode --instalar`. Importa a ponte `esteira.js` desta pasta por caminho relativo, então o clone pode mudar de diretório. O instalador não sobrescreve um plugin diferente.
- Agentes nativos: sete definições em `.opencode/agents/`, geradas de `agentes/` com `py -3 adaptadores/gerar_agentes.py --instalar opencode`. Para conferir as definições dos três runtimes, rode `py -3 adaptadores/gerar_agentes.py --verificar`.
- O OpenCode carrega essas definições como `mode: subagent`; as permissões por papel derivam de `FERRAMENTAS_CLAUDE` e o modelo é herdado da sessão. Carregue skills pertinentes pela ferramenta nativa `skill`, usando os nomes `databricks-<skill>`.
- `opencode.json` pede confirmação para `databricks bundle *`. É uma camada adicional; a guarda do harness continua decidindo cwd, target, perfil e operação.
- `tool.execute.before` da ferramenta `bash`.
- A ponte chama `adaptadores/entrada.py` sem shell, com timeout de 10 s. Lança erro e impede a chamada quando a guarda nega, falha, responde algo inválido ou demora demais.
- O cwd vem de `args.workdir`, ou do prefixo literal. A ponte não altera argumentos.
- Não coleta prova nem retoma fecho.
- Em fatias estruturadas, informe `--runtime opencode` em cada comando `adaptadores/prova.py`; OpenCode não é detectado automaticamente nem pode ser incluído em `agentes_obrigatorios`.
- As definições dos sete papéis estão geradas, mas a observação dos papéis em sessão real e a ativação em trilha aguardam o gate humano G2-OC. Coleta de provas e retomada de fecho continuam pendentes de D-OC.
- Confira: inicie uma sessão nova para carregar o plugin. Teste da ponte: `node testes/teste_opencode.mjs`.

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
