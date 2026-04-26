#!/bin/bash
# Configura o Job Agent para rodar 24/7 via systemd (Linux/VPS).
# Execute: bash scripts/setup_24x7.sh

set -e

PROJECT_DIR=$(pwd)
PYTHON=$(which python3 || which python)
USER=$(whoami)

echo "Configurando Job Agent para rodar 24/7..."
echo "Diretorio: $PROJECT_DIR"
echo "Python: $PYTHON"
echo "Usuario: $USER"

# Serviço 1: Scheduler
cat > /tmp/job-agent-scheduler.service << EOF
[Unit]
Description=Job Agent Scheduler
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON scheduler.py
Restart=always
RestartSec=30
StandardOutput=append:$PROJECT_DIR/logs/scheduler-service.log
StandardError=append:$PROJECT_DIR/logs/scheduler-service-error.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Serviço 2: API FastAPI
cat > /tmp/job-agent-api.service << EOF
[Unit]
Description=Job Agent API FastAPI
After=network.target job-agent-scheduler.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=15
StandardOutput=append:$PROJECT_DIR/logs/api-service.log
StandardError=append:$PROJECT_DIR/logs/api-service-error.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "Instalando servicos (requer sudo)..."
sudo mv /tmp/job-agent-scheduler.service /etc/systemd/system/
sudo mv /tmp/job-agent-api.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable job-agent-scheduler job-agent-api
sudo systemctl start job-agent-scheduler job-agent-api

echo ""
echo "Servicos instalados e iniciados!"
echo ""
echo "Comandos uteis:"
echo "  sudo systemctl status job-agent-scheduler"
echo "  sudo systemctl status job-agent-api"
echo "  sudo systemctl restart job-agent-scheduler"
echo "  sudo journalctl -u job-agent-scheduler -f"
echo "  sudo journalctl -u job-agent-api -f"
