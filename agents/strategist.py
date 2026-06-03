import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv

try:
    from agents.groq_utils import chamar_groq
except ImportError:
    from groq_utils import chamar_groq


def parse_groq_response(text: str) -> dict:
    """Parse seguro de JSON retornado pelo Groq — trata escapes inválidos."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        cleaned = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', text)
        try:
            return json.loads(cleaned)
        except Exception:
            return {"content": text}

load_dotenv()

SKILL_PATH = Path(__file__).parent.parent / ".claude" / "skills" / "strategist.md"

# Prompts específicos para cada nível de dica
_PROMPT_DICA = {
    1: """O estudante está com dificuldade na questão abaixo e pediu a primeira dica.

QUESTÃO:
{questao}

Aplique a Dica Nível 1 — Leitura Estratégica do Enunciado.
Oriente o estudante a analisar o enunciado com atenção, identificar o comando da questão,
conectivos importantes e delimitadores. NÃO mencione as alternativas ainda.
Use tom encorajador. Termine com uma pergunta que estimule o estudante a refletir.""",

    2: """O estudante já recebeu a Dica 1 sobre leitura do enunciado e agora pede a segunda dica.

QUESTÃO:
{questao}

Aplique a Dica Nível 2 — Técnica de Eliminação.
Oriente o estudante a identificar e eliminar as alternativas claramente erradas,
especialmente as que usam palavras de absolutismo. NÃO revele qual é a correta.
Use tom encorajador. Termine incentivando o estudante a tentar eliminar ao menos 2 alternativas.""",

    3: """O estudante já recebeu as Dicas 1 e 2 e agora pede a terceira e última dica antes do gabarito.

QUESTÃO:
{questao}

Aplique a Dica Nível 3 — Análise de Pegadinhas.
Oriente o estudante a comparar as alternativas restantes, identificar pegadinhas de vocabulário
e alternativas parcialmente corretas. Após essa dica o estudante deve conseguir chegar à resposta.
Termine com uma frase motivadora dizendo que ele já tem tudo para acertar.""",
}

_PROMPT_GABARITO = """O estudante recebeu as 3 dicas e agora solicita o gabarito comentado.

QUESTÃO:
{questao}

Apresente o Gabarito Comentado completo conforme a skill:
- Identifique a alternativa correta
- Explique individualmente por que cada alternativa errada estava errada
- Destaque a palavra ou conceito-chave que confirmava a alternativa correta
- Indique qual técnica de eliminação funcionaria melhor nessa questão
- Dê uma dica para não errar questões similares no futuro
Use tom encorajador e celebre o esforço do estudante."""

_PROMPT_GABARITO_BLOQUEADO = """O estudante pediu o gabarito sem ter recebido as 3 dicas primeiro.

Dicas recebidas até agora: {dicas_recebidas} de 3.

Reforce gentilmente que o processo de dicas progressivas é importante para o aprendizado.
Explique qual dica falta e incentive o estudante a tentar primeiro.
Seja encorajador, nunca julgador."""


def _carregar_skill() -> str:
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _formatar_questao(questao: dict) -> str:
    """Serializa o dicionário da questão em texto legível para o prompt."""
    partes = []

    if questao.get("texto_apoio"):
        partes.append(f"TEXTO DE APOIO:\n{questao['texto_apoio']}")

    if questao.get("enunciado"):
        partes.append(f"ENUNCIADO:\n{questao['enunciado']}")

    alternativas = questao.get("alternativas", {})
    if alternativas:
        partes.append("ALTERNATIVAS:")
        for letra in ["A", "B", "C", "D", "E"]:
            if letra in alternativas:
                partes.append(f"  {letra}) {alternativas[letra]}")

    if questao.get("area"):
        partes.append(f"ÁREA DO CONHECIMENTO: {questao['area']}")

    return "\n\n".join(partes)


class Strategist:
    """
    Agente Estrategista ENEM.

    Mantém o estado de dicas por questão e garante que o gabarito
    só seja liberado após as 3 dicas terem sido apresentadas.

    Uso:
        s = Strategist()
        dica1 = s.get_hint(1, questao)
        dica2 = s.get_hint(2, questao)
        dica3 = s.get_hint(3, questao)
        gabarito = s.get_gabarito(questao)
    """

    def __init__(self):
        self._skill = _carregar_skill()
        # Rastreia dicas por questão usando o enunciado como chave
        self._dicas_entregues: dict[str, int] = {}

    def _chave_questao(self, questao: dict) -> str:
        """Gera uma chave única para identificar a questão no rastreamento."""
        return questao.get("enunciado", str(questao))[:120]

    def _dicas_recebidas(self, questao: dict) -> int:
        return self._dicas_entregues.get(self._chave_questao(questao), 0)

    def _registrar_dica(self, questao: dict, nivel: int) -> None:
        chave = self._chave_questao(questao)
        atual = self._dicas_entregues.get(chave, 0)
        self._dicas_entregues[chave] = max(atual, nivel)

    def _chamar_groq(self, prompt: str) -> dict:
        """Chama o Groq com fallback automático de modelo."""
        return chamar_groq(
            messages=[
                {"role": "system", "content": self._skill},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1000,
        )

    def get_hint(self, level: int, questao: dict) -> dict:
        """
        Retorna a dica do nível solicitado para a questão.

        Parâmetros:
            level: 1, 2 ou 3
            questao: dict com campos enunciado, alternativas, texto_apoio (opcional), area (opcional)

        Retorna dict com: nivel, dica, dicas_recebidas, tokens_usados, erro (se houver)
        """
        if level not in (1, 2, 3):
            return _resultado_erro(f"Nível de dica inválido: {level}. Use 1, 2 ou 3.")

        questao_texto = _formatar_questao(questao)
        prompt = _PROMPT_DICA[level].format(questao=questao_texto)
        resposta = self._chamar_groq(prompt)

        if resposta["erro"]:
            return _resultado_erro(resposta["erro"])

        self._registrar_dica(questao, level)

        return {
            "nivel": level,
            "dica": resposta["texto"],
            "dicas_recebidas": self._dicas_recebidas(questao),
            "gabarito_disponivel": self._dicas_recebidas(questao) >= 3,
            "tokens_usados": resposta["tokens_usados"],
            "erro": None,
        }

    def get_gabarito(self, questao: dict) -> dict:
        """
        Libera o gabarito comentado — apenas se as 3 dicas já foram entregues.

        Retorna dict com: gabarito, dicas_recebidas, tokens_usados, erro (se houver)
        """
        dicas = self._dicas_recebidas(questao)
        questao_texto = _formatar_questao(questao)

        if dicas < 3:
            prompt = _PROMPT_GABARITO_BLOQUEADO.format(dicas_recebidas=dicas)
            resposta = self._chamar_groq(prompt)
            return {
                "gabarito": None,
                "bloqueado": True,
                "mensagem": resposta["texto"],
                "dicas_recebidas": dicas,
                "dicas_faltando": 3 - dicas,
                "tokens_usados": resposta["tokens_usados"],
                "erro": None,
            }

        prompt = _PROMPT_GABARITO.format(questao=questao_texto)
        resposta = self._chamar_groq(prompt)

        if resposta["erro"]:
            return _resultado_erro(resposta["erro"])

        return {
            "gabarito": resposta["texto"],
            "bloqueado": False,
            "mensagem": None,
            "dicas_recebidas": dicas,
            "dicas_faltando": 0,
            "tokens_usados": resposta["tokens_usados"],
            "erro": None,
        }

    def status(self, questao: dict) -> dict:
        """Retorna o estado atual de dicas para uma questão."""
        dicas = self._dicas_recebidas(questao)
        return {
            "dicas_recebidas": dicas,
            "gabarito_disponivel": dicas >= 3,
            "proxima_dica": dicas + 1 if dicas < 3 else None,
        }

    def resetar(self, questao: dict) -> None:
        """Reseta o rastreamento de dicas para uma questão."""
        chave = self._chave_questao(questao)
        self._dicas_entregues.pop(chave, None)


def _resultado_erro(mensagem: str) -> dict:
    return {
        "nivel": None,
        "dica": None,
        "gabarito": None,
        "bloqueado": None,
        "mensagem": None,
        "dicas_recebidas": 0,
        "gabarito_disponivel": False,
        "tokens_usados": 0,
        "erro": mensagem,
    }


if __name__ == "__main__":
    questao_exemplo = {
        "area": "Ciências Humanas",
        "texto_apoio": (
            "O fordismo, sistema de produção criado por Henry Ford no início do século XX, "
            "baseava-se na linha de montagem, padronização dos produtos e produção em massa. "
            "Esse modelo transformou as relações de trabalho e impulsionou o consumo em escala industrial."
        ),
        "enunciado": (
            "O fordismo representou uma transformação profunda nas relações de trabalho do século XX. "
            "Sobre esse modelo de produção, assinale a alternativa correta:"
        ),
        "alternativas": {
            "A": "O fordismo valorizava a criatividade individual do trabalhador, incentivando a personalização dos produtos.",
            "B": "A linha de montagem fordista eliminou completamente o trabalho humano nas fábricas.",
            "C": "O fordismo se caracterizou pela produção em série, especialização de tarefas e consumo de massa.",
            "D": "Henry Ford criou o fordismo como resposta ao toyotismo japonês, buscando maior flexibilidade produtiva.",
            "E": "O modelo fordista sempre garantiu melhores condições de trabalho e maior autonomia aos operários.",
        },
    }

    agente = Strategist()
    print(f"Skill carregada: {len(agente._skill)} caracteres\n")

    print("=" * 60)
    print("STATUS INICIAL:", agente.status(questao_exemplo))

    print("\n--- DICA 1 ---")
    r1 = agente.get_hint(1, questao_exemplo)
    print(r1["dica"])
    print(f"\nTokens: {r1['tokens_usados']} | Gabarito disponível: {r1['gabarito_disponivel']}")

    print("\n--- TENTATIVA DE GABARITO SEM DICAS SUFICIENTES ---")
    rg = agente.get_gabarito(questao_exemplo)
    print(rg["mensagem"])

    print("\n--- DICA 2 ---")
    r2 = agente.get_hint(2, questao_exemplo)
    print(r2["dica"])

    print("\n--- DICA 3 ---")
    r3 = agente.get_hint(3, questao_exemplo)
    print(r3["dica"])
    print(f"\nGabarito disponível: {r3['gabarito_disponivel']}")

    print("\n--- GABARITO COMENTADO ---")
    rg2 = agente.get_gabarito(questao_exemplo)
    print(rg2["gabarito"])
    print(f"\nTokens: {rg2['tokens_usados']}")
