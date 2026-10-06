"""Aceite focado das formas 3.2 e compatibilidade de eventos 3.1."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))
from formas import nao_verificados_sandbox, validar, validar_dados


class FormasTestes(unittest.TestCase):
    def setUp(self):
        self.raiz = RAIZ.resolve()
        self.manifesto = self.raiz / "formas/catalogo.yaml"

    def evento(self, tipo, dados, produtor=None, versao="3.2"):
        donos = {
            "ataque": "refute",
            "triagem": "coordenador",
            "inspecao": "refute",
            "chamada": "adaptador",
            "guarda": "hook",
            "diagnostico": "coordenador",
            "sandbox": "dab",
            "paridade": "test",
        }
        return {
            "schema_versao": versao,
            "tipo": tipo,
            "exemplo": False,
            "execucao_id": "execucao-1",
            "fatia_id": "principal",
            "evento_id": "evento-1",
            "tentativa": 1,
            "produtor": produtor or donos[tipo],
            "registrado_em": "2026-10-03T12:00:00+00:00",
            "manifesto_ref": "formas/catalogo.yaml",
            "dados": deepcopy(dados),
        }

    def verificar(self, evento):
        return validar(evento, self.raiz, "execucao-1", "principal")

    def contrato(self, criterio):
        return {
            "objetivo": "Validar formas do contrato",
            "termino_fatia": "Critérios validados",
            "trilha": "manutencao",
            "superficie": ["implementacao/formas.py"],
            "artefatos_raiz": ".execucoes/provas",
            "fora": [],
            "fontes": ["PLANO-AGENTES-TRILHAS.md"],
            "prazo": None,
            "aceite": [criterio],
            "orcamento": {},
            "responsaveis": {},
        }

    def test_ataque_aceita_agente_id_opcional_e_recusa_identificador_invalido(self):
        dados = self.ataque()
        self.verificar(self.evento("ataque", dict(dados, agente_id="refute-1")))
        for agente_id in ("", "../refute", None):
            with self.subTest(agente_id=agente_id), self.assertRaises(ValueError):
                self.verificar(self.evento("ataque", dict(dados, agente_id=agente_id)))

    def ataque(self, veredito="com_achados"):
        tentativa = {"id": "try1", "procedimento": "Reproduzir o critério", "resultado": "pass"}
        achado = {
            "id": "finding1",
            "categoria": "simplificacao",
            "severidade": "baixa",
            "local": "src/a.py:1",
            "evidencia_ref": "implementacao/formas.py",
        }
        cobertura = [{"criterio_id": "c1", "coberto": True}]
        return {
            "entrada": {
                "intencao_ref": "PLANO-AGENTES-TRILHAS.md",
                "aceite_ref": "formas/catalogo.yaml",
                "baseline_ref": "PLANO-AGENTES-TRILHAS.md",
                "provas_refs": ["implementacao/formas.py"],
            },
            "veredito": veredito,
            "tentativas": [tentativa] if veredito == "nao_quebrei" else [],
            "achados": [achado] if veredito == "com_achados" else [],
            "cobertura": cobertura if veredito == "nao_quebrei" else [],
        }

    def test_ataque_com_achados_e_nao_quebrei_validos(self):
        self.assertEqual(self.verificar(self.evento("ataque", self.ataque())),
                         self.evento("ataque", self.ataque()))
        self.verificar(self.evento("ataque", self.ataque("nao_quebrei")))

    def test_ataque_exige_evidencia_tentativas_e_cobertura_condicionais(self):
        dados = self.ataque()
        dados["achados"] = []
        with self.assertRaises(ValueError):
            self.verificar(self.evento("ataque", dados))

        dados = self.ataque()
        dados["achados"][0]["evidencia_ref"] = "ausente.txt"
        with self.assertRaisesRegex(ValueError, "Evidencia ausente"):
            self.verificar(self.evento("ataque", dados))

        dados = self.ataque("nao_quebrei")
        dados["tentativas"] = []
        with self.assertRaises(ValueError):
            self.verificar(self.evento("ataque", dados))

        dados = self.ataque("nao_quebrei")
        dados["cobertura"] = []
        with self.assertRaises(ValueError):
            self.verificar(self.evento("ataque", dados))

        dados = self.ataque("nao_quebrei")
        dados["cobertura"][0]["coberto"] = False
        self.verificar(self.evento("ataque", dados))

    def test_triagem_exige_prova_ou_motivo_da_decisao(self):
        procedente = {
            "revisao_ref": "formas/catalogo.yaml",
            "achado_id": "finding1", "decisao": "procedente", "responsavel": "implement",
            "evidencia_resolucao_ref": "implementacao/formas.py",
        }
        self.verificar(self.evento("triagem", procedente))
        descartado = {
            "revisao_ref": "formas/catalogo.yaml",
            "achado_id": "finding1", "decisao": "descartado", "responsavel": "coordenador",
            "motivo_descarte": "A reprodução não atende ao critério.",
        }
        self.verificar(self.evento("triagem", descartado))
        for dados in (
            {k: v for k, v in procedente.items() if k != "evidencia_resolucao_ref"},
            {**descartado, "motivo_descarte": "  "},
            {k: v for k, v in descartado.items() if k != "revisao_ref"},
            {**descartado, "revisao_ref": "revisao-ausente.yaml"},
        ):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                self.verificar(self.evento("triagem", dados))

    def test_inspecao_confere_manifesto_hash_criterio_e_checagens(self):
        dados = {
            "criterio_id": "c1",
            "caminhos": ["src/a.py"],
            "manifesto_sha256": sha256(self.manifesto.read_bytes()).hexdigest(),
            "checagens": [{"id": "check1", "resultado": "pass", "evidencia_ref": "implementacao/formas.py"}],
            "resultado": "pass",
            "validade": "valida",
        }
        self.verificar(self.evento("inspecao", dados))
        for alterar in (
            lambda d: d.update(manifesto_sha256="0" * 64),
            lambda d: d.update(checagens=[]),
            lambda d: d["checagens"][0].update(evidencia_ref="ausente.txt"),
        ):
            invalido = deepcopy(dados)
            alterar(invalido)
            with self.assertRaises(ValueError):
                self.verificar(self.evento("inspecao", invalido))

    def test_chamada_requer_dados_observados_validos_e_tempo_ordenado(self):
        dados = {
            "chamada_id": "call-1",
            "papel": "implement",
            "runtime": "cursor",
            "ids_observados": [{"nome": "agent_run_id", "valor": "run-123"}],
            "inicio": "2026-10-03T12:00:00+00:00",
            "fim": "2026-10-03T12:01:00+00:00",
            "status": "concluida",
        }
        self.verificar(self.evento("chamada", dados))
        for alterar in (
            lambda d: d.update(ids_observados=[]),
            lambda d: d.update(papel="coordenador"),
            lambda d: d.update(runtime="inexistente"),
            lambda d: d.update(status="pass"),
            lambda d: d.update(fim="2026-10-03T11:59:59+00:00"),
            lambda d: d.update(inicio="2026-10-03T12:00:00"),
        ):
            invalido = deepcopy(dados)
            alterar(invalido)
            with self.assertRaises(ValueError):
                self.verificar(self.evento("chamada", invalido))

    def test_teste_vincula_subagente_e_confere_origem_do_exit_code(self):
        base = {"criterio_id": "c1", "chamada_id": "t1", "cwd": ".", "comando": "python teste.py",
                "inicio": "2026-10-05T12:00:00+00:00", "fim": "2026-10-05T12:00:01+00:00",
                "exit_code": 0, "log_ref": "formas/catalogo.yaml", "log_sha256": "0" * 64,
                "estado_testado": "0" * 64, "resultado": "pass", "validade": "valida"}
        for extras in ({}, {"agente_id": "a1b2", "exit_code_origem": "evento_sucesso"},
                       {"exit_code_origem": "campo_resultado"}):
            validar_dados("teste", {**base, **extras}, "3.2")
        falha = {**base, "exit_code": 1, "resultado": "fail", "exit_code_origem": "texto_falha"}
        validar_dados("teste", falha, "3.2")
        for extras, motivo in (({"agente_id": "a/b"}, "Identificador"),
                               ({"exit_code_origem": "texto_falha"}, "Texto de falha"),
                               ({"exit_code": None, "resultado": "inconclusivo",
                                 "exit_code_origem": "campo_resultado"}, "Origem sem exit code"),
                               ({"exit_code_origem": "relato"}, "valor invalido")):
            with self.subTest(extras=extras), self.assertRaisesRegex(ValueError, motivo):
                validar_dados("teste", {**base, **extras}, "3.2")
        with self.assertRaisesRegex(ValueError, "Evento de sucesso"):
            validar_dados("teste", {**falha, "exit_code_origem": "evento_sucesso"}, "3.2")

    def test_produtor_obedece_a_allowlist_e_a_propriedade_da_forma(self):
        evento = self.evento("chamada", {
            "chamada_id": "call-1", "papel": "test", "runtime": "cursor",
            "ids_observados": [{"nome": "agent_run_id", "valor": "run-123"}],
            "inicio": "2026-10-03T12:00:00+00:00", "fim": "2026-10-03T12:01:00+00:00",
            "status": "concluida",
        })
        with self.assertRaisesRegex(ValueError, "Produtor nao corresponde"):
            self.verificar(dict(evento, produtor="coordenador"))
        with self.assertRaisesRegex(ValueError, "Produtor invalido"):
            self.verificar(dict(evento, produtor="nao_listado"))

    def diagnostico(self, **extras):
        return dict({
            "sintoma": "A carga termina sem as linhas do dia",
            "hipotese_causa": "O filtro de data exclui o ultimo dia",
            "base": "derived",
            "evidencia_ref": "formas/catalogo.yaml",
            "criterio_reproducao": "reproduz",
            "proximo_passo": "Rodar o criterio com o filtro corrigido",
        }, **extras)

    def test_diagnostico_aceita_coordenador_e_map_e_recusa_o_resto(self):
        self.verificar(self.evento("diagnostico", self.diagnostico()))
        self.verificar(self.evento("diagnostico", self.diagnostico(), produtor="map"))
        with self.assertRaisesRegex(ValueError, "Produtor nao corresponde"):
            self.verificar(self.evento("diagnostico", self.diagnostico(), produtor="refute"))
        for campo in self.diagnostico():
            invalido = self.diagnostico()
            del invalido[campo]
            with self.subTest(ausente=campo), self.assertRaises(ValueError):
                self.verificar(self.evento("diagnostico", invalido))
        for alteracao in (dict(base="chute"), dict(sintoma="  "), dict(proximo_passo=""),
                          dict(criterio_reproducao="../x"), dict(evidencia_ref="ausente.txt"),
                          dict(extra="campo")):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                self.verificar(self.evento("diagnostico", self.diagnostico(**alteracao)))
        with self.assertRaisesRegex(ValueError, "Forma ainda nao adotada"):
            self.verificar(self.evento("diagnostico", self.diagnostico(), versao="3.1"))

    def sandbox(self, **extras):
        return dict({
            "operacao": "validate", "cwd": ".", "bundle": "saneamento_migracao", "target": "sandbox",
            "perfil": "teste", "selecao": [], "plan_ref": None, "plan_estado_compativel": None,
            "autorizacao_ref": "evidencia/autorizacao.md", "identidade": "nao_verificado",
            "destinos_resolvidos": ["nao_verificado"], "coordenacao": "nao_verificado",
            "resultado": "pass", "teste_ref": "formas/catalogo.yaml",
        }, **extras)

    def deploy(self, **extras):
        return self.sandbox(**dict(
            dict(operacao="deploy", selecao=["etapa"], plan_ref="plans/p.json", plan_estado_compativel=True,
                 identidade="usuario@avante", destinos_resolvidos=["catalogo.esquema.tabela"]), **extras))

    def test_sandbox_aceita_validate_com_campos_nao_verificados_e_deploy_com_plan(self):
        self.verificar(self.evento("sandbox", self.sandbox()))
        self.verificar(self.evento("sandbox", self.deploy()))
        self.verificar(self.evento("sandbox", self.sandbox(operacao="plan", plan_ref="plans/p.json")))
        with self.assertRaisesRegex(ValueError, "Produtor nao corresponde"):
            self.verificar(self.evento("sandbox", self.sandbox(), produtor="coordenador"))
        with self.assertRaisesRegex(ValueError, "Forma ainda nao adotada"):
            self.verificar(self.evento("sandbox", self.sandbox(), versao="3.1"))

    def test_sandbox_recusa_deploy_aprovado_sem_plan_valido_e_campos_malformados(self):
        for alteracao in (dict(plan_ref=None), dict(plan_estado_compativel=False),
                          dict(plan_estado_compativel=None)):
            with self.subTest(alteracao=alteracao), self.assertRaisesRegex(ValueError, "plan valido"):
                self.verificar(self.evento("sandbox", self.deploy(**alteracao)))
        # Deploy reprovado pode ficar registrado sem plan: o registro nao aprova nada.
        self.verificar(self.evento("sandbox", self.deploy(resultado="fail", plan_ref=None,
                                                          plan_estado_compativel=None)))
        for alteracao in (dict(destinos_resolvidos=[]), dict(destinos_resolvidos=["a", "nao_verificado"]),
                          dict(destinos_resolvidos=[" "]), dict(selecao=[""]), dict(identidade=" "),
                          dict(target=""), dict(operacao="destroy"), dict(plan_ref="../p.json"),
                          dict(teste_ref="ausente.json"), dict(agente_id="../x"), dict(extra="campo")):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                self.verificar(self.evento("sandbox", self.sandbox(**alteracao)))
        invalido = self.sandbox()
        del invalido["teste_ref"]
        with self.assertRaises(ValueError):
            self.verificar(self.evento("sandbox", invalido))

    def test_sandbox_nao_verificado_depende_da_operacao(self):
        nao_verificado = self.sandbox()
        self.assertEqual(nao_verificados_sandbox(dict(nao_verificado, operacao="validate")), [])
        self.assertEqual(nao_verificados_sandbox(dict(nao_verificado, operacao="plan")), [])
        self.assertEqual(nao_verificados_sandbox(dict(nao_verificado, operacao="deploy")),
                         ["identidade", "destinos_resolvidos"])
        self.assertEqual(nao_verificados_sandbox(dict(nao_verificado, operacao="run")),
                         ["identidade", "destinos_resolvidos", "coordenacao"])
        self.assertEqual(nao_verificados_sandbox(self.deploy()), [])
        self.assertEqual(nao_verificados_sandbox(self.deploy(destinos_resolvidos=["nao_verificado"])),
                         ["destinos_resolvidos"])

    def paridade(self, **extras):
        return dict({
            "criterio_id": "paridade", "recorte": "Competencia 2026-09",
            "insumos": [{"nome": "origem", "identificador": "tabela_a@v12"},
                        {"nome": "destino", "identificador": "tabela_b@v7"}],
            "contas": [{"id": "linhas", "descricao": "Contagem de linhas", "valor_origem": "100",
                        "valor_destino": "100", "diferenca": "0"}],
            "divergencias": [], "resultado": "pass", "teste_ref": "formas/catalogo.yaml",
        }, **extras)

    def conta_com_gap(self):
        return {"id": "soma", "descricao": "Soma do valor", "valor_origem": "10.50",
                "valor_destino": "10.00", "diferenca": "0.50"}

    def test_paridade_aceita_igualdade_e_gap_explicado(self):
        self.verificar(self.evento("paridade", self.paridade()))
        explicada = {"id": "d1", "estado": "explicada", "explicacao": "Arredondamento da origem",
                     "evidencia_ref": "implementacao/formas.py"}
        self.verificar(self.evento("paridade", self.paridade(
            contas=[self.conta_com_gap()], divergencias=[explicada])))
        pendente = {"id": "d1", "estado": "pendente"}
        self.verificar(self.evento("paridade", self.paridade(
            contas=[self.conta_com_gap()], divergencias=[pendente], resultado="fail")))
        with self.assertRaisesRegex(ValueError, "Produtor nao corresponde"):
            self.verificar(self.evento("paridade", self.paridade(), produtor="coordenador"))
        with self.assertRaisesRegex(ValueError, "Forma ainda nao adotada"):
            self.verificar(self.evento("paridade", self.paridade(), versao="3.1"))

    def test_paridade_com_gap_pendente_ou_inexplicado_nao_pode_ser_pass(self):
        pendente = {"id": "d1", "estado": "pendente"}
        with self.assertRaisesRegex(ValueError, "pendente"):
            self.verificar(self.evento("paridade", self.paridade(
                contas=[self.conta_com_gap()], divergencias=[pendente])))
        with self.assertRaisesRegex(ValueError, "diferenca nas contas"):
            self.verificar(self.evento("paridade", self.paridade(contas=[self.conta_com_gap()])))

    def test_paridade_recusa_conta_e_divergencia_malformadas(self):
        explicada = {"id": "d1", "estado": "explicada", "explicacao": "Motivo"}
        for alteracao in (
                dict(divergencias=[explicada]),  # sem evidencia
                dict(divergencias=[dict(explicada, evidencia_ref="implementacao/formas.py", explicacao=" ")]),
                dict(divergencias=[dict(explicada, evidencia_ref="ausente.txt")]),
                dict(divergencias=[{"id": "d1", "estado": "pendente"}, {"id": "d1", "estado": "pendente"}],
                     resultado="fail"),
                dict(contas=[dict(self.conta_com_gap(), diferenca="0.40")]),
                dict(contas=[dict(self.conta_com_gap(), valor_origem="muito")]),
                dict(contas=[dict(self.conta_com_gap(), valor_origem="NaN", diferenca="NaN")]),
                dict(contas=[]), dict(insumos=[]), dict(recorte=" "),
                dict(insumos=[{"nome": "origem", "identificador": " "}]),
                dict(divergencias=[{"id": "d1", "estado": "talvez"}]), dict(agente_id="../x"),
                dict(extra="campo")):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                self.verificar(self.evento("paridade", self.paridade(**alteracao)))

    def test_eventos_31_adotados_continuam_legiveis_e_candidatas_nao(self):
        legado = self.evento("guarda", {
            "operacao": "registrar_verificacao",
            "checagens": [{"id": "estado", "resultado": "nao_aplica", "motivo": "Sem alteração"}],
            "decisao": "permitir",
            "recuperacao": "",
        }, versao="3.1")
        self.verificar(legado)

        candidato = self.evento("chamada", {
            "chamada_id": "call-1", "papel": "test", "runtime": "cursor",
            "ids_observados": [{"nome": "agent_run_id", "valor": "run-123"}],
            "inicio": "2026-10-03T12:00:00+00:00", "fim": "2026-10-03T12:01:00+00:00",
            "status": "concluida",
        }, versao="3.1")
        with self.assertRaisesRegex(ValueError, "Forma ainda nao adotada"):
            self.verificar(candidato)
        with self.assertRaisesRegex(ValueError, "Forma ainda nao adotada"):
            validar_dados("chamada", candidato["dados"])

    def test_contrato_32_inspecao_dispensa_comando_e_cwd_com_regras_condicionais(self):
        criterio = {
            "id": "documentacao",
            "tipo": "inspecao_documental",
            "obrigatorio": True,
            "esperado": "Os caminhos atendem às checagens",
            "verificacao": {
                "caminhos": ["implementacao/formas.py"],
                "checagens": [{"id": "referencia", "esperado": "Fonte conferida"}],
                "produtor": "coordenador",
            },
        }
        self.assertEqual(validar_dados("contrato", self.contrato(criterio), "3.2")["aceite"][0], criterio)

        for chave in ("caminhos", "checagens", "produtor"):
            invalido = deepcopy(criterio)
            del invalido["verificacao"][chave]
            with self.subTest(campo_ausente=chave), self.assertRaises(ValueError):
                validar_dados("contrato", self.contrato(invalido), "3.2")

        invalido = deepcopy(criterio)
        invalido["verificacao"]["produtor"] = "hook"
        with self.assertRaises(ValueError):
            validar_dados("contrato", self.contrato(invalido), "3.2")

    def test_contrato_32_executavel_e_contrato_31_mantem_comando_cwd_caminhos(self):
        verificacao = {"comando": "py teste.py", "cwd": ".", "caminhos": ["implementacao/formas.py"]}
        criterio = {
            "id": "teste",
            "tipo": "teste",
            "obrigatorio": True,
            "esperado": "Processo termina em zero",
            "verificacao": deepcopy(verificacao),
        }
        validar_dados("contrato", self.contrato(criterio), "3.2")
        for chave in verificacao:
            invalido = deepcopy(criterio)
            del invalido["verificacao"][chave]
            with self.subTest(versao="3.2", campo_ausente=chave), self.assertRaises(ValueError):
                validar_dados("contrato", self.contrato(invalido), "3.2")

        inspecao_31 = {
            "id": "documentacao",
            "tipo": "inspecao_documental",
            "obrigatorio": True,
            "esperado": "Os caminhos atendem às checagens",
            "verificacao": {"caminhos": ["implementacao/formas.py"]},
        }
        with self.assertRaises(ValueError):
            validar_dados("contrato", self.contrato(inspecao_31), "3.1")
        inspecao_31["verificacao"].update(comando="py conferir.py", cwd=".")
        validar_dados("contrato", self.contrato(inspecao_31), "3.1")

    def test_autorizacao_ref_so_e_aceita_em_ambiente_32_com_caminho_relativo(self):
        ambiente = {
            "id": "sandbox",
            "tipo": "ambiente",
            "obrigatorio": True,
            "esperado": "A operação tem autorização válida",
            "verificacao": {
                "comando": "databricks bundle deploy",
                "cwd": ".",
                "caminhos": ["configuracao/politica.json"],
            },
        }
        validar_dados("contrato", self.contrato(ambiente), "3.2")
        ambiente_autorizado = deepcopy(ambiente)
        ambiente_autorizado["autorizacao_ref"] = "evidencia/autorizacao.md"
        validar_dados("contrato", self.contrato(ambiente_autorizado), "3.2")

        for ref in ("../autorizacao.md", "C:/autorizacao.md"):
            invalido = deepcopy(ambiente_autorizado)
            invalido["autorizacao_ref"] = ref
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                validar_dados("contrato", self.contrato(invalido), "3.2")

        teste_com_autorizacao = deepcopy(ambiente_autorizado)
        teste_com_autorizacao["tipo"] = "teste"
        with self.assertRaisesRegex(ValueError, "autorizacao_ref nao permitido"):
            validar_dados("contrato", self.contrato(teste_com_autorizacao), "3.2")

        with self.assertRaisesRegex(ValueError, "autorizacao_ref nao permitido"):
            validar_dados("contrato", self.contrato(ambiente_autorizado), "3.1")


if __name__ == "__main__":
    unittest.main()
