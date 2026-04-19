"""
scheduler.py — Agendador de execuções do Job Agent
Roda ciclos automáticos a cada 1 hora. Nunca para sozinho.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from datetime import datetime

from core.models import init_db
from core.agent import ciclo_completo, gerar_resumo
from notifiers.notifier_telegram import notificar_resumo_diario

INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", 1))


def job_busca():
    print(f"[INFO] [{datetime.now().strftime('%H:%M')}] Iniciando ciclo agendado...")
    logger.info(f"⏰ Iniciando ciclo agendado às {datetime.now().strftime('%H:%M')}")
    try:
        ciclo_completo()
    except Exception as e:
        logger.error(f"Erro no ciclo agendado: {e}")
        print(f"[ERRO] Erro no ciclo agendado: {e}")


def job_resumo_diario():
    print("[INFO] Enviando resumo diário...")
    logger.info("📊 Enviando resumo diário...")
    try:
        resumo = gerar_resumo()
        notificar_resumo_diario(resumo)
    except Exception as e:
        logger.error(f"Erro no resumo diário: {e}")
        print(f"[ERRO] Erro no resumo diário: {e}")


if __name__ == "__main__":
    init_db()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    # Busca de vagas a cada N horas (padrão: 1h); executa imediatamente ao iniciar
    scheduler.add_job(
        job_busca,
        "interval",
        hours=INTERVAL_HOURS,
        id="busca_vagas",
        next_run_time=datetime.now(),
    )

    # Resumo diário às 08:00
    scheduler.add_job(
        job_resumo_diario,
        CronTrigger(hour=8, minute=0, timezone="America/Sao_Paulo"),
        id="resumo_diario",
    )

    print(f"[INFO] Scheduler iniciado — ciclos a cada {INTERVAL_HOURS}h | Resumo diário às 08:00")
    print("[INFO] Pressione Ctrl+C para parar.")
    logger.info(f"✅ Scheduler iniciado — ciclos a cada {INTERVAL_HOURS}h | Resumo diário às 08:00")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Scheduler encerrado.")
        print("[INFO] Scheduler encerrado.")
