"""Testes do gerador nativo sem instalar arquivos no workspace real."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import shutil
import tempfile
import unittest

import yaml

from adaptadores import gerar_agentes


RAIZ = Path(__file__).resolve().parents[1]
SECOES = {
    "Responsabilidade",
    "Gatilho",
    "Entradas",
    "Ferramentas permitidas",
    "Skills",
    "Capacidades",
    "Saída",
    "Término",
}
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class GerarAgentesTestes(unittest.TestCase):
    def setUp(self):
        self.temporario = tempfile.TemporaryDirectory(dir=RAIZ)
        self.raiz = Path(self.temporario.name)
        shutil.copytree(RAIZ / "agentes", self.raiz / "agentes")

    def tearDown(self):
        self.temporario.cleanup()

    def test_definicoes_neutras_contem_campos_da_secao_4(self):
        for papel in sorted(gerar_agentes.PAPEIS):
            texto = (RAIZ / "agentes" / f"{papel}.md").read_text(encoding="utf-8")
            secoes = set(re.findall(r"(?m)^##\s+(.+?)\s*$", texto))
            self.assertLessEqual(SECOES, secoes, papel)

    def test_geracao_usa_apenas_frontmatter_observado_por_runtime(self):
        claude = gerar_agentes.gerar(self.raiz, "claude_code")
        cursor = gerar_agentes.gerar(self.raiz, "cursor")
        self.assertEqual(7, len(claude))
        self.assertEqual(7, len(cursor))
        frontmatter_claude = {}
        for caminho, texto in claude.items():
            correspondencia = FRONTMATTER.search(texto)
            self.assertIsNotNone(correspondencia)
            dados = yaml.safe_load(correspondencia.group(1))
            self.assertEqual(
                {"name", "description", "tools", "model", "skills"}, set(dados)
            )
            self.assertEqual("inherit", dados["model"])
            self.assertTrue(all(skill.startswith("databricks:databricks-") for skill in dados["skills"]))
            frontmatter_claude[caminho] = dados
        for texto in cursor.values():
            correspondencia = FRONTMATTER.search(texto)
            self.assertIsNotNone(correspondencia)
            dados = yaml.safe_load(correspondencia.group(1))
            self.assertEqual({"name", "description", "model"}, set(dados))
            self.assertEqual("inherit", dados["model"])
            self.assertIn(".agents/skills/databricks-<nome>/SKILL.md", texto)
        self.assertNotIn(
            "execution-compute", frontmatter_claude[".claude/agents/test.md"]["skills"]
        )
        dab_cursor = cursor[".cursor/agents/dab.md"]
        for skill in ("core", "dabs", "jobs", "pipelines"):
            self.assertIn(f".agents/skills/databricks-{skill}/SKILL.md", dab_cursor)

    def test_nome_e_descricao_sem_aspas_porque_o_cursor_as_mantem_no_nome(self):
        for runtime in ("claude_code", "cursor"):
            for caminho, texto in gerar_agentes.gerar(self.raiz, runtime).items():
                papel = Path(caminho).stem
                self.assertIn(f"\nname: {papel}\n", texto, caminho)
                self.assertRegex(texto, r"\ndescription: [^\"']", caminho)
                dados = yaml.safe_load(FRONTMATTER.search(texto).group(1))
                self.assertEqual(papel, dados["name"])

    def test_descricao_que_exigiria_aspas_e_recusada(self):
        rota = self.raiz / "agentes/roteamento.yaml"
        texto = rota.read_text(encoding="utf-8")
        rota.write_text(texto.replace("Investigar fontes e dependências sem editar produto.",
                                      "Investigar: fontes e dependências.", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "exige aspas"):
            gerar_agentes.gerar(self.raiz, "cursor")

    def test_gerador_recusa_definicao_sem_campo_da_secao_4(self):
        caminho = self.raiz / "agentes" / "map.md"
        texto = caminho.read_text(encoding="utf-8")
        caminho.write_text(texto.replace("## Saída", "## Resultado", 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "sem campos da seção 4: Saída"):
            gerar_agentes.gerar(self.raiz, "claude_code")

    def test_segunda_instalacao_fica_estavel_e_verificar_e_repetivel(self):
        gerar_agentes.instalar("claude_code", self.raiz)
        antes = {
            caminho.relative_to(self.raiz): caminho.read_bytes()
            for caminho in (self.raiz / ".claude/agents").glob("*.md")
        }
        gerar_agentes.instalar("claude_code", self.raiz)
        depois = {
            caminho.relative_to(self.raiz): caminho.read_bytes()
            for caminho in (self.raiz / ".claude/agents").glob("*.md")
        }
        self.assertEqual(antes, depois)
        self.assertEqual([], list((self.raiz / ".claude/agents").glob("*.backup.*")))
        primeira = gerar_agentes.verificar(self.raiz)
        segunda = gerar_agentes.verificar(self.raiz)
        self.assertEqual(primeira, segunda)
        self.assertTrue(primeira[0])

    def test_edicao_manual_e_detectada_e_nunca_sobrescrita(self):
        gerar_agentes.instalar("cursor", self.raiz)
        caminho = self.raiz / ".cursor/agents/map.md"
        caminho.write_bytes(caminho.read_bytes() + b"\nEdi\xc3\xa7\xc3\xa3o manual.\n")
        manual = caminho.read_bytes()
        with self.assertRaisesRegex(ValueError, "Divergência manual detectada"):
            gerar_agentes.instalar("cursor", self.raiz)
        self.assertEqual(manual, caminho.read_bytes())
        ok, resultados = gerar_agentes.verificar(self.raiz)
        self.assertFalse(ok)
        self.assertIn("DIVERGENTE: .cursor/agents/map.md", resultados)

    def test_edicao_manual_preexistente_impede_instalacao_parcial(self):
        caminho = self.raiz / ".cursor/agents/map.md"
        caminho.parent.mkdir(parents=True)
        caminho.write_text("agente escrito manualmente\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Divergência manual detectada"):
            gerar_agentes.instalar("cursor", self.raiz)
        self.assertEqual([caminho], list(caminho.parent.glob("*.md")))
        self.assertEqual("agente escrito manualmente\n", caminho.read_text(encoding="utf-8"))

    def test_arquivo_gerado_anterior_tem_backup_antes_da_atualizacao(self):
        gerar_agentes.instalar("cursor", self.raiz)
        caminho = self.raiz / ".cursor/agents/map.md"
        original = caminho.read_bytes()
        fonte = self.raiz / "agentes/map.md"
        fonte.write_text(
            fonte.read_text(encoding="utf-8") + "\nNota de revisão.\n", encoding="utf-8"
        )
        gerar_agentes.instalar("cursor", self.raiz)
        backups = list(caminho.parent.glob("map.md.backup.*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(original, backups[0].read_bytes())
        self.assertNotEqual(original, caminho.read_bytes())
        self.assertTrue(gerar_agentes.verificar(self.raiz)[0])

    def test_modo_sem_flag_mostra_sem_gravar(self):
        saida = StringIO()
        with redirect_stdout(saida):
            retorno = gerar_agentes.main([], self.raiz)
        self.assertEqual(0, retorno)
        self.assertIn("# .claude/agents/map.md", saida.getvalue())
        self.assertIn("# .cursor/agents/map.md", saida.getvalue())
        self.assertFalse((self.raiz / ".claude/agents").exists())
        self.assertFalse((self.raiz / ".cursor/agents").exists())


if __name__ == "__main__":
    unittest.main()
