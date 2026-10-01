# OpenCode

Visão geral e tabela: [adaptadores](../README.md).

- Configuração: `.opencode/plugins/esteira.js`, gerada com `py -3 adaptadores/gerenciar.py opencode --instalar`. Importa a ponte `esteira.js` desta pasta por caminho relativo, então o clone pode mudar de diretório. O instalador não sobrescreve um plugin diferente.
- `tool.execute.before` da ferramenta `bash`.
- A ponte chama `adaptadores/entrada.py` sem shell, com timeout de 10 s. Lança erro e impede a chamada quando a guarda nega, falha, responde algo inválido ou demora demais.
- O cwd vem de `args.workdir`, ou do prefixo literal. A ponte não altera argumentos.
- Não coleta prova nem retoma fecho.
- Confira: inicie uma sessão nova para carregar o plugin. Teste da ponte: `node testes/teste_opencode.mjs`.
