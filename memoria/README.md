# Memória do time

Conhecimento verificado do harness, versionado no Git e revisado por PR. Uma nota registra uma decisão, um aprendizado ou um padrão, com fonte e data de conferência. Plano completo e fases seguintes: [`plano_memoria_harness.md`](../plano_memoria_harness.md).

## Estatuto

A nota é contexto `advisory`, como [`nucleo/contexto-avante.md`](../nucleo/contexto-avante.md): orienta a investigação e nunca vale como regra, autorização ou prova. Na ordem de fontes de [`nucleo/modus-operandi.md`](../nucleo/modus-operandi.md#fontes), fica no item 4, abaixo das permissões do runtime, do pedido, do `AGENTS.md` do escopo e do código vivo.

- Quando a nota diverge da fonte, vale a fonte. Corrija ou substitua a nota.
- Procedimento que o agente deve seguir sempre vai para o arquivo operacional (trilha, guarda, skill ou `AGENTS.md`) pela trilha [`destilar`](../trilhas/destilar.md). A nota aponta para ele.
- Nota que só repete um documento existente não entra.
- A memória nativa dos runtimes (por exemplo, a auto memory do Claude Code em `~/.claude/projects/`) é pessoal. Ela não substitui nem alimenta esta pasta.
- A memória do produto fica no repositório dele, quando for adotada.

## Estrutura

```text
memoria/
  README.md          # esta política
  indice.md          # assuntos → notas ativas
  modelos/nota.md    # modelo; fora do índice e da validação de notas
  decisoes/          # decisões e seu motivo
  aprendizados/      # causas, correções e limites verificados
  padroes/           # procedimentos recorrentes com fontes
```

Crie a pasta de um tipo só quando houver nota real para ela. O nome do arquivo é o `id` da nota.

## Metadados

Frontmatter YAML simples no topo da nota. Copie [`modelos/nota.md`](modelos/nota.md).

| Campo | Regra |
|---|---|
| `schema_versao` | `1`. |
| `id` | Igual ao nome do arquivo sem `.md`; minúsculas, dígitos e hífen. Único e nunca reutilizado. |
| `tipo` | `decisao`, `aprendizado` ou `padrao`, coerente com a pasta. |
| `status` | `ativo` ou `substituido`. Proposta não é status: é o que ainda não está na `main`. |
| `tags` | Lista curta de assuntos. |
| `caminhos` | Arquivos ou pastas relacionados, relativos à raiz do harness. O prefixo `prj-avante-analytics-adb/` indica o produto. |
| `fontes` | Caminho relativo à raiz, hash de commit ou URL. Ao menos uma acessível a partir de outro clone; `.execucoes/` sozinha não basta. Hash só com dígitos vai entre aspas (`'7014887'`); sem elas, o YAML o lê como número. |
| `verificado_em` | Data `AAAA-MM-DD` da última conferência. |
| `substituida_por` | `id` da sucessora, só em nota `substituido`. |
| `modulo`, `objeto`, `etapa` | Opcionais, para chavear a nota por objeto da migração (memória do produto): módulo SAP, objeto (`cliente`, `grupo_economico`) e etapa `'01'` a `'08'` entre aspas, ou lista delas. |

Links entre notas e para o repositório são Markdown relativos. Wikilink `[[...]]` e caminho absoluto são recusados.

## Consulta

- **Caminho simples:** busque em `memoria/` só quando o pedido tocar assunto ou caminho com nota.
- **Caminho estruturado:** leia o [`indice.md`](indice.md) na entrada e abra as notas relacionadas antes de fechar o contrato. As notas usadas entram em `fontes`.
- Confira escopo, fonte e atualidade antes de aplicar uma nota. Sem nota útil, siga pelo código e pelas fontes atuais.
- Nota diferente de `origin/main` (`git diff --name-only origin/main -- memoria/`) ou não rastreada (`git status --short -- memoria/`) é proposta. Cite-a como proposta.
- Quando uma nota influenciar a decisão, cite o `id` e a fonte conferida: no relato, no caminho simples; em `fontes` do contrato, no estruturado.
- **Claude Code:** o hook `SessionStart` entrega os itens do índice, no máximo 40 linhas e 4000 caracteres. O corpo das notas não é carregado; abra a nota só quando o assunto aparecer.

## Contribuição

1. No fecho, avalie se houve descoberta reutilizável: causa de falha verificada, procedimento recorrente, decisão relevante ou limite de ferramenta observado. Tarefa comum não gera nota nem pergunta.
2. Sinalize o candidato no fecho, com assunto e fontes.
3. Grave a nota só onde a escrita está autorizada: no caminho simples, quando o pedido inclui registrá-la; no estruturado, quando `memoria/` está na superfície do contrato. Fora disso, a nota vira fatia própria.
4. Procure nota existente antes de criar outra. Atualize-a quando o assunto já estiver coberto.
5. Acrescente a nota ativa ao [`indice.md`](indice.md), rode `validar` e abra o PR. Nota em branch ou só no clone local não é conhecimento do time.
6. Depois do merge, os demais engenheiros recebem a nota ao atualizar seus clones.

Mudança de entendimento usa substituição explícita: a nota antiga passa a `substituido`, com `substituida_por`, e sai do índice. O histórico fica no Git.

```bash
python3 adaptadores/memoria.py validar
```

No Windows, `py -3 adaptadores/memoria.py validar`. O comando confere campos e valores, `id` igual ao nome, `tipo` coerente com a pasta, sucessora existente, nota ativa no índice, links relativos e fontes locais resolvidos. Ele não confere a precisão do conteúdo; isso é da revisão.

## Revisão

PRs que tocam `memoria/` são aprovados pelo mesmo revisor dos PRs do harness. Não há CI: o autor roda `validar` e as suítes do `AGENTS.md` antes do PR, e o revisor confere a saída. O revisor avalia conteúdo, fonte, utilidade, duplicação e a fronteira entre nota e instrução. A nota chega à `main` com `status: ativo`.

## Obsidian (opcional)

Abra só `memoria/` como vault. A pasta `memoria/.obsidian/` é ignorada pelo Git. Em *Files and links*, desligue *Use `[[Wikilinks]]`* e use *New link format* = *Relative path to file*. Nada depende do Obsidian.

## Limites desta versão

O índice é mantido à mão. Ainda não existem busca, índice gerado nem aviso de revalidação quando um arquivo de `caminhos` muda (Fase 2 do plano). A integração automática existe só no `SessionStart` do Claude Code; os outros runtimes recebem a orientação pelo `AGENTS.md`.
