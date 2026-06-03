import sys
import os
import time
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from agents.orchestrator import EduSynth


# ── Helpers ───────────────────────────────────────────────────────────────────
def _atualizar_dicas_historico(tema: str, nivel: int):
    hist = st.session_state["historico"]
    st.session_state["historico"] = [
        (t, a, max(d, nivel)) if t == tema else (t, a, d)
        for t, a, d in hist
    ]


# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="EduSynth — ENEM",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS Dark/Neon Global ──────────────────────────────────────────────────────
st.markdown("""
<style>
  :root {
    --bg:     #0a0a0a;
    --bg2:    #111111;
    --bg3:    #1a1a1a;
    --card:   rgba(255,255,255,0.04);
    --cyan:   #00f5ff;
    --green:  #00ff88;
    --purple: #9d4edd;
    --red:    #ff4444;
    --yellow: #ffc800;
    --text:   #ffffff;
    --text2:  #e0e0e0;
    --text3:  #888888;
    --border: rgba(0,245,255,0.18);
  }
  .stApp, .stApp > div             { background-color: var(--bg) !important; }
  section[data-testid="stSidebar"] { background-color: #0d0d0d !important; border-right: 1px solid var(--border); }

  /* Tabs */
  .stTabs [data-baseweb="tab-list"]  { background: var(--bg2); border-radius: 12px; padding: 4px; gap: 4px; }
  .stTabs [data-baseweb="tab"]       { color: var(--text3) !important; border-radius: 8px !important; font-weight: 500; }
  .stTabs [aria-selected="true"]     { background: linear-gradient(135deg,rgba(0,245,255,.12),rgba(157,78,221,.12)) !important; color: var(--cyan) !important; border: 1px solid var(--border) !important; }

  /* Textos */
  div[data-testid="stMarkdownContainer"] p,
  div[data-testid="stMarkdownContainer"] li { color: var(--text2); }
  h1, h2, h3, h4 { color: var(--text) !important; }
  div[data-testid="stCaption"] p { color: var(--text3) !important; }

  /* Input */
  .stTextInput input {
    background: var(--bg3) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: 10px !important;
    transition: border-color .2s, box-shadow .2s;
  }
  .stTextInput input:focus { border-color: var(--cyan) !important; box-shadow: 0 0 14px rgba(0,245,255,.25) !important; }

  /* Select */
  .stSelectbox > div > div {
    background: var(--bg3) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: 10px !important;
  }

  /* Botões */
  .stButton > button {
    background: var(--bg3) !important; color: var(--text2) !important;
    border: 1px solid var(--border) !important; border-radius: 8px !important;
    transition: all .2s !important;
  }
  .stButton > button:hover {
    border-color: var(--cyan) !important; color: var(--cyan) !important;
    box-shadow: 0 0 10px rgba(0,245,255,.2) !important; transform: translateY(-1px);
  }
  .stButton > button[kind="primary"] {
    background: linear-gradient(135deg,#00c8d4,#9d4edd) !important;
    color: #fff !important; border: none !important; font-weight: 700 !important;
  }
  .stButton > button[kind="primary"]:hover { box-shadow: 0 0 22px rgba(0,245,255,.4) !important; transform: translateY(-2px); }

  /* Progress */
  .stProgress > div > div { background: linear-gradient(90deg,var(--cyan),var(--purple)) !important; border-radius: 99px; }

  /* Expander */
  .stExpander { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
  .stExpander summary { color: var(--text2) !important; }

  /* Alerts */
  div[data-testid="stInfo"]   { background: rgba(0,245,255,.06) !important; border-left-color: var(--cyan)   !important; color: var(--text2) !important; }
  div[data-testid="stSuccess"]{ background: rgba(0,255,136,.06) !important; border-left-color: var(--green)  !important; color: var(--text2) !important; }
  div[data-testid="stError"]  { background: rgba(255,68,68,.06) !important;  border-left-color: var(--red)    !important; color: var(--text2) !important; }
  div[data-testid="stWarning"]{ background: rgba(255,200,0,.06) !important;  border-left-color: var(--yellow) !important; color: var(--text2) !important; }
  hr { border-color: var(--border) !important; }
  #MainMenu, footer { visibility: hidden; }

  /* ── Componentes customizados ── */
  .neon-divider { height:1px; background:linear-gradient(90deg,transparent,var(--cyan),var(--purple),transparent); border:none; margin:1.2rem 0; opacity:.45; }

  .glass-card          { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:1.2rem 1.4rem; margin:.5rem 0; backdrop-filter:blur(10px); }
  .glass-card-cyan     { border-color:rgba(0,245,255,.3);  box-shadow:0 0 12px rgba(0,245,255,.07); }
  .glass-card-green    { border-color:rgba(0,255,136,.3);  box-shadow:0 0 12px rgba(0,255,136,.07); }
  .glass-card-purple   { border-color:rgba(157,78,221,.3); box-shadow:0 0 12px rgba(157,78,221,.07); }
  .glass-card-red      { border-color:rgba(255,68,68,.3);  box-shadow:0 0 12px rgba(255,68,68,.07); }
  .glass-card-yellow   { border-color:rgba(255,200,0,.3);  box-shadow:0 0 12px rgba(255,200,0,.07); }

  /* Header */
  .edu-header { background:linear-gradient(135deg,rgba(0,245,255,.05),rgba(157,78,221,.08)); border:1px solid var(--border); border-radius:20px; padding:2rem 2.5rem 1.6rem; margin-bottom:1rem; text-align:center; position:relative; overflow:hidden; }
  .edu-header::before { content:''; position:absolute; inset:-50%; background:radial-gradient(circle at 30% 50%,rgba(0,245,255,.04),transparent 60%),radial-gradient(circle at 70% 50%,rgba(157,78,221,.04),transparent 60%); pointer-events:none; }
  .edu-title  { font-size:2.4rem; font-weight:900; background:linear-gradient(90deg,#00f5ff,#9d4edd); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin:0 0 .3rem; letter-spacing:-1px; }
  .edu-sub    { font-size:.88rem; color:var(--text3); margin:0 0 1rem; }
  .edu-greet  { font-size:1.05rem; color:var(--text2); margin:.3rem 0 1rem; }
  .edu-badges { display:flex; justify-content:center; gap:.4rem; flex-wrap:wrap; }
  .edu-badge  { background:rgba(0,245,255,.06); border:1px solid rgba(0,245,255,.3); border-radius:99px; padding:.22rem .75rem; font-size:.75rem; font-weight:600; color:var(--cyan); animation:badge-pulse 3s ease-in-out infinite; }
  .edu-badge:nth-child(2){border-color:rgba(0,255,136,.3);  color:var(--green);  animation-delay:.4s}
  .edu-badge:nth-child(3){border-color:rgba(157,78,221,.3); color:var(--purple); animation-delay:.8s}
  .edu-badge:nth-child(4){border-color:rgba(0,245,255,.3);  color:var(--cyan);   animation-delay:1.2s}
  .edu-badge:nth-child(5){border-color:rgba(0,255,136,.3);  color:var(--green);  animation-delay:1.6s}
  .edu-badge:nth-child(6){border-color:rgba(157,78,221,.3); color:var(--purple); animation-delay:2s}
  @keyframes badge-pulse { 0%,100%{box-shadow:0 0 0 rgba(0,245,255,0)} 50%{box-shadow:0 0 8px rgba(0,245,255,.3)} }

  /* Login */
  .login-wrap { max-width:460px; margin:4rem auto; text-align:center; }
  .login-title { font-size:2.8rem; font-weight:900; background:linear-gradient(90deg,#00f5ff,#9d4edd); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:.3rem; }
  .login-sub   { color:var(--text3); font-size:.9rem; margin-bottom:2rem; }

  /* Dicas e gabarito */
  .dica-box    { background:rgba(0,245,255,.04);  border-left:3px solid var(--cyan);   border-radius:0 10px 10px 0; padding:1rem 1.2rem; margin:.5rem 0; color:var(--text2); }
  .dica-box b  { color:var(--cyan); }
  .gabarito-box{ background:rgba(0,255,136,.04);  border-left:3px solid var(--green);  border-radius:0 10px 10px 0; padding:1rem 1.2rem; margin:.5rem 0; color:var(--text2); }
  .gabarito-box b { color:var(--green); }
  .erro-box    { background:rgba(255,68,68,.04);  border-left:3px solid var(--red);    border-radius:0 10px 10px 0; padding:1rem 1.2rem; margin:.5rem 0; color:var(--text2); }

  /* Métricas */
  .metric-row  { display:flex; gap:.8rem; flex-wrap:wrap; margin:.4rem 0; }
  .metric-chip { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:.35rem .85rem; font-size:.8rem; color:var(--text3); }
  .metric-chip span { color:var(--cyan); font-weight:700; }

  /* Timer */
  .timer-box   { background:rgba(0,245,255,.06); border:1px solid rgba(0,245,255,.3); border-radius:12px; padding:.7rem 1.2rem; margin:.4rem 0; font-family:monospace; color:var(--cyan); font-size:1.1rem; text-align:center; }
  .timer-warn  { border-color:rgba(255,200,0,.4) !important; color:var(--yellow) !important; background:rgba(255,200,0,.06) !important; }
  .timer-crit  { border-color:rgba(255,68,68,.4) !important;  color:var(--red) !important;    background:rgba(255,68,68,.06) !important; animation:timer-blink .8s ease-in-out infinite; }
  @keyframes timer-blink { 0%,100%{opacity:1} 50%{opacity:.5} }

  /* Sidebar */
  .sb-name   { color:var(--cyan); font-size:1rem; font-weight:700; }
  .sb-meta   { color:var(--text3); font-size:.78rem; margin:.1rem 0 .6rem; }
  .sb-label  { color:var(--text3); font-size:.72rem; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-top:.8rem; }
  .preview-v2{ background:linear-gradient(135deg,rgba(157,78,221,.12),rgba(0,245,255,.06)); border:1px solid rgba(157,78,221,.3); border-radius:12px; padding:.9rem; color:var(--text3); font-size:.8rem; margin-top:.8rem; }
  .preview-v2 b { color:var(--purple); }

  /* Relatório final */
  .report-wrap { max-width:780px; margin:2rem auto; }
  .report-hero { background:linear-gradient(135deg,rgba(0,255,136,.08),rgba(0,245,255,.05)); border:1px solid rgba(0,255,136,.3); border-radius:20px; padding:2rem; text-align:center; margin-bottom:1.5rem; }
  .report-hero h1 { font-size:2rem; background:linear-gradient(90deg,var(--green),var(--cyan)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }

  /* Onboarding */
  .onboarding-card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:1.1rem 1.3rem; text-align:center; min-width:130px; transition:border-color .2s,box-shadow .2s; }
  .onboarding-card:hover { border-color:var(--cyan); box-shadow:0 0 14px rgba(0,245,255,.12); }

  /* Log */
  .log-box { background:#0d0d0d; border:1px solid var(--border); border-radius:10px; padding:.9rem; font-family:'Courier New',monospace; font-size:.76rem; color:#666; white-space:pre-wrap; max-height:260px; overflow-y:auto; }

  /* Alternativas */
  .alt-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:.6rem 1rem; margin:.25rem 0; }
  .alt-card b { color:var(--cyan); }
  .alt-card span { color:var(--text2); }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        # Sessão do usuário
        "logged_in":        False,
        "usuario_nome":     "",
        "meta_tempo":       "Sem limite",
        "sessao_inicio":    None,
        "sessao_encerrada": False,
        # Pipeline
        "edu":              None,
        "historico":        [],
        "resultado_atual":  None,
        "tema_input":       "",
        # Questão
        "tentativas":       0,
        "nivel_dica_atual": 0,
        "dicas_texto":      [],
        "gabarito_texto":   None,
        "resposta_correta": False,
        "letra_escolhida":  None,
        # Balões de temas
        "baloes_temas":     [],
        "baloes_ts":        0.0,
        "balao_clicado":    False,
        # Timer UI
        "timer_visivel":    False,
        "meta_atingida":    False,
        "pausa_ativa":      False,
        "pausa_inicio":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

def _get_edu() -> EduSynth:
    if st.session_state["edu"] is None:
        st.session_state["edu"] = EduSynth()
    return st.session_state["edu"]

def _tempo_decorrido() -> int:
    """Retorna segundos desde o início da sessão."""
    if not st.session_state["sessao_inicio"]:
        return 0
    return int(time.time() - st.session_state["sessao_inicio"])

def _meta_em_segundos() -> int | None:
    mapa = {"30min": 1800, "1h": 3600, "2h": 7200, "3h": 10800, "Sem limite": None}
    return mapa.get(st.session_state["meta_tempo"])

def _formatar_tempo(segundos: int) -> str:
    h = segundos // 3600
    m = (segundos % 3600) // 60
    s = segundos % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# ═══════════════════════════════════════════════════════════════════════════════
# TELA 1 — LOGIN
# ═══════════════════════════════════════════════════════════════════════════════
if not st.session_state["logged_in"]:
    # Sidebar mínima no login
    with st.sidebar:
        st.markdown('<p style="color:#333;font-size:.78rem">EduSynth v1</p>', unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0 2rem">
          <div class="login-title">🎓 EduSynth</div>
          <p class="login-sub">Seu assistente de estudos para o ENEM — Powered by Generative AI</p>
        </div>
        """, unsafe_allow_html=True)

        nome = st.text_input("Qual é o seu nome?", placeholder="Ex: Ana, Carlos, Mariana...", key="input_nome")

        meta = st.selectbox(
            "Qual sua meta de estudos hoje?",
            ["Sem limite", "30min", "1h", "2h", "3h"],
            index=0,
            key="input_meta",
        )

        st.markdown("")
        if st.button("🚀 Iniciar Sessão", type="primary", use_container_width=True):
            if not nome.strip():
                st.error("Por favor, insira seu nome para continuar.")
            else:
                st.session_state["logged_in"]     = True
                st.session_state["usuario_nome"]  = nome.strip()
                st.session_state["meta_tempo"]    = meta
                st.session_state["sessao_inicio"] = time.time()
                st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# TELA 2 — RELATÓRIO FINAL (após encerrar sessão)
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["sessao_encerrada"]:
    nome     = st.session_state["usuario_nome"]
    decorrido = _tempo_decorrido()
    edu      = _get_edu()

    with st.sidebar:
        st.markdown(f'<p class="sb-name">🎓 {nome}</p>', unsafe_allow_html=True)
        st.markdown('<p style="color:#555;font-size:.8rem">Sessão encerrada</p>', unsafe_allow_html=True)
        if st.button("🔄 Nova Sessão", use_container_width=True, type="primary"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # Relatório
    st.markdown(f"""
    <div class="report-wrap">
      <div class="report-hero">
        <h1>🎉 Sessão Concluída, {nome}!</h1>
        <p style="color:var(--text3)">Você foi incrível hoje. Veja o resumo da sua jornada.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Métricas gerais
    snap     = edu.snapshot_sessao()
    temas    = snap.get("temas_estudados", [])
    difs     = snap.get("dificuldade_por_tema", {})

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="glass-card glass-card-cyan" style="text-align:center"><div style="font-size:2rem;color:var(--cyan)">{len(temas)}</div><div style="color:var(--text3);font-size:.82rem">Temas estudados</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="glass-card glass-card-green" style="text-align:center"><div style="font-size:2rem;color:var(--green)">{_formatar_tempo(decorrido)}</div><div style="color:var(--text3);font-size:.82rem">Tempo total</div></div>', unsafe_allow_html=True)
    with col3:
        dificeis = sum(1 for d in difs.values() if d == "difícil")
        st.markdown(f'<div class="glass-card glass-card-purple" style="text-align:center"><div style="font-size:2rem;color:var(--purple)">{dificeis}</div><div style="color:var(--text3);font-size:.82rem">Temas difíceis</div></div>', unsafe_allow_html=True)

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

    # Temas estudados
    if temas:
        st.markdown('<h3 style="color:var(--cyan)">📚 Temas Estudados</h3>', unsafe_allow_html=True)
        for t in temas:
            dif = difs.get(t, "—")
            cor = {"fácil": "var(--green)", "médio": "var(--yellow)", "difícil": "var(--red)"}.get(dif, "var(--text3)")
            st.markdown(f'<div class="glass-card"><span style="color:{cor}">●</span> <b style="color:var(--text)">{t}</b> <span style="color:var(--text3);font-size:.78rem">— {dif}</span></div>', unsafe_allow_html=True)

    # Relatório com IA
    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:var(--green)">🧠 Análise do Desempenho</h3>', unsafe_allow_html=True)

    with st.spinner("Gerando análise personalizada com IA..."):
        relatorio = edu.relatorio_sessao()

    st.markdown(f'<div class="glass-card glass-card-green">{relatorio.get("resumo_sessao","")}</div>', unsafe_allow_html=True)

    fracos = relatorio.get("pontos_fracos", [])
    if fracos:
        st.markdown('<h4 style="color:var(--yellow)">⚠️ Top 3 Pontos de Atenção</h4>', unsafe_allow_html=True)
        for i, pf in enumerate(fracos, 1):
            st.markdown(f'<div class="glass-card glass-card-yellow">#{i} <b style="color:var(--text)">{pf["tema"]}</b> <span style="color:var(--text3);font-size:.78rem">score: {pf["score_dificuldade"]}</span></div>', unsafe_allow_html=True)

    recomendacoes = relatorio.get("recomendacoes", [])
    if recomendacoes:
        st.markdown('<h4 style="color:var(--cyan)">🎯 Recomendações para a Próxima Sessão</h4>', unsafe_allow_html=True)
        for r in recomendacoes:
            st.markdown(f'<div class="glass-card">💡 <span style="color:var(--text2)">{r}</span></div>', unsafe_allow_html=True)

    # Preview v2
    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="glass-card glass-card-purple" style="text-align:center;padding:1.5rem">
      <b style="color:var(--purple);font-size:1rem">🚀 EduSynth v2 — Em breve</b><br><br>
      <span style="color:var(--text3)">Com o EduSynth v2, seu histórico será salvo entre sessões,
      {nome}, e você terá um plano de estudos personalizado baseado na sua evolução.<br>
      Supabase · Memória persistente · Analytics avançado</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("")
    if st.button("🔄 Iniciar Nova Sessão", type="primary", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# TELA PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
nome = st.session_state["usuario_nome"]
meta = st.session_state["meta_tempo"]
edu  = _get_edu()

# ── Verificação de meta atingida ──────────────────────────────────────────────
meta_seg = _meta_em_segundos()
decorrido = _tempo_decorrido()

if meta_seg and decorrido >= meta_seg and not st.session_state["meta_atingida"]:
    st.session_state["meta_atingida"] = True

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<p class="sb-name">👋 Olá, {nome}!</p>', unsafe_allow_html=True)
    meta_txt = f"Meta: {meta}" if meta != "Sem limite" else "Sessão livre"
    st.markdown(f'<p class="sb-meta">⏱️ {meta_txt}</p>', unsafe_allow_html=True)

    if meta_seg:
        restante = max(0, meta_seg - decorrido)
        pct = min(1.0, decorrido / meta_seg)
        st.progress(pct, text=f"{'✅' if restante == 0 else '⏳'} {_formatar_tempo(restante)} restantes")

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown('<p class="sb-label">📚 Temas estudados</p>', unsafe_allow_html=True)

    hist = st.session_state["historico"]
    if not hist:
        st.markdown('<p style="color:#444;font-size:.8rem">Nenhum tema ainda.</p>', unsafe_allow_html=True)
    else:
        for tema_h, _, dicas_h in reversed(hist):
            label = f"{'💡' * min(dicas_h, 3)} {tema_h}" if dicas_h else f"📖 {tema_h}"
            if st.button(label, key=f"hist_{tema_h}", use_container_width=True):
                st.session_state["tema_input"] = tema_h
                st.rerun()

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

    if st.button("📊 Encerrar Sessão", use_container_width=True):
        st.session_state["sessao_encerrada"] = True
        st.rerun()

    if st.button("🖥️ Log do Pipeline", use_container_width=True):
        st.markdown(f'<div class="log-box">{edu.log_sessao()}</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="preview-v2">
      <b>🚀 EduSynth v2 — Em breve</b><br><br>
      • Histórico entre sessões<br>
      • Mapa de pontos fracos<br>
      • Plano adaptativo<br>
      • Alertas proativos<br>
      <span style="color:#444;font-size:.72rem">Powered by Supabase</span>
    </div>
    """, unsafe_allow_html=True)

# ── Modal: meta atingida ──────────────────────────────────────────────────────
if st.session_state["meta_atingida"] and not st.session_state["pausa_ativa"]:
    with st.container():
        st.markdown(f"""
        <div class="glass-card glass-card-green" style="text-align:center;padding:1.8rem">
          <div style="font-size:2.5rem">🎉</div>
          <h2 style="color:var(--green)">Parabéns, {nome}!</h2>
          <p style="color:var(--text2)">Você completou sua meta de <b style="color:var(--cyan)">{meta}</b> de estudo!</p>
        </div>
        """, unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("✅ Continuar estudando", use_container_width=True):
                st.session_state["meta_atingida"] = False
                st.session_state["meta_tempo"]    = "Sem limite"
                st.rerun()
        with col_b:
            if st.button("☕ Pausa de 15 min", use_container_width=True):
                st.session_state["pausa_ativa"] = True
                st.session_state["pausa_inicio"] = time.time()
                st.rerun()
        with col_c:
            if st.button("📊 Encerrar sessão", use_container_width=True, type="primary"):
                st.session_state["sessao_encerrada"] = True
                st.rerun()
        st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

# ── Countdown da pausa ────────────────────────────────────────────────────────
if st.session_state["pausa_ativa"]:
    pausa_decorrida = int(time.time() - st.session_state["pausa_inicio"])
    pausa_restante  = max(0, 900 - pausa_decorrida)

    if pausa_restante > 0:
        st.markdown(f"""
        <div class="glass-card glass-card-yellow" style="text-align:center;padding:1.5rem">
          <div style="font-size:1.8rem">☕</div>
          <h3 style="color:var(--yellow)">Pausa em andamento</h3>
          <div class="timer-box timer-warn">⏱️ Retorno em {_formatar_tempo(pausa_restante)}</div>
          <p style="color:var(--text3);font-size:.82rem">Respire, beba água e relaxe os olhos. 🌿</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("↩️ Retornar agora", use_container_width=True):
            st.session_state["pausa_ativa"]   = False
            st.session_state["meta_atingida"] = False
        time.sleep(5)
        st.rerun()
    else:
        st.session_state["pausa_ativa"]   = False
        st.session_state["meta_atingida"] = False
        st.rerun()
    st.stop()

# ── Header principal ──────────────────────────────────────────────────────────
col_hd, col_timer = st.columns([10, 1])

with col_hd:
    st.markdown(f"""
    <div class="edu-header">
      <div class="edu-title">🎓 EduSynth</div>
      <p class="edu-sub">Powered by Generative AI — 6 agentes trabalhando para você</p>
      <p class="edu-greet">Olá, <b style="color:var(--cyan)">{nome}</b>! Pronto para estudar? 🚀</p>
      <div class="edu-badges">
        <span class="edu-badge">🔍 Pesquisador</span>
        <span class="edu-badge">📚 ENEM API</span>
        <span class="edu-badge">🏆 Ranqueador</span>
        <span class="edu-badge">🧠 Crítico</span>
        <span class="edu-badge">📝 Sintetizador</span>
        <span class="edu-badge">💡 Estrategista</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_timer:
    st.markdown('<div style="padding-top:1.2rem">', unsafe_allow_html=True)
    timer_label = "⏱️" if not st.session_state["timer_visivel"] else "✕"
    if st.button(timer_label, key="btn_timer", help="Mostrar/ocultar cronômetro"):
        st.session_state["timer_visivel"] = not st.session_state["timer_visivel"]
    st.markdown('</div>', unsafe_allow_html=True)

# ── Timer visível ─────────────────────────────────────────────────────────────
if st.session_state["timer_visivel"]:
    decorrido_f = _formatar_tempo(decorrido)
    if meta_seg:
        restante_s = max(0, meta_seg - decorrido)
        pct_resta  = restante_s / meta_seg
        cls = "timer-crit" if pct_resta < 0.1 else ("timer-warn" if pct_resta < 0.25 else "")
        st.markdown(
            f'<div class="timer-box {cls}">'
            f'⏱️ Decorrido: <b>{decorrido_f}</b> &nbsp;|&nbsp; '
            f'Restante: <b>{_formatar_tempo(restante_s)}</b> de {meta}'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="timer-box">⏱️ Tempo de sessão: <b>{decorrido_f}</b></div>', unsafe_allow_html=True)

st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)

# ── Balões de temas interativos ───────────────────────────────────────────────
import random as _random

_TODOS_TEMAS = [
    # Ciências Humanas
    "Revolução Industrial", "Segunda Guerra Mundial", "Ditadura Militar Brasileira",
    "Globalização", "Iluminismo", "Revolução Francesa", "Guerra Fria",
    "Imperialismo Africano", "Redemocratização do Brasil", "Movimentos Sociais",
    # Ciências da Natureza
    "Fotossíntese", "Genética Mendeliana", "Aquecimento Global", "Tabela Periódica",
    "Leis de Newton", "Ondas Eletromagnéticas", "Ecossistemas", "Evolução das Espécies",
    "Reações Químicas", "DNA e RNA",
    # Matemática
    "Função Quadrática", "Progressão Aritmética", "Trigonometria", "Probabilidade",
    "Geometria Espacial", "Porcentagem e Juros", "Equações do 2º Grau",
    "Estatística Básica", "Matrizes e Determinantes", "Logaritmos",
    # Linguagens
    "Modernismo Brasileiro", "Romantismo", "Figuras de Linguagem",
    "Interpretação de Texto", "Realismo e Naturalismo", "Literatura Africana",
    "Variação Linguística", "Semiótica", "Vanguardas Europeias", "Gêneros Textuais",
]

_CORES_BALAO = [
    ("rgba(0,245,255,.08)",  "rgba(0,245,255,.5)",  "#00f5ff"),   # ciano
    ("rgba(0,255,136,.08)",  "rgba(0,255,136,.5)",  "#00ff88"),   # verde
    ("rgba(157,78,221,.1)",  "rgba(157,78,221,.5)", "#9d4edd"),   # roxo
    ("rgba(255,165,0,.08)",  "rgba(255,165,0,.5)",  "#ffa500"),   # laranja
    ("rgba(255,105,180,.08)","rgba(255,105,180,.5)","#ff69b4"),   # rosa
]

_ROTACAO_SEG = 900  # 15 minutos

def _atualizar_baloes():
    """Sorteia 5 temas, evitando repetir os anteriores se possível."""
    anteriores = set(st.session_state.get("baloes_temas", []))
    pool = [t for t in _TODOS_TEMAS if t not in anteriores]
    if len(pool) < 5:
        pool = _TODOS_TEMAS
    novos = _random.sample(pool, 5)
    st.session_state["baloes_temas"] = novos
    st.session_state["baloes_ts"]    = time.time()

# Inicializa ou rotaciona os balões
if (not st.session_state["baloes_temas"] or
        time.time() - st.session_state["baloes_ts"] >= _ROTACAO_SEG):
    _atualizar_baloes()

temas_balao  = st.session_state["baloes_temas"]
prox_rotacao = max(0, int(_ROTACAO_SEG - (time.time() - st.session_state["baloes_ts"])))
prox_min     = prox_rotacao // 60
prox_seg     = prox_rotacao % 60
indicador    = f"{prox_min}min {prox_seg}s" if prox_min else f"{prox_seg}s"

# CSS dos balões (injetado uma vez)
st.markdown("""
<style>
  .balao-row { display:flex; gap:.7rem; flex-wrap:wrap; margin:.4rem 0 1rem; align-items:center; }
  .balao-btn {
    border: none; border-radius: 99px;
    padding: .38rem 1.1rem;
    font-size: .82rem; font-weight: 600;
    cursor: pointer; transition: all .22s ease;
    letter-spacing: .2px;
  }
  .balao-btn:hover { transform: translateY(-2px) scale(1.04); filter: brightness(1.15); }
  .balao-btn:active { transform: scale(.97); }
  .rotacao-hint { color:#444; font-size:.72rem; align-self:center; white-space:nowrap; }
</style>
""", unsafe_allow_html=True)

# Label
st.markdown('<p style="color:var(--text3);font-size:.8rem;margin-bottom:.2rem">💡 Temas em destaque — clique para estudar:</p>', unsafe_allow_html=True)

# Renderiza os 5 balões como botões Streamlit estilizados
cols_bal = st.columns(6)  # 5 balões + 1 para o indicador
for i, (col, tema_b) in enumerate(zip(cols_bal[:5], temas_balao)):
    bg, borda, cor = _CORES_BALAO[i]
    with col:
        # Botão nativo do Streamlit com key única
        if st.button(
            tema_b,
            key=f"balao_{tema_b}_{st.session_state['baloes_ts']:.0f}",
            use_container_width=True,
        ):
            st.session_state["tema_input"] = tema_b
            # Dispara pipeline automaticamente via flag
            st.session_state["balao_clicado"] = True
            st.rerun()

# Indicador de rotação discreto na última coluna
with cols_bal[5]:
    st.markdown(
        f'<div style="color:#444;font-size:.7rem;padding-top:.6rem;text-align:center">'
        f'🔄 {indicador}</div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ── Input ─────────────────────────────────────────────────────────────────────
col_inp, col_btn = st.columns([5, 1])
with col_inp:
    tema_digitado = st.text_input(
        "Tema",
        value=st.session_state["tema_input"],
        placeholder="Digite um tema ou palavra-chave do ENEM...",
        label_visibility="collapsed",
    )
with col_btn:
    iniciar = st.button("🚀 Estudar Agora", type="primary", use_container_width=True)

# ── Pipeline ──────────────────────────────────────────────────────────────────
# Balão clicado dispara o pipeline automaticamente
if st.session_state.get("balao_clicado") and st.session_state["tema_input"]:
    st.session_state["balao_clicado"] = False
    iniciar = True
    tema_digitado = st.session_state["tema_input"]

if iniciar and tema_digitado.strip():
    tema = tema_digitado.strip()
    st.session_state.update({
        "tema_input":       tema,
        "nivel_dica_atual": 0,
        "dicas_texto":      [],
        "gabarito_texto":   None,
        "tentativas":       0,
        "resposta_correta": False,
        "letra_escolhida":  None,
    })

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown(f'<h3 style="color:var(--cyan)">⚡ {nome}, gerando material sobre: <span style="color:#fff">{tema}</span></h3>', unsafe_allow_html=True)

    barra  = st.progress(0, text="Iniciando pipeline...")
    status = st.empty()

    try:
        from agents.researcher  import pesquisar   as _pesquisar
        from agents.critic      import analisar     as _analisar
        from agents.synthesizer import sintetizar   as _sintetizar

        barra.progress(10, text="🔍 Pesquisando conteúdo...")
        with status.container():
            st.info(f"🔍 **Pesquisador** buscando fontes para **{nome}**...")
        r_pesquisa = _pesquisar(tema)
        if r_pesquisa.get("tipo_busca") == "erro":
            raise RuntimeError(r_pesquisa.get("erro"))

        total_f = sum(len(r_pesquisa.get(k, [])) for k in ["conteudo_didatico","noticias_relevantes","referencias_academicas"])
        barra.progress(30, text="✅ Pesquisa concluída!")
        with status.container():
            st.success(f"🔍 {total_f} fontes encontradas (modo: **{r_pesquisa.get('tipo_busca','')}**)")

        barra.progress(42, text="🧠 Análise crítica...")
        with status.container():
            st.info("🧠 **Crítico** analisando frequência no ENEM e conexões interdisciplinares...")
        r_critica = _analisar(r_pesquisa)
        if r_critica.get("erro"):
            raise RuntimeError(r_critica["erro"])

        barra.progress(62, text="✅ Análise concluída!")
        with status.container():
            st.success(f"🧠 Análise concluída — prioridade: **{r_critica.get('nivel_prioridade','—')}** | {r_critica.get('tokens_usados',0)} tokens")

        barra.progress(72, text="📝 Sintetizando material...")
        with status.container():
            st.info("📝 **Sintetizador** criando material personalizado e questão ENEM...")
        r_sintese = _sintetizar(r_pesquisa, r_critica, edu._analista.snapshot())
        if r_sintese.get("erro"):
            raise RuntimeError(r_sintese["erro"])

        barra.progress(92, text="📊 Registrando sessão...")
        edu._analista.register_search(tema)
        barra.progress(100, text="✅ Pronto!")
        with status.container():
            st.success(f"✅ Pronto, {nome}! Material gerado com {r_sintese.get('tokens_usados',0)} tokens.")

        st.session_state["resultado_atual"] = {
            "tema": tema, "pesquisa": r_pesquisa,
            "critica": r_critica, "sintese": r_sintese,
        }

        hist = [(t,a,d) for t,a,d in st.session_state["historico"] if t != tema]
        hist.append((tema, "não informada", 0))
        st.session_state["historico"] = hist

    except Exception as e:
        barra.progress(100, text="❌ Erro no pipeline")
        with status.container():
            st.error(f"❌ {nome}, ocorreu um erro: {e}")

# ── Resultado em abas ─────────────────────────────────────────────────────────
if st.session_state["resultado_atual"]:
    res      = st.session_state["resultado_atual"]
    pesquisa = res["pesquisa"]
    critica  = res["critica"]
    sintese  = res["sintese"]

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="color:var(--cyan)">📖 {sintese.get("tema","").upper()}</h2>', unsafe_allow_html=True)

    aba1, aba2, aba3, aba4 = st.tabs([
        "📚 Material de Estudo",
        "🔍 Fontes Pesquisadas",
        "🧠 Análise Crítica",
        "📊 Minha Sessão",
    ])

    # ── Aba 1: Material ───────────────────────────────────────────────────────
    with aba1:
        intro = sintese.get("introducao", "")
        if intro:
            st.markdown('<h3 style="color:var(--cyan)">🔍 Introdução</h3>', unsafe_allow_html=True)
            st.markdown(f'<div class="glass-card glass-card-cyan">{intro}</div>', unsafe_allow_html=True)

        pontos = sintese.get("pontos_essenciais", [])
        if pontos:
            st.markdown('<h3 style="color:var(--green)">⭐ Pontos Essenciais</h3>', unsafe_allow_html=True)
            for p in pontos:
                enem = ' <span style="color:var(--purple);font-size:.75rem">★ ENEM</span>' if p.get("cobrado_enem") else ""
                st.markdown(
                    f'<div class="glass-card"><b style="color:var(--text)">{p.get("conceito","")}</b>{enem}<br>'
                    f'<span style="color:var(--text2)">{p.get("definicao","")}</span><br>'
                    f'<span style="color:var(--text3);font-size:.8rem">Exemplo: {p.get("exemplo","")}</span></div>',
                    unsafe_allow_html=True,
                )

        conexoes = sintese.get("conexoes_interdisciplinares", [])
        if conexoes:
            st.markdown('<h3 style="color:var(--purple)">🔗 Conexões Interdisciplinares</h3>', unsafe_allow_html=True)
            for c in conexoes:
                with st.expander(f"📌 {c.get('disciplina','')}"):
                    st.markdown(c.get("como_se_conecta", ""))
                    if c.get("exemplo_enem"):
                        st.caption(f"ENEM: {c['exemplo_enem']}")

        dicas_prova = sintese.get("dicas_de_prova", [])
        if dicas_prova:
            st.markdown('<h3 style="color:var(--cyan)">🎯 Dicas de Prova</h3>', unsafe_allow_html=True)
            for d in dicas_prova:
                st.markdown(f'<div class="glass-card">💡 <span style="color:var(--text2)">{d}</span></div>', unsafe_allow_html=True)

        leituras = sintese.get("leituras_recomendadas", {})
        if leituras:
            st.markdown('<h3 style="color:var(--green)">📖 Leituras Recomendadas</h3>', unsafe_allow_html=True)
            for ind in leituras.get("indicacoes", []):
                st.markdown(f'<div class="glass-card"><b style="color:var(--green)">{ind.get("tipo","")}</b>: <span style="color:var(--text2)">{ind.get("titulo","")} — {ind.get("onde_encontrar","")}</span></div>', unsafe_allow_html=True)
            kws = leituras.get("palavras_chave_scholar", [])
            if kws:
                st.caption(f"Google Scholar: {', '.join(kws)}")

        # ── Questão ENEM ──────────────────────────────────────────────────────
        questao          = sintese.get("questao_enem", {})
        questao_completa = sintese.get("questao_completa", questao)
        gabarito_correto = questao_completa.get("gabarito_interno", "")

        if questao:
            st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
            st.markdown('<h3 style="color:var(--cyan)">📝 Questão Estilo ENEM</h3>', unsafe_allow_html=True)

            if questao.get("texto_apoio"):
                st.markdown(
                    f'<div class="glass-card glass-card-purple">'
                    f'<span style="color:var(--text3);font-size:.72rem;letter-spacing:.5px">TEXTO DE APOIO</span><br>'
                    f'<span style="color:var(--text2)">{questao["texto_apoio"]}</span></div>',
                    unsafe_allow_html=True,
                )

            st.markdown(f'<div class="glass-card glass-card-cyan"><b style="color:var(--text)">{questao.get("enunciado","")}</b></div>', unsafe_allow_html=True)

            analise_kw = sintese.get("analise_palavras_chave", {})
            if analise_kw:
                with st.expander("🔎 Análise de Palavras-Chave"):
                    enunciado_kw = analise_kw.get("no_enunciado", {})
                    if enunciado_kw:
                        st.markdown("**No enunciado:**")
                        for c in enunciado_kw.get("conectivos", []):
                            st.markdown(f"- 🔄 {c}")
                        for d in enunciado_kw.get("delimitadores", []):
                            st.markdown(f"- ⏱️ {d}")
                        if enunciado_kw.get("comando"):
                            st.markdown(f"- 🎯 Comando: {enunciado_kw['comando']}")
                    alts_kw = analise_kw.get("nas_alternativas", {})
                    if alts_kw:
                        st.markdown("**Nas alternativas:**")
                        for a in alts_kw.get("absolutismo_armadilha", []):
                            st.markdown(f"- 🚨 {a}")
                        for p in alts_kw.get("pegadinhas_vocabulario", []):
                            st.markdown(f"- 🎭 {p}")
                        if alts_kw.get("marcadores_correto"):
                            st.markdown(f"- ✔️ {alts_kw['marcadores_correto']}")

            st.markdown("")

            tentativas   = st.session_state["tentativas"]
            nivel_dica   = st.session_state["nivel_dica_atual"]
            acertou      = st.session_state["resposta_correta"]
            gabarito_vis = st.session_state["gabarito_texto"]
            alternativas = questao.get("alternativas", {})

            if tentativas > 0 and not acertou and not gabarito_vis:
                st.markdown(f'<div class="metric-chip" style="display:inline-block;margin:.4rem 0">🔄 Tentativa <span>{tentativas}</span> de {nome} — não desista!</div>', unsafe_allow_html=True)

            for i, texto_dica in enumerate(st.session_state["dicas_texto"], start=1):
                st.markdown(f'<div class="dica-box"><b>💡 Dica {i} para {nome}</b><br>{texto_dica}</div>', unsafe_allow_html=True)

            # Acertou
            if acertou:
                letra = st.session_state["letra_escolhida"]
                msg   = f"🏆 Incrível, {nome}! Acertou de primeira!" if tentativas == 1 else f"💪 {nome} acertou na {tentativas}ª tentativa — ótima persistência!"
                st.markdown(f'<div class="gabarito-box"><b>✅ Correto! Alternativa {letra}</b><br>{msg}</div>', unsafe_allow_html=True)
                if tentativas == 1:
                    st.balloons()

                if not gabarito_vis:
                    with st.spinner("Gerando gabarito comentado..."):
                        r = edu.request_gabarito(res["tema"], questao_completa)
                    if not r.get("erro") and not r.get("bloqueado"):
                        st.session_state["gabarito_texto"] = r["gabarito"]
                        edu._analista.register_hint(res["tema"], 0)
                        st.rerun()

                if st.session_state["gabarito_texto"]:
                    st.markdown(f'<div class="gabarito-box"><b>✅ Gabarito Comentado</b><br>{st.session_state["gabarito_texto"]}</div>', unsafe_allow_html=True)

            # Gabarito por esgotamento
            elif gabarito_vis and not acertou:
                letra_err = st.session_state["letra_escolhida"]
                st.markdown(f'<div class="erro-box">❌ <b>Alternativa {letra_err}</b> não era a correta, {nome}.<br><span style="color:var(--text3)">Mas não tem problema — é assim que se aprende!</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="gabarito-box"><b>✅ Gabarito Comentado</b><br>{gabarito_vis}</div>', unsafe_allow_html=True)

            # Alternativas clicáveis
            else:
                st.markdown(f'<p style="color:var(--text3);font-size:.82rem">👆 {nome}, escolha sua resposta:</p>', unsafe_allow_html=True)
                cols_alt = st.columns(5)
                for col, letra in zip(cols_alt, ["A", "B", "C", "D", "E"]):
                    if not alternativas.get(letra):
                        continue
                    with col:
                        if st.button(f"**{letra}**", key=f"alt_{letra}_{tentativas}", use_container_width=True):
                            st.session_state["letra_escolhida"] = letra
                            st.session_state["tentativas"] += 1

                            if letra == gabarito_correto:
                                st.session_state["resposta_correta"] = True
                                edu._analista.register_hint(res["tema"], nivel_dica)
                                st.rerun()
                            else:
                                proximo = nivel_dica + 1
                                if proximo <= 3:
                                    with st.spinner(f"Preparando dica {proximo} para {nome}..."):
                                        r = edu.request_hint(res["tema"], questao, proximo)
                                    if not r.get("erro"):
                                        st.session_state["dicas_texto"].append(r["dica"])
                                        st.session_state["nivel_dica_atual"] = proximo
                                        _atualizar_dicas_historico(res["tema"], proximo)
                                else:
                                    with st.spinner("Liberando gabarito..."):
                                        r = edu.request_gabarito(res["tema"], questao_completa)
                                    if not r.get("erro") and not r.get("bloqueado"):
                                        st.session_state["gabarito_texto"] = r["gabarito"]
                                        st.session_state["nivel_dica_atual"] = 4
                                        edu._analista.register_gabarito(res["tema"])
                                st.rerun()

                # Texto das alternativas
                st.markdown("")
                for letra in ["A", "B", "C", "D", "E"]:
                    txt = alternativas.get(letra, "")
                    if txt:
                        st.markdown(f'<div class="alt-card"><b>{letra})</b> <span>{txt}</span></div>', unsafe_allow_html=True)

    # ── Aba 2: Fontes ─────────────────────────────────────────────────────────
    with aba2:
        st.markdown(f'<h3 style="color:var(--cyan)">🔍 Fontes — modo: {pesquisa.get("tipo_busca","")}</h3>', unsafe_allow_html=True)
        resumo = pesquisa.get("resumo", "")
        if resumo:
            st.markdown(f'<div class="glass-card glass-card-cyan"><span style="color:var(--text2)">{resumo}</span></div>', unsafe_allow_html=True)

        for titulo, cor, fontes in [
            ("📘 Conteúdo Didático",     "cyan",   pesquisa.get("conteudo_didatico",     [])),
            ("📰 Notícias Recentes",      "green",  pesquisa.get("noticias_relevantes",   [])),
            ("🎓 Referências Acadêmicas", "purple", pesquisa.get("referencias_academicas",[])),
        ]:
            if fontes:
                st.markdown(f'<h4 style="color:var(--{cor})">{titulo} ({len(fontes)})</h4>', unsafe_allow_html=True)
                for f in fontes:
                    with st.expander(f.get("titulo","Sem título")):
                        st.markdown(f'🔗 [{f.get("url","")}]({f.get("url","")})')
                        st.markdown(f'<span style="color:var(--text3)">{f.get("conteudo","")}</span>', unsafe_allow_html=True)

        lacunas = pesquisa.get("lacunas_e_aprofundamento", [])
        if lacunas:
            st.markdown('<h4 style="color:var(--yellow)">⚠️ Lacunas Identificadas</h4>', unsafe_allow_html=True)
            for l in lacunas:
                with st.expander(f"Camada: {l.get('camada','')}"):
                    st.markdown(l.get("descricao", ""))
                    if l.get("palavras_chave_pt"):
                        st.caption(f"Buscar em PT: {', '.join(l['palavras_chave_pt'])}")
                    if l.get("palavras_chave_en"):
                        st.caption(f"Buscar em EN: {', '.join(l['palavras_chave_en'])}")

    # ── Aba 3: Análise Crítica ────────────────────────────────────────────────
    with aba3:
        st.markdown('<h3 style="color:var(--purple)">🧠 Análise Crítica do Professor</h3>', unsafe_allow_html=True)

        prioridade = critica.get("nivel_prioridade","").lower()
        cor_p = {"alta":"var(--red)","média":"var(--yellow)","baixa":"var(--green)"}.get(prioridade,"var(--text3)")
        st.markdown(f'<div class="glass-card glass-card-purple"><b style="color:{cor_p}">● {prioridade.upper()}</b> — <span style="color:var(--text3)">{critica.get("justificativa_prioridade","")}</span></div>', unsafe_allow_html=True)

        freq = critica.get("frequencia_enem", {})
        if freq:
            st.markdown('<h4 style="color:var(--cyan)">📊 Frequência no ENEM</h4>', unsafe_allow_html=True)
            st.markdown(f'<div class="glass-card"><span style="color:var(--text2)">{freq.get("descricao","")}</span></div>', unsafe_allow_html=True)
            if freq.get("areas"):
                st.caption(f"Áreas: {' | '.join(freq['areas'])} — Profundidade: {freq.get('profundidade','')}")

        erros = critica.get("erros_comuns", [])
        if erros:
            st.markdown('<h4 style="color:var(--red)">⚠️ Erros Mais Comuns</h4>', unsafe_allow_html=True)
            for e in erros:
                with st.expander(f"❌ {e.get('erro','')}"):
                    st.markdown(f"**Por que acontece:** {e.get('explicacao','')}")
                    st.markdown(f"**Como evitar:** {e.get('como_evitar','')}")

        conexoes_c = critica.get("conexoes_interdisciplinares", [])
        if conexoes_c:
            st.markdown('<h4 style="color:var(--purple)">🔗 Conexões</h4>', unsafe_allow_html=True)
            for c in conexoes_c:
                with st.expander(f"📌 {c.get('disciplina','')}"):
                    st.markdown(c.get("conexao",""))
                    if c.get("exemplo_enem"):
                        st.caption(f"ENEM: {c['exemplo_enem']}")

        criticos = critica.get("pontos_criticos", [])
        if criticos:
            st.markdown('<h4 style="color:var(--green)">🎯 Pontos Críticos Obrigatórios</h4>', unsafe_allow_html=True)
            for p in criticos:
                ancora = " 🔑" if p.get("ancora") else ""
                st.markdown(
                    f'<div class="glass-card glass-card-green"><b style="color:var(--green)">{p.get("conceito","")}</b>{ancora} '
                    f'<span style="color:var(--text3);font-size:.75rem">({p.get("importancia","")})</span><br>'
                    f'<span style="color:var(--text2)">{p.get("descricao","")}</span></div>',
                    unsafe_allow_html=True,
                )

        ctx = critica.get("contexto_atual", {})
        if ctx:
            st.markdown('<h4 style="color:var(--cyan)">🌍 Contexto Atual</h4>', unsafe_allow_html=True)
            for label, chave in [("Eventos","eventos_recentes"),("Dados","dados_estatisticos"),("Debate","debate_atual")]:
                if ctx.get(chave):
                    st.markdown(f'<div class="glass-card"><b style="color:var(--text3)">{label}:</b> <span style="color:var(--text2)">{ctx[chave]}</span></div>', unsafe_allow_html=True)

    # ── Aba 4: Sessão ─────────────────────────────────────────────────────────
    with aba4:
        st.markdown(f'<h3 style="color:var(--green)">📊 Sessão de {nome}</h3>', unsafe_allow_html=True)
        snap = edu.snapshot_sessao()
        temas_sess = snap.get("temas_estudados", [])
        difs_sess  = snap.get("dificuldade_por_tema", {})

        st.markdown(
            f'<div class="metric-row">'
            f'<div class="metric-chip">Temas: <span>{len(temas_sess)}</span></div>'
            f'<div class="metric-chip">Duração: <span>{snap.get("duracao_min",0):.1f} min</span></div>'
            f'<div class="metric-chip">Meta: <span>{meta}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for t in temas_sess:
            dif = difs_sess.get(t, "—")
            cor = {"fácil":"var(--green)","médio":"var(--yellow)","difícil":"var(--red)"}.get(dif,"var(--text3)")
            st.markdown(f'<div class="glass-card" style="padding:.5rem 1rem"><span style="color:{cor}">●</span> <b style="color:var(--text)">{t}</b> <span style="color:var(--text3);font-size:.76rem">{dif}</span></div>', unsafe_allow_html=True)

        st.markdown("")
        if st.button("📊 Gerar Relatório Completo com IA", use_container_width=True):
            with st.spinner(f"Gerando análise personalizada para {nome}..."):
                relatorio = edu.relatorio_sessao()
            st.markdown(f'<div class="glass-card glass-card-purple">{relatorio.get("resumo_sessao","")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="preview-v2"><b>🚀</b> {relatorio.get("preview_v2","")}</div>', unsafe_allow_html=True)

        if st.button("🖥️ Ver Log do Pipeline", use_container_width=True):
            st.markdown(f'<div class="log-box">{edu.log_sessao()}</div>', unsafe_allow_html=True)

# ── Tela inicial (sem resultado) ──────────────────────────────────────────────
elif not iniciar:
    st.markdown(f"""
    <div style="text-align:center;padding:2.5rem 1rem">
      <div style="font-size:2.8rem">⚡</div>
      <h3 style="color:var(--text)">Bem-vindo, {nome}!</h3>
      <p style="color:var(--text3)">Digite um tema do ENEM ou clique em um exemplo acima.<br>
      Seus 6 agentes de IA estão prontos para você.</p>
      <br>
      <div style="display:flex;justify-content:center;gap:1rem;flex-wrap:wrap">
        <div class="onboarding-card"><div style="font-size:1.8rem">🔍</div><div style="color:var(--text);font-weight:600">Pesquisador</div><div style="color:var(--text3);font-size:.75rem">3 camadas de busca</div></div>
        <div class="onboarding-card"><div style="font-size:1.8rem">📚</div><div style="color:var(--text);font-weight:600">ENEM API</div><div style="color:var(--text3);font-size:.75rem">Questões reais</div></div>
        <div class="onboarding-card"><div style="font-size:1.8rem">🏆</div><div style="color:var(--text);font-weight:600">Ranqueador</div><div style="color:var(--text3);font-size:.75rem">Dificuldade adaptativa</div></div>
        <div class="onboarding-card"><div style="font-size:1.8rem">🧠</div><div style="color:var(--text);font-weight:600">Crítico</div><div style="color:var(--text3);font-size:.75rem">Análise estratégica</div></div>
        <div class="onboarding-card"><div style="font-size:1.8rem">📝</div><div style="color:var(--text);font-weight:600">Sintetizador</div><div style="color:var(--text3);font-size:.75rem">Material completo</div></div>
        <div class="onboarding-card"><div style="font-size:1.8rem">💡</div><div style="color:var(--text);font-weight:600">Estrategista</div><div style="color:var(--text3);font-size:.75rem">3 dicas progressivas</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
