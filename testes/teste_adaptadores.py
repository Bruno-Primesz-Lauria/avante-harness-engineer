"""Equivalencia de decisao e instalacao; sem executar ferramentas de produto."""
import json
import shutil
import shlex
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from guarda_cwd import avaliar_operacao, Operacao
from protocolo import normalizar, traduzir, RUNTIMES
from gerenciar import gerar, instalar, mesclar, destino, WORKSPACE
from executar import carregar_politica


class AdaptadoresTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/provas" / self.fixture_id
        self.raiz.parent.mkdir(parents=True, exist_ok=True)
        self.raiz.mkdir()
        self.addCleanup(self.limpar_fixture)
        self.local = self.raiz / "local"
        self.local.mkdir()
        (self.local / "databricks.yml").write_text("bundle: {name: saneamento_migracao}", encoding="utf-8")
        self.politica = {"bundle_local": str(self.local), "bundle_nome": "saneamento_migracao",
                         "registros_raiz": str(self.raiz / "registros")}
        self.config = self.raiz / "politica.json"
        self.config.write_text(json.dumps(self.politica), encoding="utf-8")

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/provas").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino)

    def evento(self, runtime, cwd):
        comando = "databricks bundle validate -t sandbox -p teste"
        if runtime == "cursor":
            return {"hook_event_name": "beforeShellExecution", "command": comando, "cwd": str(cwd)}
        if runtime == "opencode":
            return {"evento": "tool.execute.before", "tool": "bash",
                    "args": {"command": comando, "workdir": str(cwd)}}
        if runtime == "claude_code":
            comando = f"cd -- '{cwd}' && {comando}"
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(self.local),
                "tool_input": {"command": comando, "workdir": str(cwd)}}

    def executar(self, runtime, evento, bom=False):
        entrada = json.dumps(evento).encode("utf-8")
        if bom:
            entrada = b"\xef\xbb\xbf" + entrada
        return subprocess.run([sys.executable, str(RAIZ / "adaptadores/executar.py"), runtime, str(self.config)],
                              input=entrada, capture_output=True, timeout=10)

    def test_equivalencia_das_quatro_ferramentas(self):
        for runtime in RUNTIMES:
            for cwd, esperado in ((self.local, "permitir"), (self.raiz, "negar")):
                with self.subTest(runtime=runtime, esperado=esperado):
                    decisao = avaliar_operacao(normalizar(runtime, self.evento(runtime, cwd)), self.politica)
                    self.assertEqual(decisao.decisao, esperado)

    def test_subprocessos_retornam_o_protocolo_nativo(self):
        for runtime in RUNTIMES:
            for cwd in (self.local, self.raiz):
                with self.subTest(runtime=runtime, cwd=cwd):
                    evento = self.evento(runtime, cwd)
                    resposta = self.executar(runtime, evento)
                    self.assertEqual(resposta.returncode, 0, resposta.stderr)
                    decisao = avaliar_operacao(normalizar(runtime, evento), self.politica)
                    self.assertEqual(json.loads(resposta.stdout), traduzir(runtime, decisao))

    def test_falha_bloqueante_em_todos_os_protocolos(self):
        for runtime in RUNTIMES:
            self.assertEqual(self.executar(runtime, []).returncode, 2)

    def test_claude_subagentstop_com_erro_avisa_sem_prender_o_subagente(self):
        # Exit 2 no SubagentStop faria o subagente continuar; o erro vira aviso com exit 0.
        resposta = self.executar("claude_code", {"hook_event_name": "SubagentStop", "agent_id": "a1",
                                                 "agent_type": "test"})
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        self.assertIn("session_id ausente", json.loads(resposta.stdout)["systemMessage"])

    def test_cursor_aceita_utf8_bom(self):
        resposta = self.executar("cursor", self.evento("cursor", self.raiz), bom=True)
        self.assertEqual(resposta.returncode, 0)
        self.assertEqual(json.loads(resposta.stdout)["permission"], "deny")

    def test_claude_nao_infere_cwd_da_sessao_ou_campo_nao_documentado(self):
        evento = self.evento("codex", self.local)
        resultado = avaliar_operacao(normalizar("claude_code", evento), self.politica)
        self.assertEqual(resultado.codigo, "cwd_nao_observavel")

    def test_claude_powershell_normalizado(self):
        evento = self.evento("claude_code", self.local)
        evento["tool_name"] = "PowerShell"
        self.assertEqual(normalizar("claude_code", evento).ferramenta, "shell")

    def test_nucleo_nao_aceita_diretorio_de_sessao_como_prova(self):
        op = Operacao("antes_execucao", "shell", "databricks bundle validate -t sandbox -p teste",
                      str(self.local), "sessao")
        self.assertEqual(avaliar_operacao(op, self.politica).codigo, "cwd_nao_observavel")

    def test_cursor_configura_falha_fechada(self):
        self.assertTrue(gerar("cursor")["hooks"]["beforeShellExecution"][0]["failClosed"])

    def test_instalacoes_idempotentes(self):
        for runtime in RUNTIMES:
            caminho = instalar(runtime, self.raiz)
            original = caminho.read_bytes()
            instalar(runtime, self.raiz)
            self.assertEqual(caminho.read_bytes(), original)

    def test_claude_preserva_permissoes_e_hooks(self):
        atual = {"permissions": {"allow": ["Read"]}, "hooks": {"Stop": [{"hooks": []}]}}
        resultado = mesclar(atual, gerar("claude_code"))
        self.assertEqual(resultado["permissions"], atual["permissions"])
        self.assertIn(atual["hooks"]["Stop"][0], resultado["hooks"]["Stop"])
        self.assertIn(gerar("claude_code")["hooks"]["Stop"][0], resultado["hooks"]["Stop"])

    def test_cursor_preserva_outros_handlers(self):
        atual = {"version": 1, "hooks": {"beforeShellExecution": [{"command": "outra_guarda"}]}}
        resultado = mesclar(atual, gerar("cursor"))
        self.assertEqual(len(resultado["hooks"]["beforeShellExecution"]), 2)

    def test_instalacao_codex_faz_backup_dos_bytes_e_preserva_hooks(self):
        caminho = destino("codex", self.raiz)
        caminho.parent.mkdir(parents=True)
        original = b'{"description":"previo", "hooks":{"Stop":[{"hooks":[{"type":"command","command":"outro"}]}]}}\r\n'
        caminho.write_bytes(original)
        instalar("codex", self.raiz)
        backups = list(caminho.parent.glob("hooks.json.backup.*"))
        self.assertEqual([b.read_bytes() for b in backups], [original])
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self.assertEqual(dados["description"], "previo")
        self.assertEqual(dados["hooks"]["Stop"], json.loads(original)["hooks"]["Stop"])
        self.assertEqual(dados["hooks"]["PreToolUse"], gerar("codex")["hooks"]["PreToolUse"])

    def test_instalacao_nao_sobrescreve_json_invalido(self):
        caminho = destino("codex", self.raiz)
        caminho.parent.mkdir(parents=True)
        caminho.write_text("{invalido", encoding="utf-8")
        with self.assertRaises(ValueError):
            instalar("codex", self.raiz)
        self.assertEqual(caminho.read_text(encoding="utf-8"), "{invalido")

    def test_handler_existente_diferente_pede_revisao(self):
        candidato = gerar("codex")
        existente = json.loads(json.dumps(candidato))
        existente["hooks"]["PreToolUse"][0]["matcher"] = ".*"
        with self.assertRaises(ValueError):
            mesclar(existente, candidato)

    def test_saida_inesperada_do_executor_bloqueia(self):
        clone = self.raiz / "clone"
        (clone / "adaptadores").mkdir(parents=True)
        shutil.copyfile(RAIZ / "adaptadores/entrada.py", clone / "adaptadores/entrada.py")
        (clone / "adaptadores/executar.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
        resposta = subprocess.run([sys.executable, str(clone / "adaptadores/entrada.py"), "claude_code"],
                                  input="{}", capture_output=True, text=True, timeout=10)
        self.assertEqual(resposta.returncode, 2)

    def test_raiz_padrao_e_o_harness(self):
        self.assertEqual(WORKSPACE, RAIZ)
        for runtime in RUNTIMES:
            self.assertTrue(destino(runtime).is_relative_to(RAIZ))
        self.assertEqual(destino("claude_code").name, "settings.json")

    def test_configuracoes_geradas_nao_dependem_da_maquina(self):
        for runtime in RUNTIMES:
            for plataforma in ("windows", "posix"):
                texto = json.dumps(gerar(runtime, plataforma))
                self.assertNotIn(str(RAIZ), texto)
                self.assertNotIn(RAIZ.as_posix(), texto)
                self.assertNotIn("file:///", texto)
                self.assertNotIn("C:/Python", texto)

    def test_politica_aponta_para_repositorio_interno(self):
        politica = carregar_politica(RAIZ / "configuracao/politica.json")
        self.assertEqual(Path(politica["bundle_local"]),
                         RAIZ / "prj-avante-analytics-adb/bundles/src/notebooks/saneamento_migracao")
        self.assertTrue(Path(politica["registros_raiz"]).is_relative_to(RAIZ))

    def test_clone_em_outro_caminho_com_espacos(self):
        clone = self.raiz / "checkout com espacos"
        for relativo in ("adaptadores/entrada.py", "adaptadores/executar.py", "adaptadores/protocolo.py",
                         "implementacao/guarda_cwd.py", "implementacao/guarda_efeito.py",
                         "configuracao/politica.json"):
            alvo = clone / relativo
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / relativo, alvo)
        bundle = clone / "prj-avante-analytics-adb/bundles/src/notebooks/saneamento_migracao"
        bundle.mkdir(parents=True)
        (bundle / "databricks.yml").write_text("bundle: {name: saneamento_migracao}", encoding="utf-8")
        evento = self.evento("cursor", bundle)
        # Executa o comando portatil gerado, sem path do checkout original.
        comando = gerar("cursor")["hooks"]["beforeShellExecution"][0]["command"]
        resultado = subprocess.run(shlex.split(comando), cwd=clone, input=json.dumps(evento),
                                   capture_output=True, text=True, timeout=15)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(json.loads(resultado.stdout)["permission"], "allow")
        registros = list((clone / ".execucoes/cursor/cwd_bundle").glob("*.json"))
        self.assertEqual(len(registros), 1)
        self.assertEqual(Path(json.loads(registros[0].read_text(encoding="utf-8"))["decisao"]["cwd"]), bundle)

    def test_instalador_independe_do_cwd_da_chamada(self):
        resultado = subprocess.run([sys.executable, str(RAIZ / "adaptadores/gerenciar.py"), "cursor"],
                                   cwd=self.raiz, capture_output=True, text=True, timeout=10)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(json.loads(resultado.stdout), gerar("cursor"))

    def test_troca_de_plataforma_substitui_somente_nosso_hook(self):
        for runtime in ("cursor", "claude_code", "codex"):
            caminho = instalar(runtime, self.raiz, "windows")
            instalar(runtime, self.raiz, "posix")
            self.assertEqual(json.loads(caminho.read_text(encoding="utf-8")), gerar(runtime, "posix"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
