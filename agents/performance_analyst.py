import time
import os
import sys
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv

try:
    from utils.llm_client import chamar_llm
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from utils.llm_client import chamar_llm


load_dotenv()

SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "performance_analyst.md"

PREVIEW_V2 = (
    "🔜 Em breve: plano de estudo adaptativo gerado por IA com base no seu histórico, "
    "relatório da sessão por e-mail e login individual por usuário. "
    "Acompanhe as atualizações no GitHub."
)

# Regras de classificação de dificuldade conforme a skill
def _classificar_dificuldade(registro: dict) -> str:
    """
    Classifica a dificuldade de um tema com base nos eventos registrados.

    Sinais de dificuldade (skill):
    - 3 dicas usadas → difícil
    - Pesquisado mais de uma vez → difícil
    - Pulou para gabarito → médio (resistência ao processo)

    Sinais de facilidade:
    - 0 dicas → fácil
    - 1 dica → médio
    - 2 dicas → médio
    """
    pesquisas = registro.get("pesquisas", 1)
    dicas = registro.get("dicas_max", 0)
    pulou_gabarito = registro.get("pulou_gabarito", False)

    if dicas >= 3 or pesquisas > 1:
        return "difícil"
    if dicas == 0 and not pulou_gabarito:
        return "fácil"
    return "médio"


def _carregar_skill() -> str:
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _serializar_sessao(dados: dict) -> str:
    """Serializa os dados da sessão para o prompt do Claude."""
    linhas = [f"DURAÇÃO DA SESSÃO: {dados['duracao_min']:.1f} minutos"]

    temas = dados.get("temas", {})
    linhas.append(f"\nTEMAS ESTUDADOS ({len(temas)} no total):")
    for tema, reg in temas.items():
        dif = _classificar_dificuldade(reg)
        area = reg.get("area", "não informada")
        dicas = reg.get("dicas_max", 0)
        pesquisas = reg.get("pesquisas", 1)
        pulou = " | pulou para gabarito" if reg.get("pulou_gabarito") else ""
        linhas.append(
            f"  - {tema} | área: {area} | dificuldade: {dif} "
            f"| dicas usadas: {dicas} | pesquisado {pesquisas}x{pulou}"
        )

    areas = dados.get("contagem_areas", {})
    if areas:
        linhas.append("\nÁREAS MAIS ACESSADAS:")
        for area, count in sorted(areas.items(), key=lambda x: -x[1]):
            linhas.append(f"  - {area}: {count} acesso(s)")

    repetidos = [t for t, r in temas.items() if r.get("pesquisas", 1) > 1]
    if repetidos:
        linhas.append(f"\nTEMAS PESQUISADOS MAIS DE UMA VEZ: {', '.join(repetidos)}")

    return "\n".join(linhas)


class PerformanceAnalyst:
    """
    Agente Analista de Desempenho — rastreia o comportamento do estudante
    durante a sessão e gera relatório ao final.

    Uso:
        analista = PerformanceAnalyst()
        analista.register_search("fordismo", "Ciências Humanas")
        analista.register_hint("fordismo", 1)
        analista.register_hint("fordismo", 2)
        relatorio = analista.generate_report()
    """

    def __init__(self):
        self._skill = _carregar_skill()
        self._inicio_sessao = time.time()

        # Estrutura: tema → {area, pesquisas, dicas_max, pulou_gabarito, timestamps}
        self._temas: dict[str, dict] = {}
        self._contagem_areas: dict[str, int] = defaultdict(int)

    # ── Registro de eventos ───────────────────────────────────────────────────

    def register_search(self, tema: str, area: str = "não informada") -> None:
        """Registra uma nova pesquisa de tema."""
        if tema not in self._temas:
            self._temas[tema] = {
                "area": area,
                "pesquisas": 1,
                "dicas_max": 0,
                "pulou_gabarito": False,
                "timestamps": [time.time()],
            }
        else:
            self._temas[tema]["pesquisas"] += 1
            self._temas[tema]["timestamps"].append(time.time())

        self._contagem_areas[area] += 1

    def register_hint(self, tema: str, hint_level: int) -> None:
        """Registra o uso de uma dica — atualiza o nível máximo atingido."""
        if tema not in self._temas:
            self.register_search(tema)

        atual = self._temas[tema].get("dicas_max", 0)
        self._temas[tema]["dicas_max"] = max(atual, hint_level)

    def register_gabarito(self, tema: str) -> None:
        """Registra quando o estudante pulou direto para o gabarito."""
        if tema not in self._temas:
            self.register_search(tema)
        self._temas[tema]["pulou_gabarito"] = True

    # ── Geração do relatório ──────────────────────────────────────────────────

    def generate_report(self) -> dict:
        """
        Gera o relatório completo da sessão usando o Claude.

        Retorna dict com:
        - resumo_sessao, dificuldade_por_tema, pontos_fracos,
          recomendacoes, preview_v2, tokens_usados, erro
        """
        if not self._temas:
            return {
                "resumo_sessao": "Nenhum tema foi estudado nesta sessão.",
                "dificuldade_por_tema": {},
                "pontos_fracos": [],
                "recomendacoes": [],
                "preview_v2": PREVIEW_V2,
                "tokens_usados": 0,
                "erro": None,
            }

        duracao = (time.time() - self._inicio_sessao) / 60
        dados_sessao = {
            "duracao_min": duracao,
            "temas": self._temas,
            "contagem_areas": dict(self._contagem_areas),
        }

        contexto = _serializar_sessao(dados_sessao)
        dificuldade_por_tema = {
            tema: _classificar_dificuldade(reg)
            for tema, reg in self._temas.items()
        }

        prompt = f"""Com base nos dados de desempenho desta sessão de estudos, gere um relatório
encorajador e estratégico para o estudante.

DADOS DA SESSÃO:
{contexto}

Estruture sua resposta exatamente assim:

**RESUMO DA SESSÃO**
(2 a 3 frases resumindo o que foi estudado e o desempenho geral — tom positivo)

**TOP 3 PONTOS QUE MERECEM ATENÇÃO**
(Liste os 3 temas ou áreas que tiveram maior dificuldade. Para cada um:
- Nome do tema
- Por que aparece como ponto de atenção
- 2 palavras-chave para estudo aprofundado)

**RECOMENDAÇÕES PARA A PRÓXIMA SESSÃO**
(Liste de 3 a 5 recomendações específicas, com ordem de prioridade.
Seja concreto — evite conselhos genéricos como "estude mais".)

**VOCÊ AVANÇOU HOJE!**
(1 frase motivadora e personalizada com base nos temas estudados na sessão)"""

        r = chamar_llm(
            prompt=prompt,
            system_prompt=self._skill,
            max_tokens=1200,
        )

        if r["erro"]:
            return {
                "resumo_sessao": f"Limite de uso atingido ou erro ao gerar relatório: {r['erro']}",
                "dificuldade_por_tema": dificuldade_por_tema,
                "pontos_fracos": self._top_pontos_fracos(),
                "recomendacoes": self._recomendacoes_rapidas(),
                "preview_v2": PREVIEW_V2,
                "tokens_usados": 0,
                "erro": r["erro"],
            }

        return {
            "resumo_sessao": r["texto"],
            "dificuldade_por_tema": dificuldade_por_tema,
            "pontos_fracos": self._top_pontos_fracos(),
            "recomendacoes": self._recomendacoes_rapidas(),
            "preview_v2": PREVIEW_V2,
            "tokens_usados": r["tokens_usados"],
            "erro": None,
        }

    # ── Helpers de análise local (sem Claude) ─────────────────────────────────

    def _top_pontos_fracos(self, n: int = 3) -> list:
        """Retorna os n temas com maior dificuldade detectada, sem chamar a API."""
        pontuacao = {}
        for tema, reg in self._temas.items():
            score = reg.get("dicas_max", 0)
            if reg.get("pesquisas", 1) > 1:
                score += 3
            if reg.get("pulou_gabarito"):
                score += 1
            pontuacao[tema] = score

        ordenados = sorted(pontuacao.items(), key=lambda x: -x[1])
        return [{"tema": t, "score_dificuldade": s} for t, s in ordenados[:n]]

    def _recomendacoes_rapidas(self) -> list:
        """Gera recomendações básicas locais com base nos padrões detectados."""
        recomendacoes = []
        for tema, reg in self._temas.items():
            if reg.get("pesquisas", 1) > 1:
                recomendacoes.append(
                    f"Revisar '{tema}' — foi pesquisado {reg['pesquisas']}x, "
                    "o que indica que o conteúdo ainda não está fixado."
                )
            if reg.get("dicas_max", 0) >= 3:
                recomendacoes.append(
                    f"Aprofundar '{tema}' — precisou das 3 dicas, "
                    "vale estudar com mais calma."
                )
        return recomendacoes[:5]

    def snapshot(self) -> dict:
        """Retorna o estado atual da sessão sem gerar relatório."""
        return {
            "temas_estudados": list(self._temas.keys()),
            "total_temas": len(self._temas),
            "areas_acessadas": dict(self._contagem_areas),
            "duracao_min": (time.time() - self._inicio_sessao) / 60,
            "dificuldade_por_tema": {
                t: _classificar_dificuldade(r) for t, r in self._temas.items()
            },
        }


if __name__ == "__main__":
    analista = PerformanceAnalyst()
    print(f"Skill carregada: {len(analista._skill)} caracteres\n")

    # Simula uma sessão de estudos
    analista.register_search("fordismo", "Ciências Humanas")
    analista.register_hint("fordismo", 1)
    analista.register_hint("fordismo", 2)
    analista.register_hint("fordismo", 3)

    analista.register_search("fotossíntese", "Ciências da Natureza")
    analista.register_hint("fotossíntese", 1)

    analista.register_search("Revolução Industrial", "Ciências Humanas")
    analista.register_search("Revolução Industrial", "Ciências Humanas")  # repetição
    analista.register_gabarito("Revolução Industrial")

    analista.register_search("função quadrática", "Matemática")

    print("SNAPSHOT DA SESSÃO:")
    snap = analista.snapshot()
    for k, v in snap.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("GERANDO RELATÓRIO...\n")
    relatorio = analista.generate_report()

    print(relatorio["resumo_sessao"])
    print(f"\n{PREVIEW_V2}")
    print(f"\nTokens usados: {relatorio['tokens_usados']}")
    print(f"\nTop pontos fracos: {relatorio['pontos_fracos']}")

