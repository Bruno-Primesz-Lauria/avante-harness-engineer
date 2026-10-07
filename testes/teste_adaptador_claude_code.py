"""Traducoes D-CC exercitadas com eventos P0.4 e fatias temporarias."""
import copy
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
BRUTOS = RAIZ / ".execucoes/sondagens/brutos/claude_code/2026-10-05_cli-2.1.289/hooks"
SESSAO = "8839e862-c493-43cf-a289-3b8e2adff1f0"
AGENTE = "a4882a617b9ea83c1"
ARQUIVOS_P0_4 = {
    "SessionStart": "SessionStart_e2301f", "PreToolUse_Agent": "PreToolUse_9ee1a5",
    "PostToolUse_Agent": "PostToolUse_dfdd8e", "PreToolUse_Bash_subagent": "PreToolUse_65ea8d",
    "PostToolUse_Bash_subagent": "PostToolUse_39d8e3", "PreToolUse_Bash_failure": "PreToolUse_d23d66",
    "PostToolUseFailure_Bash": "PostToolUseFailure_a7042d", "PreToolUse_PowerShell": "PreToolUse_e88aa9",
    "PostToolUseFailure_PowerShell": "PostToolUseFailure_438421",
    "PreToolUse_Bash_principal": "PreToolUse_22e802", "PostToolUse_Bash_principal": "PostToolUse_61a65b",
    "Stop": "Stop_6577ee", "Stop_active": "Stop_561d58",
}

EVENTOS_P0_4 = {
    "SessionStart": {"hook_event_name": "SessionStart", "session_id": SESSAO, "source": "startup"},
    "PreToolUse_Agent": {"hook_event_name": "PreToolUse", "session_id": SESSAO,
        "tool_name": "Agent", "tool_use_id": "toolu_01CbHBMDCt1JJ4i9uHE5DUVq",
        "tool_input": {"description": "Sondagem P0.4", "prompt": "execute sua rotina",
                       "subagent_type": "sonda", "run_in_background": False}},
    "PostToolUse_Agent": {"hook_event_name": "PostToolUse", "session_id": SESSAO,
        "tool_name": "Agent", "tool_use_id": "toolu_01CbHBMDCt1JJ4i9uHE5DUVq",
        "tool_response": {"status": "completed", "agentId": AGENTE, "agentType": "sonda"}},
    "PreToolUse_Bash_subagent": {"hook_event_name": "PreToolUse", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "Bash",
        "tool_use_id": "toolu_01X9nFETWpd9cCYGzw9GCQeU",
        "tool_input": {"command": "echo sonda-sucesso"}},
    "PostToolUse_Bash_subagent": {"hook_event_name": "PostToolUse", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "Bash",
        "tool_use_id": "toolu_01X9nFETWpd9cCYGzw9GCQeU",
        "tool_input": {"command": "echo sonda-sucesso"},
        "tool_response": {"stdout": "sonda-sucesso", "stderr": "", "interrupted": False,
                          "isImage": False, "noOutputExpected": False}},
    "PreToolUse_Bash_failure": {"hook_event_name": "PreToolUse", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "Bash",
        "tool_use_id": "toolu_01PzpGomU9yGbS7tU6XdchUT", "tool_input": {"command": "exit 3"}},
    "PostToolUseFailure_Bash": {"hook_event_name": "PostToolUseFailure", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "Bash",
        "tool_use_id": "toolu_01PzpGomU9yGbS7tU6XdchUT",
        "tool_input": {"command": "exit 3"}, "error": "Exit code 3"},
    "PreToolUse_PowerShell": {"hook_event_name": "PreToolUse", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "PowerShell",
        "tool_use_id": "toolu_01JGwZPRUVx3YpXeGyNxfFTp",
        "tool_input": {"command": "Write-Output sonda-ps; exit 4"}},
    "PostToolUseFailure_PowerShell": {"hook_event_name": "PostToolUseFailure", "session_id": SESSAO,
        "agent_id": AGENTE, "agent_type": "sonda", "tool_name": "PowerShell",
        "tool_use_id": "toolu_01JGwZPRUVx3YpXeGyNxfFTp",
        "tool_input": {"command": "Write-Output sonda-ps; exit 4"},
        "error": "Exit code 4\nsonda-ps"},
    "PreToolUse_Bash_principal": {"hook_event_name": "PreToolUse", "session_id": SESSAO,
        "tool_name": "Bash", "tool_use_id": "toolu_01YGyaf1KJNKi7FoLpiBg6Ks",
        "tool_input": {"command": "echo principal-sucesso"}},
    "PostToolUse_Bash_principal": {"hook_event_name": "PostToolUse", "session_id": SESSAO,
        "tool_name": "Bash", "tool_use_id": "toolu_01YGyaf1KJNKi7FoLpiBg6Ks",
        "tool_input": {"command": "echo principal-sucesso"},
        "tool_response": {"stdout": "principal-sucesso", "stderr": "", "interrupted": False,
                          "isImage": False, "noOutputExpected": False}},
    "Stop": {"hook_event_name": "Stop", "session_id": SESSAO,
        "stop_hook_active": False, "last_assistant_message": "Sondagem concluida."},
    "Stop_active": {"hook_event_name": "Stop", "session_id": SESSAO, "stop_hook_active": True},
}

sys.path[:0] = [str(RAIZ / "implementacao"), str(RAIZ / "adaptadores")]
from claude_code.prova import tratar
from gerenciar import gerar
from provas import Provas, ler, validar


def evento_p0_4(nome):
    """Lê o bruto versionado localmente; o espelho mínimo mantém o teste portátil."""
    caminho = next(iter(sorted(BRUTOS.glob(f"*_{ARQUIVOS_P0_4[nome]}.json"))), None)
    if caminho is not None:
        return copy.deepcopy(json.loads(caminho.read_text(encoding="utf-8"))["evento"])
    return copy.deepcopy(EVENTOS_P0_4[nome])


class AdaptadorClaudeCodeTestes(unittest.TestCase):
    def setUp(self):
        self.fixture_id = uuid4().hex
        self.raiz = RAIZ / "testes/.fixtures/provas" / self.fixture_id
        self.raiz.mkdir(parents=True)
        self.addCleanup(self.limpar_fixture)
        (self.raiz / "src").mkdir()
        (self.raiz / "src/a.py").write_text("# baseline\n", encoding="utf-8")
        (self.raiz / "configuracao").mkdir()
        self.politica = {"bundle_local": str(self.raiz / "bundle"), "bundle_nome": "fixture",
                         "registros_raiz": str(self.raiz / ".execucoes"),
                         "agentes_obrigatorios": {"claude_code": [], "cursor": []}}
        self.escrever_politica()
        self.p = Provas(self.raiz, self.politica["registros_raiz"], SESSAO, runtime="claude_code")

    def limpar_fixture(self):
        raiz_fixtures = (RAIZ / "testes/.fixtures/provas").resolve()
        destino = self.raiz.resolve()
        if destino.parent != raiz_fixtures or destino.name != self.fixture_id:
            raise RuntimeError("Fixture fora da raiz temporaria esperada")
        shutil.rmtree(destino)

    def escrever_politica(self):
        (self.raiz / "configuracao/politica.json").write_text(
            json.dumps(self.politica), encoding="utf-8")

    def comando(self, corpo):
        return f"Set-Location -LiteralPath '{self.raiz}' -ErrorAction Stop; {corpo}"

    def iniciar(self, corpo="echo sonda-sucesso", ativada=False, comando=None):
        self.comando_teste = comando or self.comando(corpo)
        self.politica["agentes_obrigatorios"]["claude_code"] = ["validacao"] if ativada else []
        self.escrever_politica()
        self.p = Provas(self.raiz, self.politica["registros_raiz"], SESSAO, runtime="claude_code")
        contrato = dict(objetivo="Traduzir uma prova", termino_fatia="Teste registrado",
                        trilha="validacao", superficie=["src/a.py"], artefatos_raiz=".execucoes/provas",
                        fora=[], fontes=["src/a.py"], prazo=None,
                        aceite=[dict(id="c1", tipo="teste", obrigatorio=True, esperado="Resultado do teste",
                                     verificacao=dict(comando=self.comando_teste, cwd=".", caminhos=["src"]))],
                        orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"})
        self.p.iniciar(contrato)

    def tratar_evento(self, evento):
        return tratar(evento, self.politica, self.raiz)

    def prova_registrada(self):
        pasta = self.p.pasta()
        estado = self.p.estado(pasta)
        registro = estado["provas"]["c1"]
        return validar(ler(pasta / registro["ref"]), pasta, estado["execucao_id"], "principal")

    def test_session_start_expoe_id_observado(self):
        resposta = self.tratar_evento(evento_p0_4("SessionStart"))
        self.assertEqual(resposta["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn(SESSAO, resposta["hookSpecificOutput"]["additionalContext"])

    def test_subagente_test_casa_chamada_e_prova(self):
        self.iniciar(ativada=True)
        chamada_pre = evento_p0_4("PreToolUse_Agent")
        chamada_pre["tool_input"]["subagent_type"] = "test"
        self.assertEqual(self.tratar_evento(chamada_pre), {})
        chamada_post = evento_p0_4("PostToolUse_Agent")
        chamada_post["tool_response"]["agentType"] = "test"
        contexto = self.tratar_evento(chamada_post)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("agente_id=" + AGENTE, contexto)

        antes = evento_p0_4("PreToolUse_Bash_subagent")
        antes["agent_type"] = "test"
        antes["tool_input"]["command"] = self.comando("echo sonda-sucesso")
        self.assertEqual(self.tratar_evento(antes), {})
        depois = evento_p0_4("PostToolUse_Bash_subagent")
        depois["agent_type"] = "test"
        depois["tool_input"]["command"] = self.comando("echo sonda-sucesso")
        self.assertEqual(self.tratar_evento(depois), {})

        estado = self.p.estado(self.p.pasta())
        self.assertEqual(estado["chamadas_observadas"][0]["papel"], "test")
        self.assertEqual(estado["chamadas_observadas"][0]["chamada_id"], chamada_pre["tool_use_id"])
        self.assertEqual(self.prova_registrada()["dados"]["agente_id"], AGENTE)
        self.assertEqual(self.prova_registrada()["dados"]["exit_code_origem"], "evento_sucesso")
        _, faltam = self.p.pendencias(self.p.pasta(), estado)
        self.assertNotIn("teste_fora_do_test:c1", faltam)

    def test_tipo_sondado_fora_dos_sete_papeis_nao_registra_chamada(self):
        self.iniciar(ativada=True)
        self.assertEqual(self.tratar_evento(evento_p0_4("PreToolUse_Agent")), {})
        self.assertEqual(self.tratar_evento(evento_p0_4("PostToolUse_Agent")), {})
        self.assertEqual(self.p.estado(self.p.pasta())["chamadas_observadas"], [])

    def test_envelope_desconhecido_com_tool_input_invalido_falha_fechado(self):
        with self.assertRaisesRegex(ValueError, "tool_input invalido"):
            self.tratar_evento({"hook_event_name": "EventoFuturo", "session_id": SESSAO,
                                "tool_input": []})

    def test_papel_valido_fora_do_plano_nao_registra_nem_derruba_hook(self):
        self.iniciar(ativada=True)
        antes = evento_p0_4("PreToolUse_Agent")
        antes["tool_input"]["subagent_type"] = "config"
        depois = evento_p0_4("PostToolUse_Agent")
        depois["tool_response"]["agentType"] = "config"
        self.assertEqual(self.tratar_evento(antes), {})
        self.assertEqual(self.tratar_evento(depois), {})
        self.assertEqual(self.p.estado(self.p.pasta())["chamadas_observadas"], [])

    def test_c5_pretooluse_agent_abre_janela_e_falha_ainda_confere_superficie(self):
        self.politica["agentes_obrigatorios"]["claude_code"] = ["manutencao"]
        self.escrever_politica()
        self.p = Provas(self.raiz, self.politica["registros_raiz"], SESSAO, runtime="claude_code")
        self.p.iniciar(dict(objetivo="Alterar codigo", termino_fatia="Superficie conferida",
                            trilha="manutencao", superficie=["src/a.py"], artefatos_raiz=".execucoes/provas",
                            fora=[], fontes=["src/a.py"], prazo=None,
                            aceite=[dict(id="c1", tipo="teste", obrigatorio=True, esperado="Teste verde",
                                         verificacao=dict(comando=self.comando("echo ok"), cwd=".",
                                                          caminhos=["src"]))],
                            orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"}))
        antes = evento_p0_4("PreToolUse_Agent")
        antes["tool_input"]["subagent_type"] = "implement"
        self.assertEqual(self.tratar_evento(antes), {})
        self.assertIn(antes["tool_use_id"],
                      self.p.estado(self.p.pasta())["vigilancia_superficie"]["abertas"])
        (self.raiz / "src/b.yaml").write_text("fora: sim\n", encoding="utf-8")
        depois = evento_p0_4("PostToolUse_Agent")
        depois["tool_response"].update(agentType="implement", status="failed")
        self.assertEqual(self.tratar_evento(depois), {})

        _, faltam = self.p.pendencias(self.p.pasta(), self.p.estado(self.p.pasta()))
        self.assertIn("superficie_violada:implement:src/b.yaml", faltam)
        self.assertFalse([p for p in faltam if p.startswith("chamada_aberta")])

    def test_principal_que_rodou_teste_fica_fora_do_papel_test(self):
        self.iniciar("echo principal-sucesso", ativada=True)
        antes = evento_p0_4("PreToolUse_Bash_principal")
        antes["tool_input"]["command"] = self.comando("echo principal-sucesso")
        self.assertEqual(self.tratar_evento(antes), {})
        depois = evento_p0_4("PostToolUse_Bash_principal")
        depois["tool_input"]["command"] = self.comando("echo principal-sucesso")
        self.assertEqual(self.tratar_evento(depois), {})
        _, faltam = self.p.pendencias(self.p.pasta(), self.p.estado(self.p.pasta()))
        self.assertIn("teste_fora_do_test:c1", faltam)

    def test_verificacao_declarada_sem_prefixo_literal_e_negada(self):
        self.iniciar(comando="echo principal-sucesso")
        resposta = self.tratar_evento(evento_p0_4("PreToolUse_Bash_principal"))
        self.assertEqual(resposta["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("cd --", resposta["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.p.estado(self.p.pasta())["pendente"])

    def test_plan_com_prefixo_gera_recibo_so_depois_do_sucesso(self):
        bundle = self.raiz / "bundle"
        bundle.mkdir()
        (bundle / "databricks.yml").write_text("bundle: {name: fixture}\n", encoding="utf-8")
        corpo = "databricks bundle plan -t sandbox -p teste --select etapa"
        comando = f"Set-Location -LiteralPath '{bundle}' -ErrorAction Stop; {corpo}"
        self.p.iniciar(dict(objetivo="Registrar plan", termino_fatia="Recibo gravado", trilha="validacao",
                            superficie=["src/a.py"], artefatos_raiz=".execucoes/provas", fora=[],
                            fontes=["src/a.py"], prazo=None,
                            aceite=[dict(id="c1", tipo="teste", obrigatorio=True, esperado="Plan verde",
                                         verificacao=dict(comando=comando, cwd="bundle", caminhos=["src"]))],
                            orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"}))
        recibos = Path(self.politica["registros_raiz"]) / "plans"
        antes = evento_p0_4("PreToolUse_Bash_principal")
        antes["tool_input"]["command"] = comando
        self.assertNotEqual(self.tratar_evento(antes).get("hookSpecificOutput", {}).get("permissionDecision"),
                            "deny")
        self.assertFalse(recibos.exists())
        depois = evento_p0_4("PostToolUse_Bash_principal")
        depois["tool_input"]["command"] = comando
        self.tratar_evento(depois)
        self.assertEqual(len(list(recibos.glob("*.json"))), 1)
        deploy = evento_p0_4("PreToolUse_Bash_principal")
        deploy["tool_use_id"] = "toolu_deploy"
        deploy["tool_input"]["command"] = comando.replace("plan", "deploy")
        motivo = self.tratar_evento(deploy)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("identidade_destinos_pendentes", motivo)

    def test_posttoolusefailure_le_exit_code_da_primeira_linha(self):
        self.iniciar("exit 3")
        antes = evento_p0_4("PreToolUse_Bash_failure")
        antes["tool_input"]["command"] = self.comando("exit 3")
        self.assertEqual(self.tratar_evento(antes), {})
        depois = evento_p0_4("PostToolUseFailure_Bash")
        depois["tool_input"]["command"] = self.comando("exit 3")
        self.assertEqual(self.tratar_evento(depois), {})
        dados = self.prova_registrada()["dados"]
        self.assertEqual(dados["exit_code"], 3)
        self.assertEqual(dados["exit_code_origem"], "texto_falha")

    def test_posttoolusefailure_com_formato_desconhecido_fica_inconclusivo(self):
        self.iniciar("exit 3")
        antes = evento_p0_4("PreToolUse_Bash_failure")
        antes["tool_input"]["command"] = self.comando("exit 3")
        self.tratar_evento(antes)
        depois = evento_p0_4("PostToolUseFailure_Bash")
        depois["tool_input"]["command"] = self.comando("exit 3")
        depois["error"] = "process was interrupted"
        self.tratar_evento(depois)
        dados = self.prova_registrada()["dados"]
        self.assertIsNone(dados["exit_code"])
        self.assertEqual(dados["resultado"], "inconclusivo")
        self.assertNotIn("exit_code_origem", dados)

    def test_powerShell_failure_payload_p0_4_registra_texto_falha(self):
        comando = "Write-Output sonda-ps; exit 4"
        self.iniciar(comando)
        antes = evento_p0_4("PreToolUse_PowerShell")
        antes["tool_input"]["command"] = self.comando(comando)
        self.tratar_evento(antes)
        depois = evento_p0_4("PostToolUseFailure_PowerShell")
        depois["tool_input"]["command"] = self.comando(comando)
        self.tratar_evento(depois)
        dados = self.prova_registrada()["dados"]
        self.assertEqual(dados["exit_code"], 4)
        self.assertEqual(dados["exit_code_origem"], "texto_falha")

    def test_stop_bloqueia_fecho_pendente_e_nao_repete_com_stop_hook_active(self):
        self.iniciar()
        self.assertEqual(self.tratar_evento(evento_p0_4("Stop"))["decision"], "block")
        self.assertEqual(self.tratar_evento(evento_p0_4("Stop_active")), {})

    def subagente(self, papel, agente_id, tool_use_id, comando=None):
        """Agent pre, shell do subagente (com agent_id) e Agent pos; devolve a resposta do pos."""
        pre = evento_p0_4("PreToolUse_Agent")
        pre["tool_use_id"] = tool_use_id
        pre["tool_input"]["subagent_type"] = papel
        self.assertEqual(self.tratar_evento(pre), {})
        if comando is not None:
            for base in ("PreToolUse_Bash_subagent", "PostToolUse_Bash_subagent"):
                shell = evento_p0_4(base)
                shell.update(agent_id=agente_id, agent_type=papel, tool_use_id=tool_use_id + "-shell")
                shell["tool_input"]["command"] = comando
                self.tratar_evento(shell)
        pos = evento_p0_4("PostToolUse_Agent")
        pos["tool_use_id"] = tool_use_id
        pos["tool_response"].update(agentType=papel, agentId=agente_id)
        return self.tratar_evento(pos)

    def revisao(self, agente_id, criterios=("c1",)):
        return dict(
            agente_id=agente_id,
            entrada=dict(intencao_ref="contrato.yaml", aceite_ref="contrato.yaml",
                         baseline_ref="baseline.json", provas_refs=[]),
            veredito="nao_quebrei", tentativas=[dict(id="t1", procedimento="Reproduzir", resultado="pass")],
            achados=[], cobertura=[dict(criterio_id=c, coberto=True) for c in criterios])

    def pendencias(self):
        return self.p.pendencias(self.p.pasta(), self.p.estado(self.p.pasta()))[1]

    def iniciar_manutencao(self, aceite):
        self.politica["agentes_obrigatorios"]["claude_code"] = ["manutencao"]
        self.escrever_politica()
        self.p = Provas(self.raiz, self.politica["registros_raiz"], SESSAO, runtime="claude_code")
        self.p.iniciar(dict(objetivo="Alterar codigo", termino_fatia="Criterios conferidos",
                            trilha="manutencao", superficie=["src/a.py"], artefatos_raiz=".execucoes/provas",
                            fora=[], fontes=["src/a.py"], prazo=None, aceite=[aceite],
                            orcamento={"ciclos_correcao_max": 3}, responsaveis={"coordenador": "agente"}))

    def test_registro_da_chamada_devolve_o_agente_id_observado_ao_coordenador(self):
        self.iniciar(ativada=True)
        resposta = self.subagente("test", AGENTE, "toolu_teste", self.comando("echo sonda-sucesso"))
        contexto = resposta["hookSpecificOutput"]
        self.assertEqual(contexto["hookEventName"], "PostToolUse")
        self.assertIn("agente_id=" + AGENTE, contexto["additionalContext"])
        self.assertIn("test", contexto["additionalContext"])
        # Tipo fora dos sete papeis, papel fora do plano e retorno sem agentId nao devolvem contexto.
        self.assertEqual(self.subagente("sonda", "agente-x", "toolu_sonda"), {})
        self.assertEqual(self.subagente("implement", "agente-y", "toolu_fora"), {})
        pre = evento_p0_4("PreToolUse_Agent")
        pre.update(tool_use_id="toolu_sem_id")
        pre["tool_input"]["subagent_type"] = "refute"
        self.tratar_evento(pre)
        pos = evento_p0_4("PostToolUse_Agent")
        pos.update(tool_use_id="toolu_sem_id")
        pos["tool_response"].update(agentType="refute")
        del pos["tool_response"]["agentId"]
        self.assertEqual(self.tratar_evento(pos), {})
        estado = self.p.estado(self.p.pasta())
        self.assertEqual([c["papel"] for c in estado["chamadas_observadas"]], ["test"])
        self.assertNotIn("chamada_aberta", " ".join(self.pendencias()))

    def test_payload_completo_do_agent_p0_4_registra_a_chamada(self):
        # Formato real do PostToolUse(Agent): alem de status, agentId e agentType, traz conteudo, uso e toolStats.
        self.iniciar(ativada=True)
        pre = evento_p0_4("PreToolUse_Agent")
        pre["tool_input"]["subagent_type"] = "test"
        self.tratar_evento(pre)
        pos = evento_p0_4("PostToolUse_Agent")
        pos["duration_ms"] = 8514
        pos["tool_response"].update(
            agentType="test", prompt="Rode o teste", harnessNoteCount=0, harnessTailCount=0,
            content=[{"type": "text", "text": "Saida literal"}], resolvedModel="claude-sonnet-5",
            totalDurationMs=8514, totalTokens=33753, totalToolUseCount=1,
            usage={"output_tokens": 21}, toolStats={"readCount": 0, "bashCount": 1, "editFileCount": 0})
        self.assertIn("agente_id=" + AGENTE, self.tratar_evento(pos)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(self.p.estado(self.p.pasta())["chamadas_observadas"][0]["papel"], "test")

    def test_revisao_vincula_ao_refute_observado_com_o_id_devolvido_ao_coordenador(self):
        self.iniciar(ativada=True)
        self.subagente("test", "agente-test", "toolu_teste", self.comando("echo sonda-sucesso"))
        contexto = self.subagente("refute", "agente-refute", "toolu_refute")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("agente_id=agente-refute", contexto)
        self.assertEqual(self.pendencias(), ["revisao:ausente"])
        self.p.revisar(self.revisao("agente-test"))  # ID de outro papel.
        self.assertEqual(self.pendencias(), ["revisao:fora_do_refute"])
        self.p.revisar(self.revisao("agente-refute"))
        self.assertEqual(self.pendencias(), [])
        self.assertEqual(self.p.fechar("DONE", "Revisao do refute observado")["status"], "DONE")

    def test_ambiente_local_do_dab_leva_o_agente_id_do_subagente_sem_sandbox(self):
        # O-CU: ambiente_local roda um script; a prova leva o ID do dab e o fecho nao pede registro sandbox.
        (self.raiz / "src/autorizacao.md").write_text("Autorizado: script local\n", encoding="utf-8")
        local = self.comando("py -3 src/ambiente_local.py")
        self.comando_teste = local
        self.iniciar_manutencao(dict(
            id="c1", tipo="ambiente", obrigatorio=True, esperado="Script local com exit 0",
            autorizacao_ref="src/autorizacao.md", verificacao=dict(comando=local, cwd=".", caminhos=["src"])))
        papeis = [c["papel"] for c in self.p.estado(self.p.pasta())["chamadas_previstas"]]
        self.assertEqual(papeis, ["test", "implement", "refute", "dab"])
        self.subagente("test", "agente-prep", "toolu_prep")
        self.subagente("implement", "agente-impl", "toolu_impl")
        self.subagente("refute", "agente-refute", "toolu_refute")
        self.subagente("dab", "agente-dab", "toolu_dab", local)
        dados = self.prova_registrada()["dados"]
        self.assertEqual((dados["agente_id"], dados["resultado"]), ("agente-dab", "pass"))
        self.p.revisar(self.revisao("agente-refute"))
        self.assertEqual(self.pendencias(), [])
        self.assertEqual(self.p.fechar("DONE", "Ambiente local observado")["status"], "DONE")

    def test_agent_sobrepostos_tornam_a_autoria_da_superficie_inconclusiva(self):
        self.iniciar_manutencao(dict(
            id="c1", tipo="teste", obrigatorio=True, esperado="Teste verde",
            verificacao=dict(comando=self.comando("echo ok"), cwd=".", caminhos=["src"])))
        for papel, uso in (("test", "toolu_a"), ("implement", "toolu_b")):
            pre = evento_p0_4("PreToolUse_Agent")
            pre.update(tool_use_id=uso)
            pre["tool_input"]["subagent_type"] = papel
            self.tratar_evento(pre)
        (self.raiz / "src/a.py").write_text("# editado com duas janelas abertas\n", encoding="utf-8")
        for papel, uso, agente in (("test", "toolu_a", "agente-a"), ("implement", "toolu_b", "agente-b")):
            pos = evento_p0_4("PostToolUse_Agent")
            pos.update(tool_use_id=uso)
            pos["tool_response"].update(agentType=papel, agentId=agente)
            self.tratar_evento(pos)
        self.assertIn("superficie_inconclusiva:toolu_a", self.pendencias())
        self.assertIn("superficie_inconclusiva:toolu_b", self.pendencias())

    def test_session_start_orienta_o_comando_de_prova_com_a_sessao(self):
        contexto = self.tratar_evento(evento_p0_4("SessionStart"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("adaptadores/prova.py --sessao " + SESSAO, contexto)
        self.assertNotIn("--runtime cursor", contexto)

    def test_gerador_claude_inclui_eventos_sem_mudar_codex(self):
        claude = gerar("claude_code", "windows")["hooks"]
        codex = gerar("codex", "windows")["hooks"]
        self.assertIn("SessionStart", claude)
        self.assertIn("PostToolUse", claude)
        self.assertIn("PostToolUseFailure", claude)
        self.assertIn("Stop", claude)
        self.assertEqual(claude["PreToolUse"][0]["matcher"], "^(Bash|PowerShell|Agent)$")
        self.assertEqual(codex, {"PreToolUse": [{"matcher": "^Bash$", "hooks": [
            {"type": "command", "command": "py -3 adaptadores/entrada.py codex", "timeout": 10}
        ]}]})


if __name__ == "__main__":
    unittest.main(verbosity=2)
