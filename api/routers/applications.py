"""Rotas de candidaturas (vagas com aplicada=1)."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.db import get_db, fmt_dt

router = APIRouter()

VALID_STATUS = {
    "nova", "aplicada", "em_analise", "entrevista",
    "rejeitada", "encerrada", "proposta", "cv_gerado",
}


class StatusUpdate(BaseModel):
    status: str
    notas: str = ""


@router.get("/")
def list_applications():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, titulo, empresa, status, data_aplicacao, last_check, url, notas, score, "
        "cover_letter, cv_recommended "
        "FROM vagas WHERE aplicada=1 ORDER BY data_aplicacao DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "titulo": r["titulo"],
            "empresa": r["empresa"] or "—",
            "status": r["status"],
            "score": r["score"],
            "data_aplicacao": fmt_dt(r["data_aplicacao"]),
            "last_check": fmt_dt(r["last_check"]),
            "url": r["url"],
            "notas": r["notas"] or "",
            "cover_letter_used": r["cover_letter"] or "",
            "cv_version": r["cv_recommended"] or "",
        }
        for r in rows
    ]


@router.post("/{job_id}/status")
def update_status(job_id: int, body: StatusUpdate):
    if body.status not in VALID_STATUS:
        raise HTTPException(400, f"Status invalido: {body.status}")
    conn = get_db()
    row = conn.execute("SELECT status FROM vagas WHERE id=?", (job_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Vaga nao encontrada")
    old_status = row["status"]
    now = datetime.utcnow().isoformat()
    conn.execute("UPDATE vagas SET status=?, data_update=? WHERE id=?", (body.status, now, job_id))
    if body.notas:
        conn.execute("UPDATE vagas SET notas=? WHERE id=?", (body.notas, job_id))
    conn.execute(
        "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
        "VALUES (?, ?, ?, ?, 'Atualizado via API')",
        (job_id, old_status, body.status, now),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.get("/{job_id}/history")
def get_history(job_id: int):
    conn = get_db()
    rows = conn.execute(
        "SELECT status_old, status_new, timestamp, detalhes "
        "FROM status_history WHERE vaga_id=? ORDER BY timestamp DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [
        {
            "status_old": r["status_old"],
            "status_new": r["status_new"],
            "timestamp": fmt_dt(r["timestamp"]),
            "detalhes": r["detalhes"] or "",
        }
        for r in rows
    ]
