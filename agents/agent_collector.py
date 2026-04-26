"""
agent_collector.py — Agente Coletor.
Executa o ciclo completo de coleta + processamento usando o pipeline existente.
"""
import time
import logging
from agents import BaseAgent
from core.agent import buscar_todas_fontes, processar_e_salvar

logger = logging.getLogger(__name__)


class CollectorAgent(BaseAgent):
    def __init__(self):
        super().__init__("collector")

    def run(self, context: dict = None) -> dict:
        """
        Busca vagas em todas as fontes e executa o pipeline completo:
        dedup → quality filter → scoring → persist → notify.
        """
        start = time.time()
        try:
            self.logger.info("Coletando vagas de todas as fontes...")
            vagas_raw = buscar_todas_fontes()
            self.logger.info(f"Fontes retornaram {len(vagas_raw)} vagas")

            stats = processar_e_salvar(vagas_raw)

            duration = int((time.time() - start) * 1000)
            result = {
                "collected": len(vagas_raw),
                "new": stats.get("novas", 0),
                "notified": stats.get("notificadas", 0),
                "cvs": stats.get("cvs_gerados", 0),
                "suspicious": stats.get("suspeitas", 0),
                "errors": [],
            }
            self.log_action("collect_jobs", "success", result, duration)
            return result

        except Exception as e:
            duration = int((time.time() - start) * 1000)
            self.logger.error(f"Erro no CollectorAgent: {e}", exc_info=True)
            result = {"collected": 0, "new": 0, "errors": [str(e)]}
            self.log_action("collect_jobs", "error", result, duration)
            return result
