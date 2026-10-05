"""Traducao das chamadas Task e provas Shell observadas na sondagem P0.5."""
import copy
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from provas import Provas, ler
from cursor.prova import tratar


# Campos usados diretamente dos eventos P0.5; a sonda gravou o envelope em
# .execucoes/sondagens/brutos/cursor/2026-10-05_cursor-3.17.8/hooks/.
COORDENADOR = "ece83f0c-f593-46f9-ae43-46fb59ac7df6"
AGENTE = "f34232ff-59ad-4ef1-ae06-e87c5a9d280d"
TASK_ID = ("call-c30c3638-76a2-4188-9202-0e3412b631b0-3\n"
           "fc_f23dc96e-53a8-963e-876a-06fd58951ab1_0")
TASK_ID_2 = ("call-f95f50de-f20e-4e36-8c58-25ba97a2b056-5\n"
             "fc_91940417-1eb1-9260-8741-dec541d076fa_0")
SHELL_ID = "c958c3f8-ebbd-46f7-a9a8-60942ebeaae9"

TASK = {
    "conversation_id": COORDENADOR,
    "tool_name": "Task",
    "tool_input": {"subagent_type": "sonda"},
    "tool_use_id": TASK_ID,
    "session_id": COORDENADOR,
    "hook_event_name": "preToolUse",
    "cursor_version": "3.17.8",
}
START = {
    "conversation_id": COORDENADOR,
    "subagent_id": TASK_ID,
    "subagent_type": "sonda",
    "session_id": COORDENADOR,
    "hook_event_name": "subagentStart",
    "cursor_version": "3.17.8",
}
STOP = {
    "conversation_id": COORDENADOR,
    "subagent_id": TASK_ID,
    "subagent_type": "sonda",
    "status": "completed",
    "message_count": 0,
    "tool_call_count": 0,
    "session_id": COORDENADOR,
    "hook_event_name": "subagentStop",
    "cursor_version": "3.17.8",
}
SHELL_PRE = {
    "conversation_id": AGENTE,
    "tool_name": "Shell",
    "tool_input": {"command": "echo sonda-sucesso", "cwd": "", "timeout": 30000},
    "tool_use_id": SHELL_ID,
    "session_id": AGENTE,
    "hook_event_name": "preToolUse",
    "cursor_version": "3.17.8",
}
SHELL_POST = {
    "conversation_id": AGENTE,
    "tool_name": "Shell",
    "tool_input": {"command": "echo sonda-sucesso", "cwd": "", "timeout": 30000},
    "tool_output": '{"output":"sonda-sucesso\\r\\n","exitCode":0}',
    "tool_use_id": SHELL_ID,
    "session_id": AGENTE,
    "hook_event_name": "postToolUse",
    "cursor_version": "3.17.8",
}


class CursorSubagenteTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/provas" / self.fixture_id
        self.raiz.mkdir(parents=True)
        self.addCleanup(self.limpar_fixture)
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("# estado anterior\n", encoding="utf-8")
        (self.raiz / "configuracao").mkdir()
        self.politica = {
            "bundle_local": str(self.raiz / "src"),
            "bundle_nome": "saneamento_migracao",
            "registros_raiz": str(self.raiz / ".execucoes"),
            "agentes_obrigatorios": {"claude_code": [], "cursor": []},
        }
        (self.raiz / "configuracao/politica.json").write_text(
            json.dumps(self.politica), encoding="utf-8")
        self.provas = Provas(self.raiz, self.politica["registros_raiz"],
                             COORDENADOR, runtime="cursor")
        self.provas.iniciar({
            "objetivo": "Verificar a mudanca",
            "termino_fatia": "Teste e fecho validos",
            "trilha": "correcao",
            "superficie": ["src/a.py"],
            "artefatos_raiz": ".execucoes/provas",
            "fora": [],
            "fontes": ["src/a.py"],
            "prazo": None,
            "aceite": [{
                "id": "c1", "tipo": "teste", "obrigatorio": True,
                "esperado": "Processo termina em 0",
                "verificacao": {"comando": "python teste.py", "cwd": ".", "caminhos": ["src"]},
            }],
            "orcamento": {"ciclos_correcao_max": 3},
            "responsaveis": {"coordenador": "agente"},
        })

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/provas").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino)

    def evento(self, bruto, **alteracoes):
        evento = copy.deepcopy(bruto)
        evento.update(alteracoes)
        return evento

    def chamada(self, chamada_id=TASK_ID, papel="test"):
        tarefa = self.evento(TASK, tool_use_id=chamada_id)
        tarefa["tool_input"]["subagent_type"] = papel
        self.assertEqual(tratar(tarefa, self.politica, self.raiz), {"permission": "allow"})
        inicio = self.evento(START, subagent_id=chamada_id, subagent_type=papel)
        self.assertEqual(tratar(inicio, self.politica, self.raiz), {})
        return chamada_id

    def shell(self):
        pre = copy.deepcopy(SHELL_PRE)
        pre["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        self.assertEqual(tratar(pre, self.politica, self.raiz), {"permission": "allow"})
        pos = copy.deepcopy(SHELL_POST)
        pos["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        pos["tool_output"] = json.dumps({"output": "ok\r\n", "exitCode": 0})
        self.assertIn("Verificacao: pass", tratar(pos, self.politica, self.raiz)["additional_context"])

    def test_janela_unica_vincula_prova_e_chamada_ao_coordenador(self):
        chamada_id = self.chamada()
        self.shell()
        fim = self.evento(STOP, subagent_id=chamada_id, subagent_type="test")
        self.assertEqual(tratar(fim, self.politica, self.raiz), {})

        pasta = self.provas.pasta()
        estado = self.provas.estado(pasta)
        prova = ler(pasta / estado["provas"]["c1"]["ref"])["dados"]
        self.assertEqual(prova["resultado"], "pass")
        self.assertEqual(prova["agente_id"], AGENTE)
        chamada = estado["chamadas_observadas"][0]
        evento = ler(pasta / chamada["ref"])["dados"]
        ids = {item["nome"]: item["valor"] for item in evento["ids_observados"]}
        self.assertEqual(evento["papel"], "test")
        self.assertEqual(ids["agente_id"], AGENTE)
        self.assertEqual(ids["tool_use_id"], TASK_ID)

    def test_janela_unica_tem_precedencia_sobre_fatia_propria_do_filho(self):
        chamada_id = self.chamada()
        filho = Provas(self.raiz, self.politica["registros_raiz"], AGENTE, runtime="cursor")
        contrato = ler(self.provas.pasta() / "contrato.yaml")["dados"]
        filho.iniciar(contrato)

        self.shell()
        fim = self.evento(STOP, subagent_id=chamada_id, subagent_type="test")
        self.assertEqual(tratar(fim, self.politica, self.raiz), {})

        estado_pai = self.provas.estado(self.provas.pasta())
        estado_filho = filho.estado(filho.pasta())
        self.assertEqual(ler(self.provas.pasta() /
                             estado_pai["provas"]["c1"]["ref"])["dados"]["agente_id"], AGENTE)
        self.assertEqual(estado_filho["provas"], {})

    def test_janelas_sobrepostas_nao_registram_sucesso_shell(self):
        self.chamada(TASK_ID, "test")
        self.chamada(TASK_ID_2, "implement")
        pre = copy.deepcopy(SHELL_PRE)
        pre["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        self.assertEqual(tratar(pre, self.politica, self.raiz), {"permission": "allow"})
        pos = copy.deepcopy(SHELL_POST)
        pos["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        pos["tool_output"] = json.dumps({"output": "ok\r\n", "exitCode": 0})
        self.assertEqual(tratar(pos, self.politica, self.raiz), {})
        estado = self.provas.estado(self.provas.pasta())
        self.assertEqual(estado["provas"], {})

    def test_shell_fora_de_janela_nao_registra_sucesso(self):
        pre = copy.deepcopy(SHELL_PRE)
        pre["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        self.assertEqual(tratar(pre, self.politica, self.raiz), {"permission": "allow"})
        pos = copy.deepcopy(SHELL_POST)
        pos["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        pos["tool_output"] = json.dumps({"output": "ok\r\n", "exitCode": 0})
        self.assertEqual(tratar(pos, self.politica, self.raiz), {})
        estado = self.provas.estado(self.provas.pasta())
        self.assertEqual(estado["provas"], {})

    def test_papel_desconhecido_fecha_sem_chamada_ou_prova(self):
        chamada_id = self.chamada(TASK_ID, "sonda")
        pre = copy.deepcopy(SHELL_PRE)
        pre["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        self.assertEqual(tratar(pre, self.politica, self.raiz), {"permission": "allow"})
        pos = copy.deepcopy(SHELL_POST)
        pos["tool_input"].update(command="python teste.py", cwd=str(self.raiz))
        pos["tool_output"] = json.dumps({"output": "ok\r\n", "exitCode": 0})
        self.assertEqual(tratar(pos, self.politica, self.raiz), {})
        fim = self.evento(STOP, subagent_id=chamada_id, subagent_type="sonda")
        self.assertEqual(tratar(fim, self.politica, self.raiz), {})
        estado = self.provas.estado(self.provas.pasta())
        self.assertEqual(estado["provas"], {})
        self.assertEqual(estado["chamadas_observadas"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
