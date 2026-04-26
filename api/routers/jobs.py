"""Rotas de vagas para o dashboard React."""
import json
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from api.db import get_db, fmt_dt

router = APIRouter()


@router.get("/")
def list_jobs(
    min_score: float = Query(0.0),
    status: Optional[str] = None,
    fonte: Optional[str] = None,
    grade: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    conn = get_db()
    clauses, params = [], []

    if min_score > 0:
        clauses.append("score >= ?")
        params.append(min_score)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if fonte:
        clauses.append("LOWER(COALESCE(fonte,'')) = ?")
        params.append(fonte.lower())
    if grade:
        clauses.append("score_grade = ?")
        params.append(grade.upper())
    if q:
        clauses.append("(LOWER(titulo) LIKE ? OR LOWER(empresa) LIKE ?)")
        params.extend([f"%{q.lower()}%", f"%{q.lower()}%"])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    total = conn.execute(f"SELECT COUNT(*) FROM vagas {where}", params).fetchone()[0]

    rows = conn.execute(
        f"SELECT id, titulo, empresa, localizacao, score, score_grade, score_analysis, "
        f"url, status, aplicada, palavras_chave, data_encontrada, fonte, modalidade, "
        f"is_early_applicant, score_method, favorited, cover_letter, cv_recommended "
        f"FROM vagas {where} ORDER BY score DESC, data_encontrada DESC "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()

    jobs = []
    for r in rows:
        kws = []
        try:
            kws = json.loads(r["palavras_chave"]) if r["palavras_chave"] else []
        except Exception:
            pass
        jobs.append({
            "id": r["id"],
            "titulo": r["titulo"],
            "empresa": r["empresa"] or "—",
            "localizacao": r["localizacao"] or "—",
            "score": r["score"],
            "grade": r["score_grade"] or "",
            "score_analysis": r["score_analysis"] or "",
            "url": r["url"],
            "status": r["status"],
            "aplicada": bool(r["aplicada"]),
            "keywords": kws[:6],
            "fonte": r["fonte"] or "—",
            "modalidade": r["modalidade"] or "",
            "is_early": bool(r["is_early_applicant"]),
            "score_method": r["score_method"] or "keyword",
            "favorited": bool(r["favorited"]),
            "has_cover_letter": bool(r["cover_letter"]),
            "cv_recommended": r["cv_recommended"],
            "data_encontrada": fmt_dt(r["data_encontrada"]),
        })

    return {"vagas": jobs, "total": total, "limit": limit, "offset": offset}


@router.get("/{job_id}")
def get_job(job_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM vagas WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Vaga nao encontrada")
    job = dict(row)
    for k in ["data_encontrada", "data_aplicacao", "last_check"]:
        job[k] = fmt_dt(job.get(k))
    return job


@router.get("/{job_id}/cover-letter")
def get_cover_letter(job_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT cover_letter, titulo, empresa FROM vagas WHERE id=?", (job_id,)
    ).fetchone()
    conn.close()
    if not row or not row["cover_letter"]:
        raise HTTPException(404, "Carta nao disponivel para esta vaga")
    return {"cover_letter": row["cover_letter"], "titulo": row["titulo"], "empresa": row["empresa"]}
