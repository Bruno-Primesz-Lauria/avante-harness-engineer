import runpy
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

raiz = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(raiz / "adaptadores"), str(raiz / "implementacao")]
from provas import Provas, ler

(raiz / ".execucoes").mkdir(exist_ok=True)
kit = runpy.run_path(str(Path(__file__).with_name("preparar.py")))
compile(kit["CAPTURAR"], "capturar.py", "exec")
compile(kit["CONFERIR"], "conferir.py", "exec")
with TemporaryDirectory(prefix="validar-ocu-", dir=raiz / ".execucoes") as pasta:
    copia = Path(pasta)
    (copia / "configuracao").mkdir()
    (copia / "configuracao/politica.json").write_text(
        '{"agentes_obrigatorios":{"cursor":["manutencao","docs"]}}', encoding="utf-8")
    for ref, conteudo in kit["FIXTURE"].items():
        caminho = copia / ref
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    for nome in ("manutencao", "docs"):
        p = Provas(copia, copia / ".execucoes", "validar-" + nome, runtime="cursor")
        contrato = yaml.safe_load(kit["CONTRATOS"]["observacao/contrato-" + nome + ".yaml"])
        p.iniciar(contrato)
        plano = ler(p.pasta() / "estado.json")["chamadas_previstas"]
        assert [c["papel"] for c in plano] == (
            ["test", "config", "implement", "test", "refute", "dab"] if nome == "manutencao" else ["docs", "refute"])
        print(nome, [c["id"] for c in plano])
        p.fechar("BLOCKED", "Fixture de validação local; não é observação do Cursor")
print("Script, wrappers e contratos conferidos localmente; Cursor não executado.")
