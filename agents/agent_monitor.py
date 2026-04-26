"""
agent_monitor.py — Agente Monitor.
Verifica se vagas candidatadas ainda existem via HTTP HEAD.
Detecta vagas removidas e atualiza is_verified + status.
"""
import time
import logging
import sqlite3
import os
import requests as _req
from datetime import datetime, timedelta
from agents import BaseAgent

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

_SESSION = _req.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})


class MonitorAgent(BaseAgent):
    def __init__(self):
        super().__init__("monitor")

    def run(self, context: dict = None) -> dict:
        """
        Verifica URLs de vagas candidatadas ativas (cheque a cada 24h).
        Marca is_verified=0 e status='encerrada' se URL retornar 404/410.
        """
        start = time.time()
        yesterday = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, url, titulo, empresa, status FROM vagas "
            "WHERE aplicada=1 AND status NOT IN ('rejeitada','encerrada','proposta') "
            "AND (last_verified_at IS NULL OR last_verified_at < ?) "
            "AND url IS NOT NULL AND url != '' LIMIT 20",
            (yesterday,),
        ).fetchall()
        conn.close()

        checked = still_live = removed = 0

        for row in rows:
            try:
                resp = _SESSION.head(row["url"], timeout=10, allow_redirects=True)
                is_live = resp.status_code < 400

                conn = sqlite3.connect(_DB_PATH)
                if is_live:
                    conn.execute(
                        "UPDATE vagas SET is_verified=1, last_verified_at=? WHERE id=?",
                        (datetime.utcnow().isoformat(), row["id"]),
                    )
                    still_live += 1
                else:
                    conn.execute(
                        "UPDATE vagas SET is_verified=0, last_verified_at=?, status='encerrada' WHERE id=?",
                        (datetime.utcnow().isoformat(), row["id"]),
                    )
                    conn.execute(
                        "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
                        "VALUES (?, ?, 'encerrada', ?, 'Vaga removida — verificado pelo MonitorAgent')",
                        (row["id"], row["status"], datetime.utcnow().isoformat()),
                    )
                    self.logger.warning(f"Vaga removida: {row['titulo']} @ {row['empresa']}")
                    removed += 1
                conn.commit()
                conn.close()
                checked += 1
                time.sleep(0.5)

            except Exception as e:
                self.logger.debug(f"Erro ao verificar {row['url']}: {e}")

        duration = int((time.time() - start) * 1000)
        result = {"checked": checked, "still_live": still_live, "removed": removed}
        self.log_action("monitor_applications", "success", result, duration)
        return result
