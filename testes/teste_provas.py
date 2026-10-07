"""Provas persistidas e protocolos Cursor, com processos e arquivos locais."""
import copy
from hashlib import sha256
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

    def payload_revisao(self, veredito="nao_quebrei", achados=()):
        tentativas = [dict(id="t1", procedimento="Reproduzir o aceite", resultado="pass")]
        return dict(
            entrada=dict(intencao_ref="contrato.yaml", aceite_ref="contrato.yaml",
                         baseline_ref="baseline.json", provas_refs=[]),
            veredito=veredito, tentativas=tentativas if veredito == "nao_quebrei" else [],
            achados=[dict(id=a, categoria="lacuna", severidade="media", local="src/a.py:1",
                          evidencia_ref="contrato.yaml") for a in achados],
            cobertura=[dict(criterio_id=c["id"], coberto=True) for c in self.contrato["aceite"]])

    def revisar(self, veredito="nao_quebrei", achados=(), agente_id="call-refute"):
        return self.p.revisar(dict(self.payload_revisao(veredito, achados), agente_id=agente_id))

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
        # Payload do Cursor 3.17.8: exit diferente de zero so como texto.
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
        self.assertIn("--runtime cursor", r["additional_context"])
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

    def test_e0_chave_real_ativa_so_manutencao_no_cursor_e_esvaziar_restaura(self):
        real = ler(RAIZ / "configuracao/politica.json")["agentes_obrigatorios"]
        self.assertEqual(real, {"claude_code": [], "cursor": ["manutencao"]})
        self.politica["agentes_obrigatorios"] = real
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.contrato["trilha"] = "manutencao"
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-sem-runtime")
        with self.assertRaisesRegex(ValueError, "Runtime explicito"):
            self.iniciar()
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-claude", runtime="claude_code")
        self.assertFalse(self.p.ativada("manutencao", "claude_code"))
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-cursor", runtime="cursor")
        self.assertFalse(self.p.ativada("correcao", "cursor"))
        self.iniciar()
        self.executar()
        with self.assertRaisesRegex(ValueError, "chamada:"):
            self.p.fechar("DONE", "Sem as chamadas previstas")

        self.politica["agentes_obrigatorios"] = {"claude_code": [], "cursor": []}
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.p = Provas(self.raiz, self.politica["registros_raiz"], "sessao-rollback")
        self.iniciar()
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Chave vazia restaura o fluxo atual")["status"], "DONE")

    def test_codex_e_opencode_iniciam_e_fecham_manutencao_sem_chamadas(self):
        self.politica["agentes_obrigatorios"]["cursor"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        contrato = copy.deepcopy(self.contrato)
        contrato.update(trilha="manutencao", superficie=["src/a.py"])
        contrato["aceite"] = [dict(
            id="escopo", tipo="analise_codigo", obrigatorio=True,
            esperado="O estado pode ser inspecionado sem chamada de agente obrigatoria",
            verificacao=dict(caminhos=["src/a.py"],
                             checagens=[dict(id="fluxo_unico", esperado="Nenhuma chamada obrigatoria")],
                             produtor="coordenador"))]
        contrato_path = self.raiz / "contrato-runtime.yaml"
        contrato_path.write_text(json.dumps(contrato), encoding="utf-8")

        for runtime in ("codex", "opencode"):
            with self.subTest(runtime=runtime):
                sessao = "sessao-" + runtime
                base = ["--runtime", runtime, "--sessao", sessao]
                codigo, _, erro = self.chamar_adaptador_prova([*base, "iniciar", str(contrato_path)])
                self.assertEqual(codigo, 0, erro)
                provas = Provas(self.raiz, self.politica["registros_raiz"], sessao, runtime=runtime)
                estado = provas.estado(provas.pasta())
                self.assertEqual(estado["runtime"], runtime)
                self.assertFalse(provas.ativada("manutencao", runtime))
                self.assertEqual(estado["chamadas_observadas"], [])

                inspecao = self.arquivo_yaml("inspecao-" + runtime + ".yaml", dict(
                    criterio_id="escopo", checagens=[dict(id="fluxo_unico", resultado="pass")]))
                codigo, _, erro = self.chamar_adaptador_prova([*base, "inspecionar", inspecao])
                self.assertEqual(codigo, 0, erro)
                codigo, _, erro = self.chamar_adaptador_prova(
                    [*base, "fechar", "--resultado", "Runtime explicito sem chamadas obrigatorias"])
                self.assertEqual(codigo, 0, erro)
                conferido = provas.conferir()
                self.assertEqual(conferido["status"], "DONE")
                self.assertTrue(conferido["fecho_valido"])

    def test_runtime_ausente_e_chave_codex_na_politica_seguem_recusados(self):
        self.politica["agentes_obrigatorios"]["cursor"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        self.contrato["trilha"] = "manutencao"
        contrato_path = self.raiz / "contrato-runtime-ausente.yaml"
        contrato_path.write_text(json.dumps(self.contrato), encoding="utf-8")
        codigo, _, erro = self.chamar_adaptador_prova(
            ["--sessao", "sessao-cli-sem-runtime", "iniciar", str(contrato_path)])
        self.assertEqual(codigo, 2)
        self.assertIn("Runtime explicito", erro)

        self.politica["agentes_obrigatorios"]["codex"] = ["manutencao"]
        (self.raiz / "configuracao/politica.json").write_text(json.dumps(self.politica), encoding="utf-8")
        provas = Provas(self.raiz, self.politica["registros_raiz"], "sessao-politica-codex", runtime="codex")
        with self.assertRaisesRegex(ValueError, "agentes_obrigatorios deve ser configurado por runtime"):
            provas.politica()

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
        criterio["verificacao"].update(comando="databricks bundle validate -t sandbox -p teste", caminhos=["src"])
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
                [{"nome": "agente_id", "valor": f"sub-{numero}"}], instante, instante, "concluida")
        evento_dab = ler(pasta / ultima["evidencia_ref"])
        self.assertEqual(evento_dab["dados"]["papel"], "dab")
        self.assertEqual(evento_dab["manifesto_ref"], self.p.estado(pasta)["manifestos_autorizacao"]["c1"])
        self.assertEqual(self.p.chamadas_faltantes(pasta, self.p.estado(pasta)), [])
        with self.assertRaisesRegex(ValueError, "c1"):
            self.p.fechar("DONE", "Nao pode sem resultado observado da operacao")
        self.assertTrue(self.p.antes("op-1", "databricks bundle validate -t sandbox -p teste", str(self.raiz), "teste"))
        self.assertEqual(self.p.depois("op-1", "databricks bundle validate -t sandbox -p teste", 0, "ok")["resultado"], "pass")
        self.revisar(agente_id="sub-3")
        with self.assertRaisesRegex(ValueError, "sandbox_ausente:c1"):
            self.p.fechar("DONE", "Nao pode sem o registro de ambiente")
        self.p.registrar_sandbox("c1", dict(identidade="nao_verificado", destinos_resolvidos=["nao_verificado"],
                                            coordenacao="nao_verificado", agente_id="sub-4"))
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

        self.p.abrir_chamada("call-implement-2", "implement")
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
        self.revisar(agente_id="call-refute-2")
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

    def iniciar_superficie_mista(self):
        """Manutenção ativada com YAML e Python na superfície: config e implement no plano."""
        (self.raiz / "src/regra.yaml").write_text("regra: 1\n", encoding="utf-8")
        self.contrato.update(trilha="manutencao", superficie=["src/a.py", "src/regra.yaml"])
        self.ativar("manutencao")
        self.iniciar()

    def escrever(self, chamada_id, papel, arquivo, texto):
        self.p.abrir_chamada(chamada_id, papel)
        (self.raiz / arquivo).write_text(texto, encoding="utf-8")
        return self.chamar(chamada_id, papel)

    def pendencias_atuais(self):
        pasta = self.p.pasta()
        return self.p.pendencias(pasta, self.p.estado(pasta))[1]

    def test_c5_cada_papel_na_sua_superficie_nao_gera_pendencia(self):
        self.iniciar_superficie_mista()
        self.chamar("call-prep", "test")
        self.escrever("call-config", "config", "src/regra.yaml", "regra: 2\n")
        self.escrever("call-implement", "implement", "src/a.py", "# nova regra\n")
        self.assertFalse([p for p in self.pendencias_atuais() if "superficie" in p or "papel" in p])

    def test_c5_papel_fora_da_sua_classe_viola_superficie(self):
        self.iniciar_superficie_mista()
        self.chamar("call-prep", "test")
        self.escrever("call-config", "config", "src/a.py", "# config editou codigo\n")
        self.p.abrir_chamada("call-implement", "implement")
        (self.raiz / "src/regra.yaml").write_text("regra: 3\n", encoding="utf-8")
        self.chamar("call-implement", "implement")
        pendencias = self.pendencias_atuais()
        self.assertIn("superficie_violada:config:src/a.py", pendencias)
        self.assertIn("superficie_violada:implement:src/regra.yaml", pendencias)
        with self.assertRaisesRegex(ValueError, "superficie_violada"):
            self.p.fechar("DONE", "Papel fora da superficie")

    def test_c5_escrita_fora_da_superficie_do_contrato_viola(self):
        self.iniciar_superficie_mista()  # Verificação cobre src/, a superfície só dois arquivos.
        self.chamar("call-prep", "test")
        self.escrever("call-implement", "implement", "src/extra.py", "# fora do contrato\n")
        self.assertIn("superficie_violada:implement:src/extra.py", self.pendencias_atuais())

    def test_c5_edicao_do_principal_fora_de_janela_impede_done(self):
        self.iniciar_superficie_mista()
        self.chamar("call-prep", "test")
        (self.raiz / "src/a.py").write_text("# principal editou\n", encoding="utf-8")
        self.assertIn("edicao_fora_do_papel:src/a.py", self.pendencias_atuais())
        # Abrir a janela depois não transfere a autoria ao papel.
        self.escrever("call-config", "config", "src/regra.yaml", "regra: 2\n")
        self.assertIn("edicao_fora_do_papel:src/a.py", self.pendencias_atuais())

    def test_c5_janelas_sobrepostas_com_edicao_ficam_inconclusivas(self):
        self.iniciar_superficie_mista()
        self.chamar("call-prep", "test")
        self.p.abrir_chamada("call-config", "config")
        self.p.abrir_chamada("call-implement", "implement")
        self.assertIn("chamada_aberta:call-config", self.pendencias_atuais())
        (self.raiz / "src/a.py").write_text("# autoria ambigua\n", encoding="utf-8")
        self.chamar("call-config", "config")
        self.chamar("call-implement", "implement")
        pendencias = self.pendencias_atuais()
        self.assertIn("superficie_inconclusiva:call-config", pendencias)
        self.assertIn("superficie_inconclusiva:call-implement", pendencias)

    def test_c5_chamada_encerrada_sem_registro_ainda_e_conferida(self):
        self.iniciar_superficie_mista()
        self.p.abrir_chamada("call-config", "config")
        (self.raiz / "src/a.py").write_text("# chamada que falhou\n", encoding="utf-8")
        self.assertTrue(self.p.encerrar_chamada("call-config"))
        self.assertIn("superficie_violada:config:src/a.py", self.pendencias_atuais())

    def iniciar_docs(self):
        (self.raiz / "docs/nota.md").write_text("fato\n", encoding="utf-8")
        self.contrato.update(trilha="docs", superficie=["docs/nota.md"])
        self.contrato["aceite"] = [dict(id="doc", tipo="inspecao_documental", obrigatorio=True,
            esperado="Afirmação sustentada", verificacao={"caminhos": ["docs/nota.md"],
            "checagens": [{"id": "fonte", "esperado": "A fonte sustenta a afirmação"}],
            "produtor": "coordenador"})]
        self.ativar("docs")
        self.iniciar()

    def test_c5_docs_na_sua_superficie_nao_gera_pendencia(self):
        self.iniciar_docs()
        self.assertIn("vigilancia_superficie", self.p.estado(self.p.pasta()))
        self.escrever("call-docs", "docs", "docs/nota.md", "fato com fonte\n")
        self.assertFalse([p for p in self.pendencias_atuais() if "superficie" in p or "papel" in p])

    def test_c5_edicao_do_principal_no_documento_impede_done(self):
        # Coordenador que corrige o guia sozinho: o núcleo precisa ver a edição.
        self.iniciar_docs()
        self.escrever("call-docs", "docs", "docs/nota.md", "fato com fonte\n")
        (self.raiz / "docs/nota.md").write_text("principal corrigiu\n", encoding="utf-8")
        self.assertIn("edicao_fora_do_papel:docs/nota.md", self.pendencias_atuais())
        self.p.inspecionar("doc", [{"id": "fonte", "resultado": "pass"}])
        with self.assertRaisesRegex(ValueError, "edicao_fora_do_papel"):
            self.p.fechar("DONE", "Principal escreveu o documento")

    def test_c5_chave_vazia_nao_vigia_superficie(self):
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.assertNotIn("vigilancia_superficie", self.p.estado(self.p.pasta()))
        self.assertFalse(self.p.abrir_chamada("call-implement", "implement"))
        (self.raiz / "src/a.py").write_text("# sem chave\n", encoding="utf-8")
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Fluxo atual preservado")["status"], "DONE")

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

    def arquivo_yaml(self, nome, dados):
        caminho = self.raiz / nome
        caminho.write_text(json.dumps(dados), encoding="utf-8")  # JSON é subconjunto de YAML.
        return str(caminho)

    def test_cli_inspecao_fecha_done_com_chave_vazia(self):
        (self.raiz / "docs/nota.md").write_text("fato", encoding="utf-8")
        self.contrato.update(trilha="docs", superficie=["docs/nota.md"])
        self.contrato["aceite"] = [dict(id="doc", tipo="inspecao_documental", obrigatorio=True,
            esperado="Afirmação sustentada", verificacao={"caminhos": ["docs/nota.md"],
            "checagens": [{"id": "fonte", "esperado": "A fonte sustenta a afirmação"}],
            "produtor": "refute"})]
        base = ["--sessao", "sessao-cli-inspecao"]
        codigo, _, erro = self.chamar_adaptador_prova(
            [*base, "iniciar", self.arquivo_yaml("contrato-cli.yaml", self.contrato)])
        self.assertEqual(codigo, 0, erro)
        codigo, _, erro = self.chamar_adaptador_prova(
            [*base, "fechar", "--resultado", "Sem inspecao"])
        self.assertEqual(codigo, 2)
        self.assertIn("doc", erro)
        codigo, saida, erro = self.chamar_adaptador_prova(
            [*base, "inspecionar", self.arquivo_yaml("inspecao.yaml", dict(
                criterio_id="doc", checagens=[{"id": "fonte", "resultado": "pass"}]))])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["resultado"], "pass")
        codigo, saida, erro = self.chamar_adaptador_prova([*base, "fechar", "--resultado", "Inspecionado"])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["status"], "DONE")
        codigo, _, erro = self.chamar_adaptador_prova(
            [*base, "inspecionar", self.arquivo_yaml("outra.yaml", dict(criterio_id="nenhum", checagens=[]))])
        self.assertEqual(codigo, 2)

    def test_cli_revisao_ativada_exige_agente_de_chamada_refute_concluida(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        base = ["--runtime", "cursor", "--sessao", "sessao-a"]

        def revisar_cli(**extras):
            codigo, saida, erro = self.chamar_adaptador_prova(
                [*base, "revisar", self.arquivo_yaml("revisao.yaml", dict(self.payload_revisao(), **extras))])
            self.assertEqual(codigo, 0, erro)
            return json.loads(saida)

        def pendencias():
            return json.loads(self.chamar_adaptador_prova([*base, "estado"])[1])["pendencias"]

        revisar_cli()  # Sem agente_id: ninguem prova que veio de um refute observado.
        self.assertEqual(pendencias(), ["revisao:fora_do_refute"])
        revisar_cli(agente_id="call-test")  # ID de outro papel.
        self.assertEqual(pendencias(), ["revisao:fora_do_refute"])
        codigo, _, erro = self.chamar_adaptador_prova([*base, "fechar", "--resultado", "Nao pode"])
        self.assertEqual(codigo, 2)
        self.assertIn("revisao:fora_do_refute", erro)
        revisar_cli(agente_id="call-refute")
        self.assertEqual(pendencias(), [])
        pasta = self.p.pasta()
        revisao = self.p.estado(pasta)["revisoes"][-1]
        ataque = ler(pasta / revisao["ref"])
        self.assertEqual(ataque["dados"]["agente_id"], "call-refute")
        ataque["dados"]["agente_id"] = "call-test"
        (pasta / revisao["ref"]).write_text(json.dumps(ataque), encoding="utf-8")
        self.assertEqual(pendencias(), ["revisao:invalida"])
        # Uma revisão nova sem o ID observado permanece pendente.
        codigo, _, erro = self.chamar_adaptador_prova(
            [*base, "revisar", self.arquivo_yaml("sem-id.yaml", self.payload_revisao())])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(pendencias(), ["revisao:fora_do_refute"])
        revisar_cli(agente_id="call-refute")
        codigo, saida, erro = self.chamar_adaptador_prova([*base, "fechar", "--resultado", "Revisao observada"])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["status"], "DONE")

    def test_cli_estado_mostra_o_agente_id_de_cada_chamada_observada(self):
        # Sem isso o coordenador do Cursor não tem de onde tirar o ID que revisar exige.
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        codigo, saida, erro = self.chamar_adaptador_prova(["--runtime", "cursor", "--sessao", "sessao-a", "estado"])
        self.assertEqual(codigo, 0, erro)
        chamadas = json.loads(saida)["chamadas"]
        self.assertEqual([(c["papel"], c["agente_id"]) for c in chamadas],
                         [("test", "call-prep"), ("implement", "call-implement"),
                          ("test", "call-test"), ("refute", "call-refute")])
        self.assertTrue(all(c["status"] == "concluida" for c in chamadas))

    def test_cli_ataque_sem_chamada_refute_observada_continua_pendente(self):
        self.ativar("manutencao")
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.chamar("call-prep", "test")
        self.chamar("call-implement", "implement")
        self.chamar("call-test", "test")
        self.executar(agente_id="call-test")
        base = ["--runtime", "cursor", "--sessao", "sessao-a"]
        codigo, _, erro = self.chamar_adaptador_prova(
            [*base, "revisar", self.arquivo_yaml("sem-refute.yaml",
                dict(self.payload_revisao(), agente_id="call-refute"))])
        self.assertEqual(codigo, 0, erro)
        self.assertIn("revisao:fora_do_refute", self.p.conferir()["pendencias"])
        codigo, _, erro = self.chamar_adaptador_prova([*base, "fechar", "--resultado", "Sem chamada"])
        self.assertEqual(codigo, 2)
        self.assertIn("revisao:fora_do_refute", erro)

    def test_refute_observado_sem_revisao_registrada_impede_done(self):
        # Primeiro refute com achado e só o segundo, limpo, registrado: falta a revisão do primeiro.
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        self.chamar("call-refute-2", "refute")
        self.revisar(agente_id="call-refute-2")
        self.assertIn("revisao:sem_registro:call-refute", self.pendencias_atuais())
        with self.assertRaisesRegex(ValueError, "revisao:sem_registro:call-refute"):
            self.p.fechar("DONE", "Achado do primeiro refute descartado sem registro")

    def test_achado_de_revisao_anterior_exige_triagem(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        primeira = self.revisar("com_achados", ["A1"])["evidencia_ref"]
        self.chamar("call-refute-2", "refute")
        self.revisar(agente_id="call-refute-2")
        self.assertEqual(self.pendencias_atuais(), ["achado:A1:sem_triagem"])
        self.p.triar(dict(revisao_ref=primeira, achado_id="A1", decisao="procedente",
                          responsavel="coordenador", evidencia_resolucao_ref="contrato.yaml"))
        self.assertEqual(self.pendencias_atuais(), [])
        self.assertEqual(self.p.fechar("DONE", "Achado tratado e revisado de novo")["status"], "DONE")

    def test_cli_triagem_registra_decisao_sobre_achado_da_revisao(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        base = ["--runtime", "cursor", "--sessao", "sessao-a"]
        revisao = self.revisar("com_achados", ["A1"])["evidencia_ref"]
        self.assertIn("achado:A1:sem_triagem", json.loads(self.chamar_adaptador_prova([*base, "estado"])[1])["pendencias"])
        codigo, saida, erro = self.chamar_adaptador_prova(
            [*base, "triar", self.arquivo_yaml("triagem.yaml", dict(
                revisao_ref=revisao, achado_id="A1", decisao="descartado", responsavel="coordenador",
                motivo_descarte="Fora do contrato"))])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["decisao"], "descartado")
        self.assertEqual(json.loads(self.chamar_adaptador_prova([*base, "estado"])[1])["pendencias"], [])

    def diagnostico_declarado(self, **extras):
        return dict(dict(sintoma="A carga termina sem as linhas do dia", hipotese_causa="O filtro exclui o ultimo dia",
                         base="derived", evidencia_ref="baseline.json", criterio_reproducao="c1",
                         proximo_passo="Reproduzir com o filtro corrigido"), **extras)

    def test_diagnosticar_registra_na_fatia_e_confere_o_criterio_de_reproducao(self):
        self.iniciar()
        resultado = self.p.diagnosticar(self.diagnostico_declarado())
        pasta = self.p.pasta()
        evento = ler(pasta / resultado["evidencia_ref"])
        self.assertEqual((evento["tipo"], evento["produtor"], evento["schema_versao"]),
                         ("diagnostico", "coordenador", "3.2"))
        self.p.diagnosticar(self.diagnostico_declarado(base="direct"), produtor="map")
        self.assertEqual(len(self.p.estado(pasta)["diagnosticos"]), 2)
        with self.assertRaisesRegex(ValueError, "Criterio de reproducao"):
            self.p.diagnosticar(self.diagnostico_declarado(criterio_reproducao="nenhum"))
        with self.assertRaisesRegex(ValueError, "Produtor de diagnostico"):
            self.p.diagnosticar(self.diagnostico_declarado(), produtor="refute")
        with self.assertRaisesRegex(ValueError, "base"):
            self.p.diagnosticar(self.diagnostico_declarado(base="chute"))
        with self.assertRaisesRegex(ValueError, "Evidencia ausente"):
            self.p.diagnosticar(self.diagnostico_declarado(evidencia_ref="logs/nao-existe.txt"))

    def test_diagnostico_com_criterio_que_nao_e_de_teste_e_recusado(self):
        (self.raiz / "docs/nota.md").write_text("fato", encoding="utf-8")
        self.contrato["aceite"].append(dict(id="doc", tipo="inspecao_documental", obrigatorio=False,
            esperado="Fonte conferida", verificacao={"caminhos": ["docs/nota.md"],
            "checagens": [{"id": "fonte", "esperado": "Fonte sustenta"}], "produtor": "coordenador"}))
        self.iniciar()
        with self.assertRaisesRegex(ValueError, "Criterio de reproducao"):
            self.p.diagnosticar(self.diagnostico_declarado(criterio_reproducao="doc"))

    def test_correcao_ativada_sem_diagnostico_bloqueia_a_escrita_e_o_done(self):
        self.ativar("correcao")
        self.iniciar()
        self.chamar("call-repro", "test")
        self.escrever("call-implement", "implement", "src/a.py", "# correcao sem diagnostico\n")
        self.assertIn("diagnostico:ausente", self.pendencias_atuais())
        self.assertIn("escrita_sem_diagnostico:implement:call-implement", self.pendencias_atuais())
        with self.assertRaisesRegex(ValueError, "diagnostico:ausente"):
            self.p.fechar("DONE", "Nao pode sem diagnostico")
        # Registrar depois nao desfaz a escrita que ja aconteceu sem ele.
        self.p.diagnosticar(self.diagnostico_declarado())
        self.assertNotIn("diagnostico:ausente", self.pendencias_atuais())
        self.assertIn("escrita_sem_diagnostico:implement:call-implement", self.pendencias_atuais())
        self.assertEqual(self.p.fechar("BLOCKED", "Escrita antes do diagnostico")["status"], "BLOCKED")

        self.iniciar()
        self.p.diagnosticar(self.diagnostico_declarado())
        self.chamar("call-repro-2", "test")
        self.escrever("call-implement-2", "implement", "src/a.py", "# correcao diagnosticada\n")
        self.chamar("call-test", "test")
        self.executar(agente_id="call-test")
        self.chamar("call-refute", "refute")
        self.revisar(agente_id="call-refute")
        self.assertEqual(self.pendencias_atuais(), [])
        self.assertEqual(self.p.fechar("DONE", "Correcao com diagnostico anterior a escrita")["status"], "DONE")

    def test_diagnostico_adulterado_deixa_de_valer_e_chave_vazia_dispensa(self):
        self.ativar("correcao")
        self.iniciar()
        self.p.diagnosticar(self.diagnostico_declarado())
        pasta = self.p.pasta()
        registro = self.p.estado(pasta)["diagnosticos"][0]
        evento = ler(pasta / registro["ref"])
        evento["dados"]["hipotese_causa"] = "Outra hipotese"
        (pasta / registro["ref"]).write_text(json.dumps(evento), encoding="utf-8")
        self.assertIn("diagnostico:ausente", self.pendencias_atuais())
        self.p.fechar("BLOCKED", "Registro adulterado")
        # Fora da chave, a correcao fecha como antes, sem diagnostico.
        self.contrato["trilha"] = "manutencao"
        self.iniciar()
        self.executar()
        self.assertEqual(self.p.fechar("DONE", "Trilha fora da chave")["status"], "DONE")

    def iniciar_ambiente(self, comando, ativado=True):
        (self.raiz / "docs/autorizacao.txt").write_text("Autorizacao da tarefa", encoding="utf-8")
        (self.raiz / "docs/insumo.txt").write_text("insumo do plan", encoding="utf-8")
        self.contrato.update(trilha="manutencao", superficie=["src/a.py"])
        criterio = self.contrato["aceite"][0]
        criterio.update(tipo="ambiente", autorizacao_ref="docs/autorizacao.txt")
        criterio["verificacao"].update(comando=comando, caminhos=["src"])
        if ativado:
            self.ativar("manutencao")
        self.iniciar()
        if ativado:
            for chamada_id, papel in (("call-prep", "test"), ("call-implement", "implement"),
                                      ("call-refute", "refute"), ("call-dab", "dab")):
                self.chamar(chamada_id, papel)
            self.revisar(agente_id="call-refute")

    def operar(self, comando, chamada="op-1", codigo=0):
        self.assertTrue(self.p.antes(chamada, comando, str(self.raiz), "teste"))
        return self.p.depois(chamada, comando, codigo, "saida")["resultado"]

    def gravar_plan(self, selecao=("etapa",), perfil="teste", target="sandbox"):
        plan = self.raiz / ".execucoes/plans/p.json"
        plan.parent.mkdir(parents=True, exist_ok=True)
        insumo = self.raiz / "docs/insumo.txt"
        plan.write_text(json.dumps(dict(
            target=target, selecao=sorted(selecao), perfil_sha256=sha256(perfil.encode()).hexdigest(),
            estado=[dict(caminho=str(insumo), sha256=sha256(insumo.read_bytes()).hexdigest())])),
            encoding="utf-8")
        return "plans/p.json"

    def ambiente_declarado(self, **extras):
        return dict(dict(identidade="nao_verificado", destinos_resolvidos=["nao_verificado"],
                         coordenacao="nao_verificado", agente_id="call-dab"), **extras)

    def test_sandbox_deploy_com_identidade_ou_destino_nao_verificado_nao_fecha_ambiente(self):
        comando = "databricks bundle deploy -t sandbox -p teste --select etapa"
        self.iniciar_ambiente(comando)
        self.assertEqual(self.operar(comando), "pass")
        plan_ref = self.gravar_plan()
        registro = self.p.registrar_sandbox("c1", self.ambiente_declarado(plan_ref=plan_ref))
        self.assertEqual(registro["resultado"], "pass")
        self.assertEqual(registro["nao_verificado"], ["identidade", "destinos_resolvidos"])
        evento = ler(self.p.pasta() / registro["evidencia_ref"])
        self.assertEqual((evento["tipo"], evento["produtor"]), ("sandbox", "dab"))
        self.assertEqual(evento["dados"]["operacao"], "deploy")
        self.assertEqual(evento["dados"]["selecao"], ["etapa"])
        self.assertEqual(evento["dados"]["plan_estado_compativel"], True)
        self.assertEqual(evento["dados"]["autorizacao_ref"], "docs/autorizacao.txt")
        self.assertEqual(self.pendencias_atuais(), ["sandbox_nao_verificado:identidade:c1",
                                                    "sandbox_nao_verificado:destinos_resolvidos:c1"])
        with self.assertRaisesRegex(ValueError, "sandbox_nao_verificado:destinos_resolvidos:c1"):
            self.p.fechar("DONE", "Destino nao verificado")

        registro = self.p.registrar_sandbox("c1", self.ambiente_declarado(
            plan_ref=plan_ref, identidade="usuario@avante", destinos_resolvidos=["cat.sch.tab"]))
        self.assertEqual(registro["nao_verificado"], [])
        self.assertEqual(self.p.fechar("DONE", "Deploy com identidade e destinos verificados")["status"], "DONE")
        # O plan e pre-condicao do deploy: arquivo do plan alterado depois invalida o registro.
        (self.raiz / "docs/insumo.txt").write_text("insumo alterado", encoding="utf-8")
        self.assertEqual(self.pendencias_atuais(), ["sandbox_plan_obsoleto:c1"])
        self.assertFalse(self.p.conferir()["fecho_valido"])

    def test_sandbox_recusa_registro_que_diverge_do_observado_ou_sem_plan_compativel(self):
        comando = "databricks bundle deploy -t sandbox -p teste --select etapa"
        self.iniciar_ambiente(comando)
        self.operar(comando)
        base = self.ambiente_declarado(plan_ref=self.gravar_plan(), identidade="usuario@avante",
                                       destinos_resolvidos=["cat.sch.tab"])
        for campo, valor in (("target", "dev"), ("perfil", "outro"), ("operacao", "validate"),
                             ("selecao", ["outra"]), ("cwd", "/x"), ("resultado", "fail"),
                             ("teste_ref", "tentativas/001/eventos/outro.yaml"),
                             ("autorizacao_ref", "docs/outra.txt"), ("bundle", "outro_bundle"),
                             ("plan_estado_compativel", False)):
            with self.subTest(campo=campo), self.assertRaisesRegex(ValueError, "diverge do observado"):
                self.p.registrar_sandbox("c1", dict(base, **{campo: valor}))
        with self.assertRaisesRegex(ValueError, "plan valido"):
            self.p.registrar_sandbox("c1", dict(base, plan_ref=self.gravar_plan(selecao=("outra",))))
        self.gravar_plan()
        with self.assertRaisesRegex(ValueError, "plan valido"):
            self.p.registrar_sandbox("c1", dict(base, plan_ref="plans/nao-existe.json"))
        with self.assertRaisesRegex(ValueError, "plan valido"):
            self.p.registrar_sandbox("c1", {k: v for k, v in base.items() if k != "plan_ref"})
        with self.assertRaises(ValueError):
            self.p.registrar_sandbox("c1", dict(base, plan_ref="../fora.json"))
        with self.assertRaisesRegex(ValueError, "Criterio ambiente ausente"):
            self.p.registrar_sandbox("nenhum", base)
        with self.assertRaisesRegex(ValueError, "Registro de ambiente invalido"):
            self.p.registrar_sandbox("c1", ["nao", "e", "objeto"])
        self.assertNotIn("sandbox", self.p.estado(self.p.pasta()))

    def test_sandbox_exige_dab_observado_e_fica_obsoleto_se_o_comando_roda_de_novo(self):
        comando = "databricks bundle validate -t sandbox -p teste"
        self.iniciar_ambiente(comando)
        self.assertEqual(self.operar(comando, "op-1", codigo=1), "fail")
        registro = self.p.registrar_sandbox("c1", self.ambiente_declarado())
        self.assertEqual(registro["resultado"], "fail")
        self.assertEqual(self.operar(comando, "op-2"), "pass")
        self.assertEqual(self.pendencias_atuais(), ["sandbox_obsoleto:c1"])
        for declarado in (self.ambiente_declarado(agente_id="call-prep"),
                          {k: v for k, v in self.ambiente_declarado().items() if k != "agente_id"}):
            self.p.registrar_sandbox("c1", declarado)
            self.assertEqual(self.pendencias_atuais(), ["sandbox_fora_do_dab:c1"])
        self.p.registrar_sandbox("c1", self.ambiente_declarado())
        self.assertEqual(self.pendencias_atuais(), [])
        self.assertEqual(self.p.fechar("DONE", "Validate com dab observado")["status"], "DONE")

    def test_sandbox_adulterado_perde_o_vinculo_e_chave_vazia_nao_exige_registro(self):
        comando = "databricks bundle validate -t sandbox -p teste"
        self.iniciar_ambiente(comando, ativado=False)
        self.operar(comando)
        self.assertEqual(self.pendencias_atuais(), [])  # Sem chave, o exit 0 continua bastando.
        self.p.registrar_sandbox("c1", self.ambiente_declarado())
        self.assertEqual(self.pendencias_atuais(), [])
        pasta = self.p.pasta()
        registro = self.p.estado(pasta)["sandbox"]["c1"]
        evento = ler(pasta / registro["ref"])
        evento["dados"]["identidade"] = "alguem@avante"
        (pasta / registro["ref"]).write_text(json.dumps(evento), encoding="utf-8")
        self.assertEqual(self.pendencias_atuais(), ["sandbox_invalido:c1"])  # Registro existente vale em qualquer modo.
        self.p.registrar_sandbox("c1", self.ambiente_declarado())
        self.operar(comando, "op-2")
        self.assertEqual(self.pendencias_atuais(), ["sandbox_obsoleto:c1"])

    def test_ambiente_com_script_local_nao_leva_sandbox(self):
        # O criterio ambiente_local roda um script, nao uma operacao de bundle.
        comando = "py -3 fixture/manutencao/ambiente_local.py"
        self.iniciar_ambiente(comando)
        self.assertEqual(self.operar(comando), "pass")
        self.assertEqual(self.pendencias_atuais(), [])
        with self.assertRaisesRegex(ValueError, "operacao de bundle"):
            self.p.registrar_sandbox("c1", self.ambiente_declarado())
        self.assertEqual(self.p.fechar("DONE", "Ambiente local fecha pelo teste e pela autorizacao")["status"],
                         "DONE")

    def paridade_declarada(self, **extras):
        return dict(dict(recorte="Competencia 2026-09",
                         insumos=[dict(nome="origem", identificador="a@v1"),
                                  dict(nome="destino", identificador="b@v1")],
                         contas=[dict(id="soma", descricao="Soma do valor", valor_origem="10.50",
                                      valor_destino="10.00", diferenca="0.50")],
                         divergencias=[dict(id="d1", estado="pendente")], agente_id="call-test"), **extras)

    def test_paridade_com_divergencia_pendente_e_exit_zero_fica_fail_e_recusa_done(self):
        self.contrato["aceite"][0]["tipo"] = "paridade"
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        self.revisar(agente_id="call-refute")
        with self.assertRaisesRegex(ValueError, "paridade_ausente:c1"):
            self.p.fechar("DONE", "Nao pode sem o registro de paridade")

        registro = self.p.registrar_paridade("c1", self.paridade_declarada())
        self.assertEqual(registro["resultado"], "fail")  # Exit 0 do comando, mas gap sem explicacao.
        evento = ler(self.p.pasta() / registro["evidencia_ref"])
        self.assertEqual((evento["tipo"], evento["produtor"], evento["dados"]["criterio_id"]),
                         ("paridade", "test", "c1"))
        self.assertEqual(self.pendencias_atuais(), ["paridade_reprovado:c1"])
        with self.assertRaisesRegex(ValueError, "paridade_reprovado:c1"):
            self.p.fechar("DONE", "Gap pendente")
        with self.assertRaisesRegex(ValueError, "diverge do observado"):
            self.p.registrar_paridade("c1", self.paridade_declarada(resultado="pass"))

        explicada = dict(id="d1", estado="explicada", explicacao="Arredondamento da origem",
                         evidencia_ref="contrato.yaml")
        self.assertEqual(self.p.registrar_paridade(
            "c1", self.paridade_declarada(divergencias=[explicada]))["resultado"], "pass")
        self.assertEqual(self.pendencias_atuais(), [])
        self.assertEqual(self.p.fechar("DONE", "Gap explicado com evidencia")["status"], "DONE")

    def test_paridade_exige_test_observado_teste_atual_e_registro_integro(self):
        self.contrato["aceite"][0]["tipo"] = "paridade"
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        self.revisar(agente_id="call-refute")
        sem_gap = self.paridade_declarada(contas=[dict(id="linhas", descricao="Linhas", valor_origem="7",
                                                       valor_destino="7", diferenca="0")], divergencias=[])
        for declarado in (dict(sem_gap, agente_id="call-refute"),
                          {k: v for k, v in sem_gap.items() if k != "agente_id"}):
            self.assertEqual(self.p.registrar_paridade("c1", declarado)["resultado"], "pass")
            self.assertEqual(self.pendencias_atuais(), ["paridade_fora_do_test:c1"])
        self.p.registrar_paridade("c1", sem_gap)
        self.assertEqual(self.pendencias_atuais(), [])
        pasta = self.p.pasta()
        registro = self.p.estado(pasta)["paridades"]["c1"]
        self.assertEqual(registro["teste_ref"], self.p.estado(pasta)["provas"]["c1"]["ref"])
        self.assertEqual(ler(pasta / registro["ref"])["manifesto_ref"],
                         ler(pasta / registro["teste_ref"])["manifesto_ref"])

        # O comando de paridade roda de novo: o registro anterior deixa de valer.
        self.executar(chamada="t2", agente_id="call-test")
        self.assertEqual(self.pendencias_atuais(), ["paridade_obsoleto:c1"])
        self.p.registrar_paridade("c1", sem_gap)
        evento = ler(pasta / self.p.estado(pasta)["paridades"]["c1"]["ref"])
        evento["dados"]["recorte"] = "Outro recorte"
        (pasta / self.p.estado(pasta)["paridades"]["c1"]["ref"]).write_text(json.dumps(evento), encoding="utf-8")
        self.assertEqual(self.pendencias_atuais(), ["paridade_invalido:c1"])

    def test_paridade_exige_criterio_do_tipo_e_comando_ja_executado(self):
        self.iniciar()  # c1 e do tipo teste.
        with self.assertRaisesRegex(ValueError, "Criterio paridade ausente"):
            self.p.registrar_paridade("c1", self.paridade_declarada())
        self.contrato["aceite"][0]["tipo"] = "paridade"
        self.p.fechar("BLOCKED", "Troca de contrato")
        self.iniciar()
        with self.assertRaisesRegex(ValueError, "Rode o comando do criterio"):
            self.p.registrar_paridade("c1", self.paridade_declarada())
        with self.assertRaisesRegex(ValueError, "Registro de paridade invalido"):
            self.p.registrar_paridade("c1", "texto")

    def test_chave_vazia_paridade_sem_registro_fecha_e_registro_reprovado_bloqueia(self):
        self.contrato["aceite"][0]["tipo"] = "paridade"
        self.iniciar()
        self.executar()
        self.assertEqual(self.pendencias_atuais(), [])
        self.p.registrar_paridade("c1", self.paridade_declarada())
        self.assertEqual(self.pendencias_atuais(), ["paridade_reprovado:c1"])
        with self.assertRaisesRegex(ValueError, "paridade_reprovado:c1"):
            self.p.fechar("DONE", "Gap pendente")

    def test_fatia_sem_registros_c6_nao_ganha_chaves_de_estado_e_continua_legivel(self):
        self.ativar("manutencao")
        self.passagem_completa_de_manutencao()
        self.revisar(agente_id="call-refute")
        self.assertEqual(self.p.fechar("DONE", "Fluxo anterior ao C6")["status"], "DONE")
        estado = self.p.estado(self.p.pasta())
        self.assertFalse({"diagnosticos", "sandbox", "paridades"} & set(estado))
        self.assertTrue(self.p.conferir()["fecho_valido"])

    def test_cli_registra_diagnostico_sandbox_e_paridade(self):
        (self.raiz / "docs/autorizacao.txt").write_text("Autorizacao da tarefa", encoding="utf-8")
        comando = "databricks bundle validate -t sandbox -p teste"
        self.contrato["aceite"] = [
            dict(id="c1", tipo="paridade", obrigatorio=True, esperado="Origem e destino iguais",
                 verificacao=dict(comando="python teste.py", cwd=".", caminhos=["src"])),
            dict(id="c2", tipo="ambiente", obrigatorio=True, esperado="Validate no sandbox",
                 autorizacao_ref="docs/autorizacao.txt",
                 verificacao=dict(comando=comando, cwd=".", caminhos=["src"]))]
        base = ["--sessao", "sessao-a"]
        codigo, _, erro = self.chamar_adaptador_prova([*base, "iniciar", self.arquivo_yaml("c.yaml", self.contrato)])
        self.assertEqual(codigo, 0, erro)

        codigo, saida, erro = self.chamar_adaptador_prova([*base, "diagnosticar", self.arquivo_yaml(
            "d.yaml", dict(self.diagnostico_declarado(criterio_reproducao="c1"), produtor="map"))])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["base"], "derived")
        self.assertEqual(ler(self.p.pasta() / json.loads(saida)["evidencia_ref"])["produtor"], "map")
        codigo, _, erro = self.chamar_adaptador_prova([*base, "diagnosticar", self.arquivo_yaml(
            "d2.yaml", self.diagnostico_declarado(criterio_reproducao="nenhum"))])
        self.assertEqual(codigo, 2)
        self.assertIn("Criterio de reproducao", erro)

        self.executar()
        self.operar(comando, "op-1")
        entrada = dict(self.paridade_declarada(divergencias=[], contas=[dict(
            id="linhas", descricao="Linhas", valor_origem="7", valor_destino="7", diferenca="0")]),
            criterio_id="c1")
        del entrada["agente_id"]
        codigo, saida, erro = self.chamar_adaptador_prova(
            [*base, "registrar-paridade", self.arquivo_yaml("p.yaml", entrada)])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["resultado"], "pass")
        codigo, saida, erro = self.chamar_adaptador_prova([*base, "registrar-sandbox", self.arquivo_yaml(
            "s.yaml", dict(self.ambiente_declarado(), criterio_id="c2"))])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["resultado"], "pass")
        codigo, saida, erro = self.chamar_adaptador_prova([*base, "fechar", "--resultado", "Registros do C6"])
        self.assertEqual(codigo, 0, erro)
        self.assertEqual(json.loads(saida)["status"], "DONE")

        for subcomando, dados in (("registrar-sandbox", dict(self.ambiente_declarado(), criterio_id="nenhum")),
                                  ("registrar-sandbox", self.ambiente_declarado()),
                                  ("registrar-paridade", ["lista"]), ("diagnosticar", ["lista"])):
            with self.subTest(subcomando=subcomando):
                codigo, _, erro = self.chamar_adaptador_prova(
                    [*base, subcomando, self.arquivo_yaml("ruim.yaml", dados)])
                self.assertEqual(codigo, 2)
                self.assertIn("[prova]", erro)

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
