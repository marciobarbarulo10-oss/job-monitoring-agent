"""
agent_notifier.py — Agente Notificador.
Envia resumos diários e insights semanais via Telegram.
Notificação de novas vagas já é feita pelo CollectorAgent.
"""
import logging
from agents import BaseAgent
from notifiers.notifier_telegram import notificar_resumo_diario, notify_weekly_market
from intelligence.market_insights import generate_weekly_insights
from core.agent import gerar_resumo

logger = logging.getLogger(__name__)


class NotifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("notifier")

    def run(self, context: dict = None) -> dict:
        """
        context.type:
          'daily_summary'   → resumo diário
          'weekly_insights' → relatório de mercado semanal
        """
        ntype = (context or {}).get("type", "daily_summary")

        if ntype == "daily_summary":
            return self._daily_summary()
        elif ntype == "weekly_insights":
            return self._weekly_insights()
        return {"sent": 0}

    def _daily_summary(self) -> dict:
        try:
            resumo = gerar_resumo()
            notificar_resumo_diario(resumo)
            self.log_action("daily_summary", "success")
            return {"sent": 1}
        except Exception as e:
            self.logger.error(f"Erro no resumo diário: {e}")
            self.log_action("daily_summary", "error", {"error": str(e)})
            return {"sent": 0}

    def _weekly_insights(self) -> dict:
        try:
            report = generate_weekly_insights()
            if report and not report.get("error"):
                notify_weekly_market(report)
                self.log_action("weekly_insights", "success")
                return {"sent": 1}
            return {"sent": 0}
        except Exception as e:
            self.logger.error(f"Erro nos insights semanais: {e}")
            self.log_action("weekly_insights", "error", {"error": str(e)})
            return {"sent": 0}
