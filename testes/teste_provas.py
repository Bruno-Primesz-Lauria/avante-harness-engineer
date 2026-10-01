"""Provas persistidas e protocolos Cursor, com processos e arquivos locais."""
import copy
import json
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from formas import dentro, validar, validar_dados
from provas import Provas, ler, gravar, trava
from cursor.prova import tratar


class ProvasTestes(unittest.TestCase):
    def setUp(self):
        temporarios = RAIZ / ".execucoes/testes"
        temporarios.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="prova_", dir=temporarios)
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name).resolve()
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("# trabalho anterior\n", encoding="utf-8")
        (self.raiz / "docs").mkdir()
        self.politica = {"bundle_local": str(self.raiz / "src"), "bundle_nome": "saneamento_migracao",
                         "registros_raiz": str(self.raiz / ".execucoes")}
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a")
        self.contrato = dict(objetivo="Verificar a mudanca", termino_fatia="Teste e fecho validos",
                             trilha="correcao", superficie=["src/a.py"], artefatos_raiz=".execucoes/provas",
                             fora=[], fontes=["src/a.py"], prazo=None,
                             aceite=[dict(id="c1", tipo="teste", obrigatorio=True, esperado="Processo termina em 0",
                                          verificacao=dict(comando="python teste.py", cwd=".", caminhos=["src"]))],
                             orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"})

    def iniciar(self):
        self.p.iniciar(self.contrato)

    def executar(self, codigo=0, saida="ok", chamada="t1"):
        self.assertTrue(self.p.antes(chamada, "python teste.py", str(self.raiz), "teste"))
        return self.p.depois(chamada, "python teste.py", codigo, saida)

    def evento(self, nome, **extras):
        evento = dict(hook_event_name=nome, conversation_id="sessao-a", cursor_version="teste",
                      tool_name="Shell", tool_use_id="t1", cwd=str(self.raiz),
                      tool_input={"command": "python teste.py", "working_directory": str(self.raiz)})
        evento.update(extras)
        return evento

    def hook(self, nome, **extras):
        return tratar(self.evento(nome, **extras), self.politica, self.raiz)

    def test_sem_tarefa_nao_interfere_no_fecho_simples(self):
        self.assertEqual(self.hook("stop", status="completed"), {})
        self.assertEqual(self.hook("preToolUse"), {"permission": "allow"})
        self.assertFalse(self.p.indice.exists())

    def test_baseline_preserva_trabalho_existente_sem_git(self):
        self.iniciar()
        original = ler(self.p.pasta() / "baseline.json")
        (self.raiz / "src/a.py").write_text("# nossa mudanca", encoding="utf-8")
        self.executar()
        self.p.fechar("DONE", "Verificado")
        self.assertEqual(ler(self.p.pasta() / "baseline.json"), original)
        self.assertTrue(self.p.conferir()["fecho_valido"])

    def test_edicao_depois_do_teste_invalida_done_inclusive_ja_publicado(self):
        self.iniciar()
        self.executar()
        self.p.fechar("DONE", "Verificado")
        (self.raiz / "src/a.py").write_text("# editado", encoding="utf-8")
        self.assertFalse(self.p.conferir()["fecho_valido"])
        with self.assertRaisesRegex(ValueError, "obsoleta"):
            self.p.fechar("DONE", "Nao pode")

    def test_edicao_depois_do_teste_invalida_review_publicado(self):
        self.iniciar()
        self.executar()
        self.p.fechar("REVIEW", "Verificado")
        (self.raiz / "src/a.py").write_text("# editado", encoding="utf-8")
        self.assertFalse(self.p.conferir()["fecho_valido"])
        self.assertIn("followup_message", self.hook("stop", status="completed", loop_count=0))

    def test_arquivo_novo_e_removido_na_dependencia_invalidam(self):
        for operacao in ("novo", "remover"):
            with self.subTest(operacao=operacao):
                self.p = Provas(self.raiz, self.politica["registros_raiz"], operacao)
                self.iniciar()
                self.executar()
                arquivo = self.raiz / "src/a.py"
                if operacao == "novo":
                    (self.raiz / "src/b.py").write_text("novo", encoding="utf-8")
                else:
                    arquivo.unlink()
                with self.assertRaises(ValueError):
                    self.p.fechar("DONE", "Nao pode")

    def test_documento_fora_do_criterio_nao_exige_reteste(self):
        self.iniciar()
        self.executar()
        (self.raiz / "docs/nota.md").write_text("nota", encoding="utf-8")
        self.assertEqual(self.p.fechar("DONE", "Verificado")["status"], "DONE")

    def test_mudanca_durante_execucao_e_inconclusiva(self):
        self.iniciar()
        self.p.antes("t1", "python teste.py", str(self.raiz), "teste")
        (self.raiz / "src/a.py").write_text("concorrente", encoding="utf-8")
        r = self.p.depois("t1", "python teste.py", 0, "ok")
        self.assertEqual(r["resultado"], "inconclusivo")
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")

    def test_resultado_falhou_ou_timeout_nao_fecha_done(self):
        for codigo in (1, None):
            self.p = Provas(self.raiz, self.politica["registros_raiz"], str(codigo))
            self.iniciar()
            self.executar(codigo)
            with self.assertRaises(ValueError):
                self.p.fechar("DONE", "Nao pode")
            self.assertEqual(self.p.fechar("BLOCKED", "Verificacao inconclusiva")["status"], "BLOCKED")

    def test_resultado_sem_pre_evento_ou_de_outra_chamada_nao_e_prova(self):
        self.iniciar()
        self.assertIsNone(self.p.depois("t1", "python teste.py", 0, "ok"))
        self.p.antes("t1", "python teste.py", str(self.raiz), "teste")
        self.assertIsNone(self.p.depois("t2", "python teste.py", 0, "ok"))
        with self.assertRaises(ValueError):
            self.p.depois("t1", "outro comando", 0, "ok")
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")

    def test_evento_repetido_nao_sobrescreve_prova(self):
        self.iniciar()
        self.executar()
        estado = (self.p.pasta() / "estado.json").read_bytes()
        self.assertIsNone(self.p.depois("t1", "python teste.py", 1, "substituir"))
        self.assertEqual((self.p.pasta() / "estado.json").read_bytes(), estado)

    def test_sessoes_nao_misturam_provas(self):
        self.iniciar()
        self.executar()
        outra = Provas(self.raiz, self.politica["registros_raiz"], "sessao-b")
        outra.iniciar(self.contrato)
        self.assertNotEqual(self.p.pasta(), outra.pasta())
        with self.assertRaises(ValueError):
            outra.fechar("DONE", "Nao pode")
        self.p.fechar("DONE", "Verificado")

    def test_lock_e_revisao_impedem_sobrescrita(self):
        self.iniciar()
        pasta = self.p.pasta()
        estado = self.p.estado(pasta)
        antigo = copy.deepcopy(estado)
        with trava(pasta):
            with self.assertRaisesRegex(ValueError, "em uso"):
                self.executar()
            self.p.atualizar(pasta, estado)
            with self.assertRaisesRegex(ValueError, "mudou"):
                self.p.atualizar(pasta, antigo)

    def test_log_manifesto_e_prova_alterados_nao_valem(self):
        for alvo in ("log", "manifesto", "evento"):
            self.p = Provas(self.raiz, self.politica["registros_raiz"], alvo)
            self.iniciar()
            r = self.executar()
            pasta = self.p.pasta()
            e = ler(pasta / r["evidencia_ref"])
            ref = {"log": e["dados"]["log_ref"], "manifesto": e["manifesto_ref"], "evento": r["evidencia_ref"]}[alvo]
            (pasta / ref).write_text("alterado", encoding="utf-8")
            with self.assertRaises(ValueError):
                self.p.fechar("DONE", "Nao pode")

    def test_mudar_contrato_ou_controle_exige_nova_verificacao(self):
        self.iniciar()
        self.executar()
        (self.raiz / "configuracao").mkdir()
        (self.raiz / "configuracao/politica.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")
        contrato = self.p.pasta() / "contrato.yaml"
        contrato.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "O contrato mudou"):
            self.p.conferir()

    def test_contrato_rejeita_campo_tipo_caminho_e_criterio_invalidos(self):
        alteracoes = [lambda c: c.update(desconhecido=True), lambda c: c.update(superficie=["../fora"]),
                      lambda c: c["aceite"][0].update(obrigatorio="true"),
                      lambda c: c["aceite"].append(copy.deepcopy(c["aceite"][0])),
                      lambda c: c.update(superficie=["sem_cobertura.py"])]
        for alterar in alteracoes:
            c = copy.deepcopy(self.contrato)
            alterar(c)
            with self.assertRaises(ValueError):
                self.p.iniciar(c)

    def test_envelope_exemplo_identidade_referencia_e_produtor_rejeitados(self):
        self.iniciar()
        pasta = self.p.pasta()
        original = ler(pasta / "contrato.yaml")
        for campos in ({"exemplo": True}, {"execucao_id": "outra"}, {"manifesto_ref": "../fora"},
                       {"produtor": "hook"}, {"tentativa": True}, {"extra": "x"}):
            evento = dict(original, **campos)
            with self.assertRaises(ValueError):
                validar(evento, pasta, original["execucao_id"], "principal")

    def test_nova_fatia_preserva_fatias_fechadas_e_nao_reusa_prova(self):
        self.iniciar()
        self.executar()
        with self.assertRaises(ValueError):
            self.iniciar()
        self.p.fechar("DONE", "Verificado")
        anterior = self.p.pasta()
        self.iniciar()
        self.assertTrue((anterior / "estado.json").is_file())
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")

    def test_hook_post_sem_exit_code_nao_inventa_sucesso(self):
        self.iniciar()
        self.hook("preToolUse")
        r = self.hook("postToolUse", tool_output='{"stdout":"All tests passed"}')
        self.assertIn("inconclusivo", r["additional_context"])
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")

    def test_hook_timeout_preserva_estado_e_nao_repete_efeito(self):
        self.iniciar()
        self.hook("preToolUse")
        r = self.hook("postToolUseFailure", failure_type="timeout")
        self.assertIn("inconclusivo", r["additional_context"])
        self.assertIn("nao_verificada", json.dumps(self.p.criterios(self.p.pasta(), self.p.estado(self.p.pasta()))))

    def test_processo_real_observado_pelos_protocolos(self):
        argv = [sys.executable, "-c", "print('prova real')"]
        comando = subprocess.list2cmdline(argv)
        self.contrato["aceite"][0]["verificacao"]["comando"] = comando
        self.iniciar()
        entrada = {"command": comando, "working_directory": str(self.raiz)}
        self.hook("preToolUse", tool_input=entrada)
        executado = subprocess.run(argv, cwd=self.raiz, capture_output=True, text=True)
        self.hook("postToolUse", tool_input=entrada, tool_output=json.dumps({"exitCode": executado.returncode,
                                                       "stdout": executado.stdout, "stderr": executado.stderr}))
        self.p.fechar("DONE", "Processo conferido")
        self.assertEqual(self.hook("stop", status="completed"), {})

    def test_prova_obsoleta_pode_ser_renovada_sem_apagar_provas_gravadas(self):
        self.iniciar()
        self.executar()
        self.p.fechar("DONE", "Primeiro fecho")
        (self.raiz / "src/a.py").write_text("# mudou", encoding="utf-8")
        self.executar(chamada="t2")
        self.assertFalse(self.p.conferir()["fecho_valido"])
        self.p.fechar("DONE", "Verificado novamente")
        self.assertTrue(self.p.conferir()["fecho_valido"])
        self.assertEqual(len(list((self.p.pasta() / "fechos").glob("*.yaml"))), 2)

    def test_pre_evento_repetido_nao_pode_reusar_resultado(self):
        self.iniciar()
        self.executar()
        with self.assertRaisesRegex(ValueError, "ja registrada"):
            self.p.antes("t1", "python teste.py", str(self.raiz), "teste")

    def test_stop_tem_limite_e_respeita_cancelamento(self):
        self.iniciar()
        self.assertIn("followup_message", self.hook("stop", status="completed", loop_count=0))
        self.assertEqual(self.hook("stop", status="completed", loop_count=2), {})
        self.assertEqual(self.hook("stop", status="aborted"), {})
        self.p.fechar("BLOCKED", "Sem capacidade para verificar")
        self.assertEqual(self.hook("stop", status="completed"), {})

    def test_session_start_injeta_id_sem_estado_global(self):
        r = self.hook("sessionStart")
        self.assertEqual(r["env"], {"ESTEIRA_SESSAO": "sessao-a"})
        self.assertFalse(self.p.indice.exists())

    def test_hook_nega_bundle_antes_de_gravar_teste(self):
        self.iniciar()
        evento = self.evento("preToolUse", tool_input={"command": "databricks bundle run algo -t sandbox -p teste",
                                                     "working_directory": str(self.raiz)})
        self.assertEqual(tratar(evento, self.politica, self.raiz)["permission"], "deny")
        self.assertIsNone(self.p.estado(self.p.pasta())["pendente"])

    def test_cwd_da_sessao_nao_comprova_execucao(self):
        self.iniciar()
        with self.assertRaisesRegex(ValueError, "Cwd"):
            self.hook("preToolUse", tool_input={"command": "python teste.py"})

    def test_shell_comum_sem_cwd_explicito_continua_sem_gerar_prova(self):
        self.iniciar()
        self.assertEqual(self.hook("preToolUse", tool_input={"command": "Get-Location"}), {"permission": "allow"})
        self.assertIsNone(self.p.estado(self.p.pasta())["pendente"])

    def test_prova_ausente_permite_registrar_impedimento(self):
        self.iniciar()
        r = self.executar()
        (self.p.pasta() / r["evidencia_ref"]).unlink()
        with self.assertRaises(ValueError):
            self.p.fechar("DONE", "Nao pode")
        self.assertEqual(self.p.fechar("BLOCKED", "Registro perdido")["status"], "BLOCKED")

    def test_manifesto_mudado_antes_do_resultado_nao_vira_prova(self):
        self.iniciar()
        self.hook("preToolUse")
        pasta = self.p.pasta()
        ref = self.p.estado(pasta)["pendente"]["manifesto"]
        manifesto = ler(pasta / ref)
        manifesto["arquivos"] = {}
        gravar(pasta / ref, manifesto, substituir=True)
        r = self.hook("postToolUse", tool_output='{"exitCode":0,"stdout":"ok"}')
        self.assertIn("inconclusivo", r["additional_context"])

    def test_cli_e_hooks_em_clone_com_espacos(self):
        clone = self.raiz / "clone com espacos"
        for pasta in ("implementacao", "adaptadores", "formas", "configuracao"):
            shutil.copytree(RAIZ / pasta, clone / pasta, ignore=shutil.ignore_patterns("__pycache__"))
        (clone / "src").mkdir()
        (clone / "src/a.py").write_text("# arquivo", encoding="utf-8")
        contrato = clone / "contrato.json"
        contrato.write_text(json.dumps(self.contrato), encoding="utf-8")

        def cli(*args):
            return subprocess.run([sys.executable, "adaptadores/prova.py", "--sessao", "sessao-a", *args],
                                  cwd=clone, capture_output=True, text=True, timeout=15)

        def hook(nome, **extras):
            evento = self.evento(nome, cwd=str(clone), tool_input={"command": "python teste.py",
                                                                 "working_directory": str(clone)})
            evento.update(extras)
            r = subprocess.run([sys.executable, "adaptadores/entrada.py", "cursor"], cwd=clone,
                               input=json.dumps(evento), text=True, capture_output=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            return json.loads(r.stdout)

        r = cli("iniciar", str(contrato))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(cli("fechar", "--resultado", "Sem prova").returncode, 2)
        negado = hook("preToolUse", tool_input={"command": "python teste.py"})
        self.assertEqual(negado["permission"], "deny")
        self.assertIn("Cwd", negado["agent_message"])
        hook("preToolUse")
        hook("postToolUse", tool_output='{"exitCode":0,"stdout":"ok"}')
        r = cli("fechar", "--resultado", "Verificado")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(hook("stop", status="completed"), {})
        (clone / "src/a.py").write_text("# editado", encoding="utf-8")
        self.assertIn("followup_message", hook("stop", status="completed"))

    def test_plan_so_gera_recibo_depois_de_resultado_atual(self):
        (self.raiz / "src/databricks.yml").write_text("bundle: {name: saneamento_migracao}\n", encoding="utf-8")
        comando = "databricks bundle plan -t sandbox -p teste --select etapa"
        self.contrato["aceite"][0]["verificacao"].update(comando=comando, cwd="src")
        self.iniciar()
        entrada = dict(command=comando, working_directory=str(self.raiz / "src"))
        self.hook("preToolUse", tool_input=entrada)
        self.assertFalse((self.p.registros / "plans").exists())
        self.hook("postToolUse", tool_input=entrada, tool_output='{"exitCode":0,"stdout":"plan"}')
        self.assertEqual(len(list((self.p.registros / "plans").glob("*.json"))), 1)
        negado = self.hook("preToolUse", tool_input=dict(entrada, command=comando.replace("plan", "deploy")))
        self.assertEqual(negado["permission"], "deny")
        self.assertIn("identidade_destinos_pendentes", negado["agent_message"])

    def test_log_omite_segredos_comuns(self):
        self.iniciar()
        r = self.executar(saida="Bearer segredo\ntoken=valor\ndapi123456789012345678901234")
        evento = ler(self.p.pasta() / r["evidencia_ref"])
        log = (self.p.pasta() / evento["dados"]["log_ref"]).read_text(encoding="utf-8")
        self.assertNotIn("segredo", log)
        self.assertNotIn("token=valor", log)

    def test_escrita_exclusiva_e_referencia_fora_da_raiz(self):
        arquivo = self.raiz / "registro.json"
        gravar(arquivo, {"a": 1})
        with self.assertRaises(FileExistsError):
            gravar(arquivo, {"a": 2})
        with self.assertRaises(ValueError):
            dentro(self.raiz, "../fora.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
