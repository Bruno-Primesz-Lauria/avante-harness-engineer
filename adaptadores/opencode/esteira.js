// Ponte nativa OpenCode. Somente before de bash pode impedir a ferramenta.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const TEMPO_LIMITE = 10000;

// Diagnóstico curto: sem ele, a falha do subprocesso no runtime real fica indistinguível.
function indisponivel(inicio, detalhe) {
  return new Error("[cwd-bundle] Guarda ou prova indisponível; a chamada não rodou. Confira a instalação. " +
    `(${detalhe}; ms=${Date.now() - inicio})`);
}

function criar_chamada(python, script, politica, executar, prefixo) {
  const args = [...prefixo, script, "opencode", ...(politica ? [politica] : [])];
  return (evento, falhaFechada = false) => {
    let resultado;
    const inicio = Date.now();
    try {
      resultado = executar(python, args, {
        input: JSON.stringify(evento), encoding: "utf8", timeout: TEMPO_LIMITE,
        maxBuffer: 1024 * 1024, windowsHide: true, shell: false,
      });
    } catch (erro) {
      if (falhaFechada) throw indisponivel(inicio, `lançou=${erro?.code ?? erro?.message ?? erro}`);
      return null;
    }
    if (resultado.error || resultado.status !== 0) {
      if (falhaFechada) {
        const stderr = String(resultado.stderr ?? "").trim().slice(0, 300);
        throw indisponivel(inicio, `erro=${resultado.error?.code ?? resultado.error?.message ?? "nenhum"}; ` +
          `status=${resultado.status}; sinal=${resultado.signal ?? "nenhum"}; stderr=${stderr}`);
      }
      return null;
    }
    try {
      return JSON.parse(resultado.stdout);
    } catch {
      if (falhaFechada) {
        throw new Error("[cwd-bundle] Resposta inválida da guarda; a chamada não rodou. Confira a instalação.");
      }
      return null;
    }
  };
}

export function criar_ponte(python, script, politica, executar = spawnSync, prefixo = []) {
  const chamar = criar_chamada(python, script, politica, executar, prefixo);
  const tentativasFecho = new Map();
  const followupEmCurso = new Set();

  return async ({ client } = {}) => ({
    "tool.execute.before": async (input, output) => {
      if (input.tool === "bash") {
        const resposta = chamar({
          evento: "tool.execute.before",
          input: { tool: input.tool, sessionID: input.sessionID, callID: input.callID },
          args: output.args,
        }, true);
        if (!resposta || !["permitir", "nao_aplica"].includes(resposta.decisao)) {
          throw new Error(resposta?.motivo || "[prova] Decisão desconhecida; a chamada não rodou.");
        }
        return;
      }
      if (input.tool === "task") {
        chamar({
          evento: "tool.execute.before",
          input: { tool: input.tool, sessionID: input.sessionID, callID: input.callID },
          args: output.args,
        });
      }
    },

    "tool.execute.after": async (input, output) => {
      if (!["bash", "task"].includes(input.tool)) return;
      chamar({
        evento: "tool.execute.after",
        input: {
          tool: input.tool, sessionID: input.sessionID, callID: input.callID,
          args: input.args ?? output.args,
        },
        output: {
          title: output.title, output: output.output, metadata: output.metadata,
        },
      });
    },

    "shell.env": async (input, output) => {
      if (!output.env || typeof output.env !== "object") output.env = {};
      if (typeof input.sessionID === "string") output.env.ESTEIRA_SESSAO = input.sessionID;
      output.env.ESTEIRA_RUNTIME = "opencode";
      const resposta = chamar({
        evento: "shell.env",
        input: { cwd: input.cwd, sessionID: input.sessionID, callID: input.callID },
      });
      if (resposta?.env && typeof resposta.env === "object") Object.assign(output.env, resposta.env);
    },

    event: async ({ event }) => {
      if (!["session.created", "session.idle"].includes(event?.type)) return;
      const sid = event?.properties?.sessionID ?? event?.properties?.info?.id;
      const resposta = chamar({ evento: event.type, properties: event.properties ?? {} });
      if (event.type !== "session.idle" || typeof sid !== "string" || !sid) return;
      if (typeof resposta?.followup_message !== "string" || !resposta.followup_message) {
        tentativasFecho.delete(sid);
        return;
      }
      const usadas = tentativasFecho.get(sid) ?? 0;
      if (usadas >= 2 || followupEmCurso.has(sid) || typeof client?.session?.prompt !== "function") return;
      tentativasFecho.set(sid, usadas + 1);
      followupEmCurso.add(sid);
      try {
        Promise.resolve(client.session.prompt({
          path: { id: sid },
          body: { parts: [{ type: "text", text: resposta.followup_message }] },
        })).catch(() => {}).finally(() => followupEmCurso.delete(sid));
      } catch {
        followupEmCurso.delete(sid);
      }
    },
  });
}

export function criar_ponte_portatil() {
  const windows = process.platform === "win32";
  const script = fileURLToPath(new URL("../entrada.py", import.meta.url));
  return criar_ponte(windows ? "py" : "python3", script, null, spawnSync, windows ? ["-3"] : []);
}
