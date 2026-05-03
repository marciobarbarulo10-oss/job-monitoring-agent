# Job Monitoring Agent v2.0

Agente automatizado de monitoramento de vagas com scoring semântico via IA,
geração automática de CV por vaga e inteligência de mercado.

---

## Funcionalidades

| Feature | Descrição |
|---------|-----------|
| Scraping multi-portal | LinkedIn, Indeed, Gupy, Vagas.com |
| Score semântico IA | Avaliação A-F via Claude (não apenas keywords) |
| CV automático | PDF customizado por vaga (score >= 7.0) |
| Alerta 48h | Notificação especial para vagas publicadas há menos de 48h |
| Dashboard web | Pipeline visual com filtros, exportação CSV e ações |
| Inteligência de mercado | Relatório semanal de tendências e keywords |
| Filtro anti-scam | Detecção automática de vagas suspeitas |
| Aprendizado | Score calibrado pelo seu histórico de entrevistas |
| Telegram | Notificações em tempo real no celular |
| Health check | Endpoint /health para monitoramento externo |

---

## Arquitetura

```
job-monitoring-agent/
├── core/
│   ├── agent.py              # Orquestrador principal do pipeline
│   ├── models.py             # ORM SQLAlchemy + migrações
│   ├── semantic_scorer.py    # Score via Claude API com cache
│   ├── cv_generator.py       # Geração de PDF via Playwright
│   ├── feedback_engine.py    # Registro de outcomes e calibração
│   ├── market_intelligence.py # Relatório semanal de tendências
│   ├── opportunity_detector.py # Detecção de vagas < 48h
│   ├── quality_filter.py     # Filtro anti-scam
│   ├── pipeline_integrity.py # Dedup + normalização semanal
│   ├── rate_limiter.py       # Rate limiting por domínio
│   ├── logger.py             # Logging centralizado com rotação
│   └── utils.py              # Retry decorator e helpers
├── scrapers/
│   ├── scraper_indeed.py
│   ├── scraper_linkedin.py
│   ├── scraper_gupy.py
│   └── scraper_vagas.py
├── notifiers/
│   └── notifier_telegram.py
├── config/
│   ├── profile.py            # Perfil legado (keyword scoring)
│   ├── profile.yml           # Perfil v2.0 (scoring semântico)
│   └── settings.py           # Configuração centralizada
├── web/
│   ├── app.py                # Dashboard Flask
│   ├── templates/index.html
│   └── static/dashboard.js
├── templates/
│   └── cv_template.html
├── data/                     # Banco SQLite (auto-criado)
├── logs/                     # Logs rotativos
├── output/                   # PDFs gerados
├── scheduler.py              # Agendador de ciclos
├── cli.py                    # Interface de linha de comando
├── setup.py                  # Setup inicial
└── requirements.txt
```

---

## Instalação

### Pre-requisitos
- Python 3.10+
- pip

### Setup em 3 passos

```bash
# 1. Clone e instale
git clone https://github.com/marciobarbarulo10-oss/job-monitoring-agent.git
cd job-monitoring-agent
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure
python setup.py   # cria pastas e .env inicial
notepad .env      # preencha suas credenciais

# 3. Rode
python scheduler.py          # agente em background
python web/app.py            # dashboard (outro terminal)
```

---

## Comandos CLI

```bash
# Listar vagas
python cli.py listar --min-score 7.0
python cli.py listar --status nova --grade A

# Marcar como aplicada
python cli.py aplicar "https://linkedin.com/jobs/view/123" --notas "Via LinkedIn"

# Atualizar status
python cli.py status 42 entrevista --detalhes "Agendada para 25/04"

# Ver histórico
python cli.py historico 42

# Resumo geral
python cli.py resumo

# Ciclo manual
python cli.py rodar

# Gerar CV para uma vaga
python cli.py cv 42

# Registrar outcome de candidatura
python cli.py feedback 42 entrevista --notas "Chamada agendada"

# Relatório de mercado
python cli.py mercado

# Manutenção do pipeline
python cli.py manutencao

# Calibrar scoring
python cli.py calibrar --min-samples 5

# Listar CVs gerados
python cli.py cvs
```

---

## Dashboard

Acesse: http://localhost:5000

| Aba | Conteúdo |
|-----|----------|
| Pipeline | Funil de candidaturas com filtros e ações |
| Mercado | Relatório de tendências e keywords |
| Feedback | Outcomes registrados e calibração |
| CVs | CVs gerados com download |
| Configuração | Edição do perfil e teste Telegram |

**Endpoints da API:**
- `GET /health` — health check com status do banco e integrações
- `GET /api/stats` — métricas do pipeline
- `GET /api/jobs` — lista de vagas com filtros e paginação
- `GET /api/export/csv` — exportação CSV de todas as vagas
- `POST /api/trigger` — dispara ciclo de busca em background
- `POST /api/cv/<id>` — gera CV on-demand para uma vaga

---

## Sistema de Score

| Grade | Score | Significado | Ação |
|-------|-------|-------------|------|
| A | 9-10 | Fit perfeito | CV gerado automaticamente + alerta prioritário |
| B | 7-8.9 | Boa aderência | CV gerado automaticamente + notificação Telegram |
| C | 5-6.9 | Aderência parcial | Notificação Telegram |
| D | 3-4.9 | Aderência baixa | Salvo sem notificação |
| F | 0-2.9 | Descartado | Ignorado |

O scoring usa Claude API por padrão (análise semântica). Sem ANTHROPIC_API_KEY,
usa keyword matching do `config/profile.py` como fallback.

---

## Variaveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot (obrigatório para notificações) |
| `TELEGRAM_CHAT_ID` | — | Chat ID do destinatário |
| `ANTHROPIC_API_KEY` | — | Chave da API Anthropic (para score semântico) |
| `SEMANTIC_MODEL` | `claude-haiku-4-5-20251001` | Modelo para scoring |
| `ENABLE_SEMANTIC_SCORING` | `true` | Habilita score via Claude |
| `MIN_SCORE_TO_NOTIFY` | `6.0` | Score mínimo para notificação |
| `MIN_SCORE_AUTO_CV` | `7.0` | Score mínimo para gerar CV |
| `CHECK_INTERVAL_HOURS` | `6` | Horas entre ciclos de busca |
| `FLASK_PORT` | `5000` | Porta do dashboard |
| `LOG_LEVEL` | `INFO` | Nível de log (DEBUG/INFO/WARNING) |

---

## Consideracoes de Uso

1. **LinkedIn** pode bloquear IPs com muitas requisições. Use intervalos de 6h+.
2. **Gupy** usa API pública REST — mais estável que scraping HTML.
3. O rate limiter em `core/rate_limiter.py` aplica delays automáticos por domínio.
4. O banco SQLite é suficiente para uso pessoal. Para múltiplos usuários, troque
   a connection string em `models.py` por PostgreSQL.
5. CVs gerados ficam em `output/` e não são versionados no git.

---

## Changelog

### v2.0 (atual)
- Score semântico via Claude API com grade A-F
- Geração automática de CV em PDF por vaga (score >= 7.0)
- Detecção de janela de oportunidade (publicadas < 48h)
- Sistema de feedback e calibração de score por histórico
- Filtro anti-scam com QualityFilter
- Relatório semanal de tendências de mercado
- Dashboard expandido com exportação CSV e health check
- Configuração centralizada em config/settings.py
- Rate limiting inteligente por domínio nos scrapers
- Logging padronizado com rotação de arquivos
- setup.py para onboarding em 3 passos

### v1.0
- Versão inicial com keyword matching
- Notificações Telegram básicas
- CLI e scheduler com APScheduler


<!-- STATS-START -->
## Métricas ao Vivo

| Métrica | Valor |
|---------|-------|
| Vagas monitoradas | **227** |
| Candidaturas ativas | **7** |
| Score médio de match | **3.2/10** |
| Entrevistas geradas | **0** |
| Novas vagas (24h) | **4** |
| Vagas com score ≥ 7 | **0** |

_Atualizado automaticamente em 03/05/2026 00:00_
<!-- STATS-END -->
