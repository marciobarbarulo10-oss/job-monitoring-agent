"""
core/utils.py — Utilitários compartilhados: retry decorator e helpers.
"""
import functools
import time
import logging

logger = logging.getLogger(__name__)


def retry(max_attempts: int = 3, delay: float = 5, backoff: float = 2, exceptions=(Exception,)):
    """Decorator de retry com backoff exponencial."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            wait = delay
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt == max_attempts:
                        raise
                    logger.warning(f"Tentativa {attempt} falhou em {func.__name__}: {e}. Aguardando {wait:.0f}s...")
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator
