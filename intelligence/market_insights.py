"""
market_insights.py — Fachada sobre MarketIntelligence existente.
Adiciona narrativa LLM quando disponível.
"""
import logging
from core.market_intelligence import MarketIntelligence
from intelligence.llm_client import get_llm_client

logger = logging.getLogger(__name__)


def generate_weekly_insights() -> dict:
    """
    Gera insights de mercado da semana.
    Retorna relatório enriquecido com narrativa LLM se disponível.
    """
    mi = MarketIntelligence()
    report = mi.weekly_report()

    if not report:
        return {"error": "Sem dados suficientes para insights"}

    client = get_llm_client()
    if client.available and report.get("total_vagas", 0) > 0:
        top_empresas = [e["empresa"] for e in report.get("top_empresas", [])[:3]]
        top_kws = [k["keyword"] for k in report.get("top_keywords", [])[:5]]
        prompt = (
            f"Analise os dados de vagas da semana e gere insights estrategicos em 3 frases diretas:\n\n"
            f"Periodo: {report.get('semana', '')}\n"
            f"Total vagas: {report.get('total_vagas', 0)}\n"
            f"Score medio: {report.get('score_medio', 0)}/10\n"
            f"Top empresas: {', '.join(top_empresas)}\n"
            f"Keywords em alta: {', '.join(top_kws)}\n"
            f"Variacao semana: {report.get('variacao_semana_pct', 0)}%\n\n"
            "Mencione: empresa mais ativa, aquecimento/esfriamento do mercado e sugestao de acao."
        )
        narrative = client.complete(prompt, max_tokens=300)
        if narrative:
            report["insights_narrative"] = narrative

    return report
