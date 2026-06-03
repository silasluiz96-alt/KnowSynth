# 🎓 EduSynth — Assistente de Estudos para o ENEM

> Sistema multi-agente de IA que pesquisa, analisa criticamente e gera material de estudo personalizado para estudantes do ENEM — em segundos.

---

## 📌 Sobre o Projeto

O **EduSynth** é uma aplicação web que combina **5 agentes de inteligência artificial** trabalhando em pipeline para transformar qualquer tema ou palavra-chave do ENEM em um material de estudo completo, com questão original, análise estratégica e dicas progressivas para resolução.

Ao digitar um tema como *"fordismo"* ou *"aquecimento global"*, o sistema:

1. **Pesquisa** conteúdo em fontes didáticas, jornalísticas e acadêmicas
2. **Analisa criticamente** a frequência do tema no ENEM, erros comuns e conexões interdisciplinares
3. **Sintetiza** um material original com introdução, pontos essenciais e questão estilo ENEM
4. **Guia** o estudante na resolução com 3 dicas progressivas antes de liberar o gabarito
5. **Acompanha** o desempenho da sessão e recomenda prioridades de estudo

---

## 🏗️ Arquitetura dos Agentes

```
Usuário (input: tema ou palavra-chave)
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                       │
│          Coordena o pipeline em sequência            │
└──────┬──────────────────────────────────────────────┘
       │
       ▼
┌─────────────────┐
│  🔍 PESQUISADOR  │  ← Tavily API
│  researcher.py  │
│                 │  • Detecta: tema amplo vs palavra-chave
│                 │  • Camada 1: fontes didáticas
│                 │  • Camada 2: notícias recentes
│                 │  • Camada 3: referências acadêmicas
└────────┬────────┘
         │ resultado_pesquisa
         ▼
┌─────────────────┐
│   🧠 CRÍTICO     │  ← Groq (LLaMA 3.3 70B)
│    critic.py    │
│                 │  • Frequência e relevância no ENEM
│                 │  • Erros mais comuns dos estudantes
│                 │  • Conexões interdisciplinares
│                 │  • Pontos críticos obrigatórios
│                 │  • Nível de prioridade: alta/média/baixa
└────────┬────────┘
         │ resultado_critica
         ▼
┌─────────────────┐
│  📝 SINTETIZADOR │  ← Groq (LLaMA 3.3 70B)
│  synthesizer.py │
│                 │  • Introdução acessível
│                 │  • 5 pontos essenciais
│                 │  • Conexões interdisciplinares
│                 │  • Questão original estilo ENEM
│                 │  • Análise de palavras-chave
│                 │  • Dicas de prova + leituras
└────────┬────────┘
         │ material_final
         ▼
┌─────────────────┐     ┌──────────────────────┐
│  💡 ESTRATEGISTA │     │  📊 ANALISTA           │
│  strategist.py  │     │  performance_analyst  │
│                 │     │                      │
│  • Dica nível 1 │     │  • Rastreia sessão   │
│  • Dica nível 2 │     │  • Classifica        │
│  • Dica nível 3 │     │    dificuldade       │
│  • Gabarito só  │     │  • Gera relatório    │
│    após 3 dicas │     │    ao final          │
└─────────────────┘     └──────────────────────┘
         │                        │
         └────────────┬───────────┘
                      ▼
             Interface Streamlit
                  app.py
```

### Skills dos Agentes

Cada agente carrega seu comportamento de um arquivo Markdown em `.claude/skills/`:

| Arquivo | Agente | Função |
|---|---|---|
| `researcher.md` | Pesquisador | Define as 3 camadas de busca e gestão de lacunas |
| `critic.md` | Crítico | Define a análise estratégica para o ENEM |
| `synthesizer.md` | Sintetizador | Define o formato do material de estudo |
| `strategist.md` | Estrategista | Define o sistema de dicas progressivas |
| `performance_analyst.md` | Analista | Define rastreamento e relatório de sessão |

---

## 🛠️ Tecnologias

| Tecnologia | Uso |
|---|---|
| **Python 3.12+** | Linguagem principal |
| **Streamlit** | Interface web |
| **Groq API** | LLM para análise, síntese e estratégia (LLaMA 3.3 70B) |
| **Tavily API** | Busca web em 3 camadas (didático, notícias, acadêmico) |
| **python-dotenv** | Gerenciamento de variáveis de ambiente |

---

## 🚀 Como Rodar Localmente

### Pré-requisitos

- Python 3.12 ou superior
- Conta gratuita no [Groq](https://console.groq.com) para obter a `GROQ_API_KEY`
- Conta gratuita no [Tavily](https://tavily.com) para obter a `TAVILY_API_KEY`

### Passo a passo

**1. Clone o repositório**
```bash
git clone https://github.com/silasluiz96-alt/EduSynth.git
cd EduSynth
```

**2. Instale as dependências**
```bash
pip install -r requirements.txt
```

**3. Configure as variáveis de ambiente**

Crie um arquivo `.env` na raiz do projeto:
```env
GROQ_API_KEY=sua_chave_groq_aqui
TAVILY_API_KEY=sua_chave_tavily_aqui
```

**4. Rode o app**
```bash
python -m streamlit run app.py
```

**5. Acesse no navegador**
```
http://localhost:8501
```

---

## 📁 Estrutura do Projeto

```
EduSynth/
├── .claude/
│   ├── settings.json          # Configurações do projeto
│   └── skills/
│       ├── researcher.md      # Skill do Pesquisador
│       ├── critic.md          # Skill do Crítico
│       ├── synthesizer.md     # Skill do Sintetizador
│       ├── strategist.md      # Skill do Estrategista
│       └── performance_analyst.md  # Skill do Analista
├── agents/
│   ├── researcher.py          # Agente Pesquisador (Tavily)
│   ├── critic.py              # Agente Crítico (Groq)
│   ├── synthesizer.py         # Agente Sintetizador (Groq)
│   ├── strategist.py          # Agente Estrategista (Groq)
│   ├── performance_analyst.py # Agente Analista (Groq)
│   └── orchestrator.py        # Orquestrador do pipeline
├── app.py                     # Interface Streamlit
├── requirements.txt
├── .env                       # Não commitado — chaves locais
└── .gitignore
```

---

## 🗺️ Roadmap — EduSynth v2

### 🔐 Autenticação e Perfil
- [ ] Login com Google via Supabase Auth
- [ ] Perfil do estudante com área de interesse e nível

### 🧠 Memória Persistente
- [ ] Histórico de sessões salvo no Supabase
- [ ] Mapa de pontos fracos acumulado ao longo do tempo
- [ ] Temas pesquisados e dificuldades registradas permanentemente

### 📊 Painel de Evolução
- [ ] Dashboard com evolução semanal e mensal
- [ ] Gráfico de desempenho por área do conhecimento
- [ ] Indicador de temas dominados vs. a revisar

### 🤖 Plano de Estudos Adaptativo
- [ ] Agente planejador que cria cronograma personalizado
- [ ] Alertas proativos para temas negligenciados
- [ ] Sugestões baseadas no calendário do ENEM

### 📱 Melhorias de UX
- [ ] PWA (Progressive Web App) — funciona como app no celular
- [ ] Modo offline para material já gerado
- [ ] Exportar material em PDF

### 🔗 Integrações
- [ ] Integração com questões reais do ENEM (banco de dados oficial)
- [ ] Compartilhamento de material entre estudantes
- [ ] API pública para integração com outras plataformas educacionais

---

## 🤝 Contribuindo

Pull requests são bem-vindos! Para mudanças maiores, abra uma issue primeiro para discutir o que você gostaria de mudar.

---

## 📄 Licença

MIT License — sinta-se livre para usar, modificar e distribuir.

---

<div align="center">
  Feito com ☕ e IA generativa para estudantes brasileiros
</div>
