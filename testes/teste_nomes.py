"""Nomes legíveis de prova, sessão e plan."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao")]
from nomes import nome_arquivo, nome_de_pasta, nome_fatia, nome_livre, nome_plan, reservar_diretorio, slug


class NomesTestes(unittest.TestCase):
    def test_slug_remove_acento_e_separador(self):
        self.assertEqual(slug("Verificar a mudança"), "verificar-a-mudanca")
        self.assertEqual(slug("../../etc"), "etc")
        self.assertEqual(slug(""), "fatia")
        self.assertEqual(slug("publicar no sandbox o job completo", 22), "publicar-no-sandbox")
        self.assertLessEqual(len(slug("palavra " * 40, 60)), 60)

    def test_nome_de_pasta_rejeita_caminho(self):
        self.assertEqual(nome_de_pasta("2026-10-19-correcao-verificar"), "2026-10-19-correcao-verificar")
        self.assertIsNone(nome_de_pasta(".."))
        self.assertIsNone(nome_de_pasta("a/b"))
        self.assertIsNone(nome_de_pasta("a\\b"))
        self.assertIsNone(nome_de_pasta("-oculto"))

    def test_reserva_e_colisao_ficam_na_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = nome_fatia("correcao", "Verificar a mudança",
                              datetime(2026, 10, 19, tzinfo=timezone.utc))
            primeiro = reservar_diretorio(pasta, base)
            segundo = reservar_diretorio(pasta, base)
            self.assertEqual(primeiro, "2026-10-19-correcao-verificar-a-mudanca")
            self.assertEqual(segundo, primeiro + "-2")
            self.assertTrue((Path(pasta) / primeiro).is_dir())
            self.assertLessEqual(len(primeiro), 100)
            self.assertLessEqual(len(segundo), 100)

    def test_nome_livre_preserva_a_pasta_atual(self):
        with tempfile.TemporaryDirectory() as pasta:
            atual = Path(pasta) / "2026-10-19-docs-layout"
            atual.mkdir()
            self.assertEqual(nome_livre(pasta, atual.name, atual), atual.name)
            self.assertEqual(nome_livre(pasta, atual.name), atual.name + "-2")

    def test_plan_usa_target_e_selecao(self):
        quando = datetime(2026, 10, 19, 12, 56, tzinfo=timezone.utc)
        self.assertEqual(
            nome_plan("sandbox", ["jobs.job_pm_coswin_snapshot"], quando),
            "2026-10-19-plan-sandbox-jobs-job-pm-coswin-snapshot")
        self.assertEqual(nome_plan("sandbox", [], quando), "2026-10-19-plan-sandbox-bundle")
        with tempfile.TemporaryDirectory() as pasta:
            nome = nome_arquivo(pasta, nome_plan("sandbox", ["etapa"], quando), ".json")
            self.assertEqual(nome, "2026-10-19-plan-sandbox-etapa")
            (Path(pasta) / f"{nome}.json").write_text("{}", encoding="utf-8")
            self.assertEqual(nome_arquivo(pasta, nome, ".json"), nome + "-2")


if __name__ == "__main__":
    unittest.main()
