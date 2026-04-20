"""
opportunity_detector.py — Detecta vagas publicadas há menos de 48h.
Aplica boost de score e gera alertas para candidatura antecipada.
"""
import re
import sqlite3
import os
from datetime import datetime, timedelta
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

EARLY_WINDOW_HOURS = 48
SCORE_BOOST = 1.0

_PATTERNS = [
    (r"há\s*(\d+)\s*hora", lambda m: timedelta(hours=int(m.group(1)))),
    (r"(\d+)\s*hour",       lambda m: timedelta(hours=int(m.group(1)))),
    (r"há\s*(\d+)\s*dia",   lambda m: timedelta(days=int(m.group(1)))),
    (r"(\d+)\s*day",        lambda m: timedelta(days=int(m.group(1)))),
    (r"ontem|yesterday",    lambda m: timedelta(days=1)),
    (r"hoje|today|just posted|agora|just now|recém publicada", lambda m: timedelta(minutes=30)),
    (r"há\s*(\d+)\s*semana", lambda m: timedelta(weeks=int(m.group(1)))),
    (r"(\d+)\s*week",        lambda m: timedelta(weeks=int(m.group(1)))),
    (r"há\s*(\d+)\s*mês|há\s*(\d+)\s*mes", lambda m: timedelta(days=30 * int(m.group(1) or m.group(2)))),
    (r"(\d+)\s*month",       lambda m: timedelta(days=30 * int(m.group(1)))),
]


def parse_posted_date(texto: str) -> datetime | None:
    """
    Extrai data de publicação de textos relativos como:
    'há 2 dias', '2 days ago', 'posted today', 'ontem', '3 hours ago'.
    """
    if not texto:
        return None

    texto_lower = texto.lower().strip()
    agora = datetime.utcnow()

    for pattern, delta_fn in _PATTERNS:
        m = re.search(pattern, texto_lower)
        if m:
            try:
                return agora - delta_fn(m)
            except Exception:
                continue

    return None


class OpportunityDetector:
    """Detecta janela de oportunidade (< 48h) e aplica boost de score."""

    def check_early_window(self, job: dict) -> bool:
        """
        Verifica se vaga está dentro da janela de 48h.
        Se sim, atualiza is_early_applicant no banco e registra alerta.
        """
        posted_at = job.get("posted_at")

        if not posted_at:
            return False

        if isinstance(posted_at, str):
            try:
                posted_at = datetime.fromisoformat(posted_at)
            except Exception:
                return False

        diff = datetime.utcnow() - posted_at
        horas = diff.total_seconds() / 3600
        is_early = horas < EARLY_WINDOW_HOURS

        if is_early:
            logger.info(f"Janela aberta: '{job.get('titulo', '')}' publicada ha {horas:.1f}h")
            self._update_flag(job)
            self._register_alert(job)

        return is_early

    def apply_boost(self, score: float, is_early: bool) -> float:
        """Aplica +1.0 ao score para vagas dentro da janela (cap em 10.0)."""
        if is_early:
            boosted = min(10.0, score + SCORE_BOOST)
            logger.debug(f"Boost aplicado: {score} → {boosted}")
            return boosted
        return score

    def _update_flag(self, job: dict):
        """Atualiza campo is_early_applicant no banco para a vaga."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            url = job.get("url", "")
            if url:
                conn.execute(
                    "UPDATE vagas SET is_early_applicant=1 WHERE url=?", (url,)
                )
                conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao atualizar early_applicant: {e}")

    def _register_alert(self, job: dict):
        """Registra alerta de janela de oportunidade (evita duplicatas)."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            url = job.get("url", "")
            if url:
                row = conn.execute("SELECT id FROM vagas WHERE url=?", (url,)).fetchone()
                if row:
                    existing = conn.execute(
                        "SELECT id FROM opportunity_alerts WHERE job_id=?", (row[0],)
                    ).fetchone()
                    if not existing:
                        conn.execute(
                            "INSERT INTO opportunity_alerts (job_id, detected_at) VALUES (?, ?)",
                            (row[0], datetime.utcnow().isoformat()),
                        )
                        conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao registrar alerta de oportunidade: {e}")
