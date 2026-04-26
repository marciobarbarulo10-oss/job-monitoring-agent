"""
scorer.py — Fachada de scoring que delega ao SemanticScorer existente.
Adapta o output para o formato usado pelos agentes v3.0.
"""
import logging
from typing import Optional
from core.semantic_scorer import SemanticScorer

logger = logging.getLogger(__name__)

_scorer: Optional[SemanticScorer] = None


def _get_scorer() -> SemanticScorer:
    global _scorer
    if _scorer is None:
        _scorer = SemanticScorer()
    return _scorer


def score_job_with_ai(job: dict) -> dict:
    """
    Calcula score de aderência da vaga ao perfil.

    Adapta o output do SemanticScorer para o formato dos agentes v3:
      score, grade, match_pct, strengths, gaps, reasoning, recommendation, cv_recommended
    """
    scorer = _get_scorer()
    raw = scorer.score_job(job)

    return {
        "score": raw.get("score", 0.0),
        "grade": raw.get("grade", "F"),
        "match_pct": int(raw.get("score", 0.0) * 10),
        "strengths": raw.get("highlights", []),
        "gaps": raw.get("gaps", []),
        "reasoning": raw.get("match_analysis", ""),
        "recommendation": raw.get("recommendation", ""),
        "cv_recommended": None,
        "score_method": raw.get("score_method", "keyword"),
    }
