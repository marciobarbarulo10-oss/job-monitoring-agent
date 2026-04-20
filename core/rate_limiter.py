"""
core/rate_limiter.py — Rate limiter por domínio para evitar bloqueios nos scrapers.
"""
import time
import random
import threading
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter por domínio com jitter aleatório para evitar padrões detectáveis."""

    def __init__(self):
        self._last_request: dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
        self.min_intervals: dict[str, float] = {
            "linkedin.com": 8.0,
            "indeed.com": 5.0,
            "gupy.io": 2.0,
            "vagas.com": 4.0,
            "default": 3.0,
        }

    def wait(self, domain: str) -> None:
        """Aguarda o intervalo mínimo necessário para o domínio antes de prosseguir."""
        min_interval = self.min_intervals.get(domain, self.min_intervals["default"])
        jitter = random.uniform(0, min_interval * 0.5)

        with self._lock:
            elapsed = time.time() - self._last_request[domain]
            wait_time = max(0.0, min_interval + jitter - elapsed)
            if wait_time > 0:
                logger.debug(f"RateLimiter [{domain}]: aguardando {wait_time:.1f}s")
                time.sleep(wait_time)
            self._last_request[domain] = time.time()


rate_limiter = RateLimiter()
