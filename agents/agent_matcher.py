"""
agent_matcher.py — Agente de Matching.
Gera cartas de apresentação para vagas com score alto que ainda não têm carta.
O scoring principal já é feito pelo CollectorAgent via SemanticScorer.
"""
import time
import json
import sqlite3
import logging
import os
from agents import BaseAgent
from intelligence.cover_letter import generate_cover_letter
from intelligence.scorer import score_job_with_ai

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

MIN_SCORE_LETTER = float(os.getenv("MIN_SCORE_AUTO_CV", "7.0"))


class MatcherAgent(BaseAgent):
    def __init__(self):
        super().__init__("matcher")

    def run(self, context: dict = None) -> dict:
        """
        Gera cartas de apresentação para vagas com score alto sem carta ainda.
        Também re-processa vagas sem score_method definido.
        """
        start = time.time()
        letters_generated = 0
        rescored = 0

        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row

        # 1. Vagas sem score ainda (salvas de forma incompleta)
        rows_no_score = conn.execute(
            "SELECT id, titulo, empresa, localizacao, descricao, fonte, url "
            "FROM vagas WHERE (score_method IS NULL OR score_method='') AND status='nova' LIMIT 30"
        ).fetchall()
        conn.close()

        for row in rows_no_score:
            job = dict(row)
            try:
                score_data = score_job_with_ai(job)
                score_raw = json.dumps(score_data, ensure_ascii=False)
                conn = sqlite3.connect(_DB_PATH)
                conn.execute(
                    "UPDATE vagas SET score=?, score_grade=?, score_analysis=?, "
                    "score_method=?, score_matched_kws=?, score_missing_kws=? WHERE id=?",
                    (
                        score_data["score"],
                        score_data["grade"],
                        score_data["reasoning"],
                        score_data["score_method"],
                        json.dumps(score_data["strengths"], ensure_ascii=False),
                        json.dumps(score_data["gaps"], ensure_ascii=False),
                        job["id"],
                    ),
                )
                conn.commit()
                conn.close()
                rescored += 1
            except Exception as e:
                self.logger.error(f"Erro ao re-score vaga {row['id']}: {e}")

        # 2. Vagas com score alto sem carta gerada
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows_no_letter = conn.execute(
            "SELECT id, titulo, empresa, localizacao, descricao, fonte, url, "
            "score, score_grade, score_analysis, score_matched_kws, score_missing_kws "
            "FROM vagas WHERE score >= ? AND (cover_letter IS NULL OR cover_letter='') "
            "AND status NOT IN ('suspeita','encerrada') LIMIT 20",
            (MIN_SCORE_LETTER,),
        ).fetchall()
        conn.close()

        for row in rows_no_letter:
            job = dict(row)
            try:
                score_data = {
                    "score": job.get("score", 0),
                    "grade": job.get("score_grade", ""),
                    "match_pct": int((job.get("score") or 0) * 10),
                    "strengths": json.loads(job.get("score_matched_kws") or "[]"),
                    "gaps": json.loads(job.get("score_missing_kws") or "[]"),
                    "reasoning": job.get("score_analysis", ""),
                }
                letter = generate_cover_letter(job, score_data)
                conn = sqlite3.connect(_DB_PATH)
                conn.execute("UPDATE vagas SET cover_letter=? WHERE id=?", (letter, job["id"]))
                conn.commit()
                conn.close()
                letters_generated += 1
                self.logger.info(f"Carta gerada: {job['titulo']} @ {job['empresa']}")
            except Exception as e:
                self.logger.error(f"Erro ao gerar carta para vaga {row['id']}: {e}")

        duration = int((time.time() - start) * 1000)
        result = {"rescored": rescored, "letters_generated": letters_generated}
        self.log_action("match_jobs", "success", result, duration)
        return result
