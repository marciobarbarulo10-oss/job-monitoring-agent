# 🤖 Job Agent — Márcio Beraldo

Agente automatizado que monitora candidaturas de emprego e busca novas vagas
em LinkedIn, Indeed, Gupy e Vagas.com, com scoring de aderência e notificações
via Telegram.

---

## 🏗️ Estrutura do Projeto

```
job_agent/
├── core/
│   ├── agent.py          # Orquestrador principal
│   └── models.py         # Banco de dados (SQLite)
├── scrapers/
│   ├── scraper_indeed.py
│   ├── scraper_linkedin.py
│   ├── scraper_gupy.py
│   └── scraper_vagas.py
├── notifiers/
│   └── notifier_telegram.py
├── config/
│   └── profile.py        # Perfil + sistema de score
├── data/                 # Banco SQLite (auto-criado)
├── logs/                 # Logs rotativos
├── scheduler.py          # Agendador de ciclos
├── cli.py                # Interface de linha de comando
├── requirements.txt
└── .env.example
```

---

## ⚙️ Configuração (Passo a Passo)

### 1. Clone e instale dependências

```bash
git clone <seu-repo>
cd job_agent
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure o arquivo .env

```bash
cp .env.example .env
nano .env  # ou abra no editor
```

Preencha:
- `TELEGRAM_BOT_TOKEN` — crie um bot com o @BotFather no Telegram
- `TELEGRAM_CHAT_ID` — envie uma mensagem para o bot e acesse:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
- `MIN_SCORE_TO_NOTIFY` — score mínimo para notificar (recomendo 6.0)

### 3. Inicialize o banco

```bash
python -c "from core.models import init_db; init_db()"
```

---

## ▶️ Como Rodar

### Modo manual (um ciclo agora)
```bash
python cli.py rodar
```

### Modo automático (ciclos agendados)
```bash
python scheduler.py
# Roda ciclos a cada 6h + resumo diário às 08:00
```

### Rodar em background (Linux)
```bash
nohup python scheduler.py > logs/scheduler.log 2>&1 &
echo $! > scheduler.pid
```

### Parar o agente
```bash
kill $(cat scheduler.pid)
```

---

## 📟 Comandos CLI

```bash
# Listar vagas com score >= 7
python cli.py listar --min-score 7.0

# Listar apenas vagas novas
python cli.py listar --status nova

# Marcar vaga como aplicada
python cli.py aplicar "https://linkedin.com/jobs/view/123" --notas "Enviei pelo LinkedIn"

# Atualizar status manualmente
python cli.py status 42 entrevista --detalhes "Agendada para 25/04"

# Ver histórico de uma vaga
python cli.py historico 42

# Ver resumo geral
python cli.py resumo
```

---

## 📊 Sistema de Score (0–10)

| Componente            | Peso máx. | Exemplos que pontuam alto               |
|-----------------------|-----------|-----------------------------------------|
| Keywords na descrição | 6.0       | importação, ANVISA, I-Broker, desembaraço |
| Match de título       | 2.5       | "Analista de Importação", "Analista Comex" |
| Localização           | 1.5       | São Paulo, Remoto, Híbrido              |

Vagas com score < 2.0 são descartadas automaticamente.
Vagas com score ≥ MIN_SCORE_TO_NOTIFY geram notificação Telegram.

---

## 🛡️ Anti-bot — Como o agente evita bloqueios

| Técnica                  | Implementação                          |
|--------------------------|----------------------------------------|
| User-Agent aleatório     | `fake-useragent` rotaciona a cada req  |
| Delays aleatórios        | `time.sleep(random.uniform(3, 9))`     |
| Retry com backoff        | `tenacity` — 3 tentativas, espera exp  |
| Gupy via API pública     | Sem scraping, usa endpoint REST        |
| LinkedIn endpoint guest  | API pública `/jobs-guest/` sem login   |
| Sessão persistente       | `requests.Session()` para cookies      |

Para sites com proteção avançada (Cloudflare), use Playwright headless:
```python
from playwright.async_api import async_playwright
# Playwright emula browser real — difícil de detectar
```

---

## 🔮 Evoluções Futuras

### v2 — IA para personalização
```python
# Usar GPT-4 para pontuar aderência com mais precisão
# e gerar carta de apresentação personalizada por vaga
from openai import OpenAI
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{
        "role": "system",
        "content": "Analise a aderência desta vaga ao perfil e retorne JSON com score e justificativa."
    }, {
        "role": "user", 
        "content": f"PERFIL: {perfil}\n\nVAGA: {descricao_vaga}"
    }]
)
```

### v3 — Auto-candidatura (Gupy)
```python
# Gupy tem fluxo de candidatura via API autenticada
# Possível automatizar o envio do currículo nas vagas score >= 8
```

### v4 — Dashboard Web
```python
# Flask/FastAPI + SQLite → visualização web das candidaturas
# Gráficos de funil: vagas encontradas → aplicadas → entrevistas
```

### v5 — Integração com currículo
```python
# Gerar PDF personalizado por vaga usando os 10 currículos já criados
# Selecionar automaticamente qual currículo usar baseado no tipo de vaga
```

---

## 🔧 Configurações Avançadas (.env)

```env
CHECK_INTERVAL_HOURS=6    # Intervalo entre ciclos (padrão: 6h)
MIN_SCORE_TO_NOTIFY=6.0   # Score mínimo para notificação
LOG_LEVEL=INFO             # DEBUG para mais detalhes
```

---

## ⚠️ Observações Importantes

1. **LinkedIn** pode bloquear IPs com muitas requisições. Use intervalos ≥ 6h.
2. **Gupy** usa API pública — mais estável que scraping.
3. **Vagas.com** muda estrutura HTML com frequência — verifique os seletores.
4. Para produção contínua, considere rodar em VPS (DigitalOcean $6/mês) ou
   Google Cloud Run (free tier).
5. O banco SQLite é suficiente para uso pessoal. Para múltiplos usuários,
   migre para PostgreSQL (troque a connection string em `models.py`).
