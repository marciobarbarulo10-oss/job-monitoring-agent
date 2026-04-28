#!/bin/bash
# Inicia todos os serviços do Job Agent em modo desenvolvimento (nohup).

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs

echo "Iniciando Job Agent v3 em modo desenvolvimento..."

# Scheduler
echo "Iniciando scheduler..."
nohup python scheduler.py > logs/scheduler.log 2>&1 &
echo $! > .scheduler.pid
echo "  Scheduler PID: $(cat .scheduler.pid)"

# API FastAPI
echo "Iniciando API FastAPI na porta 8000..."
nohup python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload \
    > logs/api.log 2>&1 &
echo $! > .api.pid
echo "  API PID: $(cat .api.pid)"

# Frontend React (somente se node_modules existir)
if [ -d "frontend/node_modules" ]; then
    echo "Iniciando frontend React na porta 5173..."
    cd frontend
    nohup npm run dev > ../logs/frontend.log 2>&1 &
    echo $! > ../.frontend.pid
    echo "  Frontend PID: $(cat ../.frontend.pid)"
    cd ..
fi

echo ""
echo "Job Agent rodando!"
echo "  Dashboard:  http://localhost:5173"
echo "  API:        http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Health QA:  http://localhost:8000/health/qa"
echo "  Webhooks:   http://localhost:8000/webhooks/mailerlite/health"
echo ""

# ngrok — expõe API externamente para que os webhooks do MailerLite funcionem localmente
if command -v ngrok &> /dev/null; then
    echo "Iniciando ngrok para expor API externamente..."
    nohup ngrok http 8000 > logs/ngrok.log 2>&1 &
    echo $! > .ngrok.pid
    sleep 3
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d['tunnels'][0]['public_url'])
except:
    pass
" 2>/dev/null)
    if [ -n "$NGROK_URL" ]; then
        echo "  URL publica: $NGROK_URL"
        echo "  Atualizando webhooks no MailerLite..."
        python scripts/update_webhook_urls.py "$NGROK_URL" 2>/dev/null || true
    else
        echo "  ngrok iniciado (aguarde URL em http://localhost:4040)"
    fi
else
    echo "ngrok nao instalado — webhooks so funcionam em producao"
    echo "Para instalar: https://ngrok.com/download"
fi

echo ""
echo "Para parar: bash scripts/stop_dev.sh"
echo "Para status: bash scripts/status.sh"
