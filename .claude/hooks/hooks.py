"""
Hooks do pipeline EduSynth.

Executados antes e depois de cada agente para logging,
rastreamento de tempo e registro de erros na sessão.
"""

import time
from datetime import datetime

# Log de sessão em memória — acumulado durante toda a execução
_session_log: list[dict] = []


def pre_agent_hook(agent_name: str) -> float:
    """
    Executado ANTES de cada agente rodar.

    - Loga no terminal: "🚀 Iniciando agente: {agent_name}"
    - Registra timestamp de início no log de sessão
    - Retorna o timestamp para calcular duração depois

    Parâmetros:
        agent_name: nome legível do agente (ex: "Pesquisador", "Crítico")

    Retorna:
        float — timestamp Unix do início
    """
    inicio = time.time()
    hora = datetime.fromtimestamp(inicio).strftime("%H:%M:%S")

    print(f"🚀 Iniciando agente: {agent_name}")

    _session_log.append({
        "evento":     "inicio",
        "agente":     agent_name,
        "timestamp":  inicio,
        "hora":       hora,
        "duracao_s":  None,
        "sucesso":    None,
        "erro":       None,
    })

    return inicio


def post_agent_hook(agent_name: str, start_time: float, success: bool = True) -> float:
    """
    Executado APÓS cada agente terminar.

    - Calcula tempo de execução em segundos
    - Loga: "✅ {agent_name} concluído em {tempo}s"
           ou "❌ {agent_name} falhou após {tempo}s"
    - Atualiza a entrada correspondente no log de sessão

    Parâmetros:
        agent_name: nome legível do agente
        start_time: timestamp retornado pelo pre_agent_hook
        success:    True se o agente concluiu sem erro

    Retorna:
        float — duração em segundos
    """
    duracao = round(time.time() - start_time, 2)

    if success:
        print(f"   ✅ {agent_name} concluído em {duracao}s")
    else:
        print(f"   ❌ {agent_name} falhou após {duracao}s")

    # Atualiza a última entrada deste agente no log
    for entrada in reversed(_session_log):
        if entrada["agente"] == agent_name and entrada["evento"] == "inicio":
            entrada["duracao_s"] = duracao
            entrada["sucesso"]   = success
            break
    else:
        # Fallback: cria entrada de conclusão se não encontrou a de início
        _session_log.append({
            "evento":    "conclusao",
            "agente":    agent_name,
            "timestamp": time.time(),
            "hora":      datetime.now().strftime("%H:%M:%S"),
            "duracao_s": duracao,
            "sucesso":   success,
            "erro":      None,
        })

    return duracao


def on_error_hook(agent_name: str, error: Exception | str) -> str:
    """
    Executado quando qualquer agente falha.

    - Loga o erro com contexto: "⚠️ Erro em {agent_name}: {error}"
    - Registra no log de sessão
    - Retorna mensagem amigável para exibir ao usuário

    Parâmetros:
        agent_name: nome legível do agente
        error:      exceção ou string descritiva do erro

    Retorna:
        str — mensagem amigável para o usuário
    """
    erro_str = str(error)
    hora = datetime.now().strftime("%H:%M:%S")

    print(f"   ⚠️  Erro em {agent_name}: {erro_str}")

    _session_log.append({
        "evento":    "erro",
        "agente":    agent_name,
        "timestamp": time.time(),
        "hora":      hora,
        "duracao_s": None,
        "sucesso":   False,
        "erro":      erro_str,
    })

    # Mensagens amigáveis por agente
    mensagens = {
        "Pesquisador": (
            "Não foi possível buscar conteúdo agora. "
            "Verifique sua conexão ou tente um tema diferente."
        ),
        "Crítico": (
            "A análise crítica encontrou um problema. "
            "O pipeline pode continuar com informações parciais."
        ),
        "Sintetizador": (
            "Houve um erro ao gerar o material de estudo. "
            "Tente novamente em instantes."
        ),
        "Estrategista": (
            "Não foi possível gerar a dica agora. "
            "Tente solicitar novamente."
        ),
        "Analista": (
            "O registro de desempenho falhou, mas isso não afeta seu material de estudo."
        ),
    }

    return mensagens.get(
        agent_name,
        f"Ocorreu um erro no agente '{agent_name}'. Tente novamente.",
    )


def get_session_log(formatted: bool = True) -> str | list[dict]:
    """
    Retorna o log completo da sessão.

    Parâmetros:
        formatted: se True, retorna string formatada para leitura.
                   se False, retorna a lista bruta de dicts.

    Retorna:
        str formatado ou list[dict]
    """
    if not formatted:
        return list(_session_log)

    if not _session_log:
        return "📋 Log de sessão vazio — nenhum agente foi executado ainda."

    linhas = ["📋 LOG DA SESSÃO EDUSYNTH", "─" * 50]

    for entrada in _session_log:
        hora      = entrada.get("hora", "?")
        agente    = entrada.get("agente", "?")
        evento    = entrada.get("evento", "?")
        duracao   = entrada.get("duracao_s")
        sucesso   = entrada.get("sucesso")
        erro      = entrada.get("erro")

        if evento == "inicio":
            linhas.append(f"[{hora}] 🚀 {agente} — iniciado")
        elif evento == "conclusao" or (evento == "inicio" and duracao is not None):
            icone = "✅" if sucesso else "❌"
            tempo_txt = f"{duracao}s" if duracao is not None else "?"
            linhas.append(f"[{hora}] {icone} {agente} — {tempo_txt}")
        elif evento == "erro":
            linhas.append(f"[{hora}] ⚠️  {agente} — ERRO: {erro}")

    # Resumo final
    total     = len([e for e in _session_log if e.get("evento") in ("inicio", "conclusao")])
    sucessos  = len([e for e in _session_log if e.get("sucesso") is True])
    erros     = len([e for e in _session_log if e.get("sucesso") is False])
    tempo_tot = sum(e["duracao_s"] for e in _session_log if e.get("duracao_s"))

    linhas.append("─" * 50)
    linhas.append(
        f"Total: {total} agente(s) | ✅ {sucessos} sucesso(s) | "
        f"❌ {erros} erro(s) | ⏱️ {tempo_tot:.1f}s total"
    )

    return "\n".join(linhas)


def clear_session_log() -> None:
    """Limpa o log de sessão (útil ao iniciar um novo pipeline)."""
    _session_log.clear()
