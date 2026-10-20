"""Entrada sob registros e indice local, sem usar o .execucoes real salvo na CLI."""
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

RAIZ = Path(__file__).resolve().parents[1]
MARCA = "entradas/<assunto>/"


def carregar_prova():
    caminho = RAIZ / "adaptadores" / "prova.py"
    # O script resolve `executar` pela propria pasta; importlib nao a coloca no path.
    pasta = str(caminho.parent.resolve())
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    spec = importlib.util.spec_from_file_location("prova_entrada_registros", caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar {caminho}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


PROVA = carregar_prova()


def escrever(caminho: Path, texto: str = "") -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


class ExigirEntradaTestes(unittest.TestCase):
    def setUp(self):
        if not hasattr(PROVA, "exigir_entrada"):
            self.fail("adaptadores/prova.py nao define exigir_entrada")

    def recusar(self, registros: Path, arquivo: Path) -> None:
        with self.assertRaisesRegex(ValueError, re.escape(MARCA)):
            PROVA.exigir_entrada(registros, arquivo)

    def test_arquivo_direto_em_registros_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "contrato.yaml")
            self.recusar(registros, arquivo)

    def test_entradas_sem_assunto_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "entradas" / "contrato.yaml")
            self.recusar(registros, arquivo)

    def test_entradas_com_assunto_aceito(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "entradas" / "pm-coswin" / "contrato.yaml")
            self.assertIsNone(PROVA.exigir_entrada(registros, arquivo))

    def test_provas_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "provas" / "abc" / "contrato.yaml")
            self.recusar(registros, arquivo)

    def test_segmento_extra_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "entradas" / "pm-coswin" / "extra" / "contrato.yaml")
            self.recusar(registros, arquivo)

    def test_assunto_oculto_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            arquivo = escrever(registros / "entradas" / ".oculto" / "contrato.yaml")
            self.recusar(registros, arquivo)

    def test_arquivo_fora_de_registros_aceito(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            registros = base / "registros"
            registros.mkdir()
            arquivo = escrever(base / "fora" / "contrato.yaml")
            self.assertIsNone(PROVA.exigir_entrada(registros, arquivo))

    def test_resolvido_dentro_do_assunto_aceito(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            escrever(registros / "entradas" / "pm-coswin" / "contrato.yaml")
            via = registros / "entradas" / "pm-coswin" / ".." / "pm-coswin" / "contrato.yaml"
            self.assertIsNone(PROVA.exigir_entrada(registros, via))

    def test_resolvido_na_raiz_de_registros_recusado(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            escrever(registros / "contrato.yaml")
            via = registros / "entradas" / "pm-coswin" / ".." / ".." / "contrato.yaml"
            self.recusar(registros, via)

    def test_resolvido_fora_de_registros_aceito(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            registros = base / "registros"
            registros.mkdir()
            escrever(base / "fora.yaml")
            via = registros / "entradas" / ".." / ".." / "fora.yaml"
            self.assertIsNone(PROVA.exigir_entrada(registros, via))


class AtualizarIndiceTestes(unittest.TestCase):
    def setUp(self):
        if not hasattr(PROVA, "atualizar_indice"):
            self.fail("adaptadores/prova.py nao define atualizar_indice")

    def indice(self, registros: Path) -> str:
        PROVA.atualizar_indice(registros)
        caminho = registros / "indice.md"
        self.assertTrue(caminho.is_file(), "indice.md ausente")
        return caminho.read_text(encoding="utf-8")

    def assert_descricao(self, texto: str) -> None:
        self.assertIn("# Registros locais", texto)
        self.assertIn(MARCA, texto)
        self.assertIn("rascunho", texto.casefold())
        self.assertIn("prova.py", texto.casefold())
        self.assertIn("## Fatias", texto)

    def test_indice_de_fatia_aberta(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            escrever(registros / "entradas" / "assunto" / "nota.yaml", "nota: 1\n")
            principal = registros / "provas" / "abc" / "principal"
            escrever(
                principal / "contrato.yaml",
                '{"dados": {"objetivo": "Objetivo de exemplo", "trilha": "manutencao"}}\n',
            )
            escrever(principal / "estado.json", '{"fecho": null}\n')
            texto = self.indice(registros)
            self.assert_descricao(texto)
            self.assertIn("Objetivo de exemplo", texto)
            self.assertIn("manutencao", texto)
            self.assertIn("aberta", texto)
            self.assertIn("assunto", texto.replace("<assunto>", ""))

    def test_indice_usa_status_do_fecho(self):
        with TemporaryDirectory() as tmp:
            registros = Path(tmp)
            yaml_principal = registros / "provas" / "abc" / "principal"
            escrever(
                yaml_principal / "contrato.yaml",
                '{"dados": {"objetivo": "Objetivo fechado", "trilha": "correcao"}}\n',
            )
            escrever(yaml_principal / "fechos" / "f1.yaml", '{"dados": {"status": "DONE"}}\n')
            escrever(yaml_principal / "estado.json", '{"fecho": {"ref": "fechos/f1.yaml"}}\n')
            json_principal = registros / "provas" / "def" / "principal"
            escrever(
                json_principal / "contrato.yaml",
                '{"dados": {"objetivo": "Segundo objetivo", "trilha": "destilar"}}\n',
            )
            escrever(json_principal / "fechos" / "f2.json", '{"dados": {"status": "BLOCKED"}}\n')
            escrever(json_principal / "estado.json", '{"fecho": {"ref": "fechos/f2.json"}}\n')
            texto = self.indice(registros)
            self.assert_descricao(texto)
            self.assertIn("Objetivo fechado", texto)
            self.assertIn("correcao", texto)
            self.assertIn("DONE", texto)
            self.assertIn("Segundo objetivo", texto)
            self.assertIn("destilar", texto)
            self.assertIn("BLOCKED", texto)


class CliEntradaRegistrosTestes(unittest.TestCase):
    def test_cli_recusa_arquivo_direto_em_execucoes(self):
        arquivo = RAIZ / ".execucoes" / "entrada-recusada-pela-suite.yaml"
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text("objetivo: x\n", encoding="utf-8")
            concluido = subprocess.run(
                [
                    sys.executable,
                    "adaptadores/prova.py",
                    "--sessao",
                    "teste-entrada-registros",
                    "--runtime",
                    "cursor",
                    "iniciar",
                    str(arquivo),
                ],
                cwd=RAIZ,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self.assertEqual(concluido.returncode, 2, concluido.stderr)
            self.assertIn(MARCA, concluido.stderr or "", concluido.stderr)
        finally:
            arquivo.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
