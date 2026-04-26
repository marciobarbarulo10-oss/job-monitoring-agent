"""
Agente de QA — verifica automaticamente se todas as funcionalidades
do Job Agent estão operando corretamente.

Checks executados:
  1. Banco de dados — acessível, íntegro e com dados
  2. Scrapers — pelo menos 1 rodou nas últimas 24h
  3. API FastAPI — respondendo nos endpoints principais
  4. Scheduler — processo ativo no sistema
  5. Fila de score — vagas sem score há mais de 2h (fila travada)
  6. Disco — espaço livre > 200 MB
  7. Logs — sem erros críticos recentes
  8. Frontend — porta 5173 respondendo
"""
import os
import time
import sqlite3
import shutil
import logging
import subprocess
import requests
from datetime import datetime, timedelta
from agents import BaseAgent

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")
API_BASE = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"


class QAAgent(BaseAgent):

    def __init__(self):
        super().__init__("qa")

    # ─────────────────────────────────────────────
    # CHECK 1 — Banco de dados
    # ─────────────────────────────────────────────
    def check_database(self) -> dict:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()

            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vagas")
            total = cursor.fetchone()[0]

            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM vagas WHERE data_encontrada >= ?", (cutoff,)
            )
            new_24h = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1")
            total_apps = cursor.fetchone()[0]

            conn.close()

            status = "ok" if integrity == "ok" and total > 0 else "error"
            return {
                "check": "database",
                "status": status,
                "details": {
                    "integrity": integrity,
                    "total_vagas": total,
                    "novas_24h": new_24h,
                    "candidaturas": total_apps,
                },
            }
        except Exception as e:
            return {"check": "database", "status": "error", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 2 — Scrapers rodaram recentemente
    # ─────────────────────────────────────────────
    def check_scrapers(self) -> dict:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()

            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            cursor.execute(
                "SELECT fonte, COUNT(*) FROM vagas "
                "WHERE data_encontrada >= ? GROUP BY fonte ORDER BY 2 DESC",
                (cutoff,),
            )
            sources = cursor.fetchall()

            # Último run do collector via agent_logs
            cursor.execute(
                "SELECT created_at FROM agent_logs "
                "WHERE agent_name='collector' AND status='success' "
                "ORDER BY created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            last_run = row[0] if row else None

            conn.close()

            status = "ok" if sources else "warning"
            return {
                "check": "scrapers",
                "status": status,
                "details": {
                    "fontes_24h": dict(sources),
                    "ultimo_collector": last_run,
                    "total_fontes_ativas": len(sources),
                },
            }
        except Exception as e:
            return {"check": "scrapers", "status": "error", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 3 — API FastAPI
    # ─────────────────────────────────────────────
    def check_api(self) -> dict:
        endpoints = [
            "/health",
            "/api/dashboard/summary",
            "/api/vagas/?limit=1",
            "/api/candidaturas/",
        ]
        results = {}
        all_ok = True

        for ep in endpoints:
            try:
                start = time.time()
                r = requests.get(f"{API_BASE}{ep}", timeout=5)
                elapsed = round((time.time() - start) * 1000)
                ok = r.status_code < 400
                results[ep] = {"status_code": r.status_code, "ok": ok, "response_ms": elapsed}
                if not ok:
                    all_ok = False
            except Exception as e:
                results[ep] = {"status_code": None, "ok": False, "error": str(e)}
                all_ok = False

        return {
            "check": "api",
            "status": "ok" if all_ok else "error",
            "details": results,
        }

    # ─────────────────────────────────────────────
    # CHECK 4 — Processos ativos
    # ─────────────────────────────────────────────
    def check_processes(self) -> dict:
        try:
            # No Windows usamos tasklist, no Linux pgrep
            import platform
            is_windows = platform.system() == "Windows"

            if is_windows:
                result = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                    capture_output=True, text=True, timeout=10
                )
                scheduler_running = "python.exe" in result.stdout
                api_result = subprocess.run(
                    ["netstat", "-an"],
                    capture_output=True, text=True, timeout=10
                )
                api_running = ":8000" in api_result.stdout
                scheduler_pids = ["(Windows — ver tasklist)"] if scheduler_running else []
                api_pids = ["(Windows — porta 8000)"] if api_running else []
            else:
                r = subprocess.run(["pgrep", "-f", "scheduler.py"], capture_output=True, text=True)
                scheduler_pids = [p for p in r.stdout.strip().split("\n") if p]
                r2 = subprocess.run(["pgrep", "-f", "uvicorn"], capture_output=True, text=True)
                api_pids = [p for p in r2.stdout.strip().split("\n") if p]
                scheduler_running = bool(scheduler_pids)
                api_running = bool(api_pids)

            # Verifica se a API responde como forma alternativa de confirmar que está rodando
            try:
                requests.get(f"{API_BASE}/health", timeout=3)
                api_running = True
            except Exception:
                pass

            return {
                "check": "processes",
                "status": "ok" if api_running else "warning",
                "details": {
                    "scheduler_pids": scheduler_pids,
                    "scheduler_running": scheduler_running,
                    "api_pids": api_pids,
                    "api_running": api_running,
                },
            }
        except Exception as e:
            return {"check": "processes", "status": "warning", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 5 — Fila de score não travada
    # ─────────────────────────────────────────────
    def check_score_queue(self) -> dict:
        try:
            conn = sqlite3.connect(DB_PATH, timeout=5)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM vagas WHERE score IS NULL")
            sem_score = cursor.fetchone()[0]

            cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
            cursor.execute(
                "SELECT COUNT(*) FROM vagas WHERE score IS NULL AND data_encontrada < ?",
                (cutoff,),
            )
            travadas = cursor.fetchone()[0]

            conn.close()

            status = "warning" if travadas > 20 else "ok"
            return {
                "check": "score_queue",
                "status": status,
                "details": {
                    "sem_score_total": sem_score,
                    "travadas_mais_2h": travadas,
                    "note": "fila travada" if travadas > 20 else "ok",
                },
            }
        except Exception as e:
            return {"check": "score_queue", "status": "error", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 6 — Espaço em disco
    # ─────────────────────────────────────────────
    def check_disk(self) -> dict:
        try:
            total, used, free = shutil.disk_usage(_BASE_DIR)
            free_mb = free // (1024 * 1024)
            used_pct = (used / total) * 100
            status = "error" if free_mb < 200 else ("warning" if free_mb < 500 else "ok")
            return {
                "check": "disk",
                "status": status,
                "details": {
                    "free_mb": free_mb,
                    "used_pct": round(used_pct, 1),
                    "total_gb": round(total / (1024 ** 3), 1),
                },
            }
        except Exception as e:
            return {"check": "disk", "status": "warning", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 7 — Logs sem erros críticos recentes
    # ─────────────────────────────────────────────
    def check_logs(self) -> dict:
        try:
            log_dir = os.path.join(_BASE_DIR, "logs")
            critical_count = 0
            sample_errors = []

            if os.path.exists(log_dir):
                for fname in os.listdir(log_dir):
                    if not fname.endswith(".log"):
                        continue
                    fpath = os.path.join(log_dir, fname)
                    if time.time() - os.path.getmtime(fpath) > 7200:
                        continue
                    with open(fpath, "r", errors="ignore") as f:
                        lines = f.readlines()
                    for line in lines[-100:]:
                        if "CRITICAL" in line or "Traceback" in line:
                            critical_count += 1
                            if len(sample_errors) < 3:
                                sample_errors.append(line.strip()[:120])

            status = "error" if critical_count > 5 else ("warning" if critical_count > 0 else "ok")
            return {
                "check": "logs",
                "status": status,
                "details": {
                    "erros_criticos_2h": critical_count,
                    "amostra": sample_errors,
                },
            }
        except Exception as e:
            return {"check": "logs", "status": "warning", "details": {"error": str(e)}}

    # ─────────────────────────────────────────────
    # CHECK 8 — Frontend respondendo
    # ─────────────────────────────────────────────
    def check_frontend(self) -> dict:
        try:
            r = requests.get(FRONTEND_URL, timeout=5)
            return {
                "check": "frontend",
                "status": "ok" if r.status_code < 400 else "warning",
                "details": {"url": FRONTEND_URL, "status_code": r.status_code},
            }
        except Exception as e:
            return {
                "check": "frontend",
                "status": "warning",
                "details": {"error": str(e), "note": "frontend pode estar desligado"},
            }

    # ─────────────────────────────────────────────
    # EXECUÇÃO PRINCIPAL
    # ─────────────────────────────────────────────
    def run(self, context: dict = None) -> dict:
        start = time.time()
        self.logger.info("=== QA Agent iniciando verificacao completa ===")

        check_results = [
            self.check_database(),
            self.check_scrapers(),
            self.check_api(),
            self.check_processes(),
            self.check_score_queue(),
            self.check_disk(),
            self.check_logs(),
            self.check_frontend(),
        ]

        failures = [c for c in check_results if c["status"] == "error"]
        warnings = [c for c in check_results if c["status"] == "warning"]
        passed = [c for c in check_results if c["status"] == "ok"]

        overall = "error" if failures else ("warning" if warnings else "ok")
        duration = round(time.time() - start, 2)

        report = {
            "overall_status": overall,
            "checks": check_results,
            "failures": [c["check"] for c in failures],
            "warnings": [c["check"] for c in warnings],
            "passed": len(passed),
            "total_checks": len(check_results),
            "duration_seconds": duration,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(
            f"QA: {overall.upper()} | "
            f"{len(passed)} ok | {len(warnings)} warnings | {len(failures)} errors | {duration}s"
        )

        if failures or warnings:
            self._send_alert(report, failures, warnings)

        self.log_action(
            "qa_check", overall,
            {"passed": len(passed), "failures": len(failures), "warnings": len(warnings)},
            int(duration * 1000),
        )

        return report

    def _send_alert(self, report: dict, failures: list, warnings: list):
        from notifiers.notifier_telegram import enviar_telegram

        emoji = "🔴" if failures else "🟡"
        overall = report["overall_status"].upper()

        lines = [
            f"{emoji} *Job Agent — Alerta QA*",
            f"Status: *{overall}*",
            f"Horario: {datetime.now().strftime('%d/%m %H:%M')}",
            "",
        ]

        if failures:
            lines.append("Falhas criticas:")
            for f in failures:
                lines.append(f"  - {f['check']}")
                det = f.get("details", {})
                if "error" in det:
                    lines.append(f"    {str(det['error'])[:80]}")
            lines.append("")

        if warnings:
            lines.append("Avisos:")
            for w in warnings:
                lines.append(f"  - {w['check']}")
            lines.append("")

        lines.append(f"Checks ok: {report['passed']}/{report['total_checks']}")

        try:
            enviar_telegram("\n".join(lines))
        except Exception as e:
            self.logger.error(f"Falha ao enviar alerta QA: {e}")

    def run_single(self, check_name: str) -> dict:
        """Executa apenas um check pelo nome."""
        check_map = {
            "database": self.check_database,
            "scrapers": self.check_scrapers,
            "api": self.check_api,
            "processes": self.check_processes,
            "score_queue": self.check_score_queue,
            "disk": self.check_disk,
            "logs": self.check_logs,
            "frontend": self.check_frontend,
        }
        fn = check_map.get(check_name)
        if not fn:
            return {"error": f"check '{check_name}' nao encontrado", "available": list(check_map)}
        return fn()
