"""
pipeline_integrity.py — Deduplicação, normalização e saúde do pipeline de vagas.
Executado semanalmente para garantir consistência do banco de dados.
"""
import sqlite3
import os
from datetime import datetime
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

_STATUS_ALIAS = {
    "novo": "nova",
    "new": "nova",
    "aplicado": "aplicada",
    "applied": "aplicada",
    "interview": "entrevista",
    "rejected": "rejeitada",
    "closed": "encerrada",
    "offer": "proposta",
    "waiting": "em_analise",
}

_STATUS_CANONICOS = {
    "nova", "avaliada", "cv_gerado", "aplicada", "em_analise",
    "entrevista", "proposta", "rejeitada", "desistencia", "suspeita", "encerrada",
}


class PipelineIntegrity:
    """Garante integridade, normalização e saúde do pipeline de vagas."""

    def dedup_jobs(self) -> int:
        """
        Remove duplicatas por título+empresa. Mantém o registro com maior descrição.
        Retorna quantidade de registros removidos.
        """
        removidos = 0
        try:
            conn = sqlite3.connect(_DB_PATH)

            grupos = conn.execute(
                """SELECT LOWER(TRIM(titulo)) as t, LOWER(TRIM(COALESCE(empresa,''))) as e,
                          COUNT(*) as cnt
                   FROM vagas
                   WHERE titulo IS NOT NULL AND TRIM(titulo) != ''
                   GROUP BY t, e
                   HAVING cnt > 1""",
            ).fetchall()

            for titulo, empresa, cnt in grupos:
                rows = conn.execute(
                    """SELECT id, LENGTH(COALESCE(descricao,'')) as dl
                       FROM vagas
                       WHERE LOWER(TRIM(titulo))=? AND LOWER(TRIM(COALESCE(empresa,'')))=?
                       ORDER BY dl DESC, data_encontrada ASC""",
                    (titulo, empresa),
                ).fetchall()

                ids_remover = [r[0] for r in rows[1:]]
                for id_rem in ids_remover:
                    conn.execute(
                        "DELETE FROM status_history WHERE vaga_id=?", (id_rem,)
                    )
                    conn.execute("DELETE FROM vagas WHERE id=?", (id_rem,))
                    removidos += 1

            conn.commit()
            conn.close()

            if removidos:
                logger.info(f"Deduplicacao: {removidos} registros removidos")

        except Exception as e:
            logger.error(f"Erro na deduplicacao: {e}")

        return removidos

    def normalize_statuses(self) -> int:
        """Mapeia status não-canônicos para seus equivalentes canônicos."""
        normalizados = 0
        try:
            conn = sqlite3.connect(_DB_PATH)
            vagas = conn.execute("SELECT id, status FROM vagas").fetchall()

            for vaga_id, status in vagas:
                s = (status or "").lower().strip()
                if s in _STATUS_ALIAS:
                    conn.execute(
                        "UPDATE vagas SET status=? WHERE id=?",
                        (_STATUS_ALIAS[s], vaga_id),
                    )
                    normalizados += 1
                elif s and s not in _STATUS_CANONICOS:
                    conn.execute(
                        "UPDATE vagas SET status='nova' WHERE id=?", (vaga_id,)
                    )
                    normalizados += 1

            conn.commit()
            conn.close()

            if normalizados:
                logger.info(f"Normalize: {normalizados} status normalizados")

        except Exception as e:
            logger.error(f"Erro na normalizacao: {e}")

        return normalizados

    def health_check(self) -> dict:
        """Diagnóstico de saúde do pipeline com métricas-chave."""
        try:
            conn = sqlite3.connect(_DB_PATH)

            total = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
            sem_score = conn.execute(
                "SELECT COUNT(*) FROM vagas WHERE score=0 OR score IS NULL"
            ).fetchone()[0]
            sem_status = conn.execute(
                "SELECT COUNT(*) FROM vagas WHERE status IS NULL OR TRIM(status)=''"
            ).fetchone()[0]
            aplicadas = conn.execute(
                "SELECT COUNT(*) FROM vagas WHERE aplicada=1"
            ).fetchone()[0]

            # Duplicatas detectadas (grupos com mais de 1 registro)
            duplicatas = conn.execute(
                """SELECT COUNT(*) FROM (
                   SELECT LOWER(TRIM(titulo)), LOWER(TRIM(COALESCE(empresa,'')))
                   FROM vagas
                   WHERE titulo IS NOT NULL
                   GROUP BY 1, 2 HAVING COUNT(*) > 1
                )""",
            ).fetchone()[0]

            # CVs órfãos (arquivo deletado mas registro no banco)
            cvs_orfaos = 0
            try:
                cv_rows = conn.execute("SELECT file_path FROM cv_exports").fetchall()
                cvs_orfaos = sum(1 for (fp,) in cv_rows if fp and not os.path.exists(fp))
            except Exception:
                pass

            conn.close()

            taxa_conv = round(aplicadas / total * 100, 1) if total else 0.0
            status = "saudavel" if duplicatas == 0 and sem_status == 0 else "atencao"

            return {
                "total_jobs": total,
                "jobs_sem_score": sem_score,
                "jobs_sem_status": sem_status,
                "duplicatas_detectadas": duplicatas,
                "cvs_orfaos": cvs_orfaos,
                "taxa_conversao": taxa_conv,
                "status": status,
            }

        except Exception as e:
            logger.error(f"Erro no health check: {e}")
            return {"erro": str(e), "status": "erro"}

    def run_maintenance(self) -> dict:
        """Executa dedup + normalize + health_check e retorna relatório completo."""
        logger.info("Iniciando manutencao semanal do pipeline...")
        start = datetime.utcnow()

        removidos = self.dedup_jobs()
        normalizados = self.normalize_statuses()
        saude = self.health_check()

        relatorio = {
            "executado_em": start.isoformat(),
            "duracao_s": round((datetime.utcnow() - start).total_seconds(), 1),
            "duplicatas_removidas": removidos,
            "status_normalizados": normalizados,
            "saude": saude,
        }

        logger.info(f"Manutencao concluida: {relatorio}")
        return relatorio
