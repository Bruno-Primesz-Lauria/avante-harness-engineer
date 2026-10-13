"""Eventos OpenCode observados e vínculo de provas entre sessão principal e filha."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from opencode.prova import tratar
from provas import Provas, ler


COMANDO = 'py -3 -c "print(1)"'


class AdaptadorOpenCodeTestes(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory(dir=RAIZ / "testes")
        self.raiz = Path(self.temporario.name)
        self.addCleanup(self.temporario.cleanup)
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("# base\n", encoding="utf-8")
        (self.raiz / "bundle").mkdir()
        (self.raiz / "configuracao").mkdir()
        self.politica = {
            "bundle_local": str(self.raiz / "bundle"),
            "bundle_nome": "saneamento_migracao",
            "registros_raiz": str(self.raiz / ".execucoes"),
            "agentes_obrigatorios": {
                "claude_code": [], "cursor": [], "opencode": ["manutencao"],
            },
        }
        (self.raiz / "configuracao/politica.json").write_text(
            json.dumps(self.politica), encoding="utf-8"
        )
        self.sessao = "ses-pai-opencode"
        self.provas = Provas(self.raiz, self.politica["registros_raiz"], self.sessao, runtime="opencode")
        self.contrato = {
            "objetivo": "Verificar a chamada OpenCode",
            "termino_fatia": "Prova de comando e chamadas observadas",
            "trilha": "manutencao",
            "superficie": ["src/a.py"],
            "artefatos_raiz": ".execucoes/provas",
            "fora": [],
            "fontes": ["src/a.py"],
            "prazo": None,
            "aceite": [{
                "id": "teste_local",
                "tipo": "teste",
                "obrigatorio": True,
                "esperado": "O processo termina com exit code zero",
                "verificacao": {"comando": COMANDO, "cwd": ".", "caminhos": ["src/a.py"]},
            }],
            "orcamento": {"ciclos_correcao_max": 3},
            "responsaveis": {"coordenador": "agente"},
        }
        self.provas.iniciar(self.contrato)
        plano = self.provas.estado(self.provas.pasta())["chamadas_previstas"]
        self.assertEqual(["test", "implement", "test", "refute"], [c["papel"] for c in plano])

    def _registrar_previa(self, chamada, papel):
        agora = datetime.now(timezone.utc).isoformat()
        return self.provas.registrar_chamada(
            chamada, papel, "opencode", [{"nome": "agente_id", "valor": "agent-" + chamada}],
            agora, agora, "concluida",
        )

    def _preparar_teste_filho(self):
        self._registrar_previa("task-preparo", "test")
        self._registrar_previa("task-implement", "implement")
        tratar({
            "evento": "tool.execute.before",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-test"},
            "args": {"subagent_type": "test", "description": "Executar teste", "prompt": "Rode o critério"},
        }, self.politica, self.raiz)
        tratar({
            "evento": "session.created",
            "properties": {"info": {"id": "ses-filho-test", "parentID": self.sessao}},
        }, self.politica, self.raiz)

    def _bash_evento(self, tipo, chamada="bash-test", codigo=0, sessao="ses-filho-test"):
        return {
            "evento": tipo,
            "input": {
                "tool": "bash", "sessionID": sessao, "callID": chamada,
                "args": {"command": COMANDO, "workdir": str(self.raiz)},
            },
            "args": {"command": COMANDO, "workdir": str(self.raiz)},
            "output": {"title": "Teste", "output": "ok", "metadata": {"exit": codigo, "output": "ok"}},
        }

    def test_task_parentid_vincula_shell_filho_ao_agente_e_ao_exit_code(self):
        self._preparar_teste_filho()
        antes = tratar(self._bash_evento("tool.execute.before"), self.politica, self.raiz)
        self.assertEqual(antes["decisao"], "nao_aplica")
        tratar(self._bash_evento("tool.execute.after"), self.politica, self.raiz)
        tratar({
            "evento": "tool.execute.after",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-test"},
            "args": {"subagent_type": "test"},
            "output": {"title": "Teste", "output": '<task id="ses-filho-test" state="completed"><task_result>feito</task_result></task>', "metadata": {
                "parentSessionId": self.sessao, "sessionId": "ses-filho-test", "truncated": False,
            }},
        }, self.politica, self.raiz)

        pasta = self.provas.pasta()
        estado = self.provas.estado(pasta)
        chamada = next(c for c in estado["chamadas_observadas"] if c["chamada_id"] == "task-test")
        self.assertEqual((chamada["papel"], chamada["status"]), ("test", "concluida"))
        chamada_observada = ler(pasta / chamada["ref"])["dados"]
        self.assertEqual((chamada_observada["papel"], chamada_observada["runtime"]),
                         ("test", "opencode"))
        self.assertEqual(chamada_observada["ids_observados"], [
            {"nome": "callID", "valor": "task-test"},
            {"nome": "agente_id", "valor": "ses-filho-test"},
        ])
        prova = ler(pasta / estado["provas"]["teste_local"]["ref"])
        self.assertEqual(prova["dados"]["resultado"], "pass")
        self.assertEqual(prova["dados"]["agente_id"], "ses-filho-test")
        idle_filho = tratar({"evento": "session.idle", "properties": {"sessionID": "ses-filho-test"}},
                            self.politica, self.raiz)
        self.assertEqual(idle_filho, {})

    def test_task_sem_sessao_filha_fecha_janela_sem_chamada_falsa(self):
        self._registrar_previa("task-preparo", "test")
        self._registrar_previa("task-implement", "implement")
        tratar({
            "evento": "tool.execute.before",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-incompleta"},
            "args": {"subagent_type": "test"},
        }, self.politica, self.raiz)
        tratar({
            "evento": "tool.execute.after",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-incompleta"},
            "output": {"title": "Falhou", "output": "sem metadados", "metadata": {"truncated": False}},
        }, self.politica, self.raiz)
        estado = self.provas.estado(self.provas.pasta())
        self.assertNotIn("task-incompleta", {c["chamada_id"] for c in estado["chamadas_observadas"]})
        self.assertEqual(estado["vigilancia_superficie"]["abertas"], {})

    def test_task_falho_nao_e_registrado_como_concluido(self):
        self._registrar_previa("task-preparo", "test")
        self._registrar_previa("task-implement", "implement")
        tratar({
            "evento": "tool.execute.before",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-falho"},
            "args": {"subagent_type": "test"},
        }, self.politica, self.raiz)
        tratar({
            "evento": "session.created",
            "properties": {"info": {"id": "ses-filho-falho", "parentID": self.sessao}},
        }, self.politica, self.raiz)
        tratar({
            "evento": "tool.execute.after",
            "input": {"tool": "task", "sessionID": self.sessao, "callID": "task-falho"},
            "output": {"title": "Falhou", "output": '<task state="failed"></task_result>', "metadata": {
                "parentSessionId": self.sessao, "sessionId": "ses-filho-falho", "truncated": False,
            }},
        }, self.politica, self.raiz)
        estado = self.provas.estado(self.provas.pasta())
        chamada = next(c for c in estado["chamadas_observadas"] if c["chamada_id"] == "task-falho")
        registro = ler(self.provas.pasta() / chamada["ref"])
        self.assertEqual(registro["dados"]["status"], "falhou")
        self.assertEqual(chamada["status"], "falhou")

    def test_exit_nao_zero_e_timeout_nao_viram_sucesso(self):
        for codigo, resultado, identificador in ((1, "fail", "bash-fail"),
                                                  (None, "inconclusivo", "bash-timeout")):
            with self.subTest(codigo=codigo):
                antes = self._bash_evento("tool.execute.before", identificador, sessao=self.sessao)
                self.assertEqual(tratar(antes, self.politica, self.raiz)["decisao"], "nao_aplica")
                depois = self._bash_evento("tool.execute.after", identificador, codigo, sessao=self.sessao)
                if codigo is None:
                    depois["output"]["metadata"]["exit"] = None
                tratar(depois, self.politica, self.raiz)
                pasta = self.provas.pasta()
                estado = self.provas.estado(pasta)
                prova = ler(pasta / estado["provas"]["teste_local"]["ref"])
                self.assertEqual(prova["dados"]["resultado"], resultado)

    def test_guarda_nega_bundle_fora_do_bundle_antes_de_registrar_prova(self):
        evento = {
            "evento": "tool.execute.before",
            "input": {"tool": "bash", "sessionID": self.sessao, "callID": "bash-guard"},
            "args": {"command": "databricks bundle validate -t sandbox -p teste", "workdir": str(self.raiz)},
        }
        resposta = tratar(evento, self.politica, self.raiz)
        self.assertEqual(resposta["decisao"], "negar")
        self.assertIsNone(self.provas.estado(self.provas.pasta())["pendente"])

    def test_shell_env_injeta_runtime_e_idle_cobra_fecho(self):
        ambiente = tratar({"evento": "shell.env", "input": {"sessionID": self.sessao}},
                          self.politica, self.raiz)
        self.assertEqual(ambiente["env"], {"ESTEIRA_SESSAO": self.sessao, "ESTEIRA_RUNTIME": "opencode"})
        resposta = tratar({"evento": "session.idle", "properties": {"sessionID": self.sessao}},
                          self.politica, self.raiz)
        self.assertIn("followup_message", resposta)
        self.assertIn("feche a fatia", resposta["followup_message"])


if __name__ == "__main__":
    unittest.main()
