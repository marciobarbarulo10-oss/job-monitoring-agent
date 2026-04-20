"""
feedback_engine.py — Registro de outcomes e recalibração de scoring por aprendizado.
Aprende quais características de vagas predizem entrevistas/propostas.
"""
import json
import sqlite3
import os
from datetime import datetime
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

VALID_OUTCOMES = {"entrevista", "rejeicao", "sem_resposta", "proposta"}

_STATUS_MAP = {
    "entrevista": "entrevista",
    "proposta": "proposta",
    "rejeicao": "rejeitada",
    "sem_resposta": "em_analise",
}


class FeedbackEngine:
    """Registra outcomes de candidaturas e calibra pesos de scoring com base nos dados."""

    def register_outcome(self, job_id: int, outcome: str, notes: str = "") -> bool:
        """
        Registra resultado de uma candidatura.
        outcome deve ser: entrevista | rejeicao | sem_resposta | proposta
        """
        if outcome not in VALID_OUTCOMES:
            logger.error(f"Outcome invalido: '{outcome}'. Validos: {sorted(VALID_OUTCOMES)}")
            return False

        try:
            conn = sqlite3.connect(_DB_PATH)

            vaga = conn.execute(
                "SELECT id, titulo, empresa FROM vagas WHERE id=?", (job_id,)
            ).fetchone()

            if not vaga:
                logger.error(f"Vaga ID {job_id} nao encontrada no banco")
                conn.close()
                return False

            conn.execute(
                "INSERT INTO feedback_outcomes (job_id, outcome, outcome_date, notes) VALUES (?, ?, ?, ?)",
                (job_id, outcome, datetime.utcnow().isoformat(), notes),
            )

            novo_status = _STATUS_MAP.get(outcome)
            if novo_status:
                conn.execute(
                    "UPDATE vagas SET status=? WHERE id=?", (novo_status, job_id)
                )

            conn.commit()
            conn.close()

            logger.info(f"Outcome registrado: vaga {job_id} ('{vaga[1]}') → {outcome}")
            return True

        except Exception as e:
            logger.error(f"Erro ao registrar outcome: {e}")
            return False

    def get_outcomes_summary(self) -> dict:
        """Retorna resumo completo dos outcomes registrados."""
        try:
            conn = sqlite3.connect(_DB_PATH)

            por_outcome = conn.execute(
                """SELECT fo.outcome, COUNT(*) as cnt, AVG(v.score) as avg_score
                   FROM feedback_outcomes fo
                   JOIN vagas v ON v.id = fo.job_id
                   GROUP BY fo.outcome""",
            ).fetchall()

            historico_rows = conn.execute(
                """SELECT fo.job_id, v.titulo, v.empresa, fo.outcome,
                          fo.outcome_date, fo.notes, v.score
                   FROM feedback_outcomes fo
                   JOIN vagas v ON v.id = fo.job_id
                   ORDER BY fo.outcome_date DESC LIMIT 50""",
            ).fetchall()

            conn.close()

            resumo_por_outcome = {
                row[0]: {
                    "count": row[1],
                    "avg_score": round(row[2], 1) if row[2] else 0,
                }
                for row in por_outcome
            }

            historico = [
                {
                    "job_id": r[0],
                    "titulo": r[1],
                    "empresa": r[2],
                    "outcome": r[3],
                    "data": r[4],
                    "notes": r[5] or "",
                    "score": r[6],
                }
                for r in historico_rows
            ]

            total = sum(v["count"] for v in resumo_por_outcome.values())
            entrevistas = resumo_por_outcome.get("entrevista", {}).get("count", 0)
            propostas = resumo_por_outcome.get("proposta", {}).get("count", 0)

            return {
                "por_outcome": resumo_por_outcome,
                "historico": historico,
                "total_feedbacks": total,
                "taxa_entrevista": round(entrevistas / total * 100, 1) if total else 0,
                "taxa_proposta": round(propostas / total * 100, 1) if total else 0,
            }

        except Exception as e:
            logger.error(f"Erro ao buscar outcomes: {e}")
            return {
                "por_outcome": {}, "historico": [], "total_feedbacks": 0,
                "taxa_entrevista": 0, "taxa_proposta": 0,
            }

    def recalibrate(self, min_samples: int = 5) -> dict:
        """
        Recalibra modelo com base nos outcomes coletados.
        Análise por faixas de score: qual faixa converte mais em entrevistas?
        """
        try:
            conn = sqlite3.connect(_DB_PATH)
            rows = conn.execute(
                """SELECT v.score, fo.outcome, v.modalidade, v.fonte
                   FROM feedback_outcomes fo
                   JOIN vagas v ON v.id = fo.job_id""",
            ).fetchall()
            conn.close()

            if len(rows) < min_samples:
                logger.info(f"Amostras insuficientes: {len(rows)} < {min_samples}")
                return {
                    "status": "amostras_insuficientes",
                    "amostras": len(rows),
                    "minimo": min_samples,
                }

            faixas: dict[str, dict] = {
                "0-3": {"positivo": 0, "total": 0},
                "3-5": {"positivo": 0, "total": 0},
                "5-7": {"positivo": 0, "total": 0},
                "7-10": {"positivo": 0, "total": 0},
            }

            for score, outcome, *_ in rows:
                score = score or 0.0
                if score < 3:
                    faixa = "0-3"
                elif score < 5:
                    faixa = "3-5"
                elif score < 7:
                    faixa = "5-7"
                else:
                    faixa = "7-10"

                faixas[faixa]["total"] += 1
                if outcome in ("entrevista", "proposta"):
                    faixas[faixa]["positivo"] += 1

            calibration = {}
            for faixa, data in faixas.items():
                if data["total"] > 0:
                    taxa = round(data["positivo"] / data["total"] * 100, 1)
                    calibration[faixa] = {
                        "taxa_conversao_pct": taxa,
                        "amostras": data["total"],
                        "positivos": data["positivo"],
                    }

            insight = self._generate_insight(calibration)
            self._save_calibration(calibration, len(rows))

            logger.info(f"Calibracao concluida: {len(rows)} amostras, insight: {insight}")
            return {
                "status": "calibrado",
                "amostras": len(rows),
                "calibration": calibration,
                "insight": insight,
            }

        except Exception as e:
            logger.error(f"Erro na calibracao: {e}")
            return {"status": "erro", "erro": str(e)}

    def _generate_insight(self, calibration: dict) -> str:
        """Gera insight textual da calibração."""
        insights = []
        dados = [(f, d) for f, d in calibration.items() if d["amostras"] >= 3]

        if not dados:
            return "Dados insuficientes para gerar insight."

        melhor = max(dados, key=lambda x: x[1]["taxa_conversao_pct"])
        pior = min(dados, key=lambda x: x[1]["taxa_conversao_pct"])

        if melhor[1]["taxa_conversao_pct"] > 0:
            insights.append(
                f"Vagas com score {melhor[0]} tem {melhor[1]['taxa_conversao_pct']}% de conversao em entrevista."
            )
        if pior[1]["taxa_conversao_pct"] < 20:
            insights.append(
                f"Vagas com score {pior[0]} convertem apenas {pior[1]['taxa_conversao_pct']}% — considere elevar o score minimo."
            )

        return " ".join(insights)

    def _save_calibration(self, calibration: dict, sample_size: int):
        """Persiste calibração no banco para consulta futura."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            for faixa, data in calibration.items():
                conn.execute(
                    """INSERT OR REPLACE INTO score_calibration (feature, weight, updated_at, sample_size)
                       VALUES (?, ?, ?, ?)""",
                    (
                        f"score_faixa_{faixa}",
                        data["taxa_conversao_pct"],
                        datetime.utcnow().isoformat(),
                        sample_size,
                    ),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao salvar calibracao: {e}")
