import sys
import os
import time
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from agents.orchestrator import KnowSynth as EduSynth
from utils.supabase_db import save_sessao, save_resposta, save_questao_cache


# ── Helpers ───────────────────────────────────────────────────────────────────

# FIX 3 — Fonte única de verdade para detecção de idioma estrangeiro
# Usada por _iniciar_tema, pelo botão "Estudar Agora" e pelo aviso de idioma
def _detectar_idioma_tema(tema: str) -> str:
    """Retorna 'ingles', 'espanhol' ou '' conforme o tema informado."""
    t = tema.lower().strip()
    if any(k in t for k in ("inglês", "ingles", "english", "língua inglesa")):
        return "ingles"
    if any(k in t for k in ("espanhol", "español", "spanish", "língua espanhola")):
        return "espanhol"
    return ""


def _atualizar_dicas_historico(tema: str, nivel: int):
    hist = st.session_state["historico"]
    st.session_state["historico"] = [
        (t, a, max(d, nivel)) if t == tema else (t, a, d)
        for t, a, d in hist
    ]


# ── Configuração da página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="KnowSynth — ENEM",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── PWA — manifest + service worker ──────────────────────────────────────────
# Manifest injetado via data URI para compatibilidade com Streamlit Cloud.
# Service worker mínimo: garante o botão "Adicionar à tela inicial" no mobile.
st.markdown("""
<link rel="manifest" href="data:application/manifest+json,{
  %22name%22: %22KnowSynth%22,
  %22short_name%22: %22KnowSynth%22,
  %22description%22: %22Assistente de estudos para o ENEM com IA%22,
  %22start_url%22: %22/%22,
  %22display%22: %22standalone%22,
  %22background_color%22: %22%230e1117%22,
  %22theme_color%22: %22%2300d4ff%22,
  %22icons%22: [{
    %22src%22: %22https://em-content.zobj.net/source/twitter/376/graduation-cap_1f393.png%22,
    %22sizes%22: %22512x512%22,
    %22type%22: %22image/png%22
  }]
}">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="KnowSynth">
<meta name="theme-color" content="#0e1117">
<script>
if ('serviceWorker' in navigator) {
  const sw = `
    self.addEventListener('install', e => self.skipWaiting());
    self.addEventListener('activate', e => clients.claim());
    self.addEventListener('fetch', e => e.respondWith(fetch(e.request).catch(() => caches.match(e.request))));
  `;
  const blob = new Blob([sw], {type: 'application/javascript'});
  const swUrl = URL.createObjectURL(blob);
  navigator.serviceWorker.register(swUrl).catch(() => {});
}
</script>
""", unsafe_allow_html=True)

# ── Marca d'água KS ───────────────────────────────────────────────────────────
st.markdown("""
    <div style="
        position: fixed;
        top: 50%;
        left: 55%;
        transform: translate(-50%, -50%);
        font-size: 22vw;
        font-weight: 900;
        color: rgba(255, 255, 255, 0.07);
        z-index: 0;
        pointer-events: none;
        user-select: none;
        letter-spacing: -0.05em;
        font-family: Arial Black, sans-serif;
    ">KS</div>
""", unsafe_allow_html=True)

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

  /* ── Tela de carregamento imersiva ── */
  @keyframes ks-spin  { to { transform: rotate(360deg); } }
  @keyframes ks-pulse { 0%,100%{box-shadow:0 0 24px rgba(0,245,255,.15),0 0 0 rgba(157,78,221,0)} 50%{box-shadow:0 0 60px rgba(0,245,255,.35),0 0 80px rgba(157,78,221,.2)} }
  @keyframes ks-fade  { 0%{opacity:0;transform:translateY(10px)} 100%{opacity:1;transform:translateY(0)} }

  .ks-loading-wrap {
    background: linear-gradient(160deg,#08080f,#0d0d1a,#0a0a0a);
    border: 1px solid rgba(0,245,255,.22);
    border-radius: 22px;
    padding: 3.5rem 2rem 3rem;
    text-align: center;
    margin: 1rem 0 2rem;
    animation: ks-pulse 2.4s ease-in-out infinite;
    position: relative;
    overflow: hidden;
  }
  .ks-loading-wrap::before {
    content:'';
    position:absolute; inset:0;
    background: radial-gradient(ellipse at 30% 40%,rgba(0,245,255,.04),transparent 55%),
                radial-gradient(ellipse at 70% 60%,rgba(157,78,221,.05),transparent 55%);
    pointer-events:none;
  }
  .ks-spinner {
    width:76px; height:76px;
    border:4px solid rgba(0,245,255,.12);
    border-top-color:#00f5ff;
    border-right-color:rgba(157,78,221,.6);
    border-radius:50%;
    animation:ks-spin .75s linear infinite;
    margin:0 auto 1.6rem;
  }
  .ks-agent-name {
    font-size:1.15rem; font-weight:800;
    background:linear-gradient(90deg,#00f5ff,#9d4edd);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
    margin-bottom:.55rem; letter-spacing:.2px;
  }
  .ks-msg {
    color:#999; font-size:.9rem; min-height:1.5em;
    animation:ks-fade .35s ease-out;
  }
  .ks-steps {
    display:flex; justify-content:center; margin:1.8rem auto .4rem;
    max-width:520px; border-radius:10px; overflow:hidden;
    border:1px solid #1c1c1c;
  }
  .ks-step {
    flex:1; padding:.38rem .5rem; font-size:.73rem; font-weight:600;
    color:#333; background:#0e0e0e; border-right:1px solid #1c1c1c;
    transition:all .3s ease; white-space:nowrap;
  }
  .ks-step:last-child { border-right:none; }
  .ks-step.active  { background:rgba(0,245,255,.08); color:#00f5ff; border-bottom:2px solid #00f5ff; }
  .ks-step.done    { background:rgba(0,255,136,.06); color:#00ff88; }
  .ks-wait-msg {
    margin-top:1.4rem; color:#444; font-size:.78rem;
    display:flex; align-items:center; justify-content:center; gap:.4rem;
  }
  /* Inputs desabilitados durante carregamento */
  .ks-disabled-hint {
    color:#555; font-size:.78rem; text-align:center;
    padding:.35rem; margin-top:.3rem;
    animation:ks-fade .3s ease-out;
  }

  /* Cards de conteúdo — fundo escuro, texto branco */
  .content-card {
    background: rgba(255,255,255,0.05);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    margin: .5rem 0;
    color: #ffffff;
  }
  .content-card p, .content-card span, .content-card li { color: #ffffff !important; }
  .content-card b, .content-card strong { color: #ffffff !important; }
  .content-card-cyan   { border: 1.5px solid rgba(0,245,255,.5);  box-shadow: 0 0 14px rgba(0,245,255,.1); }
  .content-card-green  { border: 1.5px solid rgba(0,255,136,.5);  box-shadow: 0 0 14px rgba(0,255,136,.1); }
  .content-card-purple { border: 1.5px solid rgba(157,78,221,.5); box-shadow: 0 0 14px rgba(157,78,221,.1); }
  .content-card-yellow { border: 1.5px solid rgba(255,200,0,.5);  box-shadow: 0 0 14px rgba(255,200,0,.1); }

  /* Badge da questão */
  .questao-badge {
    display: inline-block;
    background: rgba(0,245,255,.08);
    border: 1px solid rgba(0,245,255,.5);
    border-radius: 99px;
    padding: .25rem .9rem;
    font-size: .75rem;
    font-weight: 700;
    color: var(--cyan);
    letter-spacing: .4px;
    margin-bottom: .7rem;
  }
  .questao-badge-ai {
    border-color: rgba(157,78,221,.5);
    color: var(--purple);
    background: rgba(157,78,221,.08);
  }

  /* Alternativas — botão à esquerda, texto à direita */
  .alt-row {
    display: flex;
    align-items: center;
    gap: .75rem;
    background: #1a1a2e;
    border: 2.5px solid rgba(0,245,255,.45);
    border-radius: 10px;
    padding: .55rem .9rem;
    margin: .35rem 0;
    transition: border-color .2s, box-shadow .2s, background .2s;
  }
  .alt-row:hover {
    border-color: #00f5ff;
    box-shadow: 0 0 14px rgba(0,245,255,.25);
    background: rgba(0,245,255,.06);
  }
  .alt-letra {
    min-width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 7px;
    background: #0a0a0a;
    border: 3px solid #00f5ff;
    color: #00f5ff;
    font-weight: 800;
    font-size: .88rem;
    flex-shrink: 0;
    letter-spacing: 0;
  }
  .alt-texto { color: #ffffff; font-size: .9rem; line-height: 1.5; }
  .alt-row-correta {
    border-color: var(--green) !important;
    box-shadow: 0 0 16px rgba(0,255,136,.3) !important;
    background: rgba(0,255,136,.07) !important;
  }
  .alt-row-correta .alt-letra { background: #0a0a0a; border-color: var(--green); color: var(--green); }
  .alt-row-correta .alt-texto { color: #ffffff !important; }
  .alt-row-errada {
    border-color: var(--red) !important;
    box-shadow: 0 0 16px rgba(255,68,68,.3) !important;
    background: rgba(255,68,68,.07) !important;
  }
  .alt-row-errada .alt-letra { background: #0a0a0a; border-color: var(--red); color: var(--red); }
  .alt-row-errada .alt-texto { color: #ffffff !important; }

  /* Alternativas */
  .alt-card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:.6rem 1rem; margin:.25rem 0; }
  .alt-card b { color:var(--cyan); }
  .alt-card span { color:var(--text2); }

  /* Botões de letra das alternativas (col_btn) */
  div[data-testid="column"] > div > div > div > button[kind="secondary"] {
    background: #0a0a0a !important;
    border: 3px solid #00f5ff !important;
    color: #00f5ff !important;
    font-weight: 800 !important;
    font-size: .88rem !important;
    border-radius: 7px !important;
    padding: .3rem .1rem !important;
    min-height: 36px !important;
  }
  div[data-testid="column"] > div > div > div > button[kind="secondary"]:hover {
    background: rgba(0,245,255,.08) !important;
    box-shadow: 0 0 12px rgba(0,245,255,.4) !important;
    border-color: #00f5ff !important;
    color: #00f5ff !important;
  }
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
        "carregando":       False,
        "tema_pendente":    "",
        "cache_temas":      {},   # tema_key → resultado completo do pipeline
        "limpando":         False,  # flag: tela limpa antes de iniciar carregamento
        # Questão
        "tentativas":       0,
        "nivel_dica_atual": 0,
        "dicas_texto":      [],
        "gabarito_texto":   None,
        "resposta_correta": False,
        "letra_escolhida":  None,
        # Fila de questões reais (Top 3 + opcional IA)
        "fila_questoes":    [],    # lista de dicts de questão
        "fila_idx":         0,     # índice da questão atual na fila
        "questao_atual":    None,  # questão sendo exibida agora
        "oferta_ia_vista":  False, # se a oferta de questão IA já foi apresentada
        "questao_ia_ativa": False, # se o aluno aceitou a questão IA
        "fila_concluida":   False, # se terminou todas as questões do tema
        # Balões de temas
        "baloes_temas":     [],
        "baloes_ts":        0.0,
        "balao_clicado":    False,
        # Botões de idioma
        "lang_clicada":     "",   # "ingles" ou "espanhol"
        "modo_idioma":      "",   # persiste durante o pipeline
        # Timer UI
        "timer_visivel":    False,
        "meta_atingida":    False,
        "pausa_ativa":      False,
        "pausa_inicio":     None,
        # Supabase
        "respostas_buffer":    [],   # buffer de respostas — salvo em lote ao encerrar sessão
        "supabase_sessao_id":  None, # UUID da sessão no Supabase (preenchido ao encerrar)
        # Login
        "acesso_rapido_aberto": False,  # flag: exibe campo de nome no fluxo de acesso rápido
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

_ETAPAS_LOADING = ["🔍 Pesquisando", "🧠 Analisando", "📝 Sintetizando", "📚 Questões"]

def _loading_html(agente: str, mensagem: str, etapa: int) -> str:
    """Gera o HTML da tela de carregamento imersiva."""
    steps_html = ""
    for i, e in enumerate(_ETAPAS_LOADING):
        if i < etapa:
            cls = "ks-step done"
        elif i == etapa:
            cls = "ks-step active"
        else:
            cls = "ks-step"
        steps_html += f'<div class="{cls}">{e}</div>'

    return f"""
    <div class="ks-loading-wrap">
      <div class="ks-spinner"></div>
      <div class="ks-agent-name">{agente}</div>
      <div class="ks-msg">{mensagem}</div>
      <div class="ks-steps">{steps_html}</div>
      <div class="ks-wait-msg">⏳ Aguarde, gerando seu material...</div>
    </div>
    """


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
        st.markdown('<p style="color:#333;font-size:.78rem">KnowSynth v1</p>', unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        st.markdown("""
        <div style="text-align:center;padding:3rem 0 2rem">
          <div class="login-title">KnowSynth</div>
          <p class="login-sub">Synthesizing knowledge, powering learning</p>
        </div>
        """, unsafe_allow_html=True)

        # ── Fluxo: Login normal ───────────────────────────────────────────────
        nome  = st.text_input("Nome", placeholder="Ex: Ana, Carlos, Mariana...", key="input_nome")
        senha = st.text_input("Senha", placeholder="Digite sua senha", type="password", key="input_senha")

        meta = st.selectbox(
            "Qual sua meta de estudos hoje?",
            ["Sem limite", "30min", "1h", "2h", "3h"],
            index=0,
            key="input_meta",
        )

        st.markdown("")
        if st.button("🚀 Entrar", type="primary", use_container_width=True):
            if not nome.strip():
                st.error("Por favor, insira seu nome para continuar.")
            elif not senha.strip():
                st.error("Por favor, insira uma senha para continuar.")
            else:
                st.session_state["logged_in"]     = True
                st.session_state["usuario_nome"]  = nome.strip()
                st.session_state["meta_tempo"]    = meta
                st.session_state["sessao_inicio"] = time.time()
                st.rerun()

        # ── Divisor ───────────────────────────────────────────────────────────
        st.markdown("""
        <div style="display:flex;align-items:center;gap:.8rem;margin:1.2rem 0">
          <hr style="flex:1;border-color:rgba(255,255,255,.1)">
          <span style="color:#555;font-size:.8rem">ou</span>
          <hr style="flex:1;border-color:rgba(255,255,255,.1)">
        </div>
        """, unsafe_allow_html=True)

        # ── Fluxo: Acesso Rápido ──────────────────────────────────────────────
        if st.button("⚡ Acesso Rápido", use_container_width=True):
            st.session_state["acesso_rapido_aberto"] = True
            st.rerun()

        if st.session_state.get("acesso_rapido_aberto"):
            st.markdown('<p style="color:var(--text3);font-size:.85rem;margin-top:.8rem">Como você quer ser chamado?</p>', unsafe_allow_html=True)
            nome_rapido = st.text_input("Nome", placeholder="Ex: Ana, Carlos...", key="input_nome_rapido", label_visibility="collapsed")
            if st.button("▶️ Entrar sem senha", use_container_width=True):
                if not nome_rapido.strip():
                    st.error("Insira seu nome para continuar.")
                else:
                    st.session_state["logged_in"]            = True
                    st.session_state["usuario_nome"]         = nome_rapido.strip()
                    st.session_state["meta_tempo"]           = "Sem limite"
                    st.session_state["sessao_inicio"]        = time.time()
                    st.session_state["acesso_rapido_aberto"] = False
                    st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# TELA 2 — RELATÓRIO FINAL (após encerrar sessão)
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state["sessao_encerrada"]:
    nome     = st.session_state["usuario_nome"]
    decorrido = _tempo_decorrido()
    edu      = _get_edu()

    # ── Persistência Supabase — executa uma única vez ao encerrar ────────────
    if st.session_state.get("supabase_sessao_id") is None:
        _ultimo_tema = st.session_state["historico"][-1][0] if st.session_state["historico"] else ""
        _disciplina  = st.session_state["historico"][-1][1] if st.session_state["historico"] else None
        _sessao_id   = save_sessao(
            aluno_nome = nome,
            inicio     = st.session_state["sessao_inicio"],
            fim        = time.time(),
            tema       = _ultimo_tema,
            disciplina = _disciplina,
            meta_tempo = st.session_state["meta_tempo"],
        )
        st.session_state["supabase_sessao_id"] = _sessao_id or "erro"
        if _sessao_id:
            for _resp in st.session_state.get("respostas_buffer", []):
                save_resposta(sessao_id=_sessao_id, **_resp)
    # ─────────────────────────────────────────────────────────────────────────

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

    # E-mail do relatório
    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:var(--cyan)">📧 Receber Relatório por E-mail</h3>', unsafe_allow_html=True)
    st.markdown('<p style="color:var(--text3);font-size:.88rem">Opcional — enviaremos um resumo da sessão com seus pontos fracos e recomendações.</p>', unsafe_allow_html=True)

    email_col, btn_col = st.columns([3, 1])
    with email_col:
        email_input = st.text_input(
            "Seu e-mail",
            placeholder="aluno@email.com",
            label_visibility="collapsed",
            key="email_relatorio",
        )
    with btn_col:
        enviar_email = st.button("Enviar", use_container_width=True)

    if enviar_email:
        if not email_input or "@" not in email_input:
            st.warning("Digite um e-mail válido antes de enviar.")
        else:
            from utils.email_sender import enviar_relatorio
            with st.spinner("Enviando relatório..."):
                ok, msg = enviar_relatorio(
                    destinatario=email_input,
                    aluno_nome=nome,
                    relatorio=relatorio,
                )
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    # Preview v2
    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="glass-card glass-card-purple" style="text-align:center;padding:1.5rem">
      <b style="color:var(--purple);font-size:1rem">🔜 Próximas funcionalidades</b><br><br>
      <span style="color:var(--text3)">
        📊 Transformações dbt — camada analítica sobre seus dados de sessão com modelos staging e marts<br><br>
        🗺️ Mapa de pontos fracos — visualize sua evolução entre sessões ao longo do tempo<br><br>
        🔐 Login individual por usuário com histórico salvo na nuvem
      </span>
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
      <b>🔜 Em breve</b><br><br>
      • 🔐 Login individual por usuário<br>
      • 🤖 Plano adaptativo por IA
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
      <div class="edu-title">KnowSynth</div>
      <p class="edu-sub">Synthesizing knowledge, powering learning</p><p style="font-size:.78rem;color:#555;margin:0 0 .8rem">Powered by Generative AI — 6 specialized agents</p>
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

# ── Botões de Língua Estrangeira ──────────────────────────────────────────────
st.markdown("""
<style>
  .lang-header { text-align:center; color:#888; font-size:.78rem; margin-bottom:.5rem; }
  /* Aplica borda dourada nos dois botões dentro do bloco de idioma */
  div[data-testid="stHorizontalBlock"].lang-block button {
    border: 1.5px solid #ffc800 !important;
    color: #ffc800 !important;
    background: rgba(255,200,0,.05) !important;
  }
  div[data-testid="stHorizontalBlock"].lang-block button:hover {
    box-shadow: 0 0 14px rgba(255,200,0,.35) !important;
    background: rgba(255,200,0,.10) !important;
  }
  .lang-sep { height:1px; background:linear-gradient(90deg,transparent,rgba(255,200,0,.18),transparent); border:none; margin:.8rem 0 .5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="lang-header">🌍 Língua Estrangeira ENEM</p>', unsafe_allow_html=True)

_carregando_agora = st.session_state.get("carregando", False)
_spc, _col_en, _col_es, _spc2 = st.columns([2, 1, 1, 2])

with _col_en:
    if st.button("en — Inglês", key="btn_lang_ingles", use_container_width=True, disabled=_carregando_agora):
        st.session_state["lang_clicada"] = "ingles"
        st.session_state["tema_input"]   = "Inglês ENEM"
        st.rerun()

with _col_es:
    if st.button("es — Espanhol", key="btn_lang_espanhol", use_container_width=True, disabled=_carregando_agora):
        st.session_state["lang_clicada"] = "espanhol"
        st.session_state["tema_input"]   = "Espanhol ENEM"
        st.rerun()

st.markdown('<hr class="lang-sep">', unsafe_allow_html=True)

# ── Balões de temas interativos ───────────────────────────────────────────────
import random as _random
import re as _re

# Converte ![alt](url) → <img> HTML; descarta broken-images
_IMG_MD = _re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def _md_imgs_para_html(texto: str) -> str:
    """Substitui markdown de imagem por tag <img> renderizável no st.markdown."""
    def _sub(m):
        alt, url = m.group(1), m.group(2)
        if not url or "broken-image" in url:
            return ""
        return (
            f'<img src="{url}" alt="{alt}" '
            f'style="max-width:100%;border-radius:8px;margin:.6rem 0;display:block">'
        )
    return _IMG_MD.sub(_sub, texto)

_TODOS_TEMAS = [
    # Ciências Humanas
    "Revolução Industrial", "Segunda Guerra Mundial", "Ditadura Militar Brasileira", "Globalização",
    # Ciências da Natureza
    "Aquecimento Global", "Fotossíntese", "Genética Mendeliana", "Leis de Newton",
    # Matemática
    "Funções do 1º e 2º Grau", "Progressão Aritmética", "Probabilidade", "Geometria Plana",
    # Linguagens
    "Modernismo Brasileiro", "Interpretação de Texto", "Figuras de Linguagem",
]

_CORES_BALAO = [
    ("rgba(0,245,255,.08)",  "rgba(0,245,255,.5)",  "#00f5ff"),   # ciano
    ("rgba(0,255,136,.08)",  "rgba(0,255,136,.5)",  "#00ff88"),   # verde
    ("rgba(157,78,221,.1)",  "rgba(157,78,221,.5)", "#9d4edd"),   # roxo
    ("rgba(255,165,0,.08)",  "rgba(255,165,0,.5)",  "#ffa500"),   # laranja
    ("rgba(255,105,180,.08)","rgba(255,105,180,.5)","#ff69b4"),   # rosa
]

_ROTACAO_SEG = 600  # 10 minutos

def _atualizar_baloes():
    """Sorteia 5 temas diferentes dos 5 anteriores."""
    anteriores = set(st.session_state.get("baloes_temas", []))
    pool = [t for t in _TODOS_TEMAS if t not in anteriores]
    # Com 15 temas e 5 anteriores, sempre haverá 10 disponíveis — sem precisar resetar
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
        _bloqueado = st.session_state.get("carregando", False)
        if st.button(
            tema_b,
            key=f"balao_{tema_b}_{st.session_state['baloes_ts']:.0f}",
            use_container_width=True,
            disabled=_bloqueado,
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
_esta_carregando = st.session_state.get("carregando", False)
col_inp, col_btn = st.columns([5, 1])
with col_inp:
    tema_digitado = st.text_input(
        "Tema",
        value=st.session_state["tema_input"],
        placeholder="⏳ Aguarde, gerando seu material..." if _esta_carregando else "Digite um tema ou palavra-chave do ENEM...",
        label_visibility="collapsed",
        disabled=_esta_carregando,
    )
with col_btn:
    iniciar = st.button(
        "⏳ Gerando..." if _esta_carregando else "🚀 Estudar Agora",
        type="primary",
        use_container_width=True,
        disabled=_esta_carregando,
    )

if _esta_carregando:
    st.markdown('<div class="ks-disabled-hint">⏳ Aguarde — seus agentes estão trabalhando...</div>', unsafe_allow_html=True)

# ── Pipeline ──────────────────────────────────────────────────────────────────

def _iniciar_tema(tema: str, modo_idioma: str = ""):
    """
    Passo 1: limpa todo o conteúdo anterior e sinaliza 'limpando'.
    O rerun seguinte mostra a tela com balões (estado zerado).
    Passo 2: no próximo rerun, limpando=False e carregando=True dispara o pipeline.

    FIX 1 — Auto-detecta idioma quando não passado explicitamente.
    Garante que balões e histórico com "Inglês ENEM" ativem search_language_questions.
    """
    if not modo_idioma:
        modo_idioma = _detectar_idioma_tema(tema)

    st.session_state.update({
        "resultado_atual":  None,
        "tema_input":       tema,
        "tema_pendente":    tema,
        "modo_idioma":      modo_idioma,
        "limpando":         True,
        "carregando":       False,
        # Questão
        "nivel_dica_atual": 0, "dicas_texto": [], "gabarito_texto": None,
        "tentativas": 0, "resposta_correta": False, "letra_escolhida": None,
        # Fila
        "fila_questoes": [], "fila_idx": 0, "questao_atual": None,
        "oferta_ia_vista": False, "questao_ia_ativa": False, "fila_concluida": False,
    })
    st.rerun()

# Língua clicada
if st.session_state.get("lang_clicada") and st.session_state["tema_input"]:
    _modo = st.session_state["lang_clicada"]
    st.session_state["lang_clicada"] = ""
    _iniciar_tema(st.session_state["tema_input"], modo_idioma=_modo)

# Balão clicado
if st.session_state.get("balao_clicado") and st.session_state["tema_input"]:
    st.session_state["balao_clicado"] = False
    _iniciar_tema(st.session_state["tema_input"])

# Botão "Estudar Agora" — usa _detectar_idioma_tema como fonte única (FIX 3)
if iniciar and tema_digitado.strip():
    if _detectar_idioma_tema(tema_digitado.strip()):
        st.warning("Para estudar Inglês ou Espanhol, use os botões dedicados acima 👆")
    else:
        _iniciar_tema(tema_digitado.strip())

# Passo 2: tela já está limpa → agora ativa o carregamento
if st.session_state.get("limpando") and st.session_state.get("tema_pendente"):
    st.session_state["limpando"]  = False
    st.session_state["carregando"] = True
    st.rerun()

# ── Execução do pipeline com tela imersiva ────────────────────────────────────
if st.session_state["carregando"] and st.session_state["tema_pendente"]:
    tema = st.session_state["tema_pendente"]

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    loading_area = st.empty()

    def _show(agente: str, msg: str, etapa: int):
        loading_area.markdown(_loading_html(agente, msg, etapa), unsafe_allow_html=True)

    _show("🔍 Pesquisador", "Pesquisando nas melhores fontes para você...", 0)

    # ── Cache: reutiliza resultado se o tema já foi pesquisado nessa sessão ──
    _tema_key = tema.lower().replace(" ", "")
    _cache = st.session_state.get("cache_temas", {})
    if _tema_key in _cache:
        loading_area.empty()
        st.session_state["resultado_atual"]  = _cache[_tema_key]
        st.session_state["carregando"]       = False
        st.session_state["tema_pendente"]    = ""
        st.session_state["fila_questoes"]    = _cache[_tema_key].get("_fila", [])
        st.session_state["fila_idx"]         = 0
        st.session_state["questao_atual"]    = st.session_state["fila_questoes"][0] if st.session_state["fila_questoes"] else None
        st.session_state.update({
            "nivel_dica_atual": 0, "dicas_texto": [], "gabarito_texto": None,
            "tentativas": 0, "resposta_correta": False, "letra_escolhida": None,
            "oferta_ia_vista": False, "questao_ia_ativa": False, "fila_concluida": False,
        })
        st.rerun()

    _erro_pipeline = None
    try:
        from agents.researcher  import pesquisar   as _pesquisar
        from agents.critic      import analisar     as _analisar
        from agents.synthesizer import sintetizar   as _sintetizar
        import sys as _sys, os as _os
        _hooks_dir = _os.path.join(_os.path.dirname(__file__), ".claude", "hooks")
        if _hooks_dir not in _sys.path:
            _sys.path.insert(0, _hooks_dir)
        from hooks import pre_agent_hook, post_agent_hook, on_error_hook, clear_session_log

        clear_session_log()

        _t = pre_agent_hook("Pesquisador")
        r_pesquisa = _pesquisar(tema)
        if r_pesquisa.get("tipo_busca") == "erro":
            post_agent_hook("Pesquisador", _t, success=False)
            raise RuntimeError(r_pesquisa.get("erro"))
        post_agent_hook("Pesquisador", _t, success=True)

        _show("🧠 Crítico", "Analisando o que mais cai no ENEM...", 1)
        time.sleep(3)  # respeita limite 20 req/min
        _t = pre_agent_hook("Crítico")
        r_critica = _analisar(r_pesquisa)
        if r_critica.get("erro"):
            post_agent_hook("Crítico", _t, success=False)
            raise RuntimeError(r_critica["erro"])
        post_agent_hook("Crítico", _t, success=True)

        _show("📝 Sintetizador", "Preparando seu material personalizado com carinho...", 2)
        time.sleep(3)  # respeita limite 20 req/min
        _t = pre_agent_hook("Sintetizador")
        r_sintese = _sintetizar(r_pesquisa, r_critica, edu._analista.snapshot())
        if r_sintese.get("erro"):
            post_agent_hook("Sintetizador", _t, success=False)
            raise RuntimeError(r_sintese["erro"])
        post_agent_hook("Sintetizador", _t, success=True)

        edu._analista.register_search(tema)

        _show("🏆 ENEM API + Ranqueador", "Classificando as questões por dificuldade...", 3)
        _t = pre_agent_hook("ENEM API + Ranqueador")
        _modo_idioma_pipeline = st.session_state.get("modo_idioma", "")
        try:
            from agents.enem_api          import search_questions_by_topic, search_language_questions
            from agents.complexity_ranker import classificar_top3

            if _modo_idioma_pipeline:
                questoes_reais = search_language_questions(_modo_idioma_pipeline)
            else:
                questoes_reais = search_questions_by_topic(tema, limit=15)
            if questoes_reais:
                top3 = classificar_top3(questoes_reais)
                fila = [top3[c] for c in ("facil", "medio", "dificil") if top3.get(c)]
                st.session_state["fila_questoes"] = fila
                st.session_state["fila_idx"]      = 0
                st.session_state["questao_atual"] = fila[0] if fila else None
                # Registra cada questão no catálogo (upsert — seguro chamar múltiplas vezes)
                for _q in fila:
                    _qid = f"{str(_q.get('titulo','sem-titulo'))[:50]}-{_q.get('ano','')}"
                    save_questao_cache(
                        questao_id  = _qid,
                        titulo      = _q.get("titulo"),
                        ano         = _q.get("ano"),
                        tema        = tema,
                        disciplina  = _q.get("disciplina"),
                        dificuldade = _q.get("dificuldade"),
                        tem_imagem  = bool(_q.get("files")),
                        is_ai_generated = False,
                    )
            post_agent_hook("ENEM API + Ranqueador", _t, success=True)
        except Exception as _e_rank:
            post_agent_hook("ENEM API + Ranqueador", _t, success=False)
            on_error_hook("ENEM API + Ranqueador", _e_rank)
            st.session_state["fila_questoes"] = []
            st.session_state["questao_atual"] = None

        _resultado = {
            "tema": tema, "pesquisa": r_pesquisa,
            "critica": r_critica, "sintese": r_sintese,
            "_fila": st.session_state.get("fila_questoes", []),
        }
        st.session_state["resultado_atual"] = _resultado
        # Salva no cache da sessão para evitar reprocessamento
        st.session_state["cache_temas"][_tema_key] = _resultado

        hist = [(t, a, d) for t, a, d in st.session_state["historico"] if t != tema]
        hist.append((tema, "não informada", 0))
        st.session_state["historico"] = hist

    except Exception as e:
        _erro_pipeline = e

    finally:
        st.session_state["carregando"]    = False
        st.session_state["tema_pendente"] = ""

    # Limpa overlay ou mostra erro
    if _erro_pipeline:
        loading_area.error(f"❌ {nome}, ocorreu um erro: {_erro_pipeline}")
    else:
        loading_area.empty()

# ── Resultado em abas ─────────────────────────────────────────────────────────
if st.session_state["resultado_atual"]:
    res      = st.session_state["resultado_atual"]
    pesquisa = res["pesquisa"]
    critica  = res["critica"]
    sintese  = res["sintese"]

    st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="color:var(--cyan)">📖 {sintese.get("tema","").upper()}</h2>', unsafe_allow_html=True)

    aba1, aba2, aba3, aba4, aba5 = st.tabs([
        "📚 Material de Estudo",
        "🔍 Fontes Pesquisadas",
        "🧠 Análise Crítica",
        "📊 Minha Sessão",
        "🗺️ Pontos Fracos",
    ])

    # ── Aba 1: Material ───────────────────────────────────────────────────────
    with aba1:

        # Detecta fallback de JSON (quando Groq retornou texto inválido)
        _conteudo_fallback = sintese.get("content", "")
        _tem_material = bool(
            sintese.get("introducao") or
            sintese.get("pontos_essenciais") or
            sintese.get("conexoes_interdisciplinares") or
            sintese.get("dicas_de_prova") or
            sintese.get("leituras_recomendadas")
        )

        if not _tem_material:
            # Exibe conteúdo bruto se JSON falhou ou campos estão todos vazios
            if _conteudo_fallback:
                st.markdown('<h3 style="color:var(--cyan)">📚 Material de Estudo</h3>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="content-card content-card-cyan">'
                    f'<span style="color:#fff">{_conteudo_fallback}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("⚠️ O material ainda está sendo processado. Tente gerar novamente.")
        else:
            intro = sintese.get("introducao", "")
            if intro:
                st.markdown('<h3 style="color:var(--cyan)">🔍 Introdução</h3>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="content-card content-card-cyan"><span style="color:#fff">{intro}</span></div>',
                    unsafe_allow_html=True,
                )

            pontos = sintese.get("pontos_essenciais", [])
            if pontos:
                st.markdown('<h3 style="color:var(--green)">⭐ Pontos Essenciais</h3>', unsafe_allow_html=True)
                for p in pontos:
                    enem = ' <span style="color:var(--purple);font-size:.75rem;font-weight:700">★ ENEM</span>' if p.get("cobrado_enem") else ""
                    st.markdown(
                        f'<div class="content-card content-card-green">'
                        f'<b style="color:#00f5ff">{p.get("conceito","")}</b>{enem}<br>'
                        f'<span style="color:#fff">{p.get("definicao","")}</span><br>'
                        f'<span style="color:#e0e0e0;font-size:.8rem">Exemplo: {p.get("exemplo","")}</span></div>',
                        unsafe_allow_html=True,
                    )

            conexoes = sintese.get("conexoes_interdisciplinares", [])
            if conexoes:
                st.markdown('<h3 style="color:var(--purple)">🔗 Conexões Interdisciplinares</h3>', unsafe_allow_html=True)
                for c in conexoes:
                    with st.expander(f"📌 {c.get('disciplina','')}"):
                        st.markdown(f'<span style="color:#fff">{c.get("como_se_conecta","")}</span>', unsafe_allow_html=True)
                        if c.get("exemplo_enem"):
                            st.caption(f"ENEM: {c['exemplo_enem']}")

            dicas_prova = sintese.get("dicas_de_prova", [])
            if dicas_prova:
                st.markdown('<h3 style="color:var(--cyan)">🎯 Dicas de Prova</h3>', unsafe_allow_html=True)
                for d in dicas_prova:
                    st.markdown(
                        f'<div class="content-card content-card-cyan">💡 <span style="color:#fff">{d}</span></div>',
                        unsafe_allow_html=True,
                    )

            leituras = sintese.get("leituras_recomendadas", {})
            if leituras:
                st.markdown('<h3 style="color:var(--green)">📖 Leituras Recomendadas</h3>', unsafe_allow_html=True)
                for ind in leituras.get("indicacoes", []):
                    st.markdown(
                        f'<div class="content-card content-card-green">'
                        f'<b style="color:var(--green)">{ind.get("tipo","")}</b>: '
                        f'<span style="color:#fff">{ind.get("titulo","")} — {ind.get("onde_encontrar","")}</span></div>',
                        unsafe_allow_html=True,
                    )
                kws = leituras.get("palavras_chave_scholar", [])
                if kws:
                    st.caption(f"Google Scholar: {', '.join(kws)}")

        # ── Seção de questões: fila real + opcional IA ───────────────────────
        st.markdown('<hr class="neon-divider">', unsafe_allow_html=True)
        st.markdown('<h3 style="color:var(--cyan)">📝 Questões</h3>', unsafe_allow_html=True)

        fila          = st.session_state["fila_questoes"]
        fila_idx      = st.session_state["fila_idx"]
        fila_concluida = st.session_state["fila_concluida"]
        oferta_ia     = st.session_state["oferta_ia_vista"]
        questao_ia    = st.session_state["questao_ia_ativa"]

        # Helper: reseta estado da questão atual
        def _resetar_questao():
            st.session_state.update({
                "tentativas": 0, "nivel_dica_atual": 0, "dicas_texto": [],
                "gabarito_texto": None, "resposta_correta": False, "letra_escolhida": None,
            })

        # Helper: renderiza uma questão (real ou sintética)
        def _render_questao(questao_exibir: dict, questao_gabarito: dict):
            gabarito_correto_q = questao_gabarito.get("gabarito_interno", "") or questao_exibir.get("gabarito", "")

            # Badge
            ano_q  = questao_exibir.get("ano")
            is_ai  = questao_exibir.get("is_ai_generated", True)
            dif_q  = questao_exibir.get("dificuldade", "")
            dif_icon = {"fácil": "🟢", "médio": "🟡", "difícil": "🔴"}.get(dif_q, "")

            if not is_ai and ano_q:
                badge_txt   = f"📋 ENEM {ano_q}  {dif_icon} {dif_q.upper() if dif_q else ''}"
                badge_class = "questao-badge"
            else:
                badge_txt   = f"🤖 Questão Gerada por IA — Estilo ENEM  {dif_icon} {dif_q.upper() if dif_q else ''}"
                badge_class = "questao-badge questao-badge-ai"
            st.markdown(f'<span class="{badge_class}">{badge_txt.strip()}</span>', unsafe_allow_html=True)

            # Contexto / texto de apoio
            contexto = questao_exibir.get("contexto") or questao_exibir.get("texto_apoio", "")
            files    = questao_exibir.get("files", [])
            if contexto or files:
                contexto_html = _md_imgs_para_html(contexto) if contexto else ""
                # Imagens do campo files (tabelas, gráficos separados do texto)
                files_html = "".join(
                    f'<img src="{url}" style="max-width:100%;border-radius:8px;margin:.6rem 0;display:block">'
                    for url in files
                )
                st.markdown(
                    f'<div style="background:#1a1a2e;border:2.5px solid rgba(157,78,221,.5);border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">'
                    f'<span style="color:#00f5ff;font-size:.7rem;font-weight:700;letter-spacing:1px;text-transform:uppercase">Texto de Apoio</span><br><br>'
                    f'<span style="color:#ffffff;font-size:.9rem;line-height:1.6">{contexto_html}</span>'
                    f'{files_html}</div>',
                    unsafe_allow_html=True,
                )

            enunciado = questao_exibir.get("enunciado") or questao_exibir.get("alternativesIntroduction", "")
            if enunciado:
                enunciado_html = _md_imgs_para_html(enunciado)
                st.markdown(
                    f'<div style="background:#1a1a2e;border:2.5px solid rgba(0,245,255,.5);border-radius:12px;padding:1rem 1.2rem;margin:.5rem 0">'
                    f'<b style="color:#ffffff;font-size:.95rem;line-height:1.6">{enunciado_html}</b></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("")
            tentativas   = st.session_state["tentativas"]
            nivel_dica   = st.session_state["nivel_dica_atual"]
            acertou      = st.session_state["resposta_correta"]
            gabarito_vis = st.session_state["gabarito_texto"]
            alternativas = questao_exibir.get("alternativas", {})

            if tentativas > 0 and not acertou and not gabarito_vis:
                st.markdown(f'<div class="metric-chip" style="display:inline-block;margin:.4rem 0">🔄 Tentativa <span>{tentativas}</span> — não desista, {nome}!</div>', unsafe_allow_html=True)

            for i, texto_dica in enumerate(st.session_state["dicas_texto"], start=1):
                st.markdown(f'<div class="dica-box"><b>💡 Dica {i} para {nome}</b><br>{texto_dica}</div>', unsafe_allow_html=True)

            # ── Acertou ───────────────────────────────────────────────────────
            if acertou:
                letra = st.session_state["letra_escolhida"]
                msg   = f"🏆 Incrível, {nome}! Acertou de primeira!" if tentativas == 1 else f"💪 {nome} acertou na {tentativas}ª tentativa!"
                st.markdown(f'<div class="gabarito-box"><b>✅ Correto! Alternativa {letra}</b><br>{msg}</div>', unsafe_allow_html=True)
                if tentativas == 1:
                    st.balloons()

                # FIX 5 — busca e exibe gabarito no mesmo ciclo (sem rerun extra)
                if not gabarito_vis:
                    with st.spinner("Gerando gabarito comentado..."):
                        r = edu.request_gabarito(res["tema"], questao_gabarito, force=True)
                    if not r.get("erro"):
                        gabarito_vis = r["gabarito"]
                        st.session_state["gabarito_texto"] = gabarito_vis

                if gabarito_vis:
                    st.markdown(f'<div class="gabarito-box"><b>✅ Gabarito Comentado</b><br>{gabarito_vis}</div>', unsafe_allow_html=True)

                return True  # questão resolvida

            # ── Gabarito por esgotamento ──────────────────────────────────────
            elif gabarito_vis and not acertou:
                letra_err = st.session_state["letra_escolhida"]
                st.markdown(f'<div class="erro-box">❌ <b>Alternativa {letra_err}</b> não era a correta, {nome}.<br><span style="color:var(--text3)">Mas não tem problema — é assim que se aprende!</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="gabarito-box"><b>✅ Gabarito Comentado</b><br>{gabarito_vis}</div>', unsafe_allow_html=True)
                return True  # questão resolvida

            # ── Alternativas clicáveis ────────────────────────────────────────
            else:
                st.markdown(f'<p style="color:var(--text3);font-size:.82rem;margin-bottom:.4rem">👆 {nome}, escolha sua resposta:</p>', unsafe_allow_html=True)
                for letra in ["A", "B", "C", "D", "E"]:
                    txt = alternativas.get(letra, "")
                    if not txt:
                        continue
                    col_btn, col_txt = st.columns([1, 11])
                    with col_btn:
                        if st.button(letra, key=f"alt_{letra}_{fila_idx}_{tentativas}", use_container_width=True):
                            st.session_state["letra_escolhida"] = letra
                            st.session_state["tentativas"] += 1

                            # Bufferiza resposta para salvar no Supabase ao encerrar sessão
                            _qid_buf = f"{str(questao_exibir.get('titulo','sem-titulo'))[:50]}-{questao_exibir.get('ano','ai')}"
                            st.session_state["respostas_buffer"].append({
                                "questao_id":             _qid_buf,
                                "alternativa_escolhida":  letra,
                                "alternativa_correta":    gabarito_correto_q,
                                "acertou":                letra == gabarito_correto_q,
                                "dicas_usadas":           nivel_dica,
                            })

                            if letra == gabarito_correto_q:
                                st.session_state["resposta_correta"] = True
                                st.rerun()
                            else:
                                proximo = nivel_dica + 1
                                if proximo <= 3:
                                    with st.spinner(f"Preparando dica {proximo}..."):
                                        r = edu.request_hint(res["tema"], questao_exibir, proximo)
                                    if not r.get("erro"):
                                        st.session_state["dicas_texto"].append(r["dica"])
                                        st.session_state["nivel_dica_atual"] = proximo
                                        _atualizar_dicas_historico(res["tema"], proximo)
                                else:
                                    with st.spinner("Liberando gabarito..."):
                                        r = edu.request_gabarito(res["tema"], questao_gabarito)
                                    if not r.get("erro") and not r.get("bloqueado"):
                                        st.session_state["gabarito_texto"] = r["gabarito"]
                                        st.session_state["nivel_dica_atual"] = 4
                                        edu._analista.register_gabarito(res["tema"])
                                st.rerun()
                    with col_txt:
                        st.markdown(
                            f'<div class="alt-row" style="margin-top:.15rem">'
                            f'<span class="alt-letra">{letra}</span>'
                            f'<span class="alt-texto">{txt}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                return False  # questão ainda em andamento

        # ── Lógica de navegação da fila ───────────────────────────────────────

        # Estado: fila concluída
        if fila_concluida:
            st.markdown(f"""
            <div class="glass-card glass-card-green" style="text-align:center;padding:1.5rem">
              <div style="font-size:2rem">🏆</div>
              <h3 style="color:var(--green)">Parabéns, {nome}!</h3>
              <p style="color:var(--text2)">Você completou as 3 questões reais do ENEM sobre este tema.</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("🔍 Estudar novo tema", type="primary", use_container_width=True, key="btn_novo_tema"):
                st.session_state["resultado_atual"] = None
                st.session_state["tema_input"]      = ""
                st.rerun()

        # Estado: oferta de questão IA (após as 3 reais)
        elif oferta_ia and not questao_ia:
            st.markdown(f"""
            <div class="glass-card glass-card-purple" style="padding:1.2rem">
              <b style="color:var(--purple)">🤖 Quer praticar mais antes do próximo tema?</b><br>
              <span style="color:var(--text2)">Posso gerar uma questão de IA sobre <b>{res["tema"]}</b> para reforçar o aprendizado.</span>
            </div>
            """, unsafe_allow_html=True)
            col_sim, col_nao = st.columns(2)
            with col_sim:
                if st.button("🤖 Sim, gerar questão IA", use_container_width=True):
                    st.session_state["questao_ia_ativa"] = True
                    _resetar_questao()
                    st.rerun()
            with col_nao:
                if st.button("🔍 Não, estudar novo tema", use_container_width=True, type="primary"):
                    st.session_state["fila_concluida"] = True
                    st.rerun()

        # Estado: questão IA ativa
        elif questao_ia:
            questao_sint  = sintese.get("questao_enem", {})
            questao_comp  = sintese.get("questao_completa", questao_sint)
            resolvida = _render_questao(questao_sint, questao_comp)
            if resolvida and st.session_state["gabarito_texto"]:
                st.markdown("")
                if st.button("🔍 Estudar novo tema", type="primary", use_container_width=True, key="btn_novo_apos_ia"):
                    st.session_state["fila_concluida"] = True
                    st.rerun()

        # Estado: questões reais da fila
        elif fila:
            # Indicador de progresso da fila
            labels = ["🟢 Fácil", "🟡 Médio", "🔴 Difícil"]
            prog_html = ""
            for i, lbl in enumerate(labels[:len(fila)]):
                cor = "var(--cyan)" if i == fila_idx else ("var(--green)" if i < fila_idx else "var(--text3)")
                prog_html += f'<span style="color:{cor};font-weight:{"700" if i==fila_idx else "400"}">{lbl}</span>'
                if i < len(fila) - 1:
                    prog_html += ' <span style="color:#333"> → </span> '
            st.markdown(f'<div style="margin:.4rem 0 .8rem;font-size:.82rem">{prog_html}</div>', unsafe_allow_html=True)

            questao_real = fila[fila_idx]
            resolvida    = _render_questao(questao_real, questao_real)

            # Botão "Próxima" após resolução
            if resolvida and st.session_state["gabarito_texto"]:
                st.markdown("")
                proxima_idx = fila_idx + 1
                if proxima_idx < len(fila):
                    if st.button("➡️ Próxima Questão", use_container_width=True, key="btn_proxima"):
                        st.session_state["fila_idx"] = proxima_idx
                        st.session_state["questao_atual"] = fila[proxima_idx]
                        _resetar_questao()
                        st.rerun()
                else:
                    # Terminou as reais → oferta IA
                    if st.button("➡️ Continuar", use_container_width=True, key="btn_apos_reais"):
                        st.session_state["oferta_ia_vista"] = True
                        _resetar_questao()
                        st.rerun()

        # Fallback: fila vazia → mostra questão sintética diretamente
        else:
            questao_sint = sintese.get("questao_enem", {})
            questao_comp = sintese.get("questao_completa", questao_sint)
            if questao_sint:
                resolvida = _render_questao(questao_sint, questao_comp)
                if resolvida and st.session_state["gabarito_texto"]:
                    st.markdown("")
                    if st.button("🔍 Estudar novo tema", type="primary", use_container_width=True, key="btn_novo_fb"):
                        st.session_state["resultado_atual"] = None
                        st.session_state["tema_input"]      = ""
                        st.rerun()

        # Análise de palavras-chave (sempre visível para o material)
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

    # ── Aba 5: Mapa de Pontos Fracos ─────────────────────────────────────────
    with aba5:
        from utils.supabase_db import get_mapa_pontos_fracos

        st.markdown(f'<h3 style="color:var(--purple)">🗺️ Mapa de Pontos Fracos — {nome}</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color:var(--text3);font-size:.85rem">Baseado em todas as suas sessões anteriores. Atualizado diariamente pelo pipeline dbt.</p>', unsafe_allow_html=True)

        dados = get_mapa_pontos_fracos(nome)

        if not dados:
            st.markdown(
                '<div class="glass-card" style="text-align:center;padding:2rem">'
                '<div style="font-size:2rem">📭</div>'
                '<p style="color:var(--text3)">Nenhum dado encontrado ainda.<br>'
                'Complete sessões de estudo para o mapa ser gerado.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            for item in dados:
                taxa = item.get("taxa_acerto_pct") or 0
                tema = item.get("tema", "—")
                disc = item.get("disciplina") or "—"
                total_q = item.get("total_questoes", 0)
                acertos = item.get("total_acertos", 0)
                sessoes = item.get("total_sessoes", 0)

                if taxa < 40:
                    cor = "var(--red)"
                    icone = "🔴"
                elif taxa < 70:
                    cor = "var(--yellow)"
                    icone = "🟡"
                else:
                    cor = "var(--green)"
                    icone = "🟢"

                st.markdown(
                    f'<div class="glass-card" style="margin-bottom:.5rem;padding:.75rem 1rem">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<div>'
                    f'<span style="font-size:1rem">{icone}</span> '
                    f'<b style="color:var(--text)">{tema}</b> '
                    f'<span style="color:var(--text3);font-size:.78rem">· {disc}</span>'
                    f'</div>'
                    f'<div style="color:{cor};font-weight:700;font-size:1.1rem">{taxa:.0f}%</div>'
                    f'</div>'
                    f'<div style="color:var(--text3);font-size:.75rem;margin-top:.3rem">'
                    f'{acertos}/{total_q} acertos · {sessoes} sessão(ões)'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

# ── Tela inicial (sem resultado e sem carregamento) ───────────────────────────
elif not st.session_state.get("carregando") and not iniciar:
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

