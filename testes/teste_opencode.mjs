import assert from "node:assert/strict";
import { criar_ponte, executar_assincrono } from "../adaptadores/opencode/esteira.js";

const comandos = [];
let resposta = { decisao: "permitir" };
let falhaExecucao = null;
let lancarExecucao = false;
const executar = (exe, args, opcoes) => {
  assert.equal(opcoes.shell, false);
  assert.equal(opcoes.windowsHide, true);
  assert.equal(opcoes.timeout, 10000);
  comandos.push(JSON.parse(opcoes.input));
  if (lancarExecucao) throw new Error("spawnSync falhou");
  return falhaExecucao ?? { status: 0, stdout: JSON.stringify(resposta) };
};
const prompts = [];
const client = { session: { prompt: (valor) => { prompts.push(valor); return Promise.resolve({ data: {} }); } } };
const plugin = await criar_ponte("python", "executar.py", null, executar)({ client });

const bashArgs = { command: "databricks bundle validate", workdir: "D:/bundle" };
const bashOutput = { args: bashArgs };
await plugin["tool.execute.before"](
  { tool: "bash", sessionID: "ses-main", callID: "call-bash-before" }, bashOutput,
);
assert.deepEqual(comandos.at(-1), {
  evento: "tool.execute.before",
  input: { tool: "bash", sessionID: "ses-main", callID: "call-bash-before" },
  args: bashArgs,
});
await plugin["tool.execute.before"]({ tool: "read", sessionID: "ses-main" }, {});
assert.equal(comandos.length, 1);

const taskArgs = { subagent_type: "test", description: "Executar teste", prompt: "Valide o critério" };
await plugin["tool.execute.before"](
  { tool: "task", sessionID: "ses-main", callID: "call-task" }, { args: taskArgs },
);
assert.deepEqual(comandos.at(-1), {
  evento: "tool.execute.before",
  input: { tool: "task", sessionID: "ses-main", callID: "call-task" },
  args: taskArgs,
});

await plugin["tool.execute.after"](
  { tool: "bash", sessionID: "ses-child", callID: "call-bash-after", args: bashArgs },
  { title: "Comando", output: "ok", metadata: { exit: 0, output: "ok", truncated: false } },
);
assert.deepEqual(comandos.at(-1), {
  evento: "tool.execute.after",
  input: { tool: "bash", sessionID: "ses-child", callID: "call-bash-after", args: bashArgs },
  output: { title: "Comando", output: "ok", metadata: { exit: 0, output: "ok", truncated: false } },
});
await plugin["tool.execute.after"](
  { tool: "task", sessionID: "ses-main", callID: "call-task", args: taskArgs },
  { title: "Concluído", output: "feito", metadata: { parentSessionId: "ses-main", sessionId: "ses-child" } },
);
assert.equal(comandos.at(-1).input.callID, "call-task");
assert.equal(comandos.at(-1).output.metadata.sessionId, "ses-child");

const shellEnv = { env: {} };
await plugin["shell.env"]({ cwd: "D:/harness", sessionID: "ses-child", callID: "call-env" }, shellEnv);
assert.deepEqual(shellEnv.env, { ESTEIRA_SESSAO: "ses-child", ESTEIRA_RUNTIME: "opencode" });
assert.equal(comandos.at(-1).evento, "shell.env");

await plugin.event({ event: { type: "session.created", properties: { info: { id: "ses-child", parentID: "ses-main" } } } });
assert.equal(comandos.at(-1).evento, "session.created");

resposta = { followup_message: "Feche a fatia ativa." };
const idle = { type: "session.idle", properties: { sessionID: "ses-main" } };
await plugin.event({ event: idle });
await plugin.event({ event: idle });
await plugin.event({ event: idle });
assert.equal(prompts.length, 2);
assert.equal(prompts[0].path.id, "ses-main");
assert.equal(prompts[0].body.parts[0].text, "Feche a fatia ativa.");

resposta = {};
await plugin.event({ event: idle });
resposta = { followup_message: "Nova fatia incompleta." };
await plugin.event({ event: idle });
assert.equal(prompts.length, 3, "fecho válido deve reiniciar o limite por sessão");

resposta = { decisao: "negar", motivo: "bundle fora do escopo" };
await assert.rejects(() => plugin["tool.execute.before"](
  { tool: "bash", sessionID: "ses-main", callID: "call-denied" }, bashOutput,
), /bundle fora do escopo/);
const erroSpawn = Object.assign(new Error("spawnSync py EINVAL"), { code: "EINVAL" });
for (const [resultado, detalhe] of [
  [{ status: 2, stdout: "", stderr: "Traceback: falhou\n" }, /status=2.*stderr=Traceback: falhou/],
  [{ status: null, signal: "SIGTERM", error: erroSpawn }, /erro=EINVAL.*status=null.*sinal=SIGTERM/],
  [{ status: 0, stdout: "nao-json" }, /Resposta inválida/],
  [{ status: 0, stdout: JSON.stringify({ decisao: "desconhecida" }) }, /Decisão desconhecida/],
]) {
  falhaExecucao = resultado;
  await assert.rejects(() => plugin["tool.execute.before"](
    { tool: "bash", sessionID: "ses-main", callID: "call-failed" }, bashOutput,
  ), detalhe);
}

falhaExecucao = { status: 2, stdout: "" };
await assert.doesNotReject(() => plugin["tool.execute.after"](
  { tool: "bash", sessionID: "ses-child", callID: "call-after-fails", args: bashArgs }, {},
));
falhaExecucao = null;
lancarExecucao = true;
await assert.doesNotReject(() => plugin["tool.execute.before"](
  { tool: "task", sessionID: "ses-main", callID: "call-task-best-effort" }, { args: taskArgs },
));
await assert.doesNotReject(() => plugin["shell.env"](
  { sessionID: "ses-main" }, { env: {} },
));
await assert.doesNotReject(() => plugin.event({ event: idle }));
await assert.rejects(() => plugin["tool.execute.before"](
  { tool: "bash", sessionID: "ses-main", callID: "call-before-throws" }, bashOutput,
), /lançou=spawnSync falhou.*ms=\d+/);
lancarExecucao = false;
assert.deepEqual(bashOutput, { args: bashArgs }, "a ponte não pode alterar os argumentos da ferramenta");
const opcoesReais = { input: "{\"eco\":\"ç\"}", encoding: "utf8", timeout: 10000, maxBuffer: 1024 * 1024, windowsHide: true, shell: false };
const eco = await executar_assincrono(process.execPath, ["-e",
  "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{process.stdout.write(d);process.stderr.write('aviso');process.exit(3)})"],
  opcoesReais);
assert.deepEqual([eco.status, eco.stdout, eco.stderr, eco.error], [3, "{\"eco\":\"ç\"}", "aviso", undefined]);
const lento = await executar_assincrono(process.execPath, ["-e", "setTimeout(()=>{}, 5000)"], { ...opcoesReais, timeout: 200 });
assert.equal(lento.error?.code, "ETIMEDOUT");
assert.equal(lento.status, null);
const ausente = await executar_assincrono("executavel-que-nao-existe-esteira", [], opcoesReais);
assert.equal(ausente.status, null);
assert.ok(ausente.error, "falha ao iniciar deve virar erro, não exceção");
console.log("OpenCode: eventos, ambiente, follow-up limitado e fail-closed somente antes de bash passaram.");
