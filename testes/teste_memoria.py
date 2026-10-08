"""Memoria versionada: validar, resumo do indice e entrega no SessionStart do Claude Code."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from claude_code.prova import tratar
from memorias import resumo_indice, validar

# O CLI e carregado pelo caminho, como o engenheiro o executa.
_spec = importlib.util.spec_from_file_location("cli_memoria", RAIZ / "adaptadores/memoria.py")
cli_memoria = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli_memoria)

NOTA = """---
schema_versao: 1
id: {id}
tipo: {tipo}
status: {status}
tags: [teste]
caminhos: [src/a.py]
fontes: [{fontes}]
verificado_em: 2026-10-06
{extra}---

# Nota de teste

Fonte: [codigo](../../src/a.py).
"""


class MemoriaTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/memoria" / self.fixture_id
        self.addCleanup(self.limpar_fixture)
        (self.raiz / "src").mkdir(parents=True)
        (self.raiz / "src/a.py").write_text("# fonte\n", encoding="utf-8")
        base = self.raiz / "memoria"
        (base / "modelos").mkdir(parents=True)
        (base / "README.md").write_text("# Memoria\n\nVer [indice](indice.md).\n", encoding="utf-8")
        (base / "modelos/nota.md").write_text("---\nid: modelo\n---\n# Modelo\n", encoding="utf-8")
        self.nota("aprendizados", "nota-valida")
        self.indice(["aprendizados/nota-valida.md"])

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/memoria").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino, ignore_errors=True)

    def nota(self, pasta, identificador, tipo=None, status="ativo", fontes="src/a.py", extra="",
             nome=None, texto=None):
        tipo = tipo or {"aprendizados": "aprendizado", "decisoes": "decisao", "padroes": "padrao"}.get(pasta, "aprendizado")
        caminho = self.raiz / "memoria" / pasta / f"{nome or identificador}.md"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto if texto is not None else NOTA.format(
            id=identificador, tipo=tipo, status=status, fontes=fontes, extra=extra), encoding="utf-8")
        return caminho

    def indice(self, notas):
        linhas = ["# Indice", "", "Texto de apoio fora da lista.", ""]
        linhas += [f"- [{Path(n).stem}]({n}) — resumo de {Path(n).stem}" for n in notas]
        (self.raiz / "memoria/indice.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    def assert_erro(self, trecho):
        erros = validar(self.raiz)
        self.assertTrue(any(trecho in erro for erro in erros), f"esperado '{trecho}' em {erros}")

    def test_memoria_entregue_e_valida(self):
        self.assertEqual(validar(RAIZ), [])

    def test_fixture_valida_e_cli_sai_zero(self):
        self.assertEqual(validar(self.raiz), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli_memoria.principal(["validar"], raiz=self.raiz), 0)

    def test_cli_sai_diferente_de_zero_com_erro(self):
        (self.raiz / "memoria/indice.md").write_text("# Indice\n", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as saida:
            self.assertEqual(cli_memoria.principal(["validar"], raiz=self.raiz), 1)
        self.assertIn("ausente de memoria/indice.md", saida.getvalue())

    def test_sem_pasta_memoria(self):
        shutil.rmtree(self.raiz / "memoria")
        self.assertEqual(validar(self.raiz), ["memoria/ ausente"])

    def test_frontmatter_ausente(self):
        self.nota("aprendizados", "nota-valida", texto="# Sem metadados\n")
        self.assert_erro("Frontmatter ausente")

    def test_chave_yaml_duplicada(self):
        self.nota("aprendizados", "nota-valida", extra="tags: [outra]\n")
        self.assert_erro("Chave YAML duplicada")

    def test_yaml_malformado(self):
        self.nota("aprendizados", "nota-valida", extra="tags: [aberta\n")
        self.assert_erro("Frontmatter YAML invalido")

    def test_campo_ausente_e_desconhecido(self):
        texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo", fontes="src/a.py",
                            extra="responsavel: alguem\n").replace("verificado_em: 2026-10-06\n", "")
        self.nota("aprendizados", "nota-valida", texto=texto)
        self.assert_erro("campos ausentes: verificado_em")
        self.assert_erro("campos desconhecidos: responsavel")

    def test_schema_versao(self):
        texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo", fontes="src/a.py", extra="")
        self.nota("aprendizados", "nota-valida", texto=texto.replace("schema_versao: 1", "schema_versao: 2"))
        self.assert_erro("schema_versao deve ser 1")

    def test_id_diferente_do_nome(self):
        self.nota("aprendizados", "outro-id", nome="nota-valida")
        self.assert_erro("difere do nome do arquivo")

    def test_id_com_maiuscula(self):
        self.nota("aprendizados", "Nota", nome="Nota")
        self.assert_erro("id deve usar minusculas")

    def test_id_repetido_em_outra_pasta(self):
        self.nota("decisoes", "nota-valida")
        self.assert_erro("id nota-valida repetido")

    def test_tipo_incoerente_com_pasta(self):
        self.nota("aprendizados", "nota-valida", tipo="decisao")
        self.assert_erro("tipo deve ser aprendizado")

    def test_pasta_desconhecida(self):
        self.nota("rascunhos", "solta")
        self.assert_erro("a nota deve ficar direto em")

    def test_status_invalido(self):
        self.nota("aprendizados", "nota-valida", status="candidato")
        self.assert_erro("status deve ser ativo ou substituido")

    def test_ativa_com_substituida_por(self):
        self.nota("aprendizados", "nota-valida", extra="substituida_por: outra\n")
        self.assert_erro("nota ativa nao tem substituida_por")

    def test_sucessora_inexistente(self):
        self.nota("aprendizados", "antiga", status="substituido", extra="substituida_por: nao-existe\n")
        self.assert_erro("substituida_por aponta para nota inexistente")

    def test_substituida_fora_do_indice_e_aceita(self):
        self.nota("aprendizados", "antiga", status="substituido", extra="substituida_por: nota-valida\n")
        self.assertEqual(validar(self.raiz), [])

    def test_tags_vazias(self):
        texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo", fontes="src/a.py", extra="")
        self.nota("aprendizados", "nota-valida", texto=texto.replace("tags: [teste]", "tags: []"))
        self.assert_erro("tags deve ser lista nao vazia")

    def test_caminho_absoluto_ou_escapando(self):
        for valor in ("/etc/passwd", "../fora.py", "C:/x.py"):
            with self.subTest(valor=valor):
                texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo",
                                    fontes="src/a.py", extra="")
                self.nota("aprendizados", "nota-valida",
                          texto=texto.replace("caminhos: [src/a.py]", f"caminhos: ['{valor}']"))
                self.assert_erro("caminhos deve ser lista de caminhos relativos")

    def test_fontes_vazias(self):
        texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo", fontes="", extra="")
        self.nota("aprendizados", "nota-valida", texto=texto)
        self.assert_erro("fontes deve ser lista nao vazia")

    def test_commit_so_com_digitos_sem_aspas(self):
        self.nota("aprendizados", "nota-valida", fontes="7014887")
        self.assert_erro("coloque o hash do commit entre aspas")
        self.nota("aprendizados", "nota-valida", fontes="'7014887'")
        self.assertEqual(validar(self.raiz), [])

    def test_fonte_local_inexistente(self):
        self.nota("aprendizados", "nota-valida", fontes="src/nao_existe.py")
        self.assert_erro("fonte local inexistente")

    def test_fonte_so_em_execucoes_e_recusada(self):
        (self.raiz / ".execucoes").mkdir()
        (self.raiz / ".execucoes/log.txt").write_text("bruto\n", encoding="utf-8")
        self.nota("aprendizados", "nota-valida", fontes=".execucoes/log.txt")
        self.assert_erro("precisa de ao menos uma fonte acessivel de outro clone")

    def test_fontes_portaveis_aceitas(self):
        fontes = ".execucoes/log.txt, 83ed7e3, https://exemplo.org/doc, prj-avante-analytics-adb/AGENTS.md"
        (self.raiz / ".execucoes").mkdir()
        (self.raiz / ".execucoes/log.txt").write_text("bruto\n", encoding="utf-8")
        self.nota("aprendizados", "nota-valida", fontes=fontes)
        self.assertEqual(validar(self.raiz), [])

    def test_verificado_em_invalido(self):
        texto = NOTA.format(id="nota-valida", tipo="aprendizado", status="ativo", fontes="src/a.py", extra="")
        self.nota("aprendizados", "nota-valida", texto=texto.replace("2026-10-06", "ontem"))
        self.assert_erro("verificado_em deve ser data")

    def test_wikilink_recusado_e_em_codigo_ignorado(self):
        caminho = self.nota("aprendizados", "nota-valida")
        caminho.write_text(caminho.read_text(encoding="utf-8") + "\nVer `[[exemplo]]` em codigo.\n",
                           encoding="utf-8")
        self.assertEqual(validar(self.raiz), [])
        caminho.write_text(caminho.read_text(encoding="utf-8") + "\nVer [[outra-nota]].\n", encoding="utf-8")
        self.assert_erro("wikilink")

    def test_link_absoluto_quebrado_ou_fora_da_raiz(self):
        casos = {"[x](/tmp/a.md)": "link absoluto", "[x](inexistente.md)": "link quebrado",
                 "[x](../../../fora.md)": "link sai da raiz"}
        for link, trecho in casos.items():
            with self.subTest(link=link):
                self.nota("aprendizados", "nota-valida")
                caminho = self.raiz / "memoria/aprendizados/nota-valida.md"
                caminho.write_text(caminho.read_text(encoding="utf-8") + f"\n{link}\n", encoding="utf-8")
                self.assert_erro(trecho)

    def test_ativa_fora_do_indice(self):
        self.nota("decisoes", "nova-decisao")
        self.assert_erro("decisoes/nova-decisao.md: nota ativa ausente de memoria/indice.md")

    def test_modelo_fica_fora_das_notas(self):
        (self.raiz / "memoria/modelos/nota.md").write_text("---\nid: QUALQUER\n---\n", encoding="utf-8")
        self.assertEqual(validar(self.raiz), [])

    def test_resumo_do_indice_limita_volume(self):
        self.indice([f"aprendizados/n{i}.md" for i in range(60)])
        resumo = resumo_indice(self.raiz, max_linhas=5)
        self.assertIn("advisory", resumo)
        self.assertNotIn("Texto de apoio", resumo)
        self.assertEqual(sum(1 for linha in resumo.splitlines() if linha.startswith("- ")), 5)
        self.assertIn("indice truncado: 5 de 60", resumo)
        curto = resumo_indice(self.raiz, max_caracteres=400)
        self.assertLessEqual(len(curto.rsplit("\n", 1)[0]), 400)

    def test_resumo_sem_indice(self):
        (self.raiz / "memoria/indice.md").unlink()
        self.assertIsNone(resumo_indice(self.raiz))

    def test_campos_por_objeto_validos(self):
        self.nota("aprendizados", "nota-valida",
                  extra="modulo: BP\nobjeto: grupo_economico\netapa: ['04', '06']\n")
        self.assertEqual(validar(self.raiz), [])

    def test_campos_por_objeto_invalidos(self):
        casos = {"modulo: ''\n": "modulo deve ser texto", "objeto: Cliente PDV\n": "objeto deve usar",
                 "etapa: 4\n": "etapa deve ser", "etapa: '09'\n": "etapa deve ser", "etapa: []\n": "etapa deve ser"}
        for extra, trecho in casos.items():
            with self.subTest(extra=extra):
                self.nota("aprendizados", "nota-valida", extra=extra)
                self.assert_erro(trecho)

    def test_pasta_configuravel_fora_de_memoria(self):
        destino = self.raiz / "bundles/.claude/memoria"
        destino.parent.mkdir(parents=True)
        shutil.move(self.raiz / "memoria", destino)
        caminho = destino / "aprendizados/nota-valida.md"
        caminho.write_text(caminho.read_text(encoding="utf-8").replace("../../src/a.py", "../../../../src/a.py"),
                           encoding="utf-8")
        self.assertEqual(validar(self.raiz, "bundles/.claude/memoria"), [])
        self.assertEqual(validar(self.raiz), ["memoria/ ausente"])
        self.assertIn("relativa a raiz", validar(self.raiz, "../fora")[0])
        resumo = resumo_indice(self.raiz, "bundles/.claude/memoria")
        self.assertIn("links relativos a bundles/.claude/memoria/", resumo)
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            codigo = cli_memoria.principal(["validar", "--raiz", str(self.raiz),
                                            "--pasta", "bundles/.claude/memoria"])
        self.assertEqual(codigo, 0)
        self.assertIn("1 nota(s)", saida.getvalue())

    def test_cli_sessao_entrega_indice_e_nao_bloqueia_sem_memoria(self):
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(cli_memoria.principal(["sessao", "--raiz", str(self.raiz)]), 0)
        resposta = json.loads(saida.getvalue())
        self.assertEqual(resposta["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("aprendizados/nota-valida.md", resposta["hookSpecificOutput"]["additionalContext"])
        shutil.rmtree(self.raiz / "memoria")
        with contextlib.redirect_stdout(io.StringIO()) as saida:
            self.assertEqual(cli_memoria.principal(["sessao", "--raiz", str(self.raiz)]), 0)
        self.assertEqual(json.loads(saida.getvalue()), {})

    def test_session_start_entrega_indice(self):
        evento = {"hook_event_name": "SessionStart", "session_id": "sessao-memoria", "source": "startup"}
        contexto = tratar(evento, {}, self.raiz)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("sessao-memoria", contexto)
        self.assertIn("- [nota-valida](aprendizados/nota-valida.md)", contexto)
        self.assertNotIn("Nota de teste", contexto)

    def test_session_start_sem_memoria_mantem_sessao(self):
        shutil.rmtree(self.raiz / "memoria")
        evento = {"hook_event_name": "SessionStart", "session_id": "sessao-memoria", "source": "startup"}
        contexto = tratar(evento, {}, self.raiz)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("sessao-memoria", contexto)
        self.assertNotIn("Memoria do time", contexto)


if __name__ == "__main__":
    unittest.main()
