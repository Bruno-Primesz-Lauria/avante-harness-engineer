"""Target efetivo e plan antes de deploy. Sem CLI Databricks."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))
from guarda_cwd import Operacao, avaliar_operacao
from guarda_efeito import observar_resultado_plan


class GuardasEfeitoTestes(unittest.TestCase):
    def setUp(self):
        temporarios = RAIZ / ".execucoes/testes"
        temporarios.mkdir(parents=True, exist_ok=True)
        self.temporario = tempfile.TemporaryDirectory(prefix="harness_efeito_", dir=temporarios)
        self.addCleanup(self.temporario.cleanup)
        self.raiz = Path(self.temporario.name).resolve()
        self.local = self.raiz / "saneamento_migracao"
        self.local.mkdir()
        self.yaml_local = self.local / "databricks.yml"
        self.yaml_local.write_text("bundle:\n  name: saneamento_migracao\n", encoding="utf-8")
        self.politica = {"bundle_local": str(self.local), "bundle_nome": "saneamento_migracao",
                         "registros_raiz": str(self.raiz / "registros")}

    def avaliar(self, comando, politica=None, cwd=None):
        return avaliar_operacao(Operacao(
            "antes_execucao", "shell", comando, str(cwd or self.local), "ferramenta",
        ), politica or self.politica)

    def observar(self, comando="databricks bundle plan -t sandbox -p teste --select etapa",
                 politica=None, caminhos=(), identidade="nao_observada"):
        return observar_resultado_plan(
            politica or self.politica, cwd=str(self.local), comando=comando,
            caminhos=caminhos, identidade=identidade)

    def test_plan_sandbox_explicito_nao_autoriza_deploy(self):
        plan = self.avaliar("databricks bundle plan -t sandbox -p teste")
        self.assertEqual(plan.codigo, "plan_conferido")
        self.assertIn("nao autoriza deploy", plan.motivo)
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa").codigo,
                         "plan_ausente")

    def test_prefixo_de_target_literal_e_conflito(self):
        self.assertEqual(
            self.avaliar("DATABRICKS_BUNDLE_TARGET=sandbox databricks bundle validate -p teste").decisao,
            "permitir")
        self.assertEqual(
            self.avaliar("DATABRICKS_BUNDLE_TARGET=dev databricks bundle validate -t sandbox -p teste").codigo,
            "target_conflitante")
        self.assertEqual(
            self.avaliar("DATABRICKS_BUNDLE_TARGET=dev databricks bundle plan -p teste").codigo,
            "target_dev_pendente")

    def test_ambiente_do_processo_e_default_nao_entram(self):
        anterior = os.environ.get("DATABRICKS_BUNDLE_TARGET")
        os.environ["DATABRICKS_BUNDLE_TARGET"] = "sandbox"
        try:
            self.assertEqual(self.avaliar("databricks bundle validate -p teste").codigo,
                             "target_nao_observavel")
        finally:
            if anterior is None:
                os.environ.pop("DATABRICKS_BUNDLE_TARGET", None)
            else:
                os.environ["DATABRICKS_BUNDLE_TARGET"] = anterior

    def test_outro_ambiente_literal_nao_passa(self):
        self.assertEqual(
            self.avaliar("DATABRICKS_CONFIG_PROFILE=teste databricks bundle validate -t sandbox").codigo,
            "ambiente_nao_suportado")

    def test_executavel_com_sufixo_windows(self):
        self.assertEqual(
            self.avaliar("databricks.cmd bundle validate --target sandbox --profile teste").decisao,
            "permitir")

    def test_dev_sem_autorizacao_nao_usa_plan(self):
        comando_plan = "databricks bundle plan -t dev -p teste --select etapa"
        self.assertEqual(self.observar(comando_plan).codigo, "target_dev_pendente")
        politica = dict(self.politica, autorizacoes_dev=[
            {"operacao": "plan", "selecao": ["etapa"]},
            {"operacao": "deploy", "selecao": ["etapa"]},
        ])
        self.assertEqual(self.observar(comando_plan, politica=politica).codigo, "plan_registrado")
        deploy = "databricks bundle deploy -t dev -p teste --select etapa"
        self.assertEqual(self.avaliar(deploy).codigo, "target_dev_pendente")
        self.assertEqual(self.avaliar(deploy, politica).codigo, "identidade_destinos_pendentes")

    def test_deploy_completo_pede_intencao_e_plan(self):
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste").codigo,
                         "deploy_completo_nao_declarado")
        self.observar("databricks bundle plan -t sandbox -p teste")
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste").codigo,
                         "deploy_completo_nao_declarado")
        politica = dict(self.politica, intencao_deploy_completo=True)
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste", politica).codigo,
                         "identidade_destinos_pendentes")

    def test_arquivo_chamado_plan_nao_autoriza(self):
        (self.local / "plan").write_text("exit 0\n", encoding="utf-8")
        (self.local / "plan.json").write_text('{"target":"sandbox"}\n', encoding="utf-8")
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa").codigo,
                         "plan_ausente")

    def test_select_igual_com_ordem_diferente_e_hash_que_cai(self):
        self.assertEqual(self.observar().codigo, "plan_registrado")
        recibo = next((self.raiz / "registros/plans").glob("*.json"))
        dados = json.loads(recibo.read_text(encoding="utf-8"))
        self.assertNotIn("perfil", dados)
        self.assertNotIn("teste", dados["perfil_sha256"])
        self.assertTrue(all(valor != "teste" for valor in dados.values() if not isinstance(valor, (dict, list))))
        mesmo = self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa")
        self.assertEqual(mesmo.codigo, "identidade_destinos_pendentes")
        self.assertEqual(mesmo.decisao, "negar")
        self.assertIn("nao restringe o sync", mesmo.recuperacao)
        invertido = self.avaliar(
            "databricks bundle deploy --select etapa -t sandbox --profile=teste")
        self.assertEqual(invertido.codigo, "identidade_destinos_pendentes")
        self.yaml_local.write_text("bundle:\n  name: saneamento_migracao\n# mudou\n", encoding="utf-8")
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa").codigo,
                         "plan_obsoleto")

    def test_selecao_e_perfil_diferentes_nao_reaproveitam_recibo(self):
        self.observar()
        self.assertEqual(
            self.avaliar("databricks bundle deploy -t sandbox -p teste --select outra").codigo,
            "plan_ausente")
        self.assertEqual(
            self.avaliar("databricks bundle deploy -t sandbox -p outro --select etapa").codigo,
            "plan_incompativel")

    def test_recibo_com_chave_extra_ou_fora_do_bundle_nao_vale(self):
        self.observar()
        recibo = next((self.raiz / "registros/plans").glob("*.json"))
        dados = json.loads(recibo.read_text(encoding="utf-8"))
        dados["exemplo"] = False
        recibo.write_text(json.dumps(dados), encoding="utf-8")
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa").codigo,
                         "plan_ausente")
        fora = self.raiz / "fora.yml"
        fora.write_text("x\n", encoding="utf-8")
        self.assertEqual(self.observar(caminhos=[fora]).codigo, "estado_nao_verificado")

    def test_gancho_de_plan_nao_grava_recibo(self):
        caminho = self.raiz / "politica.json"
        caminho.write_text(json.dumps(self.politica), encoding="utf-8")
        evento = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                  "tool_input": {"command": "databricks bundle plan -t sandbox -p teste --select etapa",
                                 "workdir": str(self.local)}}
        resposta = subprocess.run(
            [sys.executable, str(RAIZ / "adaptadores/entrada.py"), "codex", str(caminho)],
            input=json.dumps(evento), text=True, capture_output=True, timeout=10)
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        self.assertNotIn("permissionDecision", json.loads(resposta.stdout)["hookSpecificOutput"])
        self.assertFalse((self.raiz / "registros/plans").exists())

    def test_gancho_nega_deploy_antes_do_efeito(self):
        caminho = self.raiz / "politica.json"
        caminho.write_text(json.dumps(self.politica), encoding="utf-8")
        evento = {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                  "tool_input": {"command": "databricks bundle deploy -t sandbox -p perfil_privado --select etapa",
                                 "workdir": str(self.local)}}
        resposta = subprocess.run(
            [sys.executable, str(RAIZ / "adaptadores/entrada.py"), "codex", str(caminho)],
            input=json.dumps(evento), text=True, capture_output=True, timeout=10)
        corpo = json.loads(resposta.stdout)["hookSpecificOutput"]
        marcador = self.raiz / "efeito.txt"
        if corpo.get("permissionDecision") != "deny":
            marcador.write_text("executou", encoding="utf-8")
        self.assertFalse(marcador.exists())
        self.assertIn("plan_ausente", corpo["permissionDecisionReason"])
        self.assertNotIn("perfil_privado", corpo["permissionDecisionReason"])

    def test_deploy_sandbox_autorizado_exige_plan_e_so_vale_no_sandbox(self):
        politica = dict(self.politica, deploy_sandbox_autorizado=True)
        deploy = "databricks bundle deploy -t sandbox -p teste --select etapa"
        self.assertEqual(self.avaliar(deploy, politica).codigo, "plan_ausente")
        self.assertEqual(self.observar(politica=politica).codigo, "plan_registrado")
        liberado = self.avaliar(deploy, politica)
        self.assertEqual((liberado.decisao, liberado.codigo), ("permitir", "deploy_sandbox_autorizado"))
        self.assertEqual(self.avaliar(deploy).codigo, "identidade_destinos_pendentes")
        self.assertEqual(
            self.avaliar("databricks bundle deploy -t sandbox -p teste --select outra", politica).codigo,
            "plan_ausente")
        self.assertEqual(
            self.avaliar("databricks bundle deploy -p teste --select etapa", politica).codigo,
            "target_nao_observavel")
        com_dev = dict(politica, autorizacoes_dev=[{"operacao": "plan", "selecao": ["etapa"]},
                                                   {"operacao": "deploy", "selecao": ["etapa"]}])
        self.assertEqual(self.observar("databricks bundle plan -t dev -p teste --select etapa",
                                       politica=com_dev).codigo, "plan_registrado")
        self.assertEqual(
            self.avaliar("databricks bundle deploy -t dev -p teste --select etapa", com_dev).codigo,
            "identidade_destinos_pendentes")
        for valor in (False, "true", 1):
            self.assertEqual(
                self.avaliar(deploy, dict(self.politica, deploy_sandbox_autorizado=valor)).codigo,
                "identidade_destinos_pendentes")

    def test_deploy_sandbox_autorizado_nao_vale_fora_do_bundle(self):
        politica = dict(self.politica, deploy_sandbox_autorizado=True)
        self.observar(politica=politica)
        fora = self.raiz / "outro"
        fora.mkdir()
        decisao = self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa",
                               politica, cwd=fora)
        self.assertEqual(decisao.decisao, "negar")

    def test_identidade_do_recibo_diferente_nao_serve_ao_gancho(self):
        self.assertEqual(self.observar(identidade="pessoa@exemplo").codigo, "plan_registrado")
        self.assertEqual(self.avaliar("databricks bundle deploy -t sandbox -p teste --select etapa").codigo,
                         "plan_incompativel")


if __name__ == "__main__":
    unittest.main(verbosity=2)
