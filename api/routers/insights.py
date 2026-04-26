"""Rota de insights de mercado."""
from fastapi import APIRouter
from core.market_intelligence import MarketIntelligence

router = APIRouter()


@router.get("/market")
def get_market_report():
    mi = MarketIntelligence()
    report = mi.get_latest_report()
    if not report:
        return {"message": "Nenhum relatorio disponivel. Execute o ciclo semanal primeiro."}
    return report


@router.post("/market/generate")
def generate_market_report():
    from intelligence.market_insights import generate_weekly_insights
    report = generate_weekly_insights()
    return report


@router.get("/agent-logs")
def get_agent_logs(limit: int = 50):
    from api.db import get_db
    import json
    conn = get_db()
    rows = conn.execute(
        "SELECT agent_name, action, status, details, duration_ms, created_at "
        "FROM agent_logs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "agent": r["agent_name"],
            "action": r["action"],
            "status": r["status"],
            "details": json.loads(r["details"] or "{}"),
            "duration_ms": r["duration_ms"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
