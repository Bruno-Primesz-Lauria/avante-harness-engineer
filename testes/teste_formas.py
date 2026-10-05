"""Aceite focado das formas 3.2 e compatibilidade de eventos 3.1."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))
from formas import validar, validar_dados


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
