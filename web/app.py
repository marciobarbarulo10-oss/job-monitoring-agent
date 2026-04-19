"""
web/app.py — Dashboard Flask do Job Agent
"""
import os, sys, json, sqlite3
from flask import Flask, render_template, jsonify, request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.profile import PERFIL, calcular_score

app = Flask(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH  = os.path.join(_BASE_DIR, "data", "job_agent.db")


def _get_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _fmt_dt(val):
    if not val:
        return ""
    try:
        dt = datetime.fromisoformat(str(val))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)


# ── ROTAS ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("index.html")


@app.route("/api/metrics")
def api_metrics():
    conn = _get_db()
    c = conn.cursor()

    total      = c.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
    aplicadas  = c.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1").fetchone()[0]
    novas      = c.execute("SELECT COUNT(*) FROM vagas WHERE status='nova'").fetchone()[0]
    encerradas = c.execute("SELECT COUNT(*) FROM vagas WHERE status='encerrada'").fetchone()[0]
    em_analise = c.execute("SELECT COUNT(*) FROM vagas WHERE status='em_analise'").fetchone()[0]
    entrevista = c.execute("SELECT COUNT(*) FROM vagas WHERE status='entrevista'").fetchone()[0]
    rejeitadas = c.execute("SELECT COUNT(*) FROM vagas WHERE status='rejeitada'").fetchone()[0]

    scores = c.execute("SELECT score FROM vagas WHERE score > 0").fetchall()
    conn.close()

    score_vals = [r[0] for r in scores]
    media_score = round(sum(score_vals) / len(score_vals), 1) if score_vals else 0
    acima_6     = len([s for s in score_vals if s >= 6])
    pct_acima_6 = round((acima_6 / len(score_vals) * 100)) if score_vals else 0
    taxa_conv   = round((aplicadas / total * 100), 1) if total else 0

    return jsonify({
        "total": total,
        "aplicadas": aplicadas,
        "novas": novas,
        "encerradas": encerradas,
        "em_analise": em_analise,
        "entrevista": entrevista,
        "rejeitadas": rejeitadas,
        "media_score": media_score,
        "pct_acima_6": pct_acima_6,
        "taxa_conversao": taxa_conv,
        "atualizado_em": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
    })


@app.route("/api/top-vagas")
def api_top_vagas():
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, titulo, empresa, localizacao, score, url, status, aplicada, palavras_chave "
        "FROM vagas WHERE score >= 6 ORDER BY score DESC LIMIT 5"
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        kw = []
        try:
            kw = json.loads(r["palavras_chave"]) if r["palavras_chave"] else []
        except Exception:
            pass
        result.append({
            "id": r["id"],
            "titulo": r["titulo"],
            "empresa": r["empresa"] or "—",
            "localizacao": r["localizacao"] or "—",
            "score": r["score"],
            "url": r["url"],
            "status": r["status"],
            "aplicada": bool(r["aplicada"]),
            "keywords": kw[:6],
        })
    return jsonify(result)


@app.route("/api/vagas")
def api_vagas():
    status_filter = request.args.get("status", "")
    q = request.args.get("q", "").lower()
    page  = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 20))
    offset = (page - 1) * limit

    conn = _get_db()
    where_clauses = []
    params = []

    if status_filter:
        where_clauses.append("status=?")
        params.append(status_filter)
    if q:
        where_clauses.append("(LOWER(titulo) LIKE ? OR LOWER(empresa) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    count_row = conn.execute(f"SELECT COUNT(*) FROM vagas {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT id, titulo, empresa, localizacao, score, url, status, aplicada, "
        f"data_encontrada, data_aplicacao, last_check, fonte "
        f"FROM vagas {where} ORDER BY score DESC, data_encontrada DESC "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "titulo": r["titulo"],
            "empresa": r["empresa"] or "—",
            "localizacao": r["localizacao"] or "—",
            "score": r["score"],
            "url": r["url"],
            "status": r["status"],
            "aplicada": bool(r["aplicada"]),
            "fonte": r["fonte"] or "—",
            "data_encontrada": _fmt_dt(r["data_encontrada"]),
            "data_aplicacao": _fmt_dt(r["data_aplicacao"]),
            "last_check": _fmt_dt(r["last_check"]),
        })
    return jsonify({"vagas": result, "total": count_row, "page": page, "limit": limit})


@app.route("/api/candidaturas")
def api_candidaturas():
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, titulo, empresa, status, data_aplicacao, last_check, url, notas "
        "FROM vagas WHERE aplicada=1 ORDER BY data_aplicacao DESC"
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "titulo": r["titulo"],
            "empresa": r["empresa"] or "—",
            "status": r["status"],
            "data_aplicacao": _fmt_dt(r["data_aplicacao"]),
            "last_check": _fmt_dt(r["last_check"]),
            "url": r["url"],
            "notas": r["notas"] or "",
        })
    return jsonify(result)


@app.route("/api/pipeline")
def api_pipeline():
    conn = _get_db()
    funil = {}
    for stage in ["nova", "aplicada", "em_analise", "entrevista", "rejeitada", "encerrada"]:
        n = conn.execute(
            "SELECT COUNT(*) FROM vagas WHERE status=?", (stage,)
        ).fetchone()[0]
        funil[stage] = n
    conn.close()
    return jsonify(funil)


@app.route("/api/historico/<int:vaga_id>")
def api_historico(vaga_id):
    conn = _get_db()
    rows = conn.execute(
        "SELECT status_old, status_new, timestamp, detalhes "
        "FROM status_history WHERE vaga_id=? ORDER BY timestamp DESC",
        (vaga_id,)
    ).fetchall()
    vaga = conn.execute(
        "SELECT titulo, empresa FROM vagas WHERE id=?", (vaga_id,)
    ).fetchone()
    conn.close()

    hist = [{
        "status_old": r["status_old"],
        "status_new": r["status_new"],
        "timestamp": _fmt_dt(r["timestamp"]),
        "detalhes": r["detalhes"] or "",
    } for r in rows]

    return jsonify({
        "vaga": {"titulo": vaga["titulo"], "empresa": vaga["empresa"]} if vaga else {},
        "historico": hist,
    })


@app.route("/api/marcar-aplicada", methods=["POST"])
def api_marcar_aplicada():
    data = request.get_json()
    vaga_id = data.get("id")
    if not vaga_id:
        return jsonify({"ok": False, "erro": "ID obrigatorio"}), 400

    conn = _get_db()
    try:
        conn.execute(
            "UPDATE vagas SET aplicada=1, status='aplicada', data_aplicacao=? "
            "WHERE id=? AND aplicada=0",
            (datetime.utcnow().isoformat(), vaga_id)
        )
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, 'nova', 'aplicada', ?, 'Marcada via Dashboard')",
            (vaga_id, datetime.utcnow().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@app.route("/api/atualizar-status", methods=["POST"])
def api_atualizar_status():
    data = request.get_json()
    vaga_id    = data.get("id")
    novo_status = data.get("status")
    VALID = {"nova", "aplicada", "em_analise", "entrevista", "rejeitada", "encerrada"}
    if not vaga_id or novo_status not in VALID:
        return jsonify({"ok": False, "erro": "Parametros invalidos"}), 400

    conn = _get_db()
    try:
        row = conn.execute("SELECT status FROM vagas WHERE id=?", (vaga_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "erro": "Vaga nao encontrada"}), 404
        old_status = row["status"]
        conn.execute(
            "UPDATE vagas SET status=?, data_update=? WHERE id=?",
            (novo_status, datetime.utcnow().isoformat(), vaga_id)
        )
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, ?, ?, ?, 'Atualizado via Dashboard')",
            (vaga_id, old_status, novo_status, datetime.utcnow().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

    return jsonify({"ok": True})


@app.route("/api/perfil")
def api_perfil():
    conn = _get_db()
    top_kw_raw = conn.execute(
        "SELECT palavras_chave FROM vagas WHERE palavras_chave IS NOT NULL AND palavras_chave != '' "
        "AND score >= 4 ORDER BY score DESC LIMIT 50"
    ).fetchall()
    conn.close()

    kw_count = {}
    for row in top_kw_raw:
        try:
            kws = json.loads(row[0])
            for k in kws:
                kw_count[k] = kw_count.get(k, 0) + 1
        except Exception:
            pass

    top_kws = sorted(kw_count.items(), key=lambda x: -x[1])[:12]

    # Análise de match forte vs fraco
    perfil_kws = PERFIL["keywords"]
    fortes = [(k, v) for k, v in perfil_kws.items() if v == 3][:6]
    medios  = [(k, v) for k, v in perfil_kws.items() if v == 2][:6]

    return jsonify({
        "nome": PERFIL["nome"],
        "nivel": PERFIL["nivel"],
        "localizacao": PERFIL["localizacao"],
        "aceita_remoto": PERFIL["aceita_remoto"],
        "aceita_hibrido": PERFIL["aceita_hibrido"],
        "fortes": [k for k, _ in fortes],
        "medios": [k for k, _ in medios],
        "top_keywords_vagas": [{"kw": k, "count": c} for k, c in top_kws],
    })


if __name__ == "__main__":
    if not os.path.exists(_DB_PATH):
        print(f"[ERRO] Banco nao encontrado: {_DB_PATH}")
        print("       Execute 'python scheduler.py' primeiro para criar o banco.")
        sys.exit(1)
    print(f"[INFO] Banco: {_DB_PATH}")
    print("[INFO] Dashboard: http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
