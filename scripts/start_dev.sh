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
echo "  Dashboard: http://localhost:5173"
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Health QA: http://localhost:8000/health/qa"
echo ""
echo "Para parar: bash scripts/stop_dev.sh"
echo "Para status: bash scripts/status.sh"
