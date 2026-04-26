"""
scheduler.py — Agendador de execuções do Job Agent v3.0
Usa Orchestrator multi-agentes: Collector + Matcher + Monitor.
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
from notifiers.notifier_telegram import (
    notify_feedback_insight,
    notify_maintenance_report,
)

INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", 6))

# Orchestrator inicializado lazy para não bloquear a inicialização do scheduler
_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from agents.orchestrator import Orchestrator
        _orchestrator = Orchestrator()
    return _orchestrator


def job_busca():
    """Ciclo principal via Orchestrator (Collector + Matcher + Monitor)."""
    logger.info(f"Ciclo agendado iniciado as {datetime.now().strftime('%H:%M')}")
    try:
        _get_orchestrator().run_full_cycle()
    except Exception as e:
        logger.error(f"Erro no ciclo agendado: {e}")


def job_resumo_diario():
    """Envia resumo diário das candidaturas via Telegram."""
    logger.info("Enviando resumo diario...")
    try:
        _get_orchestrator().run_daily_summary()
    except Exception as e:
        logger.error(f"Erro no resumo diario: {e}")


def job_relatorio_mercado():
    """Gera e envia relatório semanal de mercado + insights LLM."""
    logger.info("Gerando relatorio semanal de mercado...")
    try:
        _get_orchestrator().run_weekly_insights()
        logger.info("Relatorio de mercado enviado via Telegram")
    except Exception as e:
        logger.error(f"Erro no relatorio de mercado: {e}")


def job_manutencao():
    """Executa manutenção semanal do pipeline (dedup + normalize + health)."""
    logger.info("Iniciando manutencao semanal do pipeline...")
    try:
        from core.pipeline_integrity import PipelineIntegrity
        pi = PipelineIntegrity()
        relatorio = pi.run_maintenance()
        notify_maintenance_report(relatorio)
        logger.info("Manutencao concluida e relatorio enviado")
    except Exception as e:
        logger.error(f"Erro na manutencao semanal: {e}")


def job_calibracao():
    """Tenta recalibrar o scoring baseado nos feedbacks registrados."""
    logger.info("Verificando calibracao de scoring...")
    try:
        from core.feedback_engine import FeedbackEngine
        fe = FeedbackEngine()
        resultado = fe.recalibrate(min_samples=5)
        if resultado.get("status") == "calibrado":
            insight = resultado.get("insight", "")
            amostras = resultado.get("amostras", 0)
            if insight:
                notify_feedback_insight(insight, amostras)
                logger.info(f"Insight de calibracao enviado: {insight}")
    except Exception as e:
        logger.error(f"Erro na calibracao automatica: {e}")


def job_qa():
    """QA automático — verifica saúde do sistema a cada 2h."""
    logger.info("Executando QA check automatico...")
    try:
        _get_orchestrator().run_qa_check()
    except Exception as e:
        logger.error(f"Erro no QA check: {e}")


def job_qa_matinal():
    """Relatório QA matinal às 07:00 — enviado ao Telegram sempre."""
    logger.info("Executando relatorio QA matinal...")
    try:
        orch = _get_orchestrator()
        report = orch.run_qa_check()
        overall = report["overall_status"]
        emoji = "OK" if overall == "ok" else ("AVISO" if overall == "warning" else "FALHA")
        from notifiers.notifier_telegram import enviar_telegram
        msg = (
            f"*Job Agent — Relatorio Matinal*\n"
            f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"Status: *{emoji}*\n\n"
            f"Checks ok: {report['passed']}/{report['total_checks']}"
        )
        if report["warnings"]:
            msg += f"\nAvisos: {', '.join(report['warnings'])}"
        if report["failures"]:
            msg += f"\nFalhas: {', '.join(report['failures'])}"
        enviar_telegram(msg)
    except Exception as e:
        logger.error(f"Erro no relatorio QA matinal: {e}")


def job_git_push_diario():
    """Push diário automático às 23:00 para o GitHub."""
    logger.info("Executando push diario para o GitHub...")
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        _get_orchestrator().run_git_push(
            message=f"chore: daily auto-sync {today}",
            notify=True,
        )
    except Exception as e:
        logger.error(f"Erro no push diario: {e}")


def job_git_push_semanal():
    """Push semanal às sextas 22:00."""
    logger.info("Executando push semanal para o GitHub...")
    try:
        week = datetime.now().strftime("%Y-W%U")
        _get_orchestrator().run_git_push(
            message=f"chore: weekly snapshot {week}",
            notify=True,
        )
    except Exception as e:
        logger.error(f"Erro no push semanal: {e}")


if __name__ == "__main__":
    init_db()

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")

    # Ciclo principal a cada N horas (padrão: 6h), executa imediatamente ao iniciar
    scheduler.add_job(
        job_busca,
        "interval",
        hours=INTERVAL_HOURS,
        id="busca_vagas",
        max_instances=1,
        next_run_time=datetime.now(),
    )

    # Resumo diário às 08:00
    scheduler.add_job(
        job_resumo_diario,
        CronTrigger(hour=8, minute=0, timezone="America/Sao_Paulo"),
        id="resumo_diario",
        max_instances=1,
    )

    # Relatório de mercado todo domingo às 18:00
    scheduler.add_job(
        job_relatorio_mercado,
        CronTrigger(day_of_week="sun", hour=18, minute=0, timezone="America/Sao_Paulo"),
        id="relatorio_mercado",
        max_instances=1,
    )

    # Manutenção semanal toda segunda às 07:00
    scheduler.add_job(
        job_manutencao,
        CronTrigger(day_of_week="mon", hour=7, minute=0, timezone="America/Sao_Paulo"),
        id="manutencao_pipeline",
        max_instances=1,
    )

    # Calibração automática toda quarta às 12:00
    scheduler.add_job(
        job_calibracao,
        CronTrigger(day_of_week="wed", hour=12, minute=0, timezone="America/Sao_Paulo"),
        id="calibracao_scoring",
        max_instances=1,
    )

    # QA a cada 2 horas
    scheduler.add_job(
        job_qa,
        "interval",
        hours=2,
        id="qa_check",
        max_instances=1,
    )

    # Relatório QA matinal às 07:00 (todo dia)
    scheduler.add_job(
        job_qa_matinal,
        CronTrigger(hour=7, minute=0, timezone="America/Sao_Paulo"),
        id="qa_matinal",
        max_instances=1,
    )

    # Push diário às 23:00
    scheduler.add_job(
        job_git_push_diario,
        CronTrigger(hour=23, minute=0, timezone="America/Sao_Paulo"),
        id="git_push_diario",
        max_instances=1,
    )

    # Push semanal toda sexta às 22:00
    scheduler.add_job(
        job_git_push_semanal,
        CronTrigger(day_of_week="fri", hour=22, minute=0, timezone="America/Sao_Paulo"),
        id="git_push_semanal",
        max_instances=1,
    )

    logger.info(f"Scheduler v3.0 iniciado — ciclos a cada {INTERVAL_HOURS}h")
    logger.info("Jobs: resumo 08h | qa 2h | qa-matinal 07h | mercado dom 18h | manutencao seg 07h | calibracao qua 12h | push 23h | push-semanal sex 22h")
    logger.info("Pressione Ctrl+C para parar.")
    logger.info(f"Scheduler v2.0 iniciado — {INTERVAL_HOURS}h entre ciclos")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler encerrado.")
        print("[INFO] Scheduler encerrado.")
