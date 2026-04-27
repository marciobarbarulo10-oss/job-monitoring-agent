"""
orchestrator.py — Coordenador central do sistema multi-agentes.
Substitui ciclo_completo() do core/agent.py com responsabilidades separadas.
"""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Ciclo padrão:
      1. CollectorAgent  → busca + pipeline completo (score, notify, CV)
      2. MatcherAgent    → cartas de apresentação para vagas high-score
      3. MonitorAgent    → verifica candidaturas ativas
    """

    def __init__(self):
        self.cycle_count = 0
        self._init_agents()

    def _init_agents(self):
        from agents.agent_collector import CollectorAgent
        from agents.agent_matcher import MatcherAgent
        from agents.agent_monitor import MonitorAgent
        from agents.agent_notifier import NotifierAgent
        from agents.agent_qa import QAAgent
        from agents.agent_git import GitAgent
        from agents.agent_marketer import MarketerAgent

        self.collector = CollectorAgent()
        self.matcher = MatcherAgent()
        self.monitor = MonitorAgent()
        self.notifier = NotifierAgent()
        self.qa = QAAgent()
        self.git = GitAgent()
        self.marketer = MarketerAgent()
        logger.info("Orquestrador: todos os agentes inicializados")

    def run_full_cycle(self) -> dict:
        """Executa ciclo completo: coletar → matching/cartas → monitorar."""
        self.cycle_count += 1
        start = time.time()
        ts = datetime.now().strftime("%H%M")
        cycle_id = f"cycle_{self.cycle_count}_{ts}"
        logger.info(f"=== CICLO {cycle_id} INICIADO ===")

        results = {}

        logger.info("[1/3] Coletando e processando vagas...")
        results["collection"] = self.collector.run()

        logger.info("[2/3] Gerando cartas de apresentacao...")
        results["matching"] = self.matcher.run()

        logger.info("[3/3] Monitorando candidaturas ativas...")
        results["monitoring"] = self.monitor.run()

        duration = round(time.time() - start, 1)
        logger.info(
            f"=== CICLO {cycle_id} CONCLUIDO em {duration}s | "
            f"Novas: {results['collection'].get('new', 0)} | "
            f"Cartas: {results['matching'].get('letters_generated', 0)} ==="
        )

        results["duration_seconds"] = duration
        results["cycle_id"] = cycle_id
        return results

    def run_daily_summary(self):
        """Resumo diário via Telegram."""
        self.notifier.run({"type": "daily_summary"})

    def run_weekly_insights(self):
        """Insights semanais via Telegram."""
        self.notifier.run({"type": "weekly_insights"})

    def run_qa_check(self) -> dict:
        """Executa verificação completa de saúde do sistema."""
        return self.qa.run()

    def run_qa_single(self, check_name: str) -> dict:
        """Executa um check específico pelo nome."""
        return self.qa.run_single(check_name)

    def run_git_push(self, message: str = None, notify: bool = True) -> dict:
        """Faz push das mudanças para o GitHub."""
        return self.git.run(context={"message": message, "notify": notify})

    def run_marketing(self) -> dict:
        """Ciclo completo de marketing: newsletter + posts + README + push."""
        return self.marketer.run()
