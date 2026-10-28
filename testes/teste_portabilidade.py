"""Aceite da continuidade entre CLIs usando processos locais reais e estados isolados."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from provas import Provas, gravar, ler, retrato, hash_arquivo, trava
from executor_local import verificar, argumentos_locais, recuperar_local
import prova as cli


class PortabilidadeTestes(unittest.TestCase):
    def setUp(self):
        fixtures = RAIZ / "testes/.fixtures"
        fixtures.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("valor = 1\n", encoding="utf-8")
        (self.raiz / "testes").mkdir()
        (self.raiz / "testes/teste_local.py").write_text("print('teste executado')\n", encoding="utf-8")
        (self.raiz / "configuracao").mkdir()
        self.politica = dict(execucao_portatil=True, agentes_obrigatorios={},
                             registros_raiz="../.execucoes", bundle_local="../src")
        self.salvar_politica()
        self.contrato = dict(objetivo="Continuidade", termino_fatia="Teste e revisao atuais", trilha="manutencao",
                             superficie=["src/a.py", "testes/teste_local.py"], artefatos_raiz=".execucoes/provas",
                             fora=["Databricks"], fontes=["src/a.py"], responsaveis={},
                             aceite=[dict(id="local", tipo="teste", obrigatorio=True, esperado="Exit 0",
                                          verificacao=dict(comando="py -3 testes/teste_local.py", cwd=".",
                                                           caminhos=["src", "testes"]))])
        self.p = self.participante("origem", "claude_code")

    def salvar_politica(self):
        gravar(self.raiz / "configuracao/politica.json", self.politica, substituir=True)

    def participante(self, sessao, runtime, execucao=None):
        return Provas(self.raiz, self.raiz / ".execucoes", sessao, runtime, execucao)

    def iniciar(self):
        return self.p.iniciar(copy.deepcopy(self.contrato))["execucao_id"]

    def revisar(self, p=None, **extras):
        p = p or self.p
        dados = dict(modo="autorrevisao", entrada=dict(intencao_ref="contrato.yaml", aceite_ref="contrato.yaml",
                     baseline_ref="baseline.json", provas_refs=[]), veredito="nao_quebrei",
                     tentativas=[dict(id="t1", procedimento="Conferir criterio e regressao", resultado="pass")],
                     achados=[], cobertura=[dict(criterio_id=c["id"], coberto=True) for c in self.contrato["aceite"]])
        dados.update(extras)
        return p.revisar(dados)

    def liberar(self):
        return self.p.salvar_checkpoint(dict(proximo_passo="Conferir e fechar", autorizacoes=[]), liberar=True)

    def test_trocas_preservam_baseline_provas_procedencia_e_fecho(self):
        for origem, destino in [("claude_code", "cursor"), ("claude_code", "codex"),
                                ("cursor", "opencode"), ("codex", "codex")]:
            with self.subTest(origem=origem, destino=destino):
                self.p = self.participante("origem-" + destino, origem)
                execucao = self.iniciar()
                self.assertEqual(verificar(self.p, "local")["resultado"], "pass")
                self.revisar()
                pasta = self.p.pasta()
                antes = {f.relative_to(pasta).as_posix(): hash_arquivo(f) for f in pasta.rglob("*")
                         if f.is_file() and f.name != "estado.json"}
                self.liberar()
                novo = self.participante("destino-" + destino, destino, execucao)
                self.assertEqual(novo.retomar("Troca de CLI")["pendencias"], [])
                self.assertEqual(novo.fechar("DONE", "Aceite verificado")["modo_revisao"], "autorrevisao")
                for ref, digest in antes.items():
                    self.assertEqual(hash_arquivo(pasta / ref), digest)
                estado = novo.estado(pasta)
                teste = ler(pasta / estado["provas"]["local"]["ref"])
                self.assertEqual(teste["origem"]["runtime"], origem)
                with self.assertRaises(ValueError):
                    self.p.fechar("DONE", "Coordenador antigo")
                self.assertTrue(novo.conferir()["fecho_valido"])

    def test_sem_hook_ou_subagente_aceite_exige_revisao_e_prova(self):
        self.iniciar()
        self.assertIn("local", self.p.conferir()["pendencias"])
        self.assertEqual(verificar(self.p, "local")["resultado"], "pass")
        with self.assertRaisesRegex(ValueError, "revisao:ausente"):
            self.p.fechar("DONE", "Ainda nao")
        self.revisar()
        self.assertEqual(self.p.fechar("DONE", "Verificado")["status"], "DONE")

    def test_falha_timeout_comando_ausente_e_prova_obsoleta_impedem_done(self):
        self.iniciar()
        self.revisar()
        script = self.raiz / "testes/teste_local.py"
        for conteudo, timeout, esperado in [("raise SystemExit(7)", 10, "fail"),
                                              ("import time; time.sleep(5)", 1, "inconclusivo")]:
            script.write_text(conteudo, encoding="utf-8")
            self.assertEqual(verificar(self.p, "local", timeout)["resultado"], esperado)
            with self.assertRaises(ValueError):
                self.p.fechar("DONE", "Nao pode")
            self.assertIsNone(self.p.estado(self.p.pasta())["pendente"])
        with patch("executor_local.subprocess.run", side_effect=FileNotFoundError("Interpretador ausente")):
            self.assertEqual(verificar(self.p, "local")["resultado"], "inconclusivo")
        script.write_text("print('ok')", encoding="utf-8")
        verificar(self.p, "local")
        self.revisar()
        (self.raiz / "src/a.py").write_text("valor = 2", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "local.*revisao:obsoleta"):
            self.p.fechar("DONE", "Nao pode")

    def test_concorrencia_lock_e_recuperacao_explicita_com_revisao(self):
        execucao = self.iniciar()
        novo = self.participante("nova", "cursor", execucao)
        self.assertTrue(novo.conferir()["ativa"])
        with self.assertRaisesRegex(ValueError, "Coordenador ativo"):
            novo.retomar("Troca")
        with trava(self.p.pasta()):
            with self.assertRaisesRegex(ValueError, "Registro em uso"):
                novo.retomar("Interrompida", 0, True)
        self.p.salvar_checkpoint(dict(proximo_passo="Continuar"))
        with self.assertRaisesRegex(ValueError, "Revisao mudou"):
            novo.retomar("Interrompida", 0, True)
        novo.retomar("Processo original encerrado e conferido", 1, True)
        with self.assertRaises(ValueError):
            self.p.salvar_checkpoint(dict(proximo_passo="Escrita antiga"))

    def test_chamada_pendente_nao_e_repetida_na_troca(self):
        execucao = self.iniciar()
        self.p.antes("em_curso", self.contrato["aceite"][0]["verificacao"]["comando"], str(self.raiz), "teste")
        novo = self.participante("nova", "codex", execucao)
        with self.assertRaisesRegex(ValueError, "Chamada pendente"):
            novo.retomar("Conversa caiu", 1, True)
        with self.assertRaisesRegex(ValueError, "sem resultado"):
            verificar(self.p, "local")
        self.p.depois("em_curso", self.contrato["aceite"][0]["verificacao"]["comando"], None, "Interrompida")
        self.liberar()
        self.assertIn("local", novo.retomar("Conferida na origem")["pendencias"])

    def test_efeito_externo_pendente_sobrevive_checkpoint_e_troca(self):
        execucao = self.iniciar()
        self.p.salvar_checkpoint(dict(proximo_passo="Consultar operacao", operacoes=[dict(id="run-42", referencia="job/42")]))
        self.liberar()
        novo = self.participante("nova", "codex", execucao)
        self.assertIn("operacao_pendente:run-42", novo.retomar("Conferir resultado externo")["pendencias"])
        with self.assertRaises(ValueError):
            novo.fechar("DONE", "Nao pode")
        with self.assertRaises(ValueError):
            novo.resolver_operacao("run-42", "src/a.py")
        gravar(self.raiz / "conferencia.json", dict(operacao_id="run-42", referencia="job/42",
               resultado="concluida", observado_em="2026-10-28T15:00:00+00:00"))
        novo.resolver_operacao("run-42", "conferencia.json")
        self.assertNotIn("operacao_pendente:run-42", novo.conferir()["pendencias"])
        self.assertIn("local", novo.conferir()["pendencias"])

    def test_revisao_independente_nao_e_satisfeita_por_autorrevisao_ou_outra_chamada(self):
        self.contrato["revisao"] = "independente"
        execucao = self.iniciar()
        verificar(self.p, "local")
        self.revisar()
        self.liberar()
        novo = self.participante("nova", "codex", execucao)
        self.assertIn("revisao:independencia_pendente", novo.retomar("Revisao pendente")["pendencias"])
        with self.assertRaisesRegex(ValueError, "evidencia"):
            self.revisar(novo, modo="independente", revisor="pessoa")
        pasta = novo.pasta()
        atestado = dict(tipo="revisao_humana", revisor="pessoa", execucao_id=execucao,
                        contexto="revisao-fora-do-chat", contexto_independente=True,
                        arquivos=retrato(self.raiz, ["src/a.py", "testes/teste_local.py", "src", "testes"]))
        gravar(pasta / "atestado.json", atestado)
        self.revisar(novo, modo="independente", revisor="pessoa", evidencia_independencia_ref="atestado.json")
        self.assertEqual(novo.fechar("DONE", "Revisado")["status"], "DONE")
        gravar(pasta / "atestado.json", dict(atestado, revisor="adulterado"), substituir=True)
        self.assertIn("revisao:obsoleta", novo.conferir()["pendencias"])

    def test_achado_anterior_sobrevive_troca_e_nova_revisao(self):
        execucao = self.iniciar()
        verificar(self.p, "local")
        achado = dict(id="a1", categoria="lacuna", severidade="alta", local="src/a.py",
                      evidencia_ref="contrato.yaml")
        revisao = self.revisar(veredito="com_achados", achados=[achado])
        self.liberar()
        novo = self.participante("nova", "opencode", execucao)
        novo.retomar("Tratar achado")
        self.revisar(novo)
        with self.assertRaisesRegex(ValueError, "a1:sem_triagem"):
            novo.fechar("DONE", "Nao pode")
        novo.triar(dict(revisao_ref=revisao["evidencia_ref"], achado_id="a1", decisao="descartado",
                        responsavel="coordenador", motivo_descarte="Caso coberto pelo requisito e pelo teste"))
        self.assertEqual(novo.fechar("DONE", "Verificado")["status"], "DONE")

    def test_autorizacao_ambiente_e_formas_exigidas_sem_agentes(self):
        for tipo in ("ambiente", "paridade"):
            with self.subTest(tipo=tipo):
                self.p = self.participante(tipo, "codex")
                self.contrato["aceite"][0]["tipo"] = tipo
                self.iniciar()
                v = self.contrato["aceite"][0]["verificacao"]
                self.p.antes("hook", v["comando"], str(self.raiz), "hook")
                self.p.depois("hook", v["comando"], 0, "ok")
                pendencias = self.p.conferir()["pendencias"]
                self.assertIn("autorizacao_ambiente:local" if tipo == "ambiente" else "paridade_ausente:local", pendencias)

    def test_politica_nao_reduz_requisitos_congelados_e_superficie_e_conferida(self):
        self.iniciar()
        self.politica["execucao_portatil"] = False
        self.salvar_politica()
        self.assertEqual(self.p.estado(self.p.pasta())["requisitos"]["revisao"], "autorrevisao")
        (self.raiz / "src/fora.py").write_text("fora", encoding="utf-8")
        self.assertIn("superficie_fora_do_contrato:src/fora.py", self.p.conferir()["pendencias"])
        gravar(self.p.pasta() / "requisitos.json", {"revisao": "nao_realizada"}, substituir=True)
        with self.assertRaisesRegex(ValueError, "Requisitos"):
            self.p.conferir()

    def test_executor_aceita_flag_bytecode_antes_do_script(self):
        argumentos_locais(self.raiz, self.raiz, "py -3 -B testes/teste_local.py")
        with self.assertRaises(ValueError):
            argumentos_locais(self.raiz, self.raiz, "py -3 -B")

    def test_executor_recusa_plataforma_wrappers_e_shell(self):
        for comando in ("databricks bundle deploy -t sandbox", "py -3 -c print(1)", "node -e test",
                        "powershell teste.ps1", "py -3 testes/teste_local.py; whoami", "cmd /c echo ok",
                        "py -3 -m pip install x", "py -3 adaptadores/prova.py estado", "node testes/databricks.js"):
            with self.subTest(comando=comando), self.assertRaises(ValueError):
                argumentos_locais(self.raiz, self.raiz, comando)

    def test_manifesto_ilegivel_nao_fabrica_sucesso_nem_deixa_chamada_pendente(self):
        self.iniciar()
        with patch.object(self.p, "manifesto_atual", side_effect=PermissionError("Sem acesso")):
            self.assertEqual(verificar(self.p, "local")["resultado"], "inconclusivo")
        self.assertIsNone(self.p.estado(self.p.pasta())["pendente"])
        self.assertIn("local", self.p.conferir()["pendencias"])

    def test_recuperar_captura_local_interrompida_preserva_log_e_nao_aprova(self):
        self.iniciar()
        comando = self.contrato["aceite"][0]["verificacao"]["comando"]
        self.p.antes("local_interrompido", comando, str(self.raiz), "executor_local")
        log = self.p.pasta() / "tentativas/001/logs/resultado.txt"
        log.parent.mkdir(parents=True)
        log.write_text("Saida obtida antes da interrupcao", encoding="utf-8")
        self.assertEqual(recuperar_local(self.p, "local_interrompido", "Processo encerrado conferido")["resultado"], "inconclusivo")
        self.assertEqual(log.read_text(encoding="utf-8"), "Saida obtida antes da interrupcao")
        self.assertIn("local", self.p.conferir()["pendencias"])

    def test_duas_sessoes_nao_assumem_a_mesma_coordenacao(self):
        execucao = self.iniciar()
        self.liberar()
        def assumir(numero):
            try:
                self.participante("concorrente-" + str(numero), "codex", execucao).retomar("Transferencia")
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(assumir, [1, 2])), 1)

    def test_delegacao_opcional_pendente_impede_troca_e_fecho(self):
        execucao = self.iniciar()
        self.p.abrir_chamada("refute-local", "refute")
        self.assertIn("delegacao_pendente:refute-local", self.p.conferir()["pendencias"])
        with self.assertRaisesRegex(ValueError, "Chamada pendente"):
            self.liberar()
        novo = self.participante("nova", "codex", execucao)
        with self.assertRaisesRegex(ValueError, "Chamada pendente"):
            novo.retomar("Interrompida", 1, True)
        self.p.encerrar_chamada("refute-local")
        self.liberar()
        novo.retomar("Chamada encerrada")

    def test_bundle_sem_sandbox_e_paridade_sem_forma_nao_fecham_sem_agentes(self):
        self.contrato["aceite"][0].update(tipo="ambiente", autorizacao_ref="autorizacao.md")
        self.contrato["aceite"][0]["verificacao"]["comando"] = "databricks bundle validate -t sandbox -p perfil"
        (self.raiz / "autorizacao.md").write_text("Referencia da autorizacao no escopo do teste", encoding="utf-8")
        self.iniciar()
        v = self.contrato["aceite"][0]["verificacao"]
        self.p.antes("hook", v["comando"], str(self.raiz), "hook")
        self.p.depois("hook", v["comando"], 0, "ok")
        self.assertIn("sandbox_ausente:local", self.p.conferir()["pendencias"])
        self.assertNotIn("autorizacao_ambiente:local", self.p.conferir()["pendencias"])
        (self.raiz / "autorizacao.md").write_text("Autorizacao alterada", encoding="utf-8")
        self.assertIn("autorizacao_ambiente:local", self.p.conferir()["pendencias"])

    def test_migracao_carrega_achados_pendentes_e_exigencias_legadas(self):
        self.politica.update(execucao_portatil=False, agentes_obrigatorios={"claude_code": ["manutencao"]})
        self.salvar_politica()
        execucao = self.iniciar()
        self.revisar(veredito="com_achados", achados=[dict(id="herdado", categoria="lacuna",
                      severidade="alta", local="src/a.py", evidencia_ref="contrato.yaml")])
        self.p.fechar("BLOCKED", "Capacidade indisponivel")
        self.politica.update(execucao_portatil=True, agentes_legados=self.politica["agentes_obrigatorios"],
                             agentes_obrigatorios={})
        self.salvar_politica()
        novo = self.participante("nova", "codex", execucao)
        resultado = novo.migrar(self.contrato)
        destino = self.participante("nova", "codex", resultado["execucao_id"])
        self.assertEqual(destino.conferir()["requisitos"]["revisao"], "independente")
        destino_estado = destino.estado(destino.pasta())
        herdada = ler(destino.pasta() / destino_estado["revisoes"][0]["ref"])
        self.assertEqual(herdada["dados"]["achados"][0]["id"], "herdado")
        self.revisar(destino)
        self.assertIn("revisao:independencia_pendente", destino.conferir()["pendencias"])

    def test_migracao_preserva_origem_e_nao_aproveita_blocked_ou_provas(self):
        self.politica["execucao_portatil"] = False
        self.salvar_politica()
        execucao = self.iniciar()
        self.p.fechar("BLOCKED", "Hook indisponivel")
        pasta = self.p.pasta()
        original = {f.relative_to(pasta).as_posix(): hash_arquivo(f) for f in pasta.rglob("*") if f.is_file()}
        self.politica["execucao_portatil"] = True
        self.salvar_politica()
        novo = self.participante("nova", "codex", execucao)
        with self.assertRaisesRegex(ValueError, "antiga"):
            novo.retomar("Troca")
        contrato_menor = copy.deepcopy(self.contrato)
        contrato_menor["superficie"].pop()
        with self.assertRaisesRegex(ValueError, "reduzir"):
            novo.migrar(contrato_menor)
        resultado = novo.migrar(self.contrato)
        destino = self.participante("nova", "codex", resultado["execucao_id"])
        self.assertIsNone(destino.conferir()["status"])
        self.assertIn("local", destino.conferir()["pendencias"])
        for ref, digest in original.items():
            self.assertEqual(hash_arquivo(pasta / ref), digest)

    def test_cli_verificar_devolve_falha_real_e_estado_por_execucao(self):
        execucao = self.iniciar()
        with patch.object(cli, "RAIZ", self.raiz), patch.dict(os.environ, {"ESTEIRA_SESSAO": "", "CLAUDE_CODE_SESSION_ID": ""}):
            args = ["--sessao", "origem", "--runtime", "claude_code", "--execucao", execucao]
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(cli.principal(args + ["verificar", "local"]), 0)
                (self.raiz / "testes/teste_local.py").write_text("raise SystemExit(3)", encoding="utf-8")
                self.assertEqual(cli.principal(args + ["verificar", "local"]), 2)
                self.assertEqual(cli.principal(["--sessao", "leitor", "--runtime", "codex", "--execucao", execucao, "estado"]), 0)


if __name__ == "__main__":
    unittest.main()
