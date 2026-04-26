#!/bin/bash
# Status visual dos processos e saúde da API.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Status do Job Agent"
echo "───────────────────"

# Scheduler
if pgrep -f "scheduler.py" > /dev/null 2>&1; then
    echo "Scheduler:  RODANDO (PID: $(pgrep -f scheduler.py | head -1))"
else
    echo "Scheduler:  PARADO"
fi

# API
if pgrep -f "uvicorn" > /dev/null 2>&1; then
    echo "API:        RODANDO (PID: $(pgrep -f uvicorn | head -1))"
else
    echo "API:        PARADA"
fi

# Frontend
if pgrep -f "vite" > /dev/null 2>&1; then
    echo "Frontend:   RODANDO"
else
    echo "Frontend:   PARADO (normal em producao)"
fi

echo ""

# Health check da API
if curl -s http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "API health: OK"
    curl -s http://localhost:8000/health/status | python3 -m json.tool 2>/dev/null || true
else
    echo "API health: SEM RESPOSTA"
fi

echo ""
echo "Logs recentes do scheduler:"
tail -5 logs/scheduler.log 2>/dev/null || echo "(sem logs)"
