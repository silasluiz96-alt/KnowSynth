# CLAUDE.md — KnowSynth Project Briefing

> Leia este arquivo no início de cada sessão para retomar o contexto completo do projeto.

---

## Objetivo do Projeto

O **KnowSynth** é um sistema multi-agente de IA generativa que transforma qualquer tema do ENEM em material de estudo completo e personalizado.

O estudante digita um tema (ex: "fordismo", "fotossíntese") e o sistema:
1. Pesquisa conteúdo em fontes didáticas, jornalísticas e acadêmicas
2. Analisa criticamente o tema sob a ótica do ENEM
3. Gera material de estudo original com questão estilo ENEM
4. Guia o estudante com 3 dicas progressivas antes de liberar o gabarito
5. Busca questões reais do ENEM (2019–2023) classificadas por dificuldade
6. Acompanha o desempenho da sessão e persiste os dados no Supabase

**Público-alvo:** Estudantes do ensino médio se preparando para o ENEM.
**Princípio pedagógico:** Ensinar a pensar, não a memorizar.

---

## Stack Técnica

| Camada | Tecnologia | Uso |
|---|---|---|
| Interface | Streamlit | App web responsivo |
| LLM Principal | Gemini 2.5 Flash-Lite | Todos os agentes que usam IA generativa |
| LLM Fallback 1 | Groq `llama-3.3-70b-versatile` | Fallback automático quando Gemini falha |
| LLM Fallback 2 | OpenAI `gpt-4o-mini` | Último recurso — key com $5 de crédito |
| Busca Web | Tavily API | 3 camadas: didático, notícias, acadêmico |
| Questões reais | enem.dev API | Banco ENEM 2019–2023 |
| Persistência | Supabase (PostgreSQL) | Sessões, respostas e cache de questões |
| Transformação | dbt Cloud | Staging models conectados ao Supabase |
| Runtime | Python 3.14 | Linguagem principal |
| Env vars | python-dotenv | Carregamento do `.env` |
| Versionamento | Git + GitHub | `silasluiz96-alt/KnowSynth` |

**Variáveis de ambiente necessárias (`.env`):**
```
GEMINI_API_KEY=...
GROQ_API_KEY=...
TAVILY_API_KEY=...
OPENAI_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

**Como rodar:**
```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

---

## Os 7 Agentes

| Agente | Arquivo | Provider | Função |
|---|---|---|---|
| 🔍 Pesquisador | `agents/researcher.py` | Tavily API | 3 camadas de busca: didático, notícias, acadêmico |
| 📚 ENEM API | `agents/enem_api.py` | enem.dev | Questões reais 2019–2023 filtradas por tema |
| 🏆 Complexity Ranker | `agents/complexity_ranker.py` | Heurística local | Classifica questões em fácil/médio/difícil sem LLM |
| 🧠 Crítico | `agents/critic.py` | Gemini/Groq | Análise estratégica ENEM: frequência, erros, interdisciplinaridade |
| 📝 Sintetizador | `agents/synthesizer.py` | Gemini/Groq | Gera material completo + questão estilo ENEM |
| 💡 Estrategista | `agents/strategist.py` | Gemini/Groq | 3 dicas progressivas — gabarito só após dica 3 |
| 📊 Analista de Desempenho | `agents/performance_analyst.py` | Gemini/Groq | Rastreia sessão e gera relatório final |

**Orquestrador:** `agents/orchestrator.py` — classe `KnowSynth`, coordena o pipeline completo.

---

## Persistência — Supabase

**Arquivo:** `utils/supabase_db.py`

**Tabelas:**
- `sessoes` — id, aluno_nome, inicio, fim, tema, disciplina, meta_tempo
- `respostas` — id, sessao_id, questao_id, alternativa_escolhida, acertou, dicas_usadas
- `questoes_cache` — id, questao_id, titulo, ano, tema, disciplina, dificuldade

**Padrão de ingestão:** buffer de respostas acumulado durante a sessão → salvo em lote ao encerrar (TELA 2).

**RLS:** políticas permissivas para `anon` — fase pré-Auth.

---

## dbt Cloud

**Projeto:** KnowSynth
**Conexão:** Session Pooler — `aws-1-us-east-2.pooler.supabase.com:5432`
**Schema de desenvolvimento:** `dbt_knowsynth`
**Repositório conectado:** `silasluiz96-alt/KnowSynth` (GitHub)

**Modelos existentes (`models/staging/`):**
- `_sources.yml` — declara tabelas `sessoes`, `respostas`, `questoes_cache`
- `stg_sessoes.sql` — limpeza e padronização de sessões
- `stg_respostas.sql` — limpeza e padronização de respostas

**Próximo modelo:** `mart_desempenho` — acertos por tema, disciplina e dificuldade por aluno.

---

## Tela de Login

- **Login normal:** nome + senha (qualquer senha aceita — fase de testes)
- **Acesso Rápido:** botão entra só com nome, sem senha (para testes rápidos)
- Sessões separadas por `aluno_nome` no Supabase

---

## Estado Atual do Projeto

### v1 — Concluído ✅
Todas as features da v1 estão funcionando e em produção: https://knowsynth.streamlit.app/

### v2 — Em andamento 🔄
- ✅ Supabase conectado e recebendo dados reais
- ✅ dbt Cloud conectado ao Supabase e ao GitHub
- ✅ Modelos staging criados e validados (`dbt run` passou)
- ✅ OpenAI adicionado como fallback final
- ✅ `mart_desempenho` criado e validado (`dbt run` + `dbt test` passaram)
- ✅ Job agendado no dbt Cloud — `Daily - Run all models` (03:00 UTC / meia-noite BRT)
- ✅ `SUPABASE_URL` e `SUPABASE_KEY` configurados nos Secrets do Streamlit Cloud
- ⏳ **Próxima etapa:** Fase 3 — Supabase Auth (login real por `user_id`)

---

## Próximos Passos

1. **Fase 3 — Supabase Auth** — login real com e-mail e senha por usuário (separação por `user_id`)
2. **Mapa de pontos fracos** — rastrear evolução do aluno entre sessões com base no `mart_desempenho`
3. **Plano de estudo adaptativo** — novo agente Planejador que gera sequência de temas personalizada

---

## Padrões de Commit

Todos os commits da v2 seguem o prefixo `v2:`:

```
v2: feat: <descrição>      — nova funcionalidade
v2: fix: <descrição>       — correção de bug
v2: docs: <descrição>      — documentação
v2: chore: <descrição>     — dependências, config
v2: refactor: <descrição>  — refatoração sem mudança de comportamento
```

---

## Padrões de Código

- Agentes retornam dicionários — nunca levantam exceções para o pipeline
- Erros capturados em `{"erro": "mensagem"}` sem quebrar o fluxo
- LLM centralizado em `utils/llm_client.py` — usar `chamar_llm()` em todos os agentes
- Secrets sempre via `os.getenv()` — nunca hardcoded
- Branch dedicado para cada alteração — nunca direto no main

---

## Repositório

- **App em produção:** https://knowsynth.streamlit.app/
- **GitHub:** https://github.com/silasluiz96-alt/KnowSynth
- **Pasta local:** `C:\Users\silas\OneDrive\Desktop\knowsynth`
