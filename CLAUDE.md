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
| LLM Principal | Gemini 2.5 Flash-Lite | Todos os agentes que usam IA generativa |
| LLM Fallback | Groq `llama-3.3-70b-versatile` | Fallback automático quando Gemini falha |
| Busca Web | Tavily API | 3 camadas: didático, notícias, acadêmico |
| Questões reais | enem.dev API | Banco ENEM 2021–2023 |
| Persistência | DuckDB (local) | Sessões e chamadas de agentes gravadas por sessão |
| Transformação | dbt-duckdb | Modelos staging e marts sobre os dados brutos (em implementação) |
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
- **v1:** Memória de sessão gravada localmente no DuckDB via `utils/analytics_db.py`. Dados acumulados entre sessões na aba Analytics.

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
| `performance_analyst.md` | Analista | Rastreamento de sessão, relatório, sugestões para próxima sessão |

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
- [x] Analytics de sessões com DuckDB — aba dedicada com histórico acumulado
- [x] Card de próximas funcionalidades na sidebar (e-mail, dbt, mapa de pontos fracos)
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

### Médio prazo (v2 — dados e comunicação)
- [ ] Modelos dbt: staging e marts sobre raw_sessions e raw_agent_calls
- [ ] Envio do relatório de sessão por e-mail via SendGrid (opcional, solicitado ao encerrar)
- [ ] Mapa de pontos fracos persistente — evolução entre sessões
- [ ] Dashboard de evolução com visualizações (tempo médio, fallback rate, temas revisitados)
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

### DuckDB + dbt para persistência e análise (v1.5)
**Decisão:** Persistência implementada com DuckDB local — sem servidor, sem conta externa, zero custo. `utils/analytics_db.py` grava `raw_sessions` e `raw_agent_calls` ao encerrar cada sessão. O dbt (`dbt-duckdb`) transforma esses dados brutos em modelos staging e marts para consumo analítico. Separação clara: `requirements.txt` (runtime, só `duckdb`) vs `requirements-dev.txt` (dbt como ferramenta de desenvolvedor).

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

---

## Sessão 4 — 04/06/2026

### Estado atual
- Deploy funcionando: https://knowsynth.streamlit.app/
- Repositório: https://github.com/silasluiz96-alt/KnowSynth
- Pasta local: C:\Users\silas\OneDrive\Desktop\knowsynth

### Melhorias implementadas nessa sessão
- Ranqueador de complexidade refatorado para heurística local (zero chamadas LLM)
- ENEM API limitada a 2 anos (2022-2023) e 10 questões máximo
- LLM adicionado para seleção semântica de questões relevantes
- Modelo trocado para gemini-2.5-flash-lite (1000 RPD no free tier)
- Fallback: Groq llama-3.3-70b-versatile
- 15 temas principais definidos nos balões de sugestão
- Rotação dos balões reduzida para 10 minutos

### Problemas pendentes
- parse_resposta_json no Sintetizador retorna fallback — material didático aparece vazio
- Questões da enem.dev às vezes irrelevantes para o tema (seleção LLM melhorada mas ainda imprecisa)
- Correção pendente: synthesizer.py deve instruir LLM a retornar JSON puro sem markdown
- Correção pendente: parse_resposta_json deve tentar extrair campos via regex como fallback

### 15 temas principais definidos
Humanas: Revolução Industrial, Segunda Guerra Mundial, Ditadura Militar Brasileira, Globalização
Natureza: Aquecimento Global, Fotossíntese, Genética Mendeliana, Leis de Newton
Matemática: Funções do 1º e 2º Grau, Progressão Aritmética, Probabilidade, Geometria Plana
Linguagens: Modernismo Brasileiro, Interpretação de Texto, Figuras de Linguagem

### Próxima sessão — prioridades
1. Corrigir JSON do Sintetizador (material didático vazio)
2. Testar fluxo completo end-to-end
3. Commit e push das correções pendentes
4. Continuar roadmap de melhorias

---

## Sessão 6 — 04/06/2026

### Diagnóstico e correções aplicadas
- synthesizer.py: `desempenho_txt` agora é incluído no prompt (era calculado mas nunca enviado ao LLM)
- app.py: removido `register_hint` chamado ao acertar — métricas de desempenho não são mais distorcidas
- enem_api.py: importação de `Groq` adicionada com `try/except`; `_termos_busca` (função morta com NameError latente) removida
- enem_api.py: `get_questions_by_difficulty` agora verifica `Groq is None` antes de instanciar
- strategist.py: `_formatar_questao` agora lê `contexto` (questões reais) ou `texto_apoio` (questões IA) — Estrategista recebia contexto vazio para questões da enem.dev
- llm_client.py: ordem restaurada para Gemini → Groq (alinhada com CLAUDE.md; código estava invertido desde testes)

### Estado atual
- Deploy: https://knowsynth.streamlit.app/
- Repositório: https://github.com/silasluiz96-alt/KnowSynth
- Pasta local: C:\Users\silas\OneDrive\Desktop\knowsynth

### Próxima sessão — prioridades
1. Testar fluxo completo end-to-end com as correções
2. Commit e push das correções
3. Continuar roadmap de melhorias

---

## Sessão 5 — 04/06/2026 (tarde)

### Estado atual
- Deploy: https://knowsynth.streamlit.app/
- Repositório: https://github.com/silasluiz96-alt/KnowSynth
- Pasta local: C:\Users\silas\OneDrive\Desktop\knowsynth

### Descobertas críticas sobre a enem.dev API
- Campo "language" existe e é confiável para filtrar inglês/espanhol
- Filtros via query parameter (?discipline=, ?search=) são ignorados silenciosamente
- Questões vêm em blocos sequenciais por disciplina:
  linguagens=offset 0, humanas=offset 43, natureza=offset 90, matematica=offset 135
- Banco total: 2009-2023, ~183-185 questões por ano
- Estrutura real: {"metadata": {...}, "questions": [...]}

### Arquitetura atual da busca ENEM
- TEMA_DISCIPLINA: mapa dos 15 temas para suas disciplinas
- TEMA_KEYWORDS: keywords ampliadas por tema (implementado nessa sessão)
- Offset inicial por disciplina para evitar varredura desnecessária
- Anos: 2021, 2022, 2023
- Zero chamadas LLM na seleção — filtro local por keyword
- Heurística local para classificação fácil/médio/difícil (zero LLM)

### LLM atual
- Principal: Gemini 2.5 Flash-Lite (20 req/dia free tier — esgota rápido em testes)
- Fallback: Groq llama-3.3-70b-versatile (100k tokens/dia)
- Gemini permanece como principal — não alterar essa ordem

### Problemas pendentes
- Fotossíntese encontrou apenas 1 questão em 3 anos — keywords ampliadas devem resolver
- search_language_questions para inglês retorna 0 questões — campo language pode ter valor diferente
- Questões de idioma (inglês/espanhol) usam campo language da API diretamente
- Botões en-Inglês e es-Espanhol implementados e centralizados na interface

### Próxima sessão — prioridades
1. Testar busca com keywords ampliadas para Fotossíntese e outros temas
2. Investigar campo language para questões de inglês (debug já feito para espanhol)
3. Testar fluxo completo end-to-end no Streamlit Cloud
4. Continuar roadmap de melhorias

---

## V2 — ROADMAP E DECISÕES TÉCNICAS

### Stack de dados v2
- Banco: Supabase (PostgreSQL hosted)
- Transformação: dbt Core (roda localmente, conecta no Supabase)
- Ingestão: Python (supabase-py ou psycopg2) inserindo dados de sessão no Supabase
- Consumo: Streamlit lê tabelas marts/ já transformadas pelo dbt

### Arquitetura do fluxo
1. Aluno usa o app → Python insere respostas brutas no Supabase (tabelas raw)
2. Desenvolvedor roda `dbt run` localmente → dbt transforma raw em marts
3. Streamlit lê os marts → exibe mapa de pontos fracos, histórico, desempenho por tema

### Decisões tomadas
- Supabase escolhido como banco (free tier, PostgreSQL completo, dashboard visual)
- dbt NÃO roda dentro do Streamlit — é ferramenta de desenvolvimento externa
- DuckDB DESCONTINUADO (incompatível com Streamlit Cloud)
- Supabase-py OU psycopg2 para conexão Python → Supabase (a definir)
- dbt Cloud como opção futura quando o fluxo local estiver dominado

### Features v2 planejadas
- Persistência de sessões entre acessos
- Mapa de pontos fracos por tema e disciplina
- Plano de estudo adaptativo baseado no histórico
- RAG sobre PDFs do INEP
- Módulo de redação ENEM

### Status
- v2 em fase de aprendizado (Supabase via NoCodeStartup + dbt fundamentals)
- Modelo de dados ainda não mapeado — próxima etapa
- Nenhum código v2 implementado ainda

---

## V2 — ROADMAP DETALHADO

### Status do v1
- Imagens ENEM: ✅ corrigido (markdown `![](url)` convertido para `<img>` HTML)
- JSON Synthesizer: ✅ estabilizado (`_serializar_critica` defensiva + `parse_resposta_json` com fallback regex)
- Busca ENEM por tema: ✅ corrigido (normalização de acentos, 30+ temas mapeados, retry em 429, anos 2019–2023)
- Detecção de inglês/espanhol: ✅ corrigido (regex SVO estrutural substitui contagem de palavras)
- Analytics de sessão: ✅ implementado com DuckDB local (`utils/analytics_db.py` + aba Analytics no app)
- DuckDB no código: ⚠️ ainda ativo em `app.py` e `utils/analytics_db.py` — descontinuado nos docs mas migração para Supabase ainda não foi feita; remover ao implementar Fase 1
- Conditional orchestration: 🔜 pendente para v2
- Subagente língua estrangeira (`language_specialist.py`): 🔜 pendente para v2
- v1 considerado FECHADO para novas features

### Fase 1 — Infraestrutura de dados
- Criar projeto no Supabase (free tier)
- Conectar dbt Cloud ao Supabase
- Definir e criar tabelas raw no Supabase:
  - `sessoes` (id, aluno_nome, inicio, fim, tema, disciplina)
  - `respostas` (id, sessao_id, questao_id, alternativa_escolhida, acertou, dicas_usadas, tempo_resposta)
  - `questoes_cache` (id, questao_id, tema, disciplina, dificuldade, tem_imagem)
- Python do app (supabase-py) inserindo dados ao final de cada sessão
- Remover `utils/analytics_db.py` e referências ao DuckDB no `app.py`

### Fase 2 — Pipeline dbt
- `sources.yml` apontando para tabelas raw do Supabase
- `stg_sessoes.sql` — limpeza e padronização
- `stg_respostas.sql` — limpeza e padronização
- `fct_desempenho_aluno.sql` — acertos por tema, disciplina, dificuldade
- `fct_pontos_fracos.sql` — temas com menor taxa de acerto por aluno
- `dim_questoes.sql` — catálogo de questões com metadados
- Tests: `not_null` e `unique` em todos os ids
- Documentação de todos os models no `schema.yml`

### Fase 3 — Features do app
- Tela de histórico: aluno insere nome e vê sessões anteriores
- Mapa de pontos fracos: gráfico por tema baseado nos marts dbt
- Plano adaptativo: Strategist usa histórico para priorizar temas fracos

### Fase 4 — Arquitetura avançada
- Conditional orchestration: orquestrador decide pipeline por tipo de tema
- Subagente `language_specialist.py` para inglês/espanhol
- RAG sobre PDFs do INEP com embeddings

### Stack v2
- Banco: Supabase PostgreSQL (free tier)
- Transformação: dbt Cloud (Developer plan, gratuito)
- Conexão Python: supabase-py
- Orquestrador: condicional por tipo de tema (v2)

### Dependências entre fases
- Fase 2 depende da Fase 1 estar completa
- Fase 3 depende dos marts da Fase 2
- Fase 4 é independente — pode ser desenvolvida em paralelo
