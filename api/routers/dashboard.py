"""Rota de dashboard — dados agregados para o frontend React."""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter
from api.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
def get_summary():
    try:
        conn = get_db()

        try:
            total = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0] or 0
        except Exception:
            total = 0

        try:
            high_score = conn.execute("SELECT COUNT(*) FROM vagas WHERE score >= 7").fetchone()[0] or 0
        except Exception:
            high_score = 0

        try:
            notificadas = conn.execute("SELECT COUNT(*) FROM vagas WHERE notificada=1").fetchone()[0] or 0
        except Exception:
            notificadas = 0

        status_counts = {}
        try:
            for row in conn.execute("SELECT status, COUNT(*) FROM vagas GROUP BY status").fetchall():
                status_counts[row[0]] = row[1]
        except Exception:
            pass

        try:
            aplicadas = conn.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1").fetchone()[0] or 0
        except Exception:
            aplicadas = 0

        entrevistas = status_counts.get("entrevista", 0)
        propostas = status_counts.get("proposta", 0)

        try:
            row = conn.execute("SELECT AVG(score) FROM vagas WHERE score > 0").fetchone()
            avg_score = round(row[0] or 0, 1)
        except Exception:
            avg_score = 0.0

        by_source = []
        try:
            by_source = [
                {"fonte": r[0] or "outros", "count": r[1]}
                for r in conn.execute(
                    "SELECT fonte, COUNT(*) FROM vagas GROUP BY fonte ORDER BY COUNT(*) DESC"
                ).fetchall()
            ]
        except Exception:
            pass

        daily_trend = []
        try:
            week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
            daily_trend = [
                {"day": r[0], "count": r[1]}
                for r in conn.execute(
                    "SELECT date(data_encontrada) as day, COUNT(*) FROM vagas "
                    "WHERE date(data_encontrada) >= ? GROUP BY day ORDER BY day",
                    (week_ago,),
                ).fetchall()
            ]
        except Exception:
            pass

        top_today = []
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            for r in conn.execute(
                "SELECT id, titulo, empresa, score, score_grade, url, fonte "
                "FROM vagas WHERE date(data_encontrada) = ? "
                "ORDER BY score DESC LIMIT 5",
                (today,),
            ).fetchall():
                top_today.append({
                    "id": r[0], "titulo": r[1], "empresa": r[2] or "—",
                    "score": r[3], "grade": r[4] or "", "url": r[5], "fonte": r[6] or "—",
                })
        except Exception:
            pass

        try:
            conn.close()
        except Exception:
            pass

        return {
            "funnel": {
                "total_found": total,
                "high_score": high_score,
                "notified": notificadas,
                "applied": aplicadas,
                "interview": entrevistas,
                "offer": propostas,
            },
            "avg_score": avg_score,
            "by_source": by_source,
            "daily_trend": daily_trend,
            "status_counts": status_counts,
            "top_today": top_today,
        }

    except Exception as e:
        logger.error(f"Dashboard summary error: {e}", exc_info=True)
        return {
            "funnel": {
                "total_found": 0, "high_score": 0, "notified": 0,
                "applied": 0, "interview": 0, "offer": 0,
            },
            "avg_score": 0.0,
            "by_source": [],
            "daily_trend": [],
            "status_counts": {},
            "top_today": [],
            "_error": str(e),
        }


@router.get("/growth-stats")
def get_growth_stats():
    """Stats consolidados de crescimento: GitHub + MailerLite + Email Sequence + Job Agent."""
    from datetime import datetime as _dt
    result = {"updated_at": _dt.now().isoformat()}

    try:
        from intelligence.github_client import get_github_client
        result["github"] = get_github_client().get_full_stats()
    except Exception as e:
        result["github"] = {"error": str(e)}

    try:
        from intelligence.mailerlite_client import get_mailerlite_client
        ml = get_mailerlite_client()
        result["mailerlite"] = ml.get_stats() if ml.available else {"available": False}
    except Exception as e:
        result["mailerlite"] = {"error": str(e)}

    try:
        from agents.agent_email_sequence import EmailSequenceAgent
        result["email_sequence"] = EmailSequenceAgent().get_stats()
    except Exception as e:
        result["email_sequence"] = {"error": str(e)}

    try:
        import sqlite3, os
        db = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "job_agent.db")
        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM vagas")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM vagas WHERE status='entrevista'")
        interviews = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1")
        applied = c.fetchone()[0]
        conn.close()
        result["job_agent"] = {"total_jobs": total, "active_applications": applied, "interviews": interviews}
    except Exception as e:
        result["job_agent"] = {"error": str(e)}

    return result


@router.get("/email-sequence-stats")
def get_email_sequence_stats():
    """Stats da sequencia de emails para o dashboard."""
    try:
        from agents.agent_email_sequence import EmailSequenceAgent
        seq = EmailSequenceAgent()
        return {"available": True, "stats": seq.get_stats()}
    except Exception as e:
        return {"available": False, "error": str(e)}


@router.get("/marketing-stats")
def get_marketing_stats():
    """Estatísticas do MailerLite para o painel de Insights."""
    try:
        from intelligence.mailerlite_client import get_mailerlite_client
        ml = get_mailerlite_client()
        stats = ml.get_stats()
        return {
            "available": ml.available,
            "stats": stats,
            "groups": {
                "novos_usuarios": "185866558038345309",
                "usuarios_ativos": "185866565658347071",
                "comunidade_github": "185866574904689757",
            },
        }
    except Exception as e:
        return {"available": False, "error": str(e)}
