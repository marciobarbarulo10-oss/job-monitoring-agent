# 🤖 Job Agent — Agente Autônomo de Busca de Emprego

> Sistema multi-agentes que monitora vagas 24/7, calcula score de aderência por IA e gera cartas de apresentação personalizadas para cada vaga.

## 🚀 O que é

O Job Agent automatiza o processo de busca de emprego para **qualquer profissional** em busca ativa ou passiva de novas oportunidades.

Enquanto você trabalha ou dorme, o agente:
- Varre LinkedIn, Gupy e Vagas.com continuamente
- Calcula score de aderência comparando cada vaga com seu perfil
- Gera cartas de apresentação personalizadas para cada vaga
- Rastreia suas candidaturas em kanban visual
- Envia alertas no Telegram quando encontra vagas com alto match

## 📊 Status atual

| Componente | Status |
|---|---|
| Coleta de vagas (LinkedIn, Gupy, Vagas.com) | ✅ |
| Dashboard React com funil de candidaturas | ✅ |
| Sistema de autenticação multi-usuário | ✅ |
| Upload e gestão de currículos PDF | ✅ |
| Kanban de candidaturas | ✅ |
| Cartas de apresentação por vaga | ✅ |
| Score por IA (Claude) | ⚙️ Requer ANTHROPIC_API_KEY |
| Deploy em produção | 🔄 Em andamento |
| Planos pagos | 📋 Planejado |

## 🚀 Como rodar

```bash
git clone https://github.com/marciobarbarulo10-oss/job-monitoring-agent
cd job-monitoring-agent
pip install -r requirements.txt
cd frontend && npm install && cd ..
python scheduler.py &
python -m uvicorn api.main:app --port 8000 &
cd frontend && npm run dev
```

Acesse http://localhost:5173

## 💰 Planos

| | Free | Pro (R$49/mês) | Business (R$199/mês) |
|---|---|---|---|
| Busca automática | ✅ | ✅ | ✅ |
| Score por IA | ❌ | ✅ | ✅ |
| Cartas ilimitadas | 5/mês | ✅ | ✅ |
| Insights de mercado | ❌ | ✅ | ✅ |
| API B2B | ❌ | ❌ | ✅ |

Planos pagos em breve. [Entre na lista de espera](http://localhost:5173/planos)

## 📄 Licença

MIT

*Desenvolvido por [@marciobarbarulo10-oss](https://github.com/marciobarbarulo10-oss)*
