#!/bin/bash
# Para todos os serviços do Job Agent.

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "Parando Job Agent..."

for pid_file in .scheduler.pid .api.pid .frontend.pid; do
    if [ -f "$pid_file" ]; then
        PID=$(cat "$pid_file")
        kill "$PID" 2>/dev/null && echo "  Parado PID $PID ($pid_file)" || echo "  PID $PID ja estava parado"
        rm "$pid_file"
    fi
done

# Kill por nome como backup
pkill -f "scheduler.py"     2>/dev/null || true
pkill -f "uvicorn api.main" 2>/dev/null || true
pkill -f "vite"             2>/dev/null || true

echo "Todos os servicos parados."
