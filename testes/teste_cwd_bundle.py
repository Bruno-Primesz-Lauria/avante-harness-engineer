"""Testes locais: fixtures de bundles e processo real do adaptador, sem Databricks."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "implementacao"))
from guarda_cwd import avaliar_cwd, avaliar_operacao
sys.path.insert(0, str(RAIZ / "adaptadores"))
from protocolo import normalizar


def avaliar_evento(evento, politica):
    return avaliar_operacao(normalizar("codex", evento), politica)


class GuardaCwdTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/provas" / self.fixture_id
        self.raiz.parent.mkdir(parents=True, exist_ok=True)
        self.raiz.mkdir()
        self.addCleanup(self.limpar_fixture)
        self.oficial = self.raiz / "bundles"
        self.local = self.oficial / "src" / "notebooks" / "saneamento_migracao"
        self.local.mkdir(parents=True)
        self.yaml_local = self.local / "databricks.yml"
        self.yaml_local.write_text("bundle:\n  name: saneamento_migracao\n", encoding="utf-8")
        (self.oficial / "databricks.yml").write_text(
            "bundle:\n  name: databricks_versioned_assets\n", encoding="utf-8"
        )
        self.politica = {"bundle_local": str(self.local), "bundle_nome": "saneamento_migracao",
                         "registros_raiz": str(self.raiz / "registros")}

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/provas").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino)

    def evento(self, comando="databricks bundle validate -t sandbox -p teste", cwd=None):
        return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                "cwd": str(self.raiz), "session_id": "sessao_teste",
                "tool_input": {"command": comando, "workdir": str(cwd or self.local)}}

    def avaliar(self, comando="databricks bundle validate -t sandbox -p teste", cwd=None):
        return avaliar_evento(self.evento(comando, cwd), self.politica)

    def processo_hook(self, evento, politica=None):
        caminho = self.raiz / "politica.json"
        caminho.write_text(json.dumps(politica or self.politica), encoding="utf-8")
        resposta = subprocess.run(
            [sys.executable, str(RAIZ / "adaptadores/entrada.py"), "codex", str(caminho)],
            input=json.dumps(evento), text=True, capture_output=True, timeout=10,
        )
        if resposta.returncode == 2:
            return {"hookSpecificOutput": {"permissionDecision": "deny"}}
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        return json.loads(resposta.stdout)

    def test_bundle_local_confere(self):
        self.assertEqual(self.avaliar().decisao, "permitir")

    def test_oficial_negado_com_caminho_resolvido(self):
        resultado = self.avaliar(cwd=self.oficial)
        self.assertEqual(resultado.codigo, "cwd_incorreto")
        self.assertEqual(Path(resultado.bundle_arquivo), self.oficial / "databricks.yml")
        self.assertIn(str(self.local), resultado.recuperacao)

    def test_busca_ascendente_detecta_oficial(self):
        shared = self.oficial / "src" / "shared"
        shared.mkdir(parents=True)
        resultado = self.avaliar(cwd=shared)
        self.assertEqual(Path(resultado.bundle_arquivo), self.oficial / "databricks.yml")
        self.assertEqual(resultado.decisao, "negar")

    def test_subdiretorio_local_exige_raiz_exata(self):
        sub = self.local / "mm"
        sub.mkdir()
        self.assertEqual(self.avaliar(cwd=sub).codigo, "cwd_incorreto")

    def test_nome_igual_em_outro_bundle_nao_autoriza(self):
        (self.oficial / "databricks.yml").write_text(self.yaml_local.read_text(), encoding="utf-8")
        self.assertEqual(self.avaliar(cwd=self.oficial).decisao, "negar")

    def test_nome_incorreto(self):
        self.yaml_local.write_text("bundle: {name: oficial}\n", encoding="utf-8")
        self.assertEqual(self.avaliar().codigo, "nome_incorreto")

    def test_yaml_invalido_duplicado_ou_incompleto(self):
        for texto in ("bundle: [", "bundle: {name: a, name: saneamento_migracao}",
                      "null", "bundle: []", "!!python/object:os.system {}"):
            with self.subTest(texto=texto):
                self.yaml_local.write_text(texto, encoding="utf-8")
                self.assertEqual(self.avaliar().decisao, "negar")

    def test_bundle_ausente(self):
        self.yaml_local.unlink()
        self.assertEqual(self.avaliar().codigo, "bundle_incorreto")

    def test_duas_extensoes_sao_ambiguas(self):
        (self.local / "databricks.yaml").write_text("bundle: {}", encoding="utf-8")
        self.assertEqual(self.avaliar().decisao, "negar")

    def test_cwd_inexistente_ou_arquivo(self):
        for cwd in (self.raiz / "ausente", self.yaml_local):
            self.assertEqual(self.avaliar(cwd=cwd).decisao, "negar")

    def test_cwd_relativo_negado(self):
        self.assertEqual(avaliar_cwd(".", self.local, "saneamento_migracao").codigo, "cwd_relativo")

    def test_cwd_sessao_nao_substitui_cwd_ferramenta(self):
        evento = self.evento()
        evento["cwd"] = str(self.local)
        del evento["tool_input"]["workdir"]
        self.assertEqual(avaliar_evento(evento, self.politica).codigo, "cwd_nao_observavel")

    def test_prefixo_absoluto_recupera_sem_alterar_argumentos(self):
        comando = "databricks bundle validate --target=sandbox --profile=teste"
        negado = self.avaliar(comando, self.oficial)
        self.assertEqual(negado.decisao, "negar")
        corrigido = self.evento(f"Set-Location -LiteralPath '{self.local}' -ErrorAction Stop; {comando}", self.oficial)
        del corrigido["tool_input"]["workdir"]
        self.assertEqual(avaliar_evento(corrigido, self.politica).decisao, "permitir")

    def test_prefixo_relativo_negado(self):
        self.assertEqual(self.avaliar("Set-Location -LiteralPath '.' -ErrorAction Stop; databricks bundle validate -t sandbox -p teste").decisao, "negar")

    def test_prefixo_sem_erro_terminante_nao_fixa_o_cwd(self):
        comando = f"Set-Location -LiteralPath '{self.local}'; databricks bundle validate -t sandbox -p teste"
        self.assertEqual(self.avaliar(comando).decisao, "negar")

    def test_comandos_compostos_e_wrappers_negados(self):
        for comando in (
            "cd x; databricks bundle validate -t sandbox -p teste",
            "databricks bundle validate -t sandbox -p teste; echo efeito",
            "databricks bundle validate -t sandbox -p teste | tee log",
            "databricks bundle validate -t sandbox -p $perfil",
            "cmd /c databricks bundle validate -t sandbox -p teste",
            "powershell -Command 'databricks bundle deploy'",
            "databricks bundle validate -t sandbox -p teste\nWrite-Output efeito",
            "& databricks bundle validate -t sandbox -p teste",
        ):
            with self.subTest(comando=comando):
                self.assertEqual(self.avaliar(comando).decisao, "negar")

    def test_flag_global_antes_de_bundle_nao_foge_da_guarda(self):
        for comando in ("databricks -p teste bundle deploy -t sandbox --select etapa",
                        "databricks --profile=teste bundle destroy -t prod",
                        "databricks.exe --debug bundle deploy -t dev"):
            with self.subTest(comando=comando):
                self.assertEqual(self.avaliar(comando).decisao, "negar")

    def test_texto_com_databricks_fora_da_cli_nao_e_negado(self):
        for comando in ("pytest tests/databricks", "python x_databricks.py",
                        'git commit -m "docs; notas sobre databricks"',
                        "databricks jobs list -p teste"):
            with self.subTest(comando=comando):
                self.assertEqual(self.avaliar(comando).decisao, "nao_aplica")

    def test_cli_por_caminho_continua_negada(self):
        for comando in ("C:/bin/databricks bundle deploy -t sandbox -p teste",
                        r"C:\bin\databricks.exe bundle validate -t sandbox -p teste",
                        "./databricks bundle validate -t sandbox -p teste",
                        '"C:/Program Files/databricks.exe" bundle deploy'):
            with self.subTest(comando=comando):
                self.assertEqual(self.avaliar(comando).decisao, "negar")

    def test_sql_ad_hoc_so_leitura(self):
        q = "databricks experimental aitools tools query "
        for sql in ('"SELECT * FROM c.s.t LIMIT 10"', '"select replace(a, \'x\', \'y\') from t"',
                    '"WITH x AS (SELECT 1) SELECT * FROM x"', '"DESCRIBE TABLE c.s.t"',
                    '"SHOW TABLES IN c.s"', '"SELECT * FROM t WHERE status = \'DELETE\'"'):
            with self.subTest(sql=sql):
                self.assertEqual(self.avaliar(q + sql + " --profile teste").decisao, "permitir")
        for sql in ('"DELETE FROM c.s.t"', '"SELECT 1; DROP TABLE t"', '"WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x"',
                    '"CREATE OR REPLACE TABLE t AS SELECT 1"', '"MERGE INTO t USING s ON 1=1"',
                    '"SELECT /* it\'s */ 1; DROP TABLE t"', '"SELECT 1 -- x"', '"SELECT $(x)"',
                    '"SELECT 1" | Out-Null', '"SELECT 1"; databricks bundle deploy', "--profile teste"):
            with self.subTest(sql=sql):
                self.assertEqual(self.avaliar(q + sql).decisao, "negar")
        self.assertEqual(self.avaliar("databricks --profile teste experimental aitools tools query "
                                      "\"UPDATE t SET a = 1\"").decisao, "negar")

    def test_demais_operacoes_nao_liberadas_por_cwd(self):
        for operacao in ("run", "destroy", "sync"):
            self.assertEqual(self.avaliar(f"databricks bundle {operacao} -t sandbox -p teste").codigo,
                             "operacao_pendente")

    def test_flags_ambiguas_e_destinos_nao_liberados(self):
        for flags in ("-t dev -p teste", "-p teste", "-t sandbox", "-t sandbox -p",
                      "-t sandbox --target dev -p teste", "-t sandbox -p teste --var x=y",
                      "-t sandbox -p teste --profile outro", "-t sandbox -p --debug",
                      "-t sandbox -p teste --force"):
            with self.subTest(flags=flags):
                self.assertEqual(self.avaliar(f"databricks bundle validate {flags}").decisao, "negar")

    def test_flags_longas_e_exe(self):
        self.assertEqual(self.avaliar("databricks.exe bundle validate --profile teste --target sandbox").decisao,
                         "permitir")

    def test_leitura_comum_nao_interfere(self):
        self.assertEqual(self.avaliar("Get-Content README.md").decisao, "nao_aplica")

    def test_leitura_literal_de_databricks_yml_nao_e_operacao(self):
        for comando in ("Get-Content databricks.yml", "rg -n bundle databricks.yml",
                        "Test-Path databricks.yml", "Get-FileHash databricks.yml"):
            with self.subTest(comando=comando):
                self.assertEqual(self.avaliar(comando).decisao, "nao_aplica")

    def test_leitura_com_efeito_anexado_ou_preprocessador_nao_e_excecao(self):
        for comando in ("Get-Content databricks.yml; databricks bundle deploy",
                        "rg --pre=databricks bundle arquivo",
                        "Get-Content $(databricks bundle deploy)"):
            self.assertEqual(self.avaliar(comando).decisao, "negar")

    def test_mcp_fora_do_recorte_explicito(self):
        evento = self.evento()
        evento["tool_name"] = "mcp__databricks__deploy"
        self.assertEqual(avaliar_evento(evento, self.politica).decisao, "nao_aplica")

    def test_evento_invalido_e_rejeitado(self):
        with self.assertRaises(ValueError):
            avaliar_evento({}, self.politica)
        evento = self.evento()
        evento["tool_input"] = None
        with self.assertRaises(ValueError):
            avaliar_evento(evento, self.politica)

    def test_adaptador_real_nega_antes_do_executor_controlado(self):
        resposta = self.processo_hook(self.evento(cwd=self.oficial))
        # Simulador do consumidor do protocolo. Nao e uma sessao Codex real.
        marcador = self.raiz / "efeito.txt"
        if resposta.get("hookSpecificOutput", {}).get("permissionDecision") != "deny":
            marcador.write_text("executou", encoding="utf-8")
        self.assertFalse(marcador.exists())
        self.assertIn("cwd_incorreto", resposta["hookSpecificOutput"]["permissionDecisionReason"])

    def test_adaptador_real_permite_continuacao_sem_conceder_permissao(self):
        resposta = self.processo_hook(self.evento())
        self.assertNotIn("permissionDecision", resposta["hookSpecificOutput"])
        self.assertIn("additionalContext", resposta["hookSpecificOutput"])

    def test_adaptador_real_nao_grava_comando_ou_perfil(self):
        self.processo_hook(self.evento("databricks bundle validate -t sandbox -p perfil_privado"))
        registros = list((self.raiz / "registros").rglob("*.json"))
        self.assertEqual(len(registros), 1)
        texto = registros[0].read_text(encoding="utf-8")
        self.assertNotIn("perfil_privado", texto)
        self.assertEqual(json.loads(texto)["decisao"]["decisao"], "permitir")

    def test_cada_evento_gera_um_registro_novo(self):
        self.processo_hook(self.evento())
        self.processo_hook(self.evento())
        self.assertEqual(len(list((self.raiz / "registros").rglob("*.json"))), 2)

    def test_falha_de_registro_nega(self):
        politica = dict(self.politica, registros_raiz=str(self.yaml_local))
        resposta = self.processo_hook(self.evento(), politica)
        self.assertEqual(resposta["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_payload_invalido_no_processo_nega(self):
        resposta = self.processo_hook(["invalido"])
        self.assertEqual(resposta["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_nao_aplica_nao_cria_registro(self):
        self.assertEqual(self.processo_hook(self.evento("Get-Location")), {})
        self.assertFalse((self.raiz / "registros").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
