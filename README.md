[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://knowsynth.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.14-blue)
![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash_Lite-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

# KnowSynth

> *Synthesizing knowledge, powering learning.*

KnowSynth is a multi-agent Generative AI system with 6 specialized LLM agents that collaborate in real time to create personalized ENEM study materials.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Input                               │
│              (topic or keyword — e.g. "fordism")                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR                              │
│               orchestrator.py — KnowSynth class                 │
│         Coordinates the full pipeline with hooks                │
└───┬──────────────┬────────────────────────┬──────────────────┬──┘
    │              │                        │                  │
    ▼              ▼                        ▼                  ▼
┌────────┐   ┌──────────┐           ┌────────────┐   ┌──────────────┐
│  🔍    │   │  📚      │           │  🧠        │   │  📝          │
│Researcher│ │ ENEM API │           │  Critic    │   │ Synthesizer  │
│        │   │          │           │            │   │              │
│Tavily  │   │enem.dev  │           │Gemini /    │   │Gemini /      │
│3-layer │   │2021–2023 │           │Groq        │   │Groq          │
│search  │   │real Qs   │           │            │   │              │
└───┬────┘   └────┬─────┘           └─────┬──────┘   └──────┬───────┘
    │             │                       │                  │
    │             ▼                       │                  │
    │      ┌────────────┐                 │                  │
    │      │  🏆        │                 │                  │
    │      │ Complexity │                 │                  │
    │      │  Ranker    │                 │                  │
    │      │(heuristic) │                 │                  │
    │      └────┬───────┘                 │                  │
    │           │                         │                  │
    └─────┬─────┘                         │                  │
          │          ┌────────────────────┘                  │
          │          │          ┌────────────────────────────┘
          │          │          │
          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Interface                         │
│  Material tabs · Question queue (easy→medium→hard) · Timer      │
│  Progressive hints · Session analytics · Dark/Neon UI           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
      ┌──────────────────┐          ┌──────────────────────┐
      │  💡 Strategist   │          │  📊 Performance      │
      │                  │          │     Analyst          │
      │ 3 progressive    │          │                      │
      │ hints before     │          │ Tracks difficulty,   │
      │ answer release   │          │ hints, session time  │
      └──────────────────┘          └──────────────────────┘
```

---

## Agents

| Agent | File | Technology | Role |
|---|---|---|---|
| 🔍 **Researcher** | `agents/researcher.py` | Tavily API | 3-layer semantic web search: didactic sources, news, academic references |
| 📚 **ENEM API** | `agents/enem_api.py` | enem.dev API | Fetches real ENEM questions (2021–2023) filtered by topic and discipline |
| 🏆 **Complexity Ranker** | `agents/complexity_ranker.py` | Local heuristics | Classifies questions into easy / medium / hard with zero LLM calls |
| 🧠 **Critic** | `agents/critic.py` | Gemini 2.5 Flash-Lite / Groq | Strategic analysis: ENEM frequency, common mistakes, interdisciplinary links |
| 📝 **Synthesizer** | `agents/synthesizer.py` | Gemini 2.5 Flash-Lite / Groq | Generates the full study material: introduction, key points, ENEM-style question |
| 💡 **Strategist** | `agents/strategist.py` | Gemini 2.5 Flash-Lite / Groq | Delivers 3 progressive hints; answer only released after hint 3 |
| 📊 **Performance Analyst** | `agents/performance_analyst.py` | Gemini 2.5 Flash-Lite / Groq | Tracks session behavior and generates a personalized end-of-session report |

> The Orchestrator (`agents/orchestrator.py`) coordinates the full pipeline and exposes `estudar()`, `request_hint()`, `request_gabarito()`, and `relatorio_sessao()`.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.14 | Runtime |
| Streamlit | latest | Web interface |
| Google Gemini | 2.5 Flash-Lite | Primary LLM (free tier) |
| Groq — LLaMA 3.3 70B | `llama-3.3-70b-versatile` | Fallback LLM |
| OpenAI — GPT-4o Mini | `gpt-4o-mini` | Last-resort LLM fallback |
| Supabase | PostgreSQL | Persistent data layer (sessions, answers, questions) |
| dbt Cloud | latest | Analytics transformation layer |
| Tavily | latest | Semantic web search |
| enem.dev API | v1 | Real ENEM question bank (2009–2023) |
| python-dotenv | latest | Environment variable management |
| google-genai | 2.7.0 | Gemini SDK |

---

## How It Works

**1. Search** — The Researcher calls Tavily across 3 layers: didactic sites (Brasil Escola, Khan Academy), recent news (G1, BBC Brasil), and academic sources (SciELO, Google Scholar).

**2. Critical Analysis** — The Critic evaluates how often the topic appears in ENEM, the most common student mistakes, and which interdisciplinary connections are most likely to be tested.

**3. Synthesis** — The Synthesizer combines research + critique + the student's current session performance to generate a complete study material: introduction, key concepts, interdisciplinary links, an original ENEM-style question, and study tips.

**4. Real Questions** — The ENEM API fetches official questions from 2021–2023. The Complexity Ranker classifies them locally into easy / medium / hard with no API calls. The student works through the queue in ascending difficulty.

**5. Progressive Hints** — Every wrong answer unlocks one hint from the Strategist. The answer commentary is only released after 3 hints (or when the student gets it right). The Performance Analyst records everything and produces a personalized report at the end of the session.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Free [Groq](https://console.groq.com) account → `GROQ_API_KEY`
- Free [Tavily](https://tavily.com) account → `TAVILY_API_KEY`
- Free [Google AI Studio](https://aistudio.google.com) account → `GEMINI_API_KEY`
- [OpenAI](https://platform.openai.com) account → `OPENAI_API_KEY` *(optional — last-resort LLM fallback)*
- [Supabase](https://supabase.com) project → `SUPABASE_URL` + `SUPABASE_KEY`

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/silasluiz96-alt/KnowSynth.git
cd KnowSynth

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
# Create a .env file in the project root:
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
TAVILY_API_KEY=your_tavily_key_here
OPENAI_API_KEY=your_openai_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_key_here
```

### Running Locally

```bash
python -m streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Deploy on Streamlit Cloud

1. Fork this repository
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Select your fork, branch `main`, file `app.py`
4. Under **Advanced settings → Secrets**, add:
```toml
GEMINI_API_KEY = "your_key"
GROQ_API_KEY   = "your_key"
TAVILY_API_KEY = "your_key"
OPENAI_API_KEY = "your_key"
SUPABASE_URL   = "your_url"
SUPABASE_KEY   = "your_key"
```
5. Click **Deploy** — the app will be live in ~2 minutes

---

## Project Structure

```
knowsynth/
├── app.py                          # Streamlit interface (single-page app)
├── requirements.txt
├── .env                            # Not committed — local API keys
├── .gitignore
│
├── agents/
│   ├── orchestrator.py             # Pipeline coordinator — KnowSynth class
│   ├── researcher.py               # Researcher agent (Tavily)
│   ├── enem_api.py                 # ENEM API agent (enem.dev)
│   ├── complexity_ranker.py        # Question difficulty classifier (local heuristics)
│   ├── critic.py                   # Critic agent (Gemini / Groq)
│   ├── synthesizer.py              # Synthesizer agent (Gemini / Groq)
│   ├── strategist.py               # Strategist agent (Gemini / Groq)
│   └── performance_analyst.py      # Performance Analyst agent (Gemini / Groq)
│
├── utils/
│   ├── __init__.py
│   ├── llm_client.py               # Centralized LLM client (Gemini → Groq → OpenAI fallback)
│   └── supabase_db.py              # Supabase persistence layer (sessions, answers, cache)
│
└── .claude/
    ├── hooks/
    │   └── hooks.py                # Pre/post/error observability hooks
    └── skills/
        ├── researcher.md           # Researcher agent behavior spec
        ├── critic.md               # Critic agent behavior spec
        ├── synthesizer.md          # Synthesizer agent behavior spec
        ├── strategist.md           # Strategist agent behavior spec
        └── performance_analyst.md  # Performance Analyst behavior spec
```

---

## Roadmap

### v1 — Current (multi-agent study assistant)
- [x] 6 specialized agents coordinated by an orchestrator
- [x] 3-layer web search (didactic, news, academic)
- [x] Real ENEM question bank (2021–2023) with difficulty classification
- [x] 3 progressive hints before answer release
- [x] Session performance tracking and end-of-session report
- [x] Dark/Neon Streamlit UI with topic suggestion bubbles
- [x] Gemini 2.5 Flash-Lite as primary LLM with Groq fallback
- [x] Foreign language mode (English / Spanish ENEM questions)
- [x] Deployed on Streamlit Cloud

### v2 — In progress (Supabase + dbt + advanced architecture)
- [x] Supabase PostgreSQL as persistent data layer (replaces local storage)
- [x] dbt Cloud pipeline — staging models + marts for student performance analytics
- [ ] Long-term weak-points map — track evolution across sessions
- [ ] Adaptive study plan generated by a new planner agent
- [ ] Conditional orchestration — pipeline adapts dynamically by topic type
- [ ] Dedicated `language_specialist` subagent for English/Spanish ENEM
- [ ] RAG over INEP PDFs with embeddings
- [ ] Session report delivered by e-mail via SendGrid
- [ ] ENEM essay (*redação*) grading agent with competency rubric
- [ ] PWA support — works as a mobile app

> **Development practices:** starting from v2, this project follows a formal
> [Development Best Practices Agreement](https://www.linkedin.com/in/silas-bom-fim) (authored by Silas Luiz Bom Fim)
> covering agent lifecycle (Plan → Act → Evaluate), branch governance, secrets management,
> traceability and human accountability. Implemented from v2 onwards.

---

## Author

**Silas Luiz Bom Fim** — Data Engineer · ML & AI Developer · Python | PL/SQL | LLM | UFABC

[![LinkedIn](https://img.shields.io/badge/LinkedIn-silas--bom--fim-blue?logo=linkedin)](https://www.linkedin.com/in/silas-bom-fim)
[![GitHub](https://img.shields.io/badge/GitHub-silasluiz96--alt-black?logo=github)](https://github.com/silasluiz96-alt)
[![MDPI](https://img.shields.io/badge/MDPI_Logistics-2025-orange?logo=academia)](https://doi.org/10.3390/logistics9030109)

📄 **Published researcher** — *Machine Failure Prediction using ML for Predictive Maintenance*,
Logistics, Vol. 9, Issue 3, Art. 109 · MDPI · 2025 · Open Access
→ [doi.org/10.3390/logistics9030109](https://doi.org/10.3390/logistics9030109)

---

<div align="center">
  Built with Generative AI for Brazilian high school students preparing for ENEM
</div>
