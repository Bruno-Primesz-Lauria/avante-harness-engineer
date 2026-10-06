# Prova da fatia — uso no Cursor

Manual da prova estruturada: iniciar a fatia, rodar as verificações, fechar. Política de validade e status: [`fecho.md`](fecho.md). Layout dos arquivos: [`layout.md`](layout.md). Requisitos: Python 3.12 ou mais novo e PyYAML (`requirements.txt`).

## Fluxo

1. Abra o harness como raiz. O hook `sessionStart` entrega o identificador da sessão ao agente.
2. No trabalho estruturado, prepare o contrato e inicie a fatia **antes de editar**.
3. Rode pelo chat os comandos exatos do contrato, com o diretório absoluto no campo `cwd` da ferramenta Shell (Cursor 3.17.8; versões anteriores usavam `working_directory`). Sem diretório, a verificação declarada é negada. O `preToolUse` captura o estado; o `postToolUse` registra `exitCode` e saída; o `postToolUseFailure` registra o exit diferente de zero lido do texto `Command failed with exit code N`; negação, timeout ou texto inesperado ficam inconclusivos. Terminal manual não gera esses eventos. Só a ferramenta Shell é observada, e só o comando que casa com um critério do contrato (mesmo texto e mesmo cwd) vira prova.
4. Consulte o estado e feche. Edição relevante depois da prova exige nova verificação.

O runtime informa ao núcleo qual lista de `agentes_obrigatorios` consultar. Os valores aceitos são `claude_code`, `cursor`, `codex` e `opencode`. Passe `--runtime cursor` no Cursor. No Claude Code, `CLAUDE_CODE_SESSION_ID` detecta `claude_code`; `--runtime` explícito prevalece sobre a detecção. Codex e OpenCode não são detectados pelo `prova.py`: informe `--runtime codex` ou `--runtime opencode` em cada comando. Eles ficam fora da chave de agentes obrigatórios; essa seleção permite abrir e fechar uma fatia sem exigir chamadas de agente. Ela não instala coleta de provas de shell: os hooks desses runtimes continuam cobrindo apenas a guarda, então não produzem registros `teste` nem comprovam por si sós critérios de comando. A chave não aceita `codex` ou `opencode`. Com a chave vazia, a ausência de runtime preserva o fluxo atual. Informar `claude_code` não habilita coleta de provas do Claude Code; essa integração depende do adaptador próprio.

```powershell
py -3 adaptadores/prova.py --sessao ID iniciar .execucoes/contrato.yaml
py -3 adaptadores/prova.py --sessao ID estado
py -3 adaptadores/prova.py --sessao ID fechar --resultado "Critérios verificados"
```

Quando a trilha estiver habilitada para o runtime, declare-o em cada comando:

```powershell
py -3 adaptadores/prova.py --runtime cursor --sessao ID iniciar .execucoes/contrato.yaml
py -3 adaptadores/prova.py --runtime cursor --sessao ID fechar --resultado "Critérios verificados"
```

No Codex e no OpenCode, passe o runtime explicitamente em cada operação da fatia:

```powershell
py -3 adaptadores/prova.py --runtime codex --sessao ID iniciar .execucoes/contrato.yaml
py -3 adaptadores/prova.py --runtime codex --sessao ID fechar --resultado "Critérios verificados"
py -3 adaptadores/prova.py --runtime opencode --sessao ID iniciar .execucoes/contrato.yaml
```

- Com `ESTEIRA_SESSAO` no shell, `--sessao` é dispensável. Não copie o ID de outra conversa.
- Cada comando imprime JSON. Erro sai com código 2 e mensagem `[prova] ...` no stderr.
- `iniciar` recusa abrir outra fatia se a anterior da sessão não foi fechada.
- `fechar --status` aceita `DONE` (padrão), `REVIEW`, `DECIDE`, `BLOCKED` e `FAILED`. `DONE` e `REVIEW` exigem prova atual para todo critério obrigatório e nenhuma chamada pendente; os demais registram o impedimento, por exemplo `fechar --status BLOCKED --resultado "Resultado externo não confirmado"`. Isso não transforma prova incompleta em aprovação.
- Rodar de novo um comando do contrato abre nova tentativa e reabre a fatia; o fecho anterior fica preservado.
- Com uma verificação pendente (sem resultado registrado), outra chamada é recusada até conferir o resultado.

### Inspeção, revisão e triagem

Três subcomandos leem um YAML (`.execucoes/`) e chamam o núcleo da fatia ativa:

```powershell
py -3 adaptadores/prova.py --sessao ID inspecionar .execucoes/inspecao.yaml
py -3 adaptadores/prova.py --sessao ID revisar .execucoes/revisao.yaml
py -3 adaptadores/prova.py --sessao ID triar .execucoes/triagem.yaml
```

- `inspecionar`: `criterio_id`, `checagens` (`id` e `resultado`: `pass`, `fail` ou `inconclusivo`) e, opcional, `produtor`. Com a chave vazia, critério de inspeção fecha `DONE` sem comando. Com a trilha ativada, as chamadas previstas continuam exigidas.
- `revisar`: a forma `ataque` (intenção, aceite, baseline, provas, veredito, tentativas, achados, cobertura) com `agente_id` opcional, protegido pelo hash do evento. Com a trilha ativada, o ID precisa casar com uma chamada `refute` concluída; sem esse vínculo o fecho aponta `revisao:fora_do_refute`. Cada chamada `refute` concluída precisa da sua própria revisão registrada, com o `agente_id` dela; sem isso o fecho aponta `revisao:sem_registro:<chamada>`. Chamar o refute de novo não descarta o que o anterior achou: achado de revisão anterior precisa de triagem (`achado:<id>:sem_triagem`). Com a chave vazia, o vínculo não é exigido.
- `triar`: a forma `triagem` (`revisao_ref`, `achado_id`, `decisao`, `responsavel`, e `evidencia_resolucao_ref` ou `motivo_descarte` conforme a decisão).

### Superfície por papel

Com a trilha ativada e `config`, `implement` ou `docs` no plano, o núcleo retrata a superfície e os caminhos de verificação. O adaptador abre uma janela no início de cada subagente previsto: `subagentStart` no Cursor e `PreToolUse(Agent)` no Claude Code. O núcleo fecha a janela ao registrar a chamada, ou ao descartá-la quando a chamada falha. Pendências no fecho:

- `superficie_violada:<papel>:<arquivo>`: config alterou arquivo que não é YAML, implement alterou arquivo que não é notebook, Python ou SQL, docs alterou arquivo que não é `.md`, `.rst` ou `.txt`, ou o arquivo está fora da `superficie` do contrato.
- `edicao_fora_do_papel:<arquivo>`: alteração fora de qualquer janela, como uma edição do principal. Abrir uma janela depois não transfere a autoria.
- `superficie_inconclusiva:<chamada>`: alteração com janelas sobrepostas, ou escrita registrada sem início observado.
- `chamada_aberta:<chamada>`: subagente sem fim observado.

As pendências de violação ficam na fatia; para recomeçar, feche com `BLOCKED` e abra uma fatia nova. Edição dos papéis `test`, `dab` e `refute` dentro da própria janela não é julgada aqui. Com a chave vazia, nada disso vale.

Chamada de subagente depois do `DONE` entra na fatia ainda ativa e anula o fecho, de propósito: trabalho novo pede fecho novo. Repetir um papel conta como retorno e reabre as etapas seguintes do plano, com o mesmo ID de chamada prevista. Para trabalho fora da fatia, feche-a e use outra sessão, ou rode antes do `iniciar`.

### Diagnóstico, ambiente e paridade

Três subcomandos registram as formas `diagnostico`, `sandbox` e `paridade` (3.2, aditivas). Leem um YAML, validam a forma e gravam o registro na tentativa; o agente não escreve registro à mão. O que o núcleo observa não é declarado: se vier no YAML, precisa coincidir, senão o registro é recusado (`Campo X diverge do observado`).

```powershell
py -3 adaptadores/prova.py --sessao ID diagnosticar .execucoes/diagnostico.yaml
py -3 adaptadores/prova.py --sessao ID registrar-sandbox .execucoes/sandbox.yaml
py -3 adaptadores/prova.py --sessao ID registrar-paridade .execucoes/paridade.yaml
```

- `diagnosticar`: `sintoma`, `hipotese_causa`, `base` (`direct`, `derived` ou `reported`), `evidencia_ref` (dentro da fatia: log de verificação, `baseline.json` ou `contrato.yaml`), `criterio_reproducao` (ID de um critério de teste do contrato) e `proximo_passo`; `produtor` opcional (`coordenador`, padrão, ou `map`). Na correção com a trilha ativada, o fecho aponta `diagnostico:ausente` sem um diagnóstico íntegro. Se config ou implement abrir a janela antes dele, a fatia guarda `escrita_sem_diagnostico:<papel>:<chamada>`: registrar depois não desfaz a escrita, e o caminho é fechar com `BLOCKED` e abrir fatia nova, como nas pendências de superfície. Fora da chave, nada disso vale.
- `registrar-sandbox`: `criterio_id` (critério `ambiente` com `autorizacao_ref`; o comando dele já precisa ter rodado), `plan_ref` (recibo de plan, relativo a `registros_raiz`, por exemplo `plans/<id>.json`; só em deploy e run), `identidade`, `destinos_resolvidos` (lista), `coordenacao` e `agente_id` opcional. O núcleo deriva operação, target, perfil e seleção do comando do critério, e `cwd`, `resultado` e `teste_ref` do registro `teste` atual; calcula `plan_estado_compativel` relendo o recibo (target, seleção, perfil e hashes dos arquivos do plan). O comando do critério precisa ser `databricks bundle validate`, `plan`, `deploy` ou `run` literal. Critério `ambiente` com outro comando (por exemplo, um script local) não leva `sandbox`: fecha pelo teste e pela autorização, como antes, e `registrar-sandbox` o recusa.
- Campo sem observação integrada vale `nao_verificado` (em `destinos_resolvidos`, a lista `[nao_verificado]`). Em `deploy`, `identidade` e `destinos_resolvidos` `nao_verificado` não aprovam o critério; em `run`, `coordenacao` também. `validate` e `plan` não têm efeito externo e dispensam esses campos. Hoje a CLI não observa identidade nem destinos, então um deploy contratado fica em `sandbox_nao_verificado:<campo>:<critério>` até essa integração existir. Deploy ou run `pass` exige `plan_ref` e plan compatível.
- `registrar-paridade`: `criterio_id` (critério `paridade`), `recorte`, `insumos` (`nome` e `identificador`), `contas` (`id`, `descricao`, `valor_origem`, `valor_destino` e `diferenca`, em decimal, com a diferença igual a origem menos destino), `divergencias` (`id`, `estado` `explicada` ou `pendente`; a explicada leva `explicacao` e `evidencia_ref` dentro da fatia) e `agente_id` opcional. O `resultado` é do núcleo: exit 0 com divergência pendente grava `fail`, e diferença nas contas sem divergência listada é recusada. Quem registra uma divergência `pendente` fecha a paridade em `fail`.
- Vínculo: o registro guarda `teste_ref` e o hash do registro `teste` do comando, e o evento usa o manifesto desse teste, então rodar o comando de novo ou editar os caminhos de verificação o torna obsoleto. Com a trilha ativada, o `agente_id` precisa casar com uma chamada concluída de `dab` (sandbox) ou `test` (paridade) quando o papel está no plano.

Pendências no fecho, por critério `ambiente` ou `paridade` provado pelo teste: `sandbox_ausente` e `paridade_ausente` (só com a trilha ativada), `<forma>_invalido` (registro alterado), `<forma>_obsoleto` (o comando rodou de novo), `<forma>_reprovado`, `sandbox_fora_do_dab` e `paridade_fora_do_test`, `sandbox_nao_verificado:<campo>` e `sandbox_plan_obsoleto`. Registro existente reprovado, inválido ou obsoleto bloqueia também sem a chave; a ausência dele só bloqueia com a trilha ativada.

Pergunta simples não usa contrato. Só a fatia iniciada entra neste fluxo.

## Contrato de entrada

Exemplo para verificar o próprio harness. O agente ajusta caminhos, comando e resultado esperado à tarefa.

```yaml
objetivo: Verificar a mudança do harness
termino_fatia: Correção validada pelos testes locais
trilha: correcao
superficie: [implementacao, adaptadores, formas/catalogo.yaml]
artefatos_raiz: .execucoes/provas
fora: [deploy, run]
fontes: [AGENTS.md, evidencia/uso.md]
prazo: null
aceite:
  - id: regressao
    tipo: teste
    obrigatorio: true
    esperado: A suíte termina com exit code zero
    verificacao:
      comando: py -3 -m unittest discover -s testes -p teste_*.py -v
      cwd: .
      caminhos: [implementacao, adaptadores, formas/catalogo.yaml, testes]
orcamento:
  ciclos_correcao_max: 3
  ciclos_sem_progresso_max: 2
  repeticoes_operacao_max: 2
responsaveis:
  coordenador: agente
  executor: agente
  verificador: suite_local
```

Regras do validador:

- O arquivo contém os dados do contrato. O núcleo acrescenta o envelope 3.1 e rejeita campo extra, tipo inválido, identificador de aceite repetido e contrato sem critério obrigatório.
- `artefatos_raiz` deve ser `.execucoes/provas`.
- `fontes` é lista de referências. `prazo` é data com fuso ou `null`. O núcleo não agenda tarefas nem concede permissão.
- Todo critério leva `verificacao` com `comando`, `cwd` e `caminhos` (ao menos um). Cada par comando e cwd é único.
- Todo item de `superficie` precisa estar coberto por algum caminho de `verificacao`.
- Caminhos usam `/` e são relativos à raiz do harness. `cwd: .` é a raiz. Aceitam arquivo e diretório; diretório inclui arquivos novos. Arquivo ainda inexistente fica com hash `null` até ser criado. Link simbólico é recusado.
- Escolha um comando cujo exit code decida o esperado. Comando que só imprime uma afirmação não prova o critério.

## Registros

Ficam em `.execucoes/provas/<execucao_id>/principal/`, locais e ignorados pelo Git. Arquivos `.yaml` usam JSON, que é um subconjunto de YAML.

| Registro | Conteúdo |
|---|---|
| `baseline.json` | Versão 1, instante e hashes anteriores da superfície e das dependências, mesmo sem Git e com trabalho prévio. |
| `contrato.yaml` | Evento 3.1 imutável com contrato e critérios. |
| `tentativas/NNN/manifesto.json` | Versão 1, instante, dependências e hashes anteriores, versão do Cursor informada, hash do contrato e hashes do código e da configuração do harness. |
| `tentativas/NNN/eventos/*.yaml` | Eventos 3.1 `guarda` e `teste`, com ID de chamada e referências. |
| `tentativas/NNN/logs/resultado.txt` | Saída observada, sem padrões comuns de segredo (token, senha, bearer, `dapi...`). Não rode comando que imprima credencial. |
| `fechos/*.yaml` | Eventos 3.1 `brief`. Um fecho novo preserva os anteriores. |
| `estado.json` | Versão 1, sessão, execução, revisão, tentativa, chamada pendente, IDs de chamada já usados, referências e hashes das provas, do contrato e do último fecho. |

Um índice por sessão (`.execucoes/sessoes/`) aponta a fatia ativa. Escrita exclusiva preserva os eventos; lock e revisão protegem a troca atômica do estado.

Lock deixado por processo interrompido: confira que o processo terminou e remova **aquele** lock. Não há expiração automática, porque ela permitiria duas gravações concorrentes.

## Validade

Os hashes são comparados antes e depois da chamada e de novo ao fechar. Mudança em código, dependência, log, manifesto ou configuração relevante invalida a prova. Nota fora das dependências não força reteste. `.git`, `.venv`, `.execucoes`, `__pycache__` e `.pytest_cache` não entram no retrato.

Sem `exitCode` inteiro ou sem eventos, não há prova de sucesso. Não complete campo à mão para obter `DONE`. Com resultado externo incerto, confirme o ID da operação antes de repetir qualquer efeito.

## Plan e deploy

Um `plan` declarado como verificação gera recibo só após resultado observado com exit 0 e estado preservado. O pré-hook não grava sucesso. O recibo sozinho não libera deploy: ele é pré-condição. O deploy só passa em `sandbox` com `deploy_sandbox_autorizado` na política; identidade autenticada, destinos e cobertura completa do plan não estão integrados. Não implementado: `run`. Com a trilha ativada, o critério `ambiente` fecha só com o registro `sandbox` (seção acima), e o que não é observado fica `nao_verificado`.

## Fecho e `stop`

O fecho persistido é recusado quando a prova não vale. No evento `stop`, o Cursor recebe no máximo duas mensagens para corrigir a fatia ativa. O `stop` não oculta resposta já exibida nem bloqueia o fim do chat. Siga o `AGENTS.md`: não escreva `DONE` se `fechar` recusar.

## Limites

- Os registros são isolados entre sessões, e há detecção de mudança durante a verificação.
- Não há bloqueio de edição dos arquivos de produto entre agentes. A autoria é atribuída por janela de chamada, só com a trilha ativada e só na superfície e nos caminhos de verificação; arquivo fora deles não é retratado.
- Edição seguida de reversão entre os dois retratos não é detectada.
- Quem pode editar a pasta de registros pode adulterá-la. Hashes não assinam autoria.

Fontes oficiais: [hooks do Cursor](https://cursor.com/docs/hooks) (eventos e limite de `stop`) e [regras do Cursor](https://cursor.com/docs/rules) (carregamento de `AGENTS.md`).
