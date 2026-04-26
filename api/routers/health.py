"""
api/routers/health.py — Endpoints de saúde e QA do sistema.

GET  /health/           — health check rápido
GET  /health/status     — métricas resumidas
GET  /health/qa         — QA completo (todos os 8 checks)
GET  /health/qa/{check} — um check específico
GET  /health/git/status — status do repositório git
POST /health/git/push   — dispara push manual para o GitHub
"""
from datetime import datetime, timedelta
from fastapi import APIRouter
from api.db import get_db

router = APIRouter()

_qa_agent = None
_git_agent = None


def _get_qa():
    global _qa_agent
    if _qa_agent is None:
        from agents.agent_qa import QAAgent
        _qa_agent = QAAgent()
    return _qa_agent


def _get_git():
    global _git_agent
    if _git_agent is None:
        from agents.agent_git import GitAgent
        _git_agent = GitAgent()
    return _git_agent


@router.get("/")
def health_check():
    """Health check rápido — verifica apenas o banco."""
    try:
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
        conn.close()
        return {
            "status": "ok",
            "version": "3.0.0",
            "timestamp": datetime.now().isoformat(),
            "db": {"status": "ok", "total_vagas": count},
        }
    except Exception as e:
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "db": {"status": "error", "error": str(e)},
        }


@router.get("/status")
def system_status():
    """Métricas resumidas para monitoramento externo."""
    try:
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        new_24h = conn.execute(
            "SELECT COUNT(*) FROM vagas WHERE data_encontrada >= ?", (cutoff,)
        ).fetchone()[0]
        candidaturas = conn.execute(
            "SELECT COUNT(*) FROM vagas WHERE aplicada=1"
        ).fetchone()[0]
        conn.close()
        return {
            "status": "operational",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "total_vagas": total,
                "novas_24h": new_24h,
                "candidaturas": candidaturas,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/qa")
def full_qa():
    """Executa QA completo com todos os 8 checks (pode demorar ~5-10s)."""
    return _get_qa().run()


@router.get("/qa/{check_name}")
def single_qa(check_name: str):
    """Executa apenas um check específico pelo nome."""
    return _get_qa().run_single(check_name)


@router.get("/git/status")
def git_status():
    """Retorna status do repositório git."""
    git = _get_git()
    return {
        "branch": git.branch,
        "has_changes": git.has_changes(),
        "changed_files": git.changed_files(),
        "remote_url": git.remote_url(),
    }


@router.post("/git/push")
def git_push(message: str = None):
    """Dispara push manual para o GitHub."""
    return _get_git().run(context={"message": message, "notify": True})
