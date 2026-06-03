import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.researcher import pesquisar
from agents.critic import analisar
from agents.synthesizer import sintetizar
from agents.strategist import Strategist
from agents.performance_analyst import PerformanceAnalyst
from dotenv import load_dotenv

load_dotenv()

# Importa hooks com fallback gracioso caso o caminho mude
try:
    from .claude.hooks.hooks import (
        pre_agent_hook,
        post_agent_hook,
        on_error_hook,
        get_session_log,
        clear_session_log,
    )
except ImportError:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks"))
        from hooks import (
            pre_agent_hook,
            post_agent_hook,
            on_error_hook,
            get_session_log,
            clear_session_log,
        )
    except ImportError:
        # Fallback silencioso — hooks viram no-ops se não encontrados
        def pre_agent_hook(name):          return time.time()
        def post_agent_hook(name, t, s=True): return round(time.time() - t, 2)
        def on_error_hook(name, err):      return str(err)
        def get_session_log(**kw):         return "Hooks não carregados."
        def clear_session_log():           pass


def _tempo(inicio: float) -> str:
    return f"{time.time() - inicio:.1f}s"


class KnowSynth:
    """
    Orquestrador principal do pipeline KnowSynth.

    Coordena os 5 agentes em sequência com hooks de observabilidade
    executados antes e depois de cada etapa.

    Uso típico:
        edu = KnowSynth()
        resultado = edu.estudar("fordismo")
        print(edu.log_sessao())
    """

    def __init__(self):
        self._analista    = PerformanceAnalyst()
        self._estrategista = Strategist()

    # ── Fluxo principal ───────────────────────────────────────────────────────

    def estudar(self, tema: str, area: str = "não informada") -> dict:
        """
        Executa o pipeline completo:
        Pesquisador → Crítico → Sintetizador → Analista (registro)

        Retorna dict com status, outputs de cada agente e tempos de execução.
        """
        clear_session_log()

        resultado = {
            "tema": tema,
            "sucesso": False,
            "etapas": {
                "pesquisa": {"status": None, "tempo": None, "erro": None},
                "critica":  {"status": None, "tempo": None, "erro": None},
                "sintese":  {"status": None, "tempo": None, "erro": None},
                "registro": {"status": None, "tempo": None, "erro": None},
            },
            "resultado_pesquisador": None,
            "resultado_critico": None,
            "material_final": None,
        }

        # ── Passo 1: Pesquisador ──────────────────────────────────────────────
        t0 = pre_agent_hook("Pesquisador")
        try:
            resultado_pesquisa = pesquisar(tema)

            if resultado_pesquisa.get("tipo_busca") == "erro":
                raise RuntimeError(resultado_pesquisa.get("erro", "erro na pesquisa"))

            duracao = post_agent_hook("Pesquisador", t0, success=True)
            resultado["etapas"]["pesquisa"]["status"] = "sucesso"
            resultado["etapas"]["pesquisa"]["tempo"]  = f"{duracao}s"
            resultado["resultado_pesquisador"] = resultado_pesquisa

            fontes = (
                len(resultado_pesquisa.get("conteudo_didatico", [])) +
                len(resultado_pesquisa.get("noticias_relevantes", [])) +
                len(resultado_pesquisa.get("referencias_academicas", []))
            )
            print(
                f"      {fontes} fontes encontradas "
                f"(modo: {resultado_pesquisa.get('tipo_busca', '')})"
            )

        except Exception as e:
            post_agent_hook("Pesquisador", t0, success=False)
            msg = on_error_hook("Pesquisador", e)
            resultado["etapas"]["pesquisa"]["status"] = "erro"
            resultado["etapas"]["pesquisa"]["erro"]   = msg
            resultado["etapas"]["pesquisa"]["tempo"]  = _tempo(t0)
            return resultado

        # ── Passo 2: Crítico ──────────────────────────────────────────────────
        t0 = pre_agent_hook("Crítico")
        try:
            resultado_critica = analisar(resultado_pesquisa)

            if resultado_critica.get("erro"):
                raise RuntimeError(resultado_critica["erro"])

            duracao = post_agent_hook("Crítico", t0, success=True)
            resultado["etapas"]["critica"]["status"] = "sucesso"
            resultado["etapas"]["critica"]["tempo"]  = f"{duracao}s"
            resultado["resultado_critico"] = resultado_critica
            print(
                f"      Prioridade: {resultado_critica.get('nivel_prioridade', '—')} "
                f"| {resultado_critica.get('tokens_usados', 0)} tokens"
            )

        except Exception as e:
            post_agent_hook("Crítico", t0, success=False)
            msg = on_error_hook("Crítico", e)
            resultado["etapas"]["critica"]["status"] = "erro"
            resultado["etapas"]["critica"]["erro"]   = msg
            resultado["etapas"]["critica"]["tempo"]  = _tempo(t0)
            return resultado

        # ── Passo 3: Sintetizador ─────────────────────────────────────────────
        t0 = pre_agent_hook("Sintetizador")
        try:
            snapshot = self._analista.snapshot()
            resultado_sintese = sintetizar(resultado_pesquisa, resultado_critica, snapshot)

            if resultado_sintese.get("erro"):
                raise RuntimeError(resultado_sintese["erro"])

            duracao = post_agent_hook("Sintetizador", t0, success=True)
            resultado["etapas"]["sintese"]["status"] = "sucesso"
            resultado["etapas"]["sintese"]["tempo"]  = f"{duracao}s"
            resultado["material_final"] = resultado_sintese
            print(f"      {resultado_sintese.get('tokens_usados', 0)} tokens usados")

        except Exception as e:
            post_agent_hook("Sintetizador", t0, success=False)
            msg = on_error_hook("Sintetizador", e)
            resultado["etapas"]["sintese"]["status"] = "erro"
            resultado["etapas"]["sintese"]["erro"]   = msg
            resultado["etapas"]["sintese"]["tempo"]  = _tempo(t0)
            return resultado

        # ── Passo 4: Analista registra a pesquisa ─────────────────────────────
        t0 = pre_agent_hook("Analista")
        try:
            self._analista.register_search(tema, area)
            duracao = post_agent_hook("Analista", t0, success=True)
            resultado["etapas"]["registro"]["status"] = "sucesso"
            resultado["etapas"]["registro"]["tempo"]  = f"{duracao}s"
        except Exception as e:
            post_agent_hook("Analista", t0, success=False)
            on_error_hook("Analista", e)
            resultado["etapas"]["registro"]["status"] = "erro"
            resultado["etapas"]["registro"]["erro"]   = str(e)
            resultado["etapas"]["registro"]["tempo"]  = _tempo(t0)
            # Falha no registro não interrompe o pipeline

        resultado["sucesso"] = True
        print("✅ Material pronto!")
        return resultado

    # ── Estrategista — ativado sob demanda ───────────────────────────────────

    def request_hint(self, tema: str, questao: dict, level: int) -> dict:
        """Solicita uma dica do Estrategista e registra no Analista."""
        t0 = pre_agent_hook(f"Estrategista (dica {level})")
        resultado = self._estrategista.get_hint(level, questao)
        sucesso = not bool(resultado.get("erro"))
        post_agent_hook(f"Estrategista (dica {level})", t0, success=sucesso)

        if not sucesso:
            on_error_hook("Estrategista", resultado.get("erro", "erro desconhecido"))
        else:
            try:
                self._analista.register_hint(tema, level)
            except Exception:
                pass

        return resultado

    def request_gabarito(self, tema: str, questao: dict) -> dict:
        """Solicita o gabarito comentado do Estrategista."""
        t0 = pre_agent_hook("Estrategista (gabarito)")
        resultado = self._estrategista.get_gabarito(questao)
        sucesso = not bool(resultado.get("erro"))
        post_agent_hook("Estrategista (gabarito)", t0, success=sucesso)

        if not sucesso:
            on_error_hook("Estrategista", resultado.get("erro", "erro desconhecido"))
        else:
            try:
                if resultado.get("bloqueado"):
                    self._analista.register_gabarito(tema)
            except Exception:
                pass

        return resultado

    # ── Relatório, log e utilitários ─────────────────────────────────────────

    def relatorio_sessao(self) -> dict:
        """Gera o relatório completo de desempenho da sessão."""
        t0 = pre_agent_hook("Analista (relatório)")
        relatorio = self._analista.generate_report()
        post_agent_hook("Analista (relatório)", t0, success=not bool(relatorio.get("erro")))
        return relatorio

    def log_sessao(self) -> str:
        """Retorna o log formatado de todos os agentes executados na sessão."""
        return get_session_log(formatted=True)

    def snapshot_sessao(self) -> dict:
        """Retorna o estado atual da sessão sem chamar a API."""
        return self._analista.snapshot()

    def status_dicas(self, questao: dict) -> dict:
        """Retorna quantas dicas foram dadas para uma questão."""
        return self._estrategista.status(questao)


if __name__ == "__main__":
    edu = KnowSynth()

    print(f"\nTema: fordismo\n{'─' * 50}\n")
    resultado = edu.estudar("fordismo", area="Ciências Humanas")

    print(f"\n{'─' * 50}")
    print("RESUMO DAS ETAPAS")
    print(f"{'─' * 50}")
    for etapa, dados in resultado["etapas"].items():
        status = dados.get("status", "—")
        tempo  = dados.get("tempo", "—")
        erro   = f"  ⚠ {dados['erro']}" if dados.get("erro") else ""
        print(f"  {etapa:<10} → {status:<8} ({tempo}){erro}")

    print(f"\n{edu.log_sessao()}")

    if resultado["sucesso"]:
        mat = resultado["material_final"]
        print(f"\n{'═' * 50}")
        print(f"INTRODUÇÃO:\n{mat.get('introducao', '')[:400]}...")

