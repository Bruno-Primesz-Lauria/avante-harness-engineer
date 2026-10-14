# Plano: OpenCode com paridade no harness (P0-OC → E0-OC)

## Contexto

O OpenCode já tem os sete agentes nativos, a configuração de projeto sem provedor/modelo, a coleta de provas e o kit local de observação. A guarda de shell continua no fluxo `.opencode/plugins/esteira.js` -> `adaptadores/opencode/esteira.js` -> `adaptadores/entrada.py opencode`; o runtime ainda depende de `--runtime opencode` explícito fora do shell e o OpenCode ainda não pode entrar em `agentes_obrigatorios` até a aprovação humana do G2-OC.

Objetivo: levar o OpenCode ao mesmo nível de Cursor e Claude Code — 7 papéis nativos, coleta de prova, vínculo do shell do subagente, cobrança do fecho no fim do turno e ativação por trilha — seguindo o mesmo rito do `PLANO-AGENTES-TRILHAS.md` (sondagem → B2 → D → O → G2 → E0). O provedor/modelo **fica fora do repositório**: a empresa já entrega a cada dev as API keys e os modelos disponíveis na configuração global `C:\Users\<usuário>\.config\opencode\opencode.json`. O OpenCode mescla essa configuração global com o `opencode.json` do projeto, então o arquivo do harness não declara `provider`, `model` nem credenciais, para não sobrescrever a configuração da empresa; os agentes omitem `model` e herdam o modelo escolhido na sessão.

Regra do próprio plano: nada é declarado equivalente antes de observado em sessão real (`PLANO-AGENTES-TRILHAS.md` intenção 5).

## Status de execução em 13/10/2026

- **P0-OC -- concluído** (`5ab1d1f`): sondagem registrada; versão observada 1.18.35.
- **B2-OC -- concluído** (`b606ad5`): sete agentes nativos e configuração do projeto; verificação do gerador: 21 `OK`.
- **D-OC -- concluído** (`33143dd`): coleta de provas e roteamento de eventos implementados; suíte Python (247 testes) e Node aprovados.
- **O-OC -- concluído** (`aad290b`): kit local validado. Contrato `74344cd5438841538a4770d8903d55e9` fechado como `DONE`; cópia preparada em `../.execucoes/observacao-opencode-20261013T162540Z`.
- **G2-OC -- pendente**: falta abrir uma sessão real nova e obter o aceite humano. O `PREPARO.json` das cópias de 13/10 registra versão nula por falha do `preparar.py` em achar o `opencode.cmd` do npm no Windows (corrigido; a versão é registrada, não exigida). Os papéis continuam `observado: pendente`.
- **E0-OC -- pendente**: depende da decisão humana após G2. `configuracao/politica.json` permanece sem ativação do runtime OpenCode.

## O que cada dev precisa configurar (uso)

1. OpenCode ≥ 1.18.35 (versão observada no P0-OC), Node, `py -3` + `pip install -r requirements.txt`.
2. Provedor/modelo: nada a configurar. As API keys e os modelos já vêm da empresa em `C:\Users\<usuário>\.config\opencode\opencode.json`. Basta conferir com `opencode models` e escolher o modelo na sessão. O harness não lê nem altera esse arquivo.
3. `configuracao/perfil.local.json` com `databricks_perfil` (já existe o mecanismo; vale igual para OpenCode).
4. Abrir o OpenCode **na raiz do harness** (carrega `AGENTS.md`, `opencode.json`, `.opencode/plugins/` e `.opencode/agents/`).
5. Conferir numa sessão nova: plugin carregado, `opencode agent list` (ou `@` no TUI) mostra os 7 papéis como `subagent` — Tab e `/agents` só listam agentes primários —, e uma negação real da guarda.

## Pacotes

### P0-OC · Sondagem (sem mudar comportamento)
Plugin de sondagem temporário (fora do commit) que só grava os payloads em `.execucoes/sondagem-opencode/`. Fixar, na versão instalada:
- `tool.execute.before/after` para `bash` e `task`: campos de `input` (`sessionID`, `callID`, `tool`) e `output` (`args`, `metadata` — onde vem o exit code; formato de falha/timeout).
- Subagente via `task`: `args.subagent_type`; sessão filha (`event` `session.created` com `info.parentID`); se o shell do filho chega com o `sessionID` do filho; se o `task` after traz o ID da sessão filha; síncrono ou não.
- Fim de turno: `event` `session.idle` (não bloqueia) e se `client.session.prompt` serve como follow-up (equivalente ao `followup_message` do Cursor).
- Injeção de sessão: hook `shell.env` (exportar `ESTEIRA_SESSAO` e `ESTEIRA_RUNTIME=opencode`) ou, na falta, contexto via mensagem.
- Agentes: pasta efetiva (`.opencode/agents/` ou `.opencode/agent/`), frontmatter efetivo (`description`, `mode: subagent`, `permission`/`tools`, `model` omitido = herda) e se o subagente recebe `AGENTS.md`.
- Configuração: se o `opencode.json` do projeto, sem `provider`, se mescla à configuração global da empresa sem perder modelos nem keys, e se o subagente sem `model` herda o modelo da sessão principal.
- Skills: se a ferramenta `skill` do OpenCode descobre `.agents/skills/databricks-*` no subagente.
Saída: seção "Comportamento observado do runtime" em `adaptadores/opencode/README.md` (modelo: `adaptadores/claude_code/README.md`) e linha no painel.

### B2-OC · Sete agentes nativos
- `agentes/roteamento.yaml`: `runtimes.opencode` (`skill_ref`, `instalacao_agentes: .opencode/agents/`) e `metadados.opencode` em cada papel (`instalado: false`, `observado: pendente`).
- `adaptadores/gerar_agentes.py`: `DESTINOS["opencode"]`; `_frontmatter` com `mode: subagent` e permissões por papel derivadas de `FERRAMENTAS_CLAUDE` (sem `edit`/`write` para map, refute e dab); `_corpo` reaproveitando o bloco de skills do Cursor (`.agents/skills/...`) ou a ferramenta `skill`, conforme P0-OC. Mantém marcador de hash e proteção de edição manual.
- `py -3 adaptadores/gerar_agentes.py --instalar opencode`; `--verificar` passa a 21 `OK`.
- `opencode.json` na raiz (versionado, sem provider): `$schema`, `instructions` só se P0 mostrar que `AGENTS.md` não carrega no filho, e `permission.bash` pedindo confirmação para `databricks bundle *` (camada extra; a guarda continua sendo a autoridade).

### D-OC · Coleta de prova
- `adaptadores/opencode/esteira.js`: além do `tool.execute.before` (guarda, já existe), encaminhar a `entrada.py opencode` os eventos `tool.execute.before/after` de `bash` e `task`, `session.created`, `session.idle` e `shell.env`. A ponte continua sem shell, com timeout e fail-closed só no `before` de `bash`; no `session.idle` com fecho inválido, envia o follow-up (limite de 2, como o `loop_limit` do Cursor).
- `adaptadores/opencode/prova.py` (novo), espelhando `adaptadores/claude_code/prova.py`: reutiliza `Provas.antes/depois/abrir_chamada/registrar_chamada/encerrar_chamada/conferir`, `avaliar_operacao`, `observar_resultado_plan`. Vínculo do shell do filho pelo `parentID` da sessão (mais robusto que a janela única do Cursor). `cwd` de `args.workdir` ou prefixo literal (como hoje em `protocolo.py`).
- `adaptadores/executar.py`: rotear eventos opencode que não sejam o `before` de bash para `opencode.prova.tratar` (mesmo padrão dos blocos cursor/claude_code).
- `implementacao/provas.py`: aceitar `opencode` em `politica()` (l. 294–297) e em `registrar_chamada` (l. 456).
- `adaptadores/prova.py`: detectar `opencode` por `ESTEIRA_RUNTIME` (exportado no `shell.env`), mantendo `--runtime` explícito.

### O-OC · Kit de observação
`avaliacao/observacao-opencode/` (`preparar.py`, `roteiro.md`, `validar.py`) copiado de `avaliacao/observacao-claude-code/`, com as fatias de manutenção e docs, negação da guarda no `dab` por `cwd_incorreto` e falso `DONE` recusado.

### G2-OC · Gate (humano)
Sessão real nova; aceite pelos mesmos critérios do G2 do Claude Code. Atualiza `metadados.opencode.*.observado` no roteamento.

### E0-OC · Ativação
`configuracao/politica.json`: `agentes_obrigatorios.opencode = [manutencao, correcao, novo, docs, review]` (por decisão humana, igual aos outros). Rollback: esvaziar a chave.

## Documentação a alinhar (a cada pacote, só o vigente)
`adaptadores/opencode/README.md`, `adaptadores/README.md` (tabela de prova e equivalência), `adaptadores/arquitetura.md` (limites "só Cursor e Claude Code coletam prova"), `README.md` (tabela de runtimes, linha 113), `evidencia/uso.md` (`--runtime opencode` deixa de ser obrigatório), `trilhas/README.md`, `user-harness-esteira-v4.html`; histórico só no painel do `PLANO-AGENTES-TRILHAS.md`.

## Forma de execução
Cada pacote é uma fatia estruturada com contrato via `py -3 adaptadores/prova.py iniciar` e fecho próprio; branch `feat/engenheiro-bruno-lauria`, `git add` explícito, mensagem iniciada pelo ID do pacote. Como `novo`/`manutencao` estão na chave do Claude Code, a implementação aqui é delegada aos papéis (`implement`/`config`/`docs` → `test` → `refute`).

## Verificação
- `py -3 -m unittest discover -s testes -p teste_*.py -v` com novos testes: `testes/teste_adaptador_opencode.py` (eventos sondados como fixtures: shell before/after, task, sessão filha, idle com/sem fecho) e casos em `teste_gerar_agentes.py`/`teste_provas.py` para o runtime `opencode`.
- `node testes/teste_opencode.mjs` estendido para os novos hooks da ponte (encaminhamento, timeout, follow-up, fail-closed).
- `py -3 adaptadores/gerar_agentes.py --verificar` → 21 `OK`.
- `py -3 avaliacao/observacao-opencode/validar.py` valida as provas locais do kit O-OC; a sessão real e o aceite humano permanecem pendentes no G2-OC.

## Riscos
- API de plugins do OpenCode muda entre versões: tudo que depender de campo de evento só entra depois do P0-OC e fica registrado com a versão.
- `session.idle` não bloqueia: o fecho é cobrado por follow-up, não por veto (mesma ressalva do Cursor).
- Provedor por dev: modelos diferentes podem variar no cumprimento dos papéis; a prova observada continua sendo o critério, não o relato.
