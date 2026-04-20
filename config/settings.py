"""
config/settings.py — Configuração centralizada do Job Agent v2.0.
Todas as variáveis de ambiente são lidas aqui e expostas via objeto settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("SEMANTIC_MODEL", "claude-haiku-4-5-20251001")
    ENABLE_SEMANTIC_SCORING: bool = os.getenv("ENABLE_SEMANTIC_SCORING", "true").lower() == "true"

    # Scoring
    MIN_SCORE_TO_NOTIFY: float = float(os.getenv("MIN_SCORE_TO_NOTIFY", "6.0"))
    MIN_SCORE_AUTO_CV: float = float(os.getenv("MIN_SCORE_AUTO_CV", "7.0"))
    SCORE_DISCARD_BELOW: float = float(os.getenv("SCORE_DISCARD_BELOW", "2.0"))

    # Scheduler
    CHECK_INTERVAL_HOURS: int = int(os.getenv("CHECK_INTERVAL_HOURS", "6"))

    # Paths
    DB_PATH: Path = BASE_DIR / "data" / "job_agent.db"
    OUTPUT_DIR: Path = BASE_DIR / "output"
    LOGS_DIR: Path = BASE_DIR / "logs"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"

    # App
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"


settings = Settings()
