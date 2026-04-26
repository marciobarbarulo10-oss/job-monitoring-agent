"""Conexão SQLite compartilhada pela API FastAPI."""
import sqlite3
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")


def get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fmt_dt(val) -> str:
    if not val:
        return ""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(val)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)
