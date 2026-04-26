"""
agents — Sistema multi-agentes do Job Agent v3.0.
Cada agente tem responsabilidade única e reporta ao Orquestrador.
"""
import json
import logging
import sqlite3
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    def log_action(self, action: str, status: str, details: dict = None, duration_ms: int = None):
        try:
            conn = sqlite3.connect(_DB_PATH)
            conn.execute(
                "INSERT INTO agent_logs (agent_name, action, status, details, duration_ms) "
                "VALUES (?, ?, ?, ?, ?)",
                (self.name, action, status, json.dumps(details or {}, ensure_ascii=False), duration_ms),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.debug(f"Falha ao registrar log do agente: {e}")

    def run(self, context: dict = None) -> dict:
        raise NotImplementedError
