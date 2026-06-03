# CLAUDE.md — KnowSynth Project Briefing

> Leia este arquivo no início de cada sessão para retomar o contexto completo do projeto.

---

## 🎯 Objetivo do Projeto

O **KnowSynth** é um sistema multi-agente de IA generativa que transforma qualquer tema ou palavra-chave do ENEM em material de estudo completo e personalizado.

O estudante digita um tema (ex: "fordismo", "fotossíntese", "Revolução Industrial") e o sistema:
1. Pesquisa conteúdo em fontes didáticas, jornalísticas e acadêmicas
2. Analisa criticamente o tema sob a ótica do ENEM
3. Gera material de estudo original com questão estilo ENEM
4. Guia o estudante com 3 dicas progressivas antes de liberar o gabarito
5. Acompanha o desempenho da sessão e recomenda prioridades

**Público-alvo:** Estudantes do ensino médio se preparando para o ENEM.
**Princípio pedagógico:** Ensinar a pensar, não a memorizar. O estudante deve raciocinar antes de ver o gabarito.

---

## 🛠️ Stack Técnica

| Camada | Tecnologia | Uso |
|---|---|---|
| Interface | Streamlit | App web responsivo |
| LLM Provider | Groq API | Inferência rápida e gratuita |
| Modelo LLM | `llama-3.3-70b-versatile` | Todos os agentes que usam IA generativa |
| Busca Web | Tavily API | 3 camadas: didático, notícias, acadêmico |
| Runtime | Python 3.14 | Linguagem principal |
| Env vars | python-dotenv | Carregamento do `.env` |
| Versionamento | Git + GitHub | Repositório: silasluiz96-alt/KnowSynth |

**Variáveis de ambiente necessárias (`.env`):**
```
GROQ_API_KEY=...
TAVILY_API_KEY=...
```

**Como rodar:**
```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

---

## 🤖 Os 5 Agentes

### 1. 🔍 Pesquisador (`agents/researcher.py`)
- **Provider:** Tavily API
- **Input:** tema ou palavra-chave do usuário
- **Função:** Detecta automaticamente se é tema amplo ou palavra-chave específica e executa 3 camadas de busca
- **Camada 1 — Didático:** Brasil Escola, Khan Academy, MEC, Mundo Educação
- **Camada 2 — Notícias:** G1, BBC Brasil, Agência Brasil, El País, Nexo Jornal
- **Camada 3 — Acadêmico:** Google Scholar, SciELO
- **Output:** `{tema, tipo_busca, conteudo_didatico, noticias_relevantes, referencias_academicas, resumo, termos_relacionados, lacunas_e_aprofundamento}`

### 2. 🧠 Crítico (`agents/critic.py`)
- **Provider:** Groq (llama-3.3-70b-versatile)
- **Input:** output do Pesquisador
- **Função:** Analisa o conteúdo sob a ótica estratégica do ENEM
- **Output:** `{frequencia_enem, erros_comuns, conexoes_interdisciplinares, pontos_criticos, contexto_atual, nivel_prioridade}`

### 3. 📝 Sintetizador (`agents/synthesizer.py`)
- **Provider:** Groq (llama-3.3-70b-versatile)
- **Input:** outputs do Pesquisador + Crítico + snapshot do Analista
- **Função:** Gera material de estudo completo e original
- **Output:** `{introducao, pontos_essenciais, conexoes_interdisciplinares, questao_enem, questao_completa, analise_palavras_chave, dicas_de_prova, leituras_recomendadas}`
- **Importante:** `questao_enem` = versão sem gabarito (para o estudante). `questao_completa` = versão com gabarito interno (para o Estrategista)

### 4. 💡 Estrategista (`agents/strategist.py`)
- **Provider:** Groq (llama-3.3-70b-versatile)
- **Input:** questão gerada pelo Sintetizador + nível de dica solicitado
- **Função:** Sistema de 3 dicas progressivas — gabarito só liberado após dica 3
- **Dica 1:** Leitura estratégica do enunciado (sem mencionar alternativas)
- **Dica 2:** Técnica de eliminação (sem revelar a correta)
- **Dica 3:** Análise de pegadinhas (estudante deve chegar à resposta)
- **Implementação:** Classe `Strategist` com rastreamento de dicas por questão via `_dicas_entregues`

### 5. 📊 Analista de Desempenho (`agents/performance_analyst.py`)
- **Provider:** Groq (llama-3.3-70b-versatile)
- **Input:** eventos da sessão (pesquisas, dicas, gabaritos)
- **Função:** Rastreia comportamento e gera relatório ao final da sessão
- **Métodos:** `register_search()`, `register_hint()`, `register_gabarito()`, `generate_report()`, `snapshot()`
- **v1:** Memória limitada à sessão atual. **v2:** Supabase para memória permanente.

### Orquestrador (`agents/orchestrator.py`)
- **Classe:** `KnowSynth`
- **Função:** Coordena o pipeline Pesquisador → Crítico → Sintetizador → Analista
- **Estrategista:** Ativado sob demanda via `request_hint()` e `request_gabarito()`
- **Instância única:** `PerformanceAnalyst` e `Strategist` persistem durante toda a sessão

---

## 📁 Skills Criadas em `.claude/skills/`

| Arquivo | Agente | Conteúdo-chave |
|---|---|---|
| `researcher.md` | Pesquisador | 3 camadas de busca, gestão de lacunas, output estruturado |
| `critic.md` | Crítico | Análise estratégica ENEM, nível de prioridade, tom direto |
| `synthesizer.md` | Sintetizador | 7 seções do material, gabarito só via Estrategista |
| `strategist.md` | Estrategista | Sistema de 3 dicas, técnicas por área, gabarito comentado |
| `performance_analyst.md` | Analista | Rastreamento de sessão, relatório, preview v2 Supabase |

---

## ✅ O Que Já Foi Implementado

- [x] Estrutura completa de arquivos e pastas
- [x] 5 agentes funcionais com skills em Markdown
- [x] Orquestrador coordenando o pipeline completo
- [x] Interface Streamlit com abas, feedback visual e barra de progresso
- [x] Detecção automática de tipo de input (tema amplo vs palavra-chave)
- [x] 3 camadas de busca no Pesquisador
- [x] Análise crítica estruturada em JSON pelo Crítico
- [x] Material completo com questão ENEM original pelo Sintetizador
- [x] Sistema de 3 dicas progressivas com bloqueio do gabarito
- [x] Rastreamento de desempenho na sessão com relatório
- [x] Histórico de temas na sidebar com contador de dicas
- [x] Preview da v2 com Supabase na sidebar
- [x] `.gitignore` configurado (`.env` não commitado)
- [x] README.md profissional com arquitetura e roadmap
- [x] Repositório no GitHub: `silasluiz96-alt/KnowSynth`
- [x] KnowSynth adicionado ao README do perfil GitHub

---

## 🔜 Próximos Passos Planejados

### Curto prazo (v1 — melhorias)
- [ ] Tratar erros de JSON inválido do Groq com retry automático
- [ ] Adicionar `__init__.py` na pasta `agents/` para imports mais limpos
- [ ] Testar o app completo com tema real e verificar fluxo ponta a ponta
- [ ] Adicionar campo de área do conhecimento no input do usuário

### Médio prazo (v2 — Supabase)
- [ ] Autenticação com Google via Supabase Auth
- [ ] Salvar histórico de sessões no banco de dados
- [ ] Mapa de pontos fracos persistente por estudante
- [ ] Dashboard de evolução semanal/mensal
- [ ] Plano de estudos adaptativo gerado por agente planejador

### Longo prazo (v3)
- [ ] Integração com banco de questões reais do ENEM (enem.dev API)
- [ ] PWA para funcionar como app no celular
- [ ] Exportar material em PDF
- [ ] API pública para integração com outras plataformas

---

## 🧠 Decisões Técnicas Importantes

### Groq em vez de Anthropic/OpenAI
**Motivo:** Groq oferece inferência gratuita e extremamente rápida via API. O modelo `llama-3.3-70b-versatile` é poderoso o suficiente para as tarefas do pipeline (análise crítica, síntese, dicas). Evita custos no desenvolvimento e testes iniciais.
**Impacto:** Todos os agentes que usam LLM chamam `Groq(api_key=os.getenv("GROQ_API_KEY"))` com `model="llama-3.3-70b-versatile"`.

### Tavily para busca web
**Motivo:** API de busca semântica com plano gratuito generoso, retorna conteúdo já extraído (não apenas URLs). Ideal para as 3 camadas de busca do Pesquisador.
**Impacto:** `TAVILY_API_KEY` necessária no `.env`.

### Skills em Markdown (`.claude/skills/`)
**Motivo:** Separar o comportamento dos agentes do código Python. Permite ajustar a persona, regras e outputs dos agentes sem alterar o código — só editar o `.md` correspondente.
**Impacto:** Cada agente carrega sua skill no `__init__` ou na função principal via `SKILL_PATH.read_text()`.

### Gabarito bloqueado pelo Estrategista
**Motivo:** Princípio pedagógico central do projeto — o estudante deve tentar resolver antes de ver a resposta. O Sintetizador gera `gabarito_interno` no JSON, mas o `app.py` só exibe após 3 dicas entregues pelo Estrategista.
**Impacto:** `questao_enem` (sem gabarito) vs `questao_completa` (com gabarito) são campos separados no retorno do Sintetizador.

### enem.dev para questões reais (v3)
**Decisão futura:** Integrar o banco de questões reais do ENEM via [enem.dev](https://enem.dev) para que o Estrategista trabalhe com questões históricas além das geradas pela IA.

### Supabase para memória persistente (v2)
**Decisão futura:** O `PerformanceAnalyst` foi projetado desde o início para ter memória de sessão apenas na v1. Na v2, cada evento (`register_search`, `register_hint`, `register_gabarito`) será persistido no Supabase, permitindo acompanhamento longitudinal do estudante.

---

## 📌 Padrões de Código

- Todos os agentes retornam dicionários — nunca levantam exceções para o pipeline
- Erros são capturados e retornados em `{"erro": "mensagem"}` sem quebrar o fluxo
- Respostas JSON do Groq têm tratamento de `json.JSONDecodeError` + remoção de blocos markdown (` ```json `)
- `python-dotenv` com `load_dotenv()` no topo de cada agente que usa API key
- Instâncias com estado (`Strategist`, `PerformanceAnalyst`) são criadas uma vez no `KnowSynth.__init__()` e reutilizadas

---

## 🗂️ Repositórios Relacionados

- **KnowSynth:** https://github.com/silasluiz96-alt/KnowSynth
- **Perfil GitHub:** https://github.com/silasluiz96-alt

---

## Sessão 2 — 03/06/2026

### Mudanças de identidade
- Projeto renomeado de EduSynth para KnowSynth
- Logo: KS como marca d'água no fundo da interface
- Lema: "Synthesizing knowledge, powering learning"
- Repositório: https://github.com/silasluiz96-alt/KnowSynth
- Pasta local: C:\Users\silas\OneDrive\Desktop\knowsynth

### Novos agentes adicionados
- agents/enem_api.py — integração com enem.dev API, paginação automática, expansão de termos de busca
- agents/complexity_ranker.py — classificação de questões em fácil/médio/difícil via LLM
- .claude/hooks/hooks.py — hooks pre/post/error implementados

### Correções aplicadas
- JSON parsing corrigido com parse_groq_response() em todos os agentes
- enem.dev API corrigida: formato de alternativas, paginação, fallback
- Modelo atualizado de mixtral-8x7b-32768 para llama-3.3-70b-versatile
- Marca d'água KS via HTML injetado (body::before não funciona no Streamlit)

### Stack atual
- Python + Groq (llama-3.3-70b-versatile) + Tavily + Streamlit
- enem.dev API para questões reais
- 6 agentes + hooks + 5 skills

### Próximos passos
- Deploy no Streamlit Cloud
- Sub-agents nativos do Claude Code
- MCP configurado
- Supabase + pgvector para v2 (redação ENEM)

---

## Sessão 3 — 03/06/2026 (noite)

### Estado atual do projeto
- Nome: KnowSynth (antes EduSynth)
- Deploy: https://knowsynth.streamlit.app/ (funcionando)
- Repositório: https://github.com/silasluiz96-alt/KnowSynth
- Pasta local: C:\Users\silas\OneDrive\Desktop\knowsynth

### Stack atual
- LLM Principal: Google Gemini 2.5 Flash (google-genai 2.7.0)
- LLM Fallback: Groq llama-3.3-70b-versatile
- Busca web: Tavily API
- Questões reais: enem.dev API (restrito a 2019-2023)
- Interface: Streamlit
- Cliente LLM centralizado: utils/llm_client.py com chamar_llm()

### Arquitetura de agentes
- agents/researcher.py — Tavily, 3 camadas de busca
- agents/enem_api.py — questões reais ENEM 2019-2023
- agents/complexity_ranker.py — classifica fácil/médio/difícil
- agents/critic.py — análise crítica Professor
- agents/synthesizer.py — material pedagógico completo
- agents/strategist.py — 3 dicas progressivas
- agents/performance_analyst.py — relatório de sessão
- agents/orchestrator.py — coordena todos os agentes
- .claude/hooks/hooks.py — pre/post/error hooks

### Problemas conhecidos
- Gemini gratuito tem limite de 20 req/min — fallback para Groq funciona
- enem.dev API às vezes retorna 429 com muitas requisições simultâneas
- Material de estudo às vezes aparece vazio — JSON parsing intermitente
- Questões em espanhol/inglês filtradas mas podem escapar

### Próximos passos
- Testar fluxo completo end-to-end com Gemini + Groq
- Corrigir erro "sequence item 0: expected str instance, NoneType found" no enem_api.py
- Badge de deploy no README
- Continuar commits do roadmap
- v2: Supabase + RAG com PDFs do INEP + redação ENEM

### Chaves configuradas
- GEMINI_API_KEY: configurada no .env e Streamlit Secrets
- GROQ_API_KEY: configurada no .env e Streamlit Secrets
- TAVILY_API_KEY: configurada no .env e Streamlit Secrets

