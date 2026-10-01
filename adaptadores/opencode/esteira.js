// Ponte nativa OpenCode. Executa somente a guarda, nunca a operacao solicitada.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export function criar_ponte(python, script, politica, executar = spawnSync, prefixo = []) {
  return async () => ({
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return;
      const args = [...prefixo, script, "opencode", ...(politica ? [politica] : [])];
      const resultado = executar(python, args, {
        input: JSON.stringify({ evento: "tool.execute.before", tool: input.tool, args: output.args }),
        encoding: "utf8", timeout: 10000, maxBuffer: 1024 * 1024,
        windowsHide: true, shell: false,
      });
      if (resultado.error || resultado.status !== 0) {
        throw new Error("[cwd-bundle] Guarda indisponivel; a chamada nao rodou. Peca ao usuario para conferir a instalacao.");
      }
      let resposta;
      try { resposta = JSON.parse(resultado.stdout); }
      catch { throw new Error("[cwd-bundle] Resposta invalida da guarda; a chamada nao rodou. Peca ao usuario para conferir a instalacao."); }
      if (!resposta || !["permitir", "negar", "nao_aplica"].includes(resposta.decisao)) {
        throw new Error("[cwd-bundle] Decisao desconhecida da guarda; a chamada nao rodou. Peca ao usuario para conferir a instalacao.");
      }
      if (resposta.decisao === "negar") {
        throw new Error(resposta.motivo || "[cwd-bundle] Chamada negada pela guarda.");
      }
    },
  });
}

export function criar_ponte_portatil() {
  const windows = process.platform === "win32";
  const script = fileURLToPath(new URL("../entrada.py", import.meta.url));
  return criar_ponte(windows ? "py" : "python3", script, null, spawnSync, windows ? ["-3"] : []);
}
