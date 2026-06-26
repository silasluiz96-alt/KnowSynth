[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://knowsynth.streamlit.app/)
![Python](https://img.shields.io/badge/Python-3.14-blue)
![Gemini](https://img.shields.io/badge/Gemini-2.5_Flash_Lite-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

# KnowSynth

> *Synthesizing knowledge, powering learning.*

KnowSynth é um sistema multi-agente de IA generativa com 7 agentes especializados que colaboram em tempo real para criar materiais de estudo personalizados para o ENEM.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                       Entrada do Usuário                        │
│              (tema ou palavra-chave — ex: "fordismo")           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       ORQUESTRADOR                              │
│               orchestrator.py — classe KnowSynth                │
│         Coordena o pipeline completo com hooks                  │
└───┬──────────────┬────────────────────────┬──────────────────┬──┘
    │              │                        │                  │
    ▼              ▼                        ▼                  ▼
┌────────┐   ┌──────────┐           ┌────────────┐   ┌──────────────┐
│  🔍    │   │  📚      │           │  🧠        │   │  📝          │
│Pesqui- │   │ ENEM API │           │  Crítico   │   │ Sintetizador │
│sador   │   │          │           │            │   │              │
│Tavily  │   │enem.dev  │           │Gemini /    │   │Gemini /      │
│3 cama- │   │2021–2023 │           │Groq        │   │Groq          │
│das     │   │questões  │           │            │   │              │
└───┬────┘   └────┬─────┘           └─────┬──────┘   └──────┬───────┘
    │             │                       │                  │
    │             ▼                       │                  │
    │      ┌────────────┐                 │                  │
    │      │  🏆        │                 │                  │
    │      │ Ranqueador │                 │                  │
    │      │ Complexid. │                 │                  │
    │      │(heurística)│                 │                  │
    │      └────┬───────┘                 │                  │
    │           │                         │                  │
    └─────┬─────┘                         │                  │
          │          ┌────────────────────┘                  │
          │          │          ┌────────────────────────────┘
          │          │          │
          ▼          ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Interface Streamlit                         │
│  Abas de material · Fila de questões (fácil→médio→difícil)      │
│  Dicas progressivas · Analytics de sessão · UI Dark/Neon        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
      ┌──────────────────┐          ┌──────────────────────┐
      │  💡 Estrategista │          │  📊 Analista de      │
      │                  │          │     Desempenho       │
      │ 3 dicas          │          │                      │
      │ progressivas     │          │ Rastreia dificuldade,│
      │ antes do         │          │ dicas e tempo de     │
      │ gabarito         │          │ sessão               │
      └──────────────────┘          └──────────────────────┘
```

---

## Agentes

| Agente | Arquivo | Tecnologia | Função |
|---|---|---|---|
| 🔍 **Pesquisador** | `agents/researcher.py` | Tavily API | Busca semântica em 3 camadas: fontes didáticas, notícias, referências acadêmicas |
| 📚 **ENEM API** | `agents/enem_api.py` | enem.dev API | Busca questões reais do ENEM (2021–2023) filtradas por tema e disciplina |
| 🏆 **Ranqueador de Complexidade** | `agents/complexity_ranker.py` | Heurística local | Classifica questões em fácil / médio / difícil sem nenhuma chamada a LLM |
| 🧠 **Crítico** | `agents/critic.py` | Gemini 2.5 Flash-Lite / Groq | Análise estratégica: frequência no ENEM, erros comuns, conexões interdisciplinares |
| 📝 **Sintetizador** | `agents/synthesizer.py` | Gemini 2.5 Flash-Lite / Groq | Gera o material de estudo completo: introdução, pontos-chave e questão estilo ENEM |
| 💡 **Estrategista** | `agents/strategist.py` | Gemini 2.5 Flash-Lite / Groq | Entrega 3 dicas progressivas; gabarito liberado apenas após a dica 3 |
| 📊 **Analista de Desempenho** | `agents/performance_analyst.py` | Gemini 2.5 Flash-Lite / Groq | Rastreia o comportamento da sessão e gera relatório personalizado ao final |

> O Orquestrador (`agents/orchestrator.py`) coordena o pipeline completo e expõe `estudar()`, `request_hint()`, `request_gabarito()` e `relatorio_sessao()`.

---

## Stack Tecnológica

| Tecnologia | Versão | Finalidade |
|---|---|---|
| Python | 3.14 | Runtime |
| Streamlit | latest | Interface web |
| Google Gemini | 2.5 Flash-Lite | LLM principal (plano gratuito) |
| Groq — LLaMA 3.3 70B | `llama-3.3-70b-versatile` | LLM fallback |
| OpenAI — GPT-4o Mini | `gpt-4o-mini` | LLM fallback de último recurso |
| Supabase | PostgreSQL | Camada de persistência (sessões, respostas, questões) |
| dbt Cloud | latest | Pipeline de transformação analytics |
| Tavily | latest | Busca semântica na web |
| enem.dev API | v1 | Banco de questões reais do ENEM (2009–2023) |
| python-dotenv | latest | Gerenciamento de variáveis de ambiente |
| google-genai | 2.7.0 | SDK do Gemini |

---

## Como Funciona

**1. Pesquisa** — O Pesquisador aciona o Tavily em 3 camadas: sites didáticos (Brasil Escola, Khan Academy), notícias recentes (G1, BBC Brasil) e fontes acadêmicas (SciELO, Google Scholar).

**2. Análise Crítica** — O Crítico avalia com que frequência o tema aparece no ENEM, os erros mais comuns dos alunos e quais conexões interdisciplinares têm maior chance de cair.

**3. Síntese** — O Sintetizador combina pesquisa + crítica + desempenho atual da sessão para gerar um material de estudo completo: introdução, conceitos-chave, conexões interdisciplinares, uma questão original estilo ENEM e dicas de prova.

**4. Questões Reais** — A ENEM API busca questões oficiais de 2021–2023. O Ranqueador as classifica localmente em fácil / médio / difícil sem chamadas à API. O aluno percorre a fila em dificuldade crescente.

**5. Dicas Progressivas** — Cada resposta errada libera uma dica do Estrategista. O gabarito comentado só é liberado após 3 dicas (ou quando o aluno acerta). O Analista de Desempenho registra tudo e produz um relatório personalizado ao final da sessão.

---

## Como Usar

### Pré-requisitos

- Python 3.11+
- Conta gratuita no [Groq](https://console.groq.com) → `GROQ_API_KEY`
- Conta gratuita no [Tavily](https://tavily.com) → `TAVILY_API_KEY`
- Conta gratuita no [Google AI Studio](https://aistudio.google.com) → `GEMINI_API_KEY`
- Conta na [OpenAI](https://platform.openai.com) → `OPENAI_API_KEY` *(opcional — fallback de último recurso)*
- Projeto no [Supabase](https://supabase.com) → `SUPABASE_URL` + `SUPABASE_KEY`

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/silasluiz96-alt/KnowSynth.git
cd KnowSynth

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Configure as variáveis de ambiente
# Crie um arquivo .env na raiz do projeto:
GEMINI_API_KEY=sua_chave_gemini
GROQ_API_KEY=sua_chave_groq
TAVILY_API_KEY=sua_chave_tavily
OPENAI_API_KEY=sua_chave_openai
SUPABASE_URL=sua_url_supabase
SUPABASE_KEY=sua_chave_supabase
```

### Rodando Localmente

```bash
python -m streamlit run app.py
```

Abra [http://localhost:8501](http://localhost:8501) no navegador.

### Deploy no Streamlit Cloud

1. Faça um fork deste repositório
2. Acesse [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Selecione seu fork, branch `main`, arquivo `app.py`
4. Em **Advanced settings → Secrets**, adicione:
```toml
GEMINI_API_KEY = "sua_chave"
GROQ_API_KEY   = "sua_chave"
TAVILY_API_KEY = "sua_chave"
OPENAI_API_KEY = "sua_chave"
SUPABASE_URL   = "sua_url"
SUPABASE_KEY   = "sua_chave"
```
5. Clique em **Deploy** — o app estará no ar em ~2 minutos

---

## Estrutura do Projeto

```
knowsynth/
├── app.py                          # Interface Streamlit (app de página única)
├── requirements.txt
├── .env                            # Não commitado — chaves de API locais
├── .gitignore
│
├── agents/
│   ├── orchestrator.py             # Coordenador do pipeline — classe KnowSynth
│   ├── researcher.py               # Agente Pesquisador (Tavily)
│   ├── enem_api.py                 # Agente ENEM API (enem.dev)
│   ├── complexity_ranker.py        # Classificador de dificuldade (heurística local)
│   ├── critic.py                   # Agente Crítico (Gemini / Groq)
│   ├── synthesizer.py              # Agente Sintetizador (Gemini / Groq)
│   ├── strategist.py               # Agente Estrategista (Gemini / Groq)
│   └── performance_analyst.py      # Agente Analista de Desempenho (Gemini / Groq)
│
├── utils/
│   ├── __init__.py
│   ├── llm_client.py               # Cliente LLM centralizado (Gemini → Groq → OpenAI)
│   └── supabase_db.py              # Camada de persistência Supabase (sessões, respostas, cache)
│
└── .claude/
    ├── hooks/
    │   └── hooks.py                # Hooks de observabilidade (pré/pós/erro)
    └── skills/
        ├── researcher.md           # Spec de comportamento do Pesquisador
        ├── critic.md               # Spec de comportamento do Crítico
        ├── synthesizer.md          # Spec de comportamento do Sintetizador
        ├── strategist.md           # Spec de comportamento do Estrategista
        └── performance_analyst.md  # Spec de comportamento do Analista de Desempenho
```

---

## Roadmap

### v1 — Concluída (assistente de estudos multi-agente)
- [x] 6 agentes especializados coordenados por um orquestrador
- [x] Busca em 3 camadas (didático, notícias, acadêmico)
- [x] Banco de questões reais do ENEM (2021–2023) com classificação de dificuldade
- [x] 3 dicas progressivas antes de liberar o gabarito
- [x] Rastreamento de desempenho da sessão e relatório final personalizado
- [x] UI Dark/Neon no Streamlit com bolhas de sugestão de temas
- [x] Gemini 2.5 Flash-Lite como LLM principal com fallback para Groq
- [x] Modo de língua estrangeira (questões de inglês / espanhol do ENEM)
- [x] Deploy no Streamlit Cloud

### v2 — Concluída (Supabase + dbt + arquitetura avançada)
- [x] Supabase PostgreSQL como camada de persistência (substitui armazenamento local)
- [x] Pipeline dbt Cloud — modelos staging + `mart_desempenho` (taxa de acerto por aluno, tema, disciplina)
- [x] Job agendado no dbt Cloud — `Daily - Run all models` (03:00 UTC)
- [x] Secrets do Supabase configurados no Streamlit Cloud (pronto para produção)
- [x] Mapa de Pontos Fracos — aba com desempenho consolidado por tema
- [x] PWA — suporte a "Adicionar à tela inicial" (Android e iOS)
- [x] Relatório de sessão entregue por e-mail via SendGrid
- [x] Supabase Auth — login real com e-mail e senha por `user_id` + LGPD provisória
- [~] ~~Plano de estudo adaptativo — novo agente Planejador~~ — promovido ao v3 com motor de ML
- [~] ~~Orquestração condicional — pipeline se adapta dinamicamente por tipo de tema~~ — valor marginal; reavaliado na v3
- [~] ~~RAG sobre PDFs do INEP~~ — promovido ao v3 com pgvector + embeddings

> Agente de redação — removido do roadmap atual; escopo separado, avaliado futuramente.

### v3 — Planejada (Personalização, RAG e Machine Learning)
- [ ] Memória persistente por aluno — histórico de sessões injetado no contexto do LLM via `user_id`
- [ ] RAG sobre PDFs do INEP — embeddings com pgvector no Supabase + busca semântica sobre documentos oficiais
- [ ] Feedback de sessão — avaliação pós-sessão (1–5 estrelas + texto livre) com análise de sentimento
- [ ] Feature Store no dbt — marts de ML com taxa de acerto, sequência temporal, padrões de dificuldade por aluno
- [ ] Motor de recomendação ML — mRMR para seleção de features + Árvore de Decisão para recomendar próximo tema e leituras de reforço
- [ ] Agente Planejador — plano de estudo personalizado gerado por IA com base no perfil ML do aluno
- [ ] UI mobile-first — layout 100% responsivo para uso exclusivo via celular
- [ ] LSTM para predição de desempenho — v3.x, após consolidação do histórico de usuários

> v3 cobre as tech skills: Generative AI & Agents, Text Analysis, Information Extraction, Machine Learning (mRMR + Árvore de Decisão + LSTM), Python e SQL/dbt avançado.

> **Boas práticas de desenvolvimento:** a partir da v2, este projeto segue um
> [Acordo Formal de Boas Práticas de Desenvolvimento](https://www.linkedin.com/in/silas-bom-fim)
> (autoria de Silas Luiz Bom Fim) cobrindo ciclo de vida de agentes (Planejar → Agir → Avaliar),
> governança de branches, gestão de secrets, rastreabilidade e responsabilidade humana.

---

## Decisões de Processo

Decisões registradas durante o desenvolvimento para fins de rastreabilidade.

| Data | Decisão | Motivo |
|---|---|---|
| Jun/2026 | `gpt-4o-mini` da OpenAI adicionado como fallback final de LLM | Chave de API pré-existente (crédito de $5 de um curso); encaixa na fase de persistência v2 sem compromisso de custo adicional |
| Jun/2026 | OpenAI e Supabase adicionados à Stack Tecnológica em meio à sessão | Ambas as ferramentas já estavam implementadas; atualização do README foi uma decisão deliberada para manter o projeto atualizado |
| Jun/2026 | Verificação pós-merge do `requirements.txt` adicionada à etapa Avaliar | Dependências foram removidas silenciosamente durante merges de branches; verificação explícita após cada merge previne regressão |
| Jun/2026 | `mart_desempenho` criado no dbt — consolida sessões e respostas por aluno, tema e disciplina | Primeira camada de analytics; habilita mapa de pontos fracos e plano de estudo adaptativo |
| Jun/2026 | Job agendado no dbt Cloud configurado (03:00 UTC, ambiente Production, dbt Latest) | Mantém o mart atualizado sem execuções manuais; dbt Fusion descartado — não suporta PostgreSQL |
| Jun/2026 | `SUPABASE_URL` e `SUPABASE_KEY` adicionados aos Secrets do Streamlit Cloud | Necessário para persistência em produção; anteriormente apenas o `.env` local tinha esses valores |

---

## Autor

**Silas Luiz Bom Fim** — Engenheiro de Dados · Desenvolvedor ML & IA · Python | PL/SQL | LLM | UFABC

[![LinkedIn](https://img.shields.io/badge/LinkedIn-silas--bom--fim-blue?logo=linkedin)](https://www.linkedin.com/in/silas-bom-fim)
[![GitHub](https://img.shields.io/badge/GitHub-silasluiz96--alt-black?logo=github)](https://github.com/silasluiz96-alt)

---

<div align="center">
  Construído com IA Generativa para estudantes brasileiros se preparando para o ENEM
</div>
