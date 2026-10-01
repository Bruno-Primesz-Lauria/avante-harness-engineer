import assert from "node:assert/strict";
import { criar_ponte } from "../adaptadores/opencode/esteira.js";

let chamadas = 0;
let retorno = { status: 0, stdout: '{"decisao":"permitir"}' };
const executar = (exe, args, opcoes) => {
  chamadas++;
  assert.equal(opcoes.shell, false);
  assert.equal(opcoes.windowsHide, true);
  assert.equal(JSON.parse(opcoes.input).args.command, "databricks bundle validate");
  return retorno;
};
const plugin = await criar_ponte("python", "executar.py", null, executar)();
const hook = plugin["tool.execute.before"];
const input = { tool: "bash" };
const output = { args: { command: "databricks bundle validate" } };
await hook(input, output);
assert.equal(chamadas, 1);
await hook({ tool: "read" }, {});
assert.equal(chamadas, 1);
for (const falha of [
  { status: 0, stdout: '{"decisao":"negar","motivo":"bundle errado"}' },
  { status: 2, stdout: "" }, { status: null, error: new Error("timeout") },
  { status: 0, stdout: "nao-json" }, { status: 0, stdout: '{"decisao":"desconhecida"}' },
]) {
  retorno = falha;
  await assert.rejects(() => hook(input, output));
}
assert.deepEqual(output, { args: { command: "databricks bundle validate" } });
console.log("OpenCode: continuacao, negações, falhas e preservacao de argumentos passaram.");
