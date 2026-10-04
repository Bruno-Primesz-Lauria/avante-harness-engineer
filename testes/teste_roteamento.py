"""Confere o roteamento YAML com o desenho incorporado e o catálogo."""
from copy import deepcopy
import json
from pathlib import Path
import re
import unicodedata
import unittest

import yaml


RAIZ = Path(__file__).resolve().parents[1]
PAPEIS = {"map", "config", "implement", "test", "refute", "docs", "dab"}
PAPEIS_COM_GATILHO = {
    "map": "investigacao_ampla",
    "config": "config",
    "implement": "implement",
    "test": "test",
    "refute": "refute",
    "docs": "docs",
    "dab": "dab",
}
TERMINAIS = {"BLOCKED", "FAILED", "DECIDE", "fecho", "omitir_membro"}
TRANSICOES = {
    "apos_execucao",
    "apos_conclusao",
    "apos_aprovacao",
    "apos_reprovacao",
    "apos_preparo",
    "apos_reproducao",
    "apos_resultado_esperado",
    "apos_resultado_inesperado",
    "apos_resultado_inconclusivo",
    "apos_sem_achado_procedente",
    "apos_achado_procedente",
    "apos_veredito",
    "se_nao_aplicavel",
    "se_indisponivel",
    "se_nenhum_membro_aplicavel",
    "se_caso_existente_decide",
    "se_criterio_ausente",
    "se_autorizacao_ausente",
    "se_autorizada",
    "se_guarda_negar",
}


def _html_constante(texto, nome):
    marcador = f"const {nome} = "
    inicio = texto.index(marcador) + len(marcador)
    return json.JSONDecoder().raw_decode(texto[inicio:])[0]


def _normalizar(texto):
    sem_acentos = unicodedata.normalize("NFKD", str(texto))
    return "".join(
        c for c in sem_acentos
        if c != "\ufffd"
        and not unicodedata.combining(c)
        and not unicodedata.category(c).startswith("C")
    ).casefold()


def _objetos_fluxo(itens):
    """Percorre passos e membros paralelos sem copiar nenhum catálogo."""
    for item in itens:
        if not isinstance(item, dict):
            continue
        yield item
        yield from _objetos_fluxo(item.get("membros", []))


def _papeis_no_fluxo(itens):
    return {
        item["responsavel"]
        for item in _objetos_fluxo(itens)
        if item.get("responsavel")
    }


def _papeis_no_rotulo(rotulo):
    termos = set(re.findall(r"[a-z_]+", _normalizar(rotulo)))
    papeis = termos & PAPEIS
    if termos & {"coordenador", "principal"} or "agente_principal" in termos:
        papeis.add("coordenador")
    return papeis


def _assert_trilhas_agente_alinhadas(caso, trilhas, papel, peca_catalogo, peca_html):
    trilhas_catalogo = set(
        trilhas if peca_catalogo["trilhas"] == "*" else peca_catalogo["trilhas"]
    )
    trilhas_html = set(trilhas if peca_html["jobs"] == "*" else peca_html["jobs"])
    caso.assertEqual(trilhas, trilhas_catalogo, f"trilhas no catálogo para {papel}")
    caso.assertEqual(trilhas, trilhas_html, f"trilhas no PECAS para {papel}")


def _assert_fontes_alinhadas(caso, rota, catalogo, dados, pecas_html):
    trilhas = rota["trilhas"]
    html_trilhas = dados["playbooks"]
    ids_trilhas = {trilha["id"] for trilha in dados["jobs"]}
    caso.assertEqual(set(trilhas), set(html_trilhas))
    caso.assertEqual(set(trilhas), ids_trilhas)

    pecas_catalogo = {
        peca["id"]: peca
        for peca in catalogo["pecas"]
        if peca.get("tipo") == "subagent"
    }
    pecas_diagrama = {
        peca["name"]: peca
        for peca in pecas_html
        if peca.get("kind") == "subagent"
    }
    caso.assertEqual(PAPEIS, set(rota["agentes"]))
    caso.assertEqual(PAPEIS, set(pecas_catalogo))
    caso.assertEqual(PAPEIS, set(pecas_diagrama))

    trilhas_por_papel = {papel: set() for papel in PAPEIS | {"coordenador"}}
    for trilha, definicao in trilhas.items():
        fluxo = definicao["fluxo"]
        objetos = list(_objetos_fluxo(fluxo))
        ids = [objeto["id"] for objeto in objetos if objeto.get("id")]
        caso.assertEqual(len(ids), len(set(ids)), f"IDs repetidos no fluxo {trilha}")
        papeis_fluxo = _papeis_no_fluxo(fluxo)
        papeis_desconhecidos = papeis_fluxo - PAPEIS - {"coordenador"}
        caso.assertLessEqual(
            papeis_fluxo, PAPEIS | {"coordenador"},
            f"papel sem definição no fluxo {trilha}: {papeis_desconhecidos}",
        )
        for papel in papeis_fluxo:
            trilhas_por_papel[papel].add(trilha)

        nos = html_trilhas[trilha]["nodes"]
        arestas = html_trilhas[trilha]["edges"]
        ids_html = [no["id"] for no in nos]
        caso.assertEqual(len(ids_html), len(set(ids_html)), f"IDs repetidos no HTML {trilha}")
        ids_html_set = set(ids_html)
        for aresta in arestas:
            caso.assertIn(aresta["from"], ids_html_set, f"origem de aresta inválida em {trilha}")
            caso.assertIn(aresta["to"], ids_html_set, f"destino de aresta inválido em {trilha}")

        papeis_html = set().union(*(_papeis_no_rotulo(no.get("agent", "")) for no in nos))
        opcional = {
            papel for papel in papeis_fluxo
            if papel == "map" and rota["gatilhos"]["investigacao_ampla"].get("opcional")
        }
        obrigatorios_no_html = papeis_fluxo - opcional
        caso.assertLessEqual(
            obrigatorios_no_html, papeis_html,
            f"papel roteado ausente dos nós HTML em {trilha}: {obrigatorios_no_html - papeis_html}",
        )

        destinos_conhecidos = set(ids)
        for objeto in objetos:
            for chave, destino in objeto.items():
                if chave not in TRANSICOES:
                    continue
                if isinstance(destino, str):
                    caso.assertIn(
                        destino, destinos_conhecidos | TERMINAIS,
                        f"destino {destino!r} não definido em {trilha}.{objeto.get('id', 'membro')}",
                    )

    gatilhos = rota["gatilhos"]
    for papel, chave_gatilho in PAPEIS_COM_GATILHO.items():
        gatilho = gatilhos[chave_gatilho]
        escopo_gatilho = gatilho.get("trilhas", "*")
        trilhas_gatilho = set(trilhas if escopo_gatilho == "*" else escopo_gatilho)
        caso.assertEqual(
            trilhas_por_papel[papel], trilhas_gatilho,
            f"trilhas do papel {papel} não acompanham seu gatilho",
        )
        peca_catalogo = pecas_catalogo[papel]
        peca_html = pecas_diagrama[papel]
        _assert_trilhas_agente_alinhadas(
            caso, trilhas_gatilho, papel, peca_catalogo, peca_html
        )

        definicao = rota["agentes"][papel]
        metadados = definicao["metadados"]
        caso.assertEqual(metadados["claude_code"]["politica"], peca_catalogo["politica"])
        caso.assertEqual(metadados["claude_code"]["politica"], peca_html["politica"])
        for runtime in ("claude_code", "cursor"):
            esperado_instalado = "instalado" if metadados[runtime]["instalado"] else "nao_instalado"
            caso.assertEqual(esperado_instalado, peca_catalogo["instalado"][runtime], f"instalado: {papel}/{runtime}")
            caso.assertEqual(esperado_instalado, peca_html["instalado"][runtime], f"instalado HTML: {papel}/{runtime}")
            caso.assertEqual(metadados[runtime]["observado"], peca_catalogo["observado"][runtime])
            caso.assertEqual(metadados[runtime]["observado"], peca_html["observado"][runtime])

        gatilho_texto = _normalizar(chave_gatilho + " " + str(gatilho))
        catalogo_texto = _normalizar(peca_catalogo.get("gatilho", ""))
        html_texto = _normalizar(peca_html.get("trigger", ""))
        pistas_rota = {
            "map": ("investigacao",),
            "config": ("yaml", "ingestao", "recurso"),
            "implement": ("notebook", "python", "sql"),
            "test": ("teste", "validacao_dados", "paridade"),
            "refute": ("trilha estruturada",),
            "docs": ("document",),
            "dab": ("ambiente", "autorizacao"),
        }[papel]
        pistas_descricao = {
            "map": ("investiga",),
            "config": ("yaml", "ingestao", "recurso"),
            "implement": ("notebook", "python", "sql"),
            "test": ("aceite",),
            "refute": ("revisao",),
            "docs": ("document",),
            "dab": ("ambiente", "autorizacao"),
        }[papel]
        for pista in pistas_rota:
            caso.assertIn(pista, gatilho_texto, f"gatilho YAML sem {pista} para {papel}")
        for pista in pistas_descricao:
            caso.assertIn(pista, catalogo_texto, f"gatilho do catálogo sem {pista} para {papel}")
            caso.assertIn(pista, html_texto, f"gatilho PECAS sem {pista} para {papel}")

        if papel == "map":
            caso.assertTrue(gatilho.get("opcional"))
            caso.assertEqual("opcional", peca_catalogo["ativacao"])
            caso.assertIn("opcional", _normalizar(peca_html["invoke"]))
        else:
            caso.assertNotEqual("opcional", peca_catalogo["ativacao"])
            caso.assertIn("obrigatorio", _normalizar(peca_html["invoke"]))
        if papel == "test":
            caso.assertEqual(
                {"teste", "validacao_dados", "paridade"}, set(gatilho["criterios"])
            )

    caso.assertTrue(trilhas_por_papel["coordenador"] == set(trilhas))


class ConsistenciaRoteamentoTestes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rota = yaml.safe_load((RAIZ / "agentes/roteamento.yaml").read_text(encoding="utf-8"))
        cls.catalogo = yaml.safe_load((RAIZ / "acervo/catalogo.yaml").read_text(encoding="utf-8"))
        # O HTML tem trechos legados com bytes inválidos; o JSON embutido continua legível em UTF-8.
        cls.html = (RAIZ / "user-harness-esteira-v3.html").read_bytes().decode("utf-8", errors="replace")
        cls.dados = _html_constante(cls.html, "DADOS")
        cls.pecas_html = _html_constante(cls.html, "PECAS")

    def assert_fontes_alinhadas(self, catalogo=None):
        _assert_fontes_alinhadas(
            self, self.rota, catalogo or self.catalogo, self.dados, self.pecas_html
        )

    def test_rotas_papeis_gatilhos_metadados_e_diagrama_coincidem(self):
        self.assert_fontes_alinhadas()

    def test_divergencia_real_de_trilha_no_catalogo_e_detectada(self):
        catalogo_alterado = deepcopy(self.catalogo)
        dab = next(peca for peca in catalogo_alterado["pecas"] if peca.get("id") == "dab")
        dab["trilhas"].remove("validacao")
        peca_html = next(peca for peca in self.pecas_html if peca.get("name") == "dab")
        with self.assertRaisesRegex(AssertionError, "trilhas no catálogo para dab"):
            _assert_trilhas_agente_alinhadas(
                self, set(self.rota["gatilhos"]["dab"]["trilhas"]), "dab",
                dab, peca_html,
            )

    def test_dec_1_separa_configuracao_e_codigo_na_correcao(self):
        self.assertEqual("aprovada", self.rota["decisoes"]["dec_1"]["estado"])
        fluxo = self.rota["trilhas"]["correcao"]["fluxo"]
        reproducao = next(passo for passo in fluxo if passo.get("id") == "teste_reproduz")
        self.assertEqual("fail", reproducao["resultado_esperado"])
        self.assertEqual("escrita_por_superficie", reproducao["apos_resultado_esperado"])
        self.assertEqual("DECIDE", reproducao["apos_resultado_inesperado"])
        self.assertEqual("BLOCKED", reproducao["apos_resultado_inconclusivo"])
        responsaveis = _papeis_no_fluxo(fluxo)
        self.assertTrue({"config", "implement"} <= responsaveis)
        self.assertIn("correcao", self.rota["gatilhos"]["config"]["trilhas"])
        self.assertIn("correcao", self.rota["gatilhos"]["implement"]["trilhas"])
        nos = self.dados["playbooks"]["correcao"]["nodes"]
        papeis_html = set().union(*(_papeis_no_rotulo(no.get("agent", "")) for no in nos))
        self.assertTrue({"config", "implement"} <= papeis_html)

    def test_dec_2_prepara_teste_somente_se_caso_nao_decidir(self):
        self.assertEqual("aprovada", self.rota["decisoes"]["dec_2"]["estado"])
        passos = {passo.get("id"): passo for passo in self.rota["trilhas"]["manutencao"]["fluxo"]}
        preparar = passos["preparar_teste_se_necessario"]
        self.assertEqual("test", preparar["responsavel"])
        self.assertIn("caso existente", _normalizar(preparar["quando"]))
        self.assertEqual("escrita_por_superficie", preparar["se_caso_existente_decide"])
        html = self.dados["playbooks"]["manutencao"]
        nos = {no["id"]: no for no in html["nodes"]}
        arestas = {(a["from"], a["to"], a.get("when")) for a in html["edges"]}
        self.assertIn("test", _papeis_no_rotulo(nos["preparar"]["agent"]))
        self.assertIn(("caso_cobre", "preparar", "nao"), {
            (origem, destino, _normalizar(quando)) for origem, destino, quando in arestas
        })
        self.assertIn(("caso_cobre", "tipo_arquivo", "sim"), arestas)

    def test_dec_3_exige_criterio_ambiente_e_autorizacao_nas_quatro_trilhas(self):
        self.assertEqual("aprovada", self.rota["decisoes"]["dec_3"]["estado"])
        gatilho = self.rota["gatilhos"]["dab"]
        self.assertEqual("ambiente", gatilho["criterio"])
        self.assertTrue(gatilho["exige_autorizacao_registrada"])
        esperadas = {"novo", "manutencao", "correcao", "validacao"}
        self.assertEqual(esperadas, set(gatilho["trilhas"]))
        for trilha in esperadas:
            passos = list(_objetos_fluxo(self.rota["trilhas"][trilha]["fluxo"]))
            gate = next(p for p in passos if p.get("id") == "gate_ambiente")
            self.assertEqual("DECIDE", gate["se_autorizacao_ausente"])
            self.assertEqual("dab", gate["se_autorizada"])
            self.assertEqual("BLOCKED", gate["se_guarda_negar"])
            self.assertTrue(any(p.get("id") == "dab" and p.get("responsavel") == "dab" for p in passos))
            html = self.dados["playbooks"][trilha]
            edges = html["edges"]
            self.assertTrue(any(
                a["to"] == "ambiente" and "autoriz" in _normalizar(a.get("when", ""))
                for a in edges
            ), f"HTML sem caminho autorizado para dab em {trilha}")
            self.assertTrue(any(
                "autoriz" in _normalizar(a.get("when", "")) and a["to"] in {"decide", "pendencia"}
                for a in edges
            ), f"HTML sem caminho de decisão por falta de autorização em {trilha}")

    def test_d4_review_coordena_antes_e_depois_do_refute_e_bloqueia_indisponibilidade(self):
        fluxo = self.rota["trilhas"]["review"]["fluxo"]
        ids = [passo.get("id") for passo in fluxo]
        self.assertLess(ids.index("coordenacao_inicial"), ids.index("refute"))
        self.assertLess(ids.index("refute"), ids.index("coordenacao_final"))
        refute = next(passo for passo in fluxo if passo.get("id") == "refute")
        self.assertEqual("BLOCKED", refute["se_indisponivel"])
        html = self.dados["playbooks"]["review"]
        arestas = {(a["from"], a["to"]) for a in html["edges"]}
        self.assertIn(("coordenador", "refute"), arestas)
        self.assertIn(("refute", "veredito"), arestas)
        nos = {no["id"]: no for no in html["nodes"]}
        self.assertIn("coordenador", _papeis_no_rotulo(nos["veredito"]["agent"]))
        self.assertIn(("refute", "blocked"), arestas)

    def test_d5_hook_de_shell_em_subagente_permanece_pendente_de_observacao(self):
        self.assertEqual(
            "pendente_p0_5",
            self.rota["runtimes"]["cursor"]["observacao_habilidades_em_subagente"],
        )
        texto = _normalizar(self.html)
        self.assertIn("cobertura no shell de subagentes", texto)
        self.assertIn("observada na sondagem p0.5", texto)
        pecas = {p["id"]: p for p in self.catalogo["pecas"] if p.get("tipo") == "subagent"}
        self.assertEqual("pendente", pecas["implement"]["observado"]["cursor"]["estado"])


if __name__ == "__main__":
    unittest.main()
