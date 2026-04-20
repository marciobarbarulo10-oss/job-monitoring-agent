"""
score_explainer.py — Explicação visual do match vaga×perfil.
Funciona 100% grátis via keyword matching; usa dados do SemanticScorer se disponíveis.
"""
import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent


def _load_profile() -> dict:
    try:
        import yaml
        with open(BASE_DIR / "config" / "profile.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        try:
            from config.profile import PERFIL
            return {"skills": {"hard": list(PERFIL.get("keywords", {}).keys())[:25]}}
        except Exception:
            return {}


def _normalize(text: str) -> str:
    """Remove acentos para comparação mais tolerante."""
    mapping = str.maketrans("áàâãäéêëíïîóôõöúûüç", "aaaaaeeeiiiooooouuuc")
    return text.lower().translate(mapping)


class ScoreExplainer:
    """Gera explicação de match/miss para qualquer vaga."""

    def __init__(self):
        self._profile = _load_profile()

    def explain(self, job: dict, score_result: dict = None) -> dict:
        """
        Retorna explicação de match.
        Prioriza dados do SemanticScorer (highlights/gaps).
        Fallback: keyword matching gratuito.
        """
        if score_result and (score_result.get("highlights") or score_result.get("gaps")):
            return {
                "matched": score_result.get("highlights", [])[:8],
                "missing": score_result.get("gaps", [])[:5],
                "recommendation": score_result.get("recommendation", ""),
                "analysis": score_result.get("match_analysis", ""),
                "method": "semantic",
                "match_pct": self._pct_from_score(score_result.get("score", 0)),
            }
        return self._keyword_explain(job)

    def _pct_from_score(self, score: float) -> int:
        return min(100, int(score * 10))

    def _keyword_explain(self, job: dict) -> dict:
        profile = self._profile
        descricao = (job.get("descricao") or "").lower()
        titulo = (job.get("titulo") or "").lower()
        texto = _normalize(f"{titulo} {descricao}")

        hard = profile.get("skills", {}).get("hard", [])
        matched, missing = [], []

        for skill in hard:
            if _normalize(skill) in texto:
                matched.append(skill)
            else:
                missing.append(skill)

        total = len(hard)
        pct = round(len(matched) / total * 100) if total else 0

        if pct >= 60:
            analysis = f"Boa aderência: {len(matched)}/{total} competências encontradas na vaga."
            rec = "aplicar"
        elif pct >= 30:
            analysis = f"Aderência parcial: {len(matched)}/{total} competências mapeadas."
            rec = "aplicar_com_ressalvas"
        else:
            analysis = f"Baixa aderência: apenas {len(matched)}/{total} competências identificadas."
            rec = "avaliar"

        return {
            "matched": matched[:8],
            "missing": missing[:5],
            "recommendation": rec,
            "analysis": analysis,
            "method": "keyword",
            "match_pct": pct,
        }

    def summary_text(self, explanation: dict) -> str:
        """Texto compacto para Telegram e CLI."""
        parts = []
        if explanation.get("matched"):
            parts.append("Match: " + ", ".join(explanation["matched"][:4]))
        if explanation.get("missing"):
            parts.append("Falta: " + ", ".join(explanation["missing"][:3]))
        return " | ".join(parts) or "Sem dados de match."
