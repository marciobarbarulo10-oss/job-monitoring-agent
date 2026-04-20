"""
core/logger.py — Configuração centralizada de logging com rotação de arquivo.
"""
import logging
import logging.handlers
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    """Configura logging com rotação de arquivo (10 MB, 5 backups) e saída no terminal."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "agent.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    for noisy in ("urllib3", "httpx", "httpcore", "asyncio", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
