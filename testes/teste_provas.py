"""Provas persistidas e protocolos Cursor, com processos e arquivos locais."""
import copy
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from formas import dentro, validar, validar_dados
from provas import Provas, ler, gravar, trava
import prova as adaptador_prova
from cursor.prova import tratar


class ProvasTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/provas" / self.fixture_id
        self.raiz.parent.mkdir(parents=True, exist_ok=True)
        self.raiz.mkdir()
        self.addCleanup(self.limpar_fixture)
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("# trabalho anterior\n", encoding="utf-8")
        (self.raiz / "docs").mkdir()
        (self.raiz / "configuracao").mkdir()
        self.politica = {"bundle_local": str(self.raiz / "src"), "bundle_nome": "saneamento_migracao",
                         "registros_raiz": str(self.raiz / ".execucoes"),
                         "agentes_obrigatorios": {"claude_code": [], "cursor": []}}
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a")
        self.contrato = dict(objetivo="Verificar a mudanca", termino_fatia="Teste e fecho validos",
                             trilha="correcao", superficie=["src/a.py"], artefatos_raiz=".execucoes/provas",
                             fora=[], fontes=["src/a.py"], prazo=None,
                             aceite=[dict(id="c1", tipo="teste", obrigatorio=True, esperado="Processo termina em 0",
                                          verificacao=dict(comando="python teste.py", cwd=".", caminhos=["src"]))],
                             orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"})

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/provas").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino)

    def iniciar(self):
        self.p.iniciar(self.contrato)

    def executar(self, codigo=0, saida="ok", chamada="t1", agente_id=None):
        self.assertTrue(self.p.antes(chamada, "python teste.py", str(self.raiz), "teste", agente_id))
        return self.p.depois(chamada, "python teste.py", codigo, saida)

    def ativar(self, *trilhas):
        self.politica["agentes_obrigatorios"]["cursor"] = list(trilhas)
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a", runtime="cursor")

    def chamar(self, chamada_id, papel):
        instante = datetime.now(timezone.utc).isoformat()
        return self.p.registrar_chamada(chamada_id, papel, "cursor",
                                        [{"nome": "agente_id", "valor": chamada_id}], instante, instante,
                                        "concluida")

    def revisar(self, veredito="nao_quebrei", achados=()):
        tentativas = [dict(id="t1", procedimento="Reproduzir o aceite", resultado="pass")]
        return self.p.revisar(dict(
            entrada=dict(intencao_ref="contrato.yaml", aceite_ref="contrato.yaml",
                         baseline_ref="baseline.json", provas_refs=[]),
            veredito=veredito, tentativas=tentativas if veredito == "nao_quebrei" else [],
            achados=[dict(id=a, categoria="lacuna", severidade="media", local="src/a.py:1",
                          evidencia_ref="contrato.yaml") for a in achados],
            cobertura=[dict(criterio_id=c["id"], coberto=True) for c in self.contrato["aceite"]]))

    def passagem_completa_de_manutencao(self):
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.chamar("call-prep", "test")
        self.chamar("call-implement", "implement")
        self.chamar("call-test", "test")
        self.executar(agente_id="call-test")
        self.chamar("call-refute", "refute")

    def evento(self, nome, **extras):
        evento = dict(hook_event_name=nome, conversation_id="sessao-a", cursor_version="teste",
                      tool_name="Shell", tool_use_id="t1", cwd=str(self.raiz),
                      tool_input={"command": "python teste.py", "working_directory": str(self.raiz)})
        evento.update(extras)
        return evento

    def hook(self, nome, **extras):
        return tratar(self.evento(nome, **extras), self.politica, self.raiz)

    def chamar_adaptador_prova(self, argumentos, claude_code_session_id=""):
        saida = io.StringIO()
        erro = io.StringIO()
        with patch.object(adaptador_prova, "RAIZ", self.raiz), \
             patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": claude_code_session_id}):
            with redirect_stdout(saida), redirect_stderr(erro):
                codigo = adaptador_prova.principal(argumentos)
        return codigo, saida.getvalue(), erro.getvalue()

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
        self.assertIn("nao_verificada", json.dumps(self.p.pendencias(self.p.pasta(), self.p.estado(self.p.pasta()))))

    def test_hook_falha_com_exit_code_no_texto_registra_fail(self):
        # Payload do Cursor 3.17.8 (sondagem P0.5): exit diferente de zero so como texto.
        self.iniciar()
        self.hook("preToolUse")
        self.hook("postToolUseFailure", failure_type="error", error_message="Command failed with exit code 3")
        pasta = self.p.pasta()
        prova = ler(pasta / self.p.estado(pasta)["provas"]["c1"]["ref"])
        self.assertEqual((prova["dados"]["exit_code"], prova["dados"]["exit_code_origem"]), (3, "texto_falha"))
        self.assertEqual(prova["dados"]["resultado"], "fail")

    def test_hook_negacao_ou_texto_inesperado_fica_inconclusivo(self):
        self.iniciar()
        for extras in (dict(failure_type="permission_denied", error_message="Command failed with exit code 1"),
                       dict(failure_type="error", error_message="Command failed with exit code 0"),
                       dict(failure_type="error", error_message="Falhou com exit code 3")):
            with self.subTest(**extras):
                chamada = extras["error_message"]
                self.hook("preToolUse", tool_use_id=chamada)
                r = self.hook("postToolUseFailure", tool_use_id=chamada, **extras)
                self.assertIn("inconclusivo", r["additional_context"])

    def test_cwd_da_ferramenta_e_saida_output_do_cursor_atual(self):
        self.iniciar()
        entrada = {"command": "python teste.py", "cwd": str(self.raiz), "timeout": 30000}
        self.assertEqual(self.hook("preToolUse", tool_input=entrada), {"permission": "allow"})
        r = self.hook("postToolUse", tool_input=entrada, tool_output='{"output":"ok\\r\\n","exitCode":0}')
        self.assertIn("pass", r["additional_context"])
        prova = ler(self.p.pasta() / r["additional_context"].split("registrada em ")[1].rstrip("."))
        self.assertEqual((self.p.pasta() / prova["dados"]["log_ref"]).read_text(encoding="utf-8").strip(), "ok")

    def test_cwd_vazio_do_cursor_atual_nao_comprova_execucao(self):
        self.iniciar()
        with self.assertRaisesRegex(ValueError, "campo cwd"):
            self.hook("preToolUse", tool_input={"command": "python teste.py", "cwd": "", "timeout": 30000})

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
        pasta = self.p.pasta()
        prova = ler(pasta / self.p.estado(pasta)["provas"]["c1"]["ref"])
        self.assertEqual(prova["dados"]["exit_code_origem"], "campo_resultado")
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
        for pasta in ("implementacao", "adaptadores", "formas", "configuracao", "agentes"):
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

    def test_plano_de_manutencao_inclui_decisao_de_teste_e_ordem_roteada(self):
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        chamadas = self.p.estado(self.p.pasta())["chamadas_previstas"]
        self.assertEqual([(c["etapa"], c["papel"]) for c in chamadas], [
            ("preparar_teste_se_necessario", "test"), ("escrita_por_superficie", "implement"),
            ("teste", "test"), ("refute", "refute")])

    def test_sessao_ativa_legada_usa_trilha_do_contrato_com_chave_vazia(self):
        self.iniciar()
        self.executar()
        estado_path = self.p.pasta() / "estado.json"
        legado = ler(estado_path)
        for campo in ("trilha", "chamadas_previstas", "chamadas_observadas"):
            legado.pop(campo, None)
        gravar(estado_path, legado, substituir=True)
        self.assertEqual(self.p.fechar("DONE", "Compatibilidade legada")["status"], "DONE")

    def test_chamadas_ativadas_validam_fatia_papel_ordem_e_fecho(self):
        self.politica["agentes_obrigatorios"]["cursor"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a", runtime="cursor")
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        with self.assertRaisesRegex(ValueError, "ordem prevista"):
            self.p.registrar_chamada("call-implement", "implement", "cursor",
                                     [{"nome": "subagent_id", "valor": "sub-1"}],
                                     datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
                                     "concluida")

        def chamada(chamada_id, papel):
            instante = datetime.now(timezone.utc).isoformat()
            return self.p.registrar_chamada(chamada_id, papel, "cursor",
                [{"nome": "agente_id", "valor": chamada_id}], instante, instante, "concluida")

        self.assertEqual(chamada("call-prep", "test")["etapa"], "preparar_teste_se_necessario")
        self.assertEqual(chamada("call-implement", "implement")["etapa"], "escrita_por_superficie")
        self.assertEqual(chamada("call-test", "test")["etapa"], "teste")
        self.executar(agente_id="call-test")
        self.assertEqual(chamada("call-refute", "refute")["etapa"], "refute")
        with self.assertRaisesRegex(ValueError, "revisao:ausente"):
            self.p.fechar("DONE", "Chamada do refute sem revisao registrada")
        self.revisar()
        self.assertEqual(self.p.fechar("DONE", "Chamadas, teste e revisao conferidos")["status"], "DONE")
        with self.assertRaisesRegex(ValueError, "nao prevista"):
            chamada("call-config", "config")

    def test_chamadas_obrigatorias_ausentes_impedem_done_e_chave_vazia_preserva_fluxo(self):
        self.politica["agentes_obrigatorios"]["cursor"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a", runtime="cursor")
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.executar()
        with self.assertRaisesRegex(ValueError, "chamada:"):
            self.p.fechar("DONE", "Nao pode")

        self.politica["agentes_obrigatorios"] = {"claude_code": [], "cursor": []}
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-chave-vazia")
        self.iniciar()
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Rollback para chave vazia")["status"], "DONE")

    def test_teste_ativado_exige_prova_de_subagente_test_observado(self):
        self.ativar("manutencao")
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.chamar("call-prep", "test")
        self.chamar("call-implement", "implement")
        self.chamar("call-test", "test")
        self.executar()  # rodou no principal, sem subagente
        self.chamar("call-refute", "refute")
        self.revisar()
        with self.assertRaisesRegex(ValueError, "teste_fora_do_test:c1"):
            self.p.fechar("DONE", "Teste do principal nao substitui o papel test")
        # ID de subagente de outro papel tambem nao vale.
        self.executar(chamada="t2", agente_id="call-implement")
        with self.assertRaisesRegex(ValueError, "teste_fora_do_test:c1"):
            self.p.fechar("DONE", "Teste fora do papel test")
        self.executar(chamada="t3", agente_id="call-test")
        pasta = self.p.pasta()
        prova = ler(pasta / self.p.estado(pasta)["provas"]["c1"]["ref"])
        self.assertEqual((prova["produtor"], prova["dados"]["agente_id"]), ("executor_teste", "call-test"))
        self.assertEqual(self.p.fechar("DONE", "Teste do subagente test observado")["status"], "DONE")

    def test_chave_vazia_aceita_teste_sem_subagente(self):
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Fluxo atual sem agentes")["status"], "DONE")

    def test_origem_do_exit_code_e_registrada_e_conferida(self):
        self.iniciar()
        self.assertTrue(self.p.antes("t1", "python teste.py", str(self.raiz), "teste"))
        ref = self.p.depois("t1", "python teste.py", 0, "ok", "evento_sucesso")["evidencia_ref"]
        self.assertEqual(ler(self.p.pasta() / ref)["dados"]["exit_code_origem"], "evento_sucesso")
        self.assertTrue(self.p.antes("t2", "python teste.py", str(self.raiz), "teste"))
        with self.assertRaisesRegex(ValueError, "Evento de sucesso exige exit 0"):
            self.p.depois("t2", "python teste.py", 1, "erro", "evento_sucesso")

    def test_criterio_inspecao_sem_comando_fecha_e_edicao_requer_reinspecao(self):
        (self.raiz / "docs/nota.md").write_text("fato inicial", encoding="utf-8")
        self.contrato.update(trilha="docs", superficie=["docs/nota.md"])
        self.contrato["aceite"] = [dict(id="doc", tipo="inspecao_documental", obrigatorio=True,
            esperado="Afirmação sustentada", verificacao={"caminhos": ["docs/nota.md"],
            "checagens": [{"id": "fonte", "esperado": "A fonte sustenta a afirmação"}],
            "produtor": "refute"})]
        self.iniciar()
        self.p.inspecionar("doc", [{"id": "fonte", "resultado": "pass"}])
        inspecao = ler(self.p.pasta() / self.p.estado(self.p.pasta())["inspecoes"]["doc"]["ref"])
        self.assertEqual(inspecao["produtor"], "refute")
        self.assertEqual(self.p.fechar("DONE", "Documento inspecionado")["status"], "DONE")
        (self.raiz / "docs/nota.md").write_text("fato alterado", encoding="utf-8")
        self.assertFalse(self.p.conferir()["fecho_valido"])
        with self.assertRaisesRegex(ValueError, "obsoleta"):
            self.p.fechar("DONE", "Nao pode")
        self.p.inspecionar("doc", [{"id": "fonte", "resultado": "pass"}])
        self.assertEqual(self.p.fechar("DONE", "Reinspecionado")["status"], "DONE")

    def test_chave_vazia_preserva_prova_de_ambiente_por_comando(self):
        self.contrato.update(trilha="novo")
        self.contrato["aceite"][0]["tipo"] = "ambiente"
        self.iniciar()
        self.assertEqual(self.executar()["resultado"], "pass")
        self.assertEqual(self.p.fechar("DONE", "Comportamento anterior a ativacao")["status"], "DONE")

    def test_ambiente_sem_autorizacao_com_trilha_ativada_vai_para_decide_sem_dab(self):
        self.ativar("manutencao")
        self.contrato.update(trilha="manutencao", superficie=["src/a.py"])
        self.contrato["aceite"][0].update(tipo="ambiente")
        self.contrato["aceite"][0]["verificacao"].update(comando="databricks bundle validate",
                                                            caminhos=["src"])
        self.iniciar()
        estado = self.p.estado(self.p.pasta())
        self.assertNotIn("dab", [c["papel"] for c in estado["chamadas_previstas"]])
        with self.assertRaisesRegex(ValueError, "autorizacao_ambiente"):
            self.p.fechar("DONE", "Nao pode sem autorizacao")
        self.assertEqual(self.p.fechar("DECIDE", "Autorizacao especifica ausente")["status"], "DECIDE")

    def test_autorizacao_ambiente_inexistente_nao_planeja_dab_e_preserva_pendencia(self):
        self.ativar("manutencao")
        self.contrato.update(trilha="manutencao", superficie=["src/a.py"])
        criterio = self.contrato["aceite"][0]
        criterio.update(tipo="ambiente", autorizacao_ref="docs/autorizacao.txt")
        criterio["verificacao"].update(comando="databricks bundle validate", caminhos=["src"])
        self.iniciar()
        pasta = self.p.pasta()
        estado = self.p.estado(pasta)
        self.assertEqual(estado["schema_versao"], "3.2")
        self.assertNotIn("docs/autorizacao.txt", estado["autorizacoes"].values())
        self.assertNotIn("dab", [c["papel"] for c in estado["chamadas_previstas"]])
        self.assertIsNone(ler(pasta / "baseline.json")["arquivos"]["docs/autorizacao.txt"])
        with self.assertRaisesRegex(ValueError, "autorizacao_ambiente"):
            self.p.fechar("DONE", "Nao pode sem arquivo de autorizacao")
        self.assertEqual(self.p.fechar("DECIDE", "Registro de autorizacao ausente") ["status"], "DECIDE")

    def test_autorizacao_valida_planeja_dab_registra_manifesto_e_edicao_invalida_chamada(self):
        autorizacao = self.raiz / "docs/autorizacao.txt"
        autorizacao.write_text("Autorizacao da tarefa", encoding="utf-8")
        self.contrato.update(trilha="manutencao", superficie=["src/a.py"])
        criterio = self.contrato["aceite"][0]
        criterio.update(tipo="ambiente", autorizacao_ref="docs/autorizacao.txt")
        criterio["verificacao"].update(comando="databricks bundle validate", caminhos=["src"])
        self.politica["agentes_obrigatorios"]["cursor"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a", runtime="cursor")
        self.iniciar()
        pasta = self.p.pasta()
        estado = self.p.estado(pasta)
        self.assertEqual(estado["autorizacoes"], {"c1": "docs/autorizacao.txt"})
        self.assertEqual([c["papel"] for c in estado["chamadas_previstas"]], ["test", "implement", "refute", "dab"])
        self.assertEqual(ler(pasta / "baseline.json")["arquivos"]["docs/autorizacao.txt"],
                         ler(pasta / estado["manifestos_autorizacao"]["c1"])["arquivos"]["docs/autorizacao.txt"])

        ultima = None
        for numero, chamada in enumerate(estado["chamadas_previstas"], start=1):
            instante = datetime.now(timezone.utc).isoformat()
            ultima = self.p.registrar_chamada(
                f"call-{numero}", chamada["papel"], "cursor",
                [{"nome": "subagent_id", "valor": f"sub-{numero}"}], instante, instante, "concluida")
        evento_dab = ler(pasta / ultima["evidencia_ref"])
        self.assertEqual(evento_dab["dados"]["papel"], "dab")
        self.assertEqual(evento_dab["manifesto_ref"], self.p.estado(pasta)["manifestos_autorizacao"]["c1"])
        self.assertEqual(self.p.chamadas_faltantes(pasta, self.p.estado(pasta)), [])
        with self.assertRaisesRegex(ValueError, "c1"):
            self.p.fechar("DONE", "Nao pode sem resultado observado da operacao")
        self.assertTrue(self.p.antes("op-1", "databricks bundle validate", str(self.raiz), "teste"))
        self.assertEqual(self.p.depois("op-1", "databricks bundle validate", 0, "ok")["resultado"], "pass")
        self.revisar()
        self.assertEqual(self.p.fechar("DONE", "Operacao autorizada observada")["status"], "DONE")

        autorizacao.write_text("Autorizacao editada", encoding="utf-8")
        self.assertIn("dab", self.p.chamadas_faltantes(pasta, self.p.estado(pasta)))
        with self.assertRaisesRegex(ValueError, "autorizacao_ambiente"):
            self.p.fechar("DONE", "Nao pode com autorizacao alterada")
        self.assertEqual(self.p.fechar("DECIDE", "Autorizacao precisa ser renovada") ["status"], "DECIDE")

    def test_autorizacao_em_area_ignorada_e_rejeitada(self):
        self.contrato.update(trilha="manutencao", superficie=["src/a.py"])
        criterio = self.contrato["aceite"][0]
        criterio.update(tipo="ambiente", autorizacao_ref=".execucoes/aprovacao.txt")
        criterio["verificacao"].update(comando="databricks bundle validate", caminhos=["src"])
        with self.assertRaisesRegex(ValueError, "area ignorada"):
            self.iniciar()

    def test_edicao_apos_revisao_exige_retorno_novo_teste_e_nova_revisao(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        revisao = self.revisar("com_achados", ["A1"])["evidencia_ref"]
        with self.assertRaisesRegex(ValueError, "achado:A1:sem_triagem"):
            self.p.fechar("DONE", "Achado sem tratamento")

        (self.raiz / "src/a.py").write_text("# requisito que faltava\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revisao:obsoleta"):
            self.p.fechar("DONE", "Edicao posterior a revisao")
        pasta = self.p.pasta()
        self.assertEqual(self.chamar("call-implement-2", "implement")["etapa"], "escrita_por_superficie")
        self.assertEqual(self.p.chamadas_faltantes(pasta, self.p.estado(pasta)), ["teste", "refute"])
        self.assertEqual(self.chamar("call-test-2", "test")["etapa"], "teste")
        resolucao = self.executar(chamada="t2", agente_id="call-test-2")["evidencia_ref"]
        self.p.triar(dict(revisao_ref=revisao, achado_id="A1", decisao="procedente",
                          responsavel="implement", evidencia_resolucao_ref=resolucao))
        with self.assertRaisesRegex(ValueError, "chamada:refute"):
            self.p.fechar("DONE", "Correcao sem nova revisao")
        self.chamar("call-refute-2", "refute")
        self.revisar()
        self.assertEqual(self.p.fechar("DONE", "Achado corrigido e revisado de novo")["status"], "DONE")

    def test_achado_descartado_com_motivo_permite_done_e_inconclusivo_nao(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        self.revisar("inconclusivo")
        with self.assertRaisesRegex(ValueError, "revisao:inconclusiva"):
            self.p.fechar("DONE", "Revisao inconclusiva")
        revisao = self.revisar("com_achados", ["A1"])["evidencia_ref"]
        with self.assertRaisesRegex(ValueError, "Achado ausente"):
            self.p.triar(dict(revisao_ref=revisao, achado_id="A9", decisao="descartado",
                              responsavel="coordenador", motivo_descarte="Inexistente"))
        with self.assertRaisesRegex(ValueError, "Revisao nao registrada"):
            self.p.triar(dict(revisao_ref="contrato.yaml", achado_id="A1", decisao="descartado",
                              responsavel="coordenador", motivo_descarte="Ref errada"))
        self.p.triar(dict(revisao_ref=revisao, achado_id="A1", decisao="descartado",
                          responsavel="coordenador", motivo_descarte="O requisito citado esta fora do contrato"))
        self.assertEqual(self.p.fechar("DONE", "Falso positivo descartado")["status"], "DONE")

    def test_review_fecha_done_com_achados_sem_editar(self):
        self.ativar("review")
        self.contrato.update(trilha="review")
        self.contrato["aceite"] = [dict(id="codigo", tipo="analise_codigo", obrigatorio=True,
            esperado="Riscos apontados", verificacao={"caminhos": ["src/a.py"],
            "checagens": [{"id": "riscos", "esperado": "Riscos com local"}], "produtor": "coordenador"})]
        self.iniciar()
        self.assertEqual([c["papel"] for c in self.p.estado(self.p.pasta())["chamadas_previstas"]], ["refute"])
        self.chamar("call-refute", "refute")
        self.p.inspecionar("codigo", [{"id": "riscos", "resultado": "pass"}])
        self.revisar("com_achados", ["S1"])
        self.assertEqual(self.p.fechar("DONE", "Veredito com_achados entregue")["status"], "DONE")

    def test_superficie_em_diretorio_atribui_escritor_e_item_sem_papel_recusa_inicio(self):
        self.contrato.update(trilha="manutencao", superficie=["src/dados.json"])
        self.iniciar()  # Chave vazia: comportamento atual, sem exigir atribuição.
        self.p.fechar("BLOCKED", "Somente conferencia do plano")

        self.ativar("manutencao")
        self.contrato["superficie"] = ["src"]
        self.iniciar()
        self.assertIn("implement", [c["papel"] for c in self.p.estado(self.p.pasta())["chamadas_previstas"]])
        self.p.fechar("BLOCKED", "Somente conferencia do plano")
        self.contrato["superficie"] = ["src/dados.json"]
        with self.assertRaisesRegex(ValueError, "sem papel de escrita"):
            self.iniciar()

    def test_paridade_preve_chamada_de_test_em_novo(self):
        self.contrato.update(trilha="novo")
        self.contrato["aceite"][0]["tipo"] = "paridade"
        self.iniciar()
        etapas = [(c["etapa"], c["papel"]) for c in self.p.estado(self.p.pasta())["chamadas_previstas"]]
        self.assertIn(("teste", "test"), etapas)

    def test_runtime_so_e_exigido_na_trilha_ativada(self):
        self.ativar("correcao")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-a")
        with self.assertRaisesRegex(ValueError, "Runtime explicito"):
            self.iniciar()
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Trilha fora da chave")["status"], "DONE")

    def test_adaptador_passa_runtime_explicito_detecta_claude_e_recusa_ausencia(self):
        contrato_path = self.raiz / "contrato.yaml"
        contrato_path.write_text(json.dumps(self.contrato), encoding="utf-8")
        argumentos = ["--sessao", "sessao-cli", "iniciar", str(contrato_path)]

        codigo, _, erro = self.chamar_adaptador_prova(argumentos)
        self.assertEqual(codigo, 0, erro)
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", "sessao-cli", "fechar", "--status", "BLOCKED",
             "--resultado", "Fluxo atual com a chave vazia"])
        self.assertEqual(codigo, 0, erro)

        sessao_sem_runtime = "sessao-fecho-sem-runtime"
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", sessao_sem_runtime, "iniciar", str(contrato_path)])
        self.assertEqual(codigo, 0, erro)

        self.politica["agentes_obrigatorios"]["cursor"] = ["correcao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        fechar_sem_runtime = ["--sessao", sessao_sem_runtime, "fechar", "--status", "BLOCKED",
                              "--resultado", "Conferência da exigência de runtime"]
        codigo, _, erro = self.chamar_adaptador_prova(fechar_sem_runtime)
        self.assertEqual(codigo, 2)
        self.assertIn("Runtime explicito", erro)

        codigo, _, erro = self.chamar_adaptador_prova(
            ["--runtime", "cursor", *fechar_sem_runtime])
        self.assertEqual(codigo, 0, erro)

        sessao_cursor = "sessao-cursor-cli"
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", sessao_cursor, "iniciar", str(contrato_path)])
        self.assertEqual(codigo, 2)
        self.assertIn("Runtime explicito", erro)

        codigo, _, erro = self.chamar_adaptador_prova(
            ["--runtime", "cursor", "--sessao", sessao_cursor, "iniciar", str(contrato_path)])
        self.assertEqual(codigo, 0, erro)
        provas_cursor = Provas(self.raiz, self.politica["registros_raiz"], sessao_cursor)
        estado_cursor = provas_cursor.estado(provas_cursor.pasta())
        self.assertEqual(estado_cursor["runtime"], "cursor")
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--runtime", "cursor", "--sessao", sessao_cursor, "fechar", "--status", "BLOCKED",
             "--resultado", "Runtime encaminhado ao núcleo"])
        self.assertEqual(codigo, 0, erro)

        self.politica["agentes_obrigatorios"]["claude_code"] = ["correcao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        sessao_claude = "sessao-claude-cli"
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", sessao_claude, "iniciar", str(contrato_path)],
            claude_code_session_id="id-da-sessao")
        self.assertEqual(codigo, 0, erro)
        provas_claude = Provas(self.raiz, self.politica["registros_raiz"], sessao_claude)
        self.assertEqual(provas_claude.estado(provas_claude.pasta())["runtime"], "claude_code")
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", sessao_claude, "fechar", "--status", "BLOCKED",
             "--resultado", "Runtime detectado pelo ambiente"])
        self.assertEqual(codigo, 0, erro)

    def test_hook_sem_diretorio_com_criterio_de_inspecao_libera_shell(self):
        (self.raiz / "docs/nota.md").write_text("fato", encoding="utf-8")
        self.contrato.update(trilha="docs", superficie=["docs/nota.md"])
        self.contrato["aceite"] = [dict(id="doc", tipo="inspecao_documental", obrigatorio=True,
            esperado="Afirmação sustentada", verificacao={"caminhos": ["docs/nota.md"],
            "checagens": [{"id": "fonte", "esperado": "A fonte sustenta a afirmação"}],
            "produtor": "coordenador"})]
        self.iniciar()
        self.assertEqual(self.hook("preToolUse", tool_input={"command": "git status"}), {"permission": "allow"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
