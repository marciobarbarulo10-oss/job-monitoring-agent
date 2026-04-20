"""
web/app.py — Dashboard Flask do Job Agent v2.0
"""
import os
import sys
import json
import sqlite3
import logging
import threading
from flask import Flask, render_template, jsonify, request, send_file, abort, Response
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = Flask(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH  = os.path.join(_BASE_DIR, "data", "job_agent.db")
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")

_cycle_running = False
_cycle_lock = threading.Lock()


def _db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt(val):
    if not val:
        return ""
    try:
        return datetime.fromisoformat(str(val)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)


# ── ROTA PRINCIPAL ─────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("index.html")


# ── API: MÉTRICAS ──────────────────────────────────────────────────────────────

@app.route("/api/stats")
@app.route("/api/metrics")
def api_stats():
    conn = _db()
    c = conn.cursor()
    total       = c.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
    aplicadas   = c.execute("SELECT COUNT(*) FROM vagas WHERE aplicada=1").fetchone()[0]
    novas       = c.execute("SELECT COUNT(*) FROM vagas WHERE status='nova'").fetchone()[0]
    encerradas  = c.execute("SELECT COUNT(*) FROM vagas WHERE status='encerrada'").fetchone()[0]
    em_analise  = c.execute("SELECT COUNT(*) FROM vagas WHERE status='em_analise'").fetchone()[0]
    entrevista  = c.execute("SELECT COUNT(*) FROM vagas WHERE status='entrevista'").fetchone()[0]
    rejeitadas  = c.execute("SELECT COUNT(*) FROM vagas WHERE status='rejeitada'").fetchone()[0]
    suspeitas   = c.execute("SELECT COUNT(*) FROM vagas WHERE status='suspeita'").fetchone()[0]
    cv_gerado   = c.execute("SELECT COUNT(*) FROM vagas WHERE status='cv_gerado'").fetchone()[0]
    early       = c.execute("SELECT COUNT(*) FROM vagas WHERE is_early_applicant=1").fetchone()[0]
    high_score  = c.execute("SELECT COUNT(*) FROM vagas WHERE score >= 7").fetchone()[0]
    scores      = [r[0] for r in c.execute("SELECT score FROM vagas WHERE score > 0").fetchall()]
    try:
        cvs_gerados = c.execute("SELECT COUNT(*) FROM cv_exports").fetchone()[0]
    except Exception:
        cvs_gerados = 0
    try:
        feedbacks = c.execute("SELECT COUNT(*) FROM feedback_outcomes").fetchone()[0]
    except Exception:
        feedbacks = 0
    conn.close()

    media = round(sum(scores) / len(scores), 1) if scores else 0
    acima_6 = len([s for s in scores if s >= 6])
    pct_acima_6 = round(acima_6 / len(scores) * 100) if scores else 0
    taxa_conv = round(aplicadas / total * 100, 1) if total else 0

    return jsonify({
        "total": total, "aplicadas": aplicadas, "novas": novas,
        "encerradas": encerradas, "em_analise": em_analise,
        "entrevista": entrevista, "rejeitadas": rejeitadas,
        "suspeitas": suspeitas, "cv_gerado": cv_gerado,
        "early_applicant": early, "high_score": high_score,
        "media_score": media, "pct_acima_6": pct_acima_6,
        "taxa_conversao": taxa_conv, "cvs_gerados": cvs_gerados,
        "feedbacks": feedbacks,
        "atualizado_em": datetime.utcnow().strftime("%d/%m/%Y %H:%M"),
        "cycle_running": _cycle_running,
    })


# ── API: VAGAS ─────────────────────────────────────────────────────────────────

@app.route("/api/jobs")
@app.route("/api/vagas")
def api_vagas():
    status_filter = request.args.get("status", "")
    grade_filter  = request.args.get("grade", "")
    fonte_filter  = request.args.get("fonte", "")
    modal_filter  = request.args.get("modalidade", "")
    q      = request.args.get("q", "").lower()
    page   = int(request.args.get("page", 1))
    limit  = int(request.args.get("limit", 20))
    offset = (page - 1) * limit

    conn = _db()
    clauses, params = [], []

    if status_filter:
        clauses.append("status=?"); params.append(status_filter)
    if grade_filter:
        clauses.append("score_grade=?"); params.append(grade_filter.upper())
    if fonte_filter:
        clauses.append("fonte=?"); params.append(fonte_filter)
    if modal_filter:
        clauses.append("LOWER(modalidade) LIKE ?"); params.append(f"%{modal_filter.lower()}%")
    if q:
        clauses.append("(LOWER(titulo) LIKE ? OR LOWER(empresa) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    total = conn.execute(f"SELECT COUNT(*) FROM vagas {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT id, titulo, empresa, localizacao, score, score_grade, score_analysis, "
        f"url, status, aplicada, palavras_chave, data_encontrada, data_aplicacao, "
        f"last_check, fonte, modalidade, is_early_applicant, score_method "
        f"FROM vagas {where} ORDER BY score DESC, data_encontrada DESC "
        f"LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        kws = []
        try:
            kws = json.loads(r["palavras_chave"]) if r["palavras_chave"] else []
        except Exception:
            pass
        result.append({
            "id": r["id"], "titulo": r["titulo"], "empresa": r["empresa"] or "—",
            "localizacao": r["localizacao"] or "—", "score": r["score"],
            "score_grade": r["score_grade"] or "", "score_analysis": r["score_analysis"] or "",
            "url": r["url"], "status": r["status"], "aplicada": bool(r["aplicada"]),
            "keywords": kws[:6], "fonte": r["fonte"] or "—",
            "modalidade": r["modalidade"] or "", "is_early": bool(r["is_early_applicant"]),
            "score_method": r["score_method"] or "keyword",
            "data_encontrada": _fmt(r["data_encontrada"]),
            "data_aplicacao": _fmt(r["data_aplicacao"]),
            "last_check": _fmt(r["last_check"]),
        })
    return jsonify({"vagas": result, "total": total, "page": page, "limit": limit})


@app.route("/api/top-vagas")
def api_top_vagas():
    conn = _db()
    rows = conn.execute(
        "SELECT id, titulo, empresa, localizacao, score, score_grade, url, status, "
        "aplicada, palavras_chave, is_early_applicant "
        "FROM vagas WHERE score >= 6 ORDER BY score DESC LIMIT 5"
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        kws = []
        try:
            kws = json.loads(r["palavras_chave"]) if r["palavras_chave"] else []
        except Exception:
            pass
        result.append({
            "id": r["id"], "titulo": r["titulo"], "empresa": r["empresa"] or "—",
            "localizacao": r["localizacao"] or "—", "score": r["score"],
            "score_grade": r["score_grade"] or "", "url": r["url"],
            "status": r["status"], "aplicada": bool(r["aplicada"]),
            "keywords": kws[:6], "is_early": bool(r["is_early_applicant"]),
        })
    return jsonify(result)


# ── API: PIPELINE ──────────────────────────────────────────────────────────────

@app.route("/api/pipeline")
def api_pipeline():
    conn = _db()
    funil = {}
    for stage in ["nova", "aplicada", "em_analise", "entrevista", "rejeitada",
                  "encerrada", "suspeita", "cv_gerado", "proposta"]:
        n = conn.execute("SELECT COUNT(*) FROM vagas WHERE status=?", (stage,)).fetchone()[0]
        funil[stage] = n
    conn.close()
    return jsonify(funil)


# ── API: CANDIDATURAS ──────────────────────────────────────────────────────────

@app.route("/api/candidaturas")
def api_candidaturas():
    conn = _db()
    rows = conn.execute(
        "SELECT id, titulo, empresa, status, data_aplicacao, last_check, url, notas "
        "FROM vagas WHERE aplicada=1 ORDER BY data_aplicacao DESC"
    ).fetchall()
    conn.close()
    return jsonify([{
        "id": r["id"], "titulo": r["titulo"], "empresa": r["empresa"] or "—",
        "status": r["status"], "data_aplicacao": _fmt(r["data_aplicacao"]),
        "last_check": _fmt(r["last_check"]), "url": r["url"], "notas": r["notas"] or "",
    } for r in rows])


# ── API: HISTÓRICO ─────────────────────────────────────────────────────────────

@app.route("/api/historico/<int:vaga_id>")
def api_historico(vaga_id):
    conn = _db()
    rows = conn.execute(
        "SELECT status_old, status_new, timestamp, detalhes "
        "FROM status_history WHERE vaga_id=? ORDER BY timestamp DESC",
        (vaga_id,),
    ).fetchall()
    vaga = conn.execute("SELECT titulo, empresa FROM vagas WHERE id=?", (vaga_id,)).fetchone()
    conn.close()

    hist = [{
        "status_old": r["status_old"], "status_new": r["status_new"],
        "timestamp": _fmt(r["timestamp"]), "detalhes": r["detalhes"] or "",
    } for r in rows]
    return jsonify({
        "vaga": {"titulo": vaga["titulo"], "empresa": vaga["empresa"]} if vaga else {},
        "historico": hist,
    })


# ── API: AÇÕES SOBRE VAGAS ─────────────────────────────────────────────────────

@app.route("/api/marcar-aplicada", methods=["POST"])
def api_marcar_aplicada():
    data = request.get_json() or {}
    vaga_id = data.get("id")
    if not vaga_id:
        return jsonify({"ok": False, "erro": "ID obrigatorio"}), 400

    conn = _db()
    try:
        conn.execute(
            "UPDATE vagas SET aplicada=1, status='aplicada', data_aplicacao=? WHERE id=? AND aplicada=0",
            (datetime.utcnow().isoformat(), vaga_id),
        )
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, 'nova', 'aplicada', ?, 'Marcada via Dashboard')",
            (vaga_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/atualizar-status", methods=["POST"])
def api_atualizar_status():
    data = request.get_json() or {}
    vaga_id    = data.get("id")
    novo_status = data.get("status")
    VALID = {"nova", "aplicada", "em_analise", "entrevista", "rejeitada",
             "encerrada", "proposta", "cv_gerado", "suspeita"}
    if not vaga_id or novo_status not in VALID:
        return jsonify({"ok": False, "erro": "Parametros invalidos"}), 400

    conn = _db()
    try:
        row = conn.execute("SELECT status FROM vagas WHERE id=?", (vaga_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "erro": "Vaga nao encontrada"}), 404
        old_status = row["status"]
        conn.execute(
            "UPDATE vagas SET status=?, data_update=? WHERE id=?",
            (novo_status, datetime.utcnow().isoformat(), vaga_id),
        )
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, ?, ?, ?, 'Atualizado via Dashboard')",
            (vaga_id, old_status, novo_status, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


# ── API: CV ────────────────────────────────────────────────────────────────────

@app.route("/api/cv/<int:job_id>", methods=["POST"])
def api_gerar_cv(job_id):
    """Gera CV on-demand para a vaga especificada."""
    conn = _db()
    vaga = conn.execute("SELECT * FROM vagas WHERE id=?", (job_id,)).fetchone()
    conn.close()

    if not vaga:
        return jsonify({"ok": False, "erro": "Vaga nao encontrada"}), 404

    try:
        from core.cv_generator import CVGenerator
        cg = CVGenerator()
        vaga_dict = {
            "id": vaga["id"], "titulo": vaga["titulo"], "empresa": vaga["empresa"],
            "localizacao": vaga["localizacao"], "descricao": vaga["descricao"],
            "url": vaga["url"], "score": vaga["score"],
        }
        caminho = cg.generate(vaga_dict)
        if caminho:
            return jsonify({"ok": True, "path": caminho, "filename": os.path.basename(caminho)})
        return jsonify({"ok": False, "erro": "Falha ao gerar PDF"}), 500
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/api/cvs")
def api_listar_cvs():
    """Lista todos os CVs gerados."""
    try:
        from core.cv_generator import CVGenerator
        cg = CVGenerator()
        return jsonify(cg.list_exports())
    except Exception as e:
        return jsonify([])


@app.route("/api/cv/download/<int:cv_id>")
def api_download_cv(cv_id):
    """Download de um CV gerado."""
    conn = _db()
    try:
        row = conn.execute("SELECT file_path FROM cv_exports WHERE id=?", (cv_id,)).fetchone()
    finally:
        conn.close()

    if not row or not row["file_path"]:
        abort(404)

    filepath = row["file_path"]
    if not os.path.exists(filepath):
        abort(404)

    return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))


# ── API: FEEDBACK ──────────────────────────────────────────────────────────────

@app.route("/api/feedback/<int:job_id>", methods=["POST"])
def api_registrar_feedback(job_id):
    """Registra outcome de uma candidatura."""
    data = request.get_json() or {}
    outcome = data.get("outcome", "")
    notes = data.get("notes", "")

    VALID = {"entrevista", "rejeicao", "sem_resposta", "proposta"}
    if outcome not in VALID:
        return jsonify({"ok": False, "erro": f"Outcome invalido: {outcome}"}), 400

    try:
        from core.feedback_engine import FeedbackEngine
        fe = FeedbackEngine()
        ok = fe.register_outcome(job_id, outcome, notes)
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/api/feedback/summary")
def api_feedback_summary():
    """Retorna resumo dos feedbacks registrados."""
    try:
        from core.feedback_engine import FeedbackEngine
        fe = FeedbackEngine()
        return jsonify(fe.get_outcomes_summary())
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/feedback/calibrate", methods=["POST"])
def api_calibrar():
    """Dispara recalibração manual."""
    try:
        from core.feedback_engine import FeedbackEngine
        fe = FeedbackEngine()
        resultado = fe.recalibrate()
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


# ── API: MERCADO ───────────────────────────────────────────────────────────────

@app.route("/api/market/report")
def api_market_report():
    """Retorna o relatório de mercado mais recente."""
    try:
        from core.market_intelligence import MarketIntelligence
        mi = MarketIntelligence()
        report = mi.get_latest_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/market/generate", methods=["POST"])
def api_gerar_market_report():
    """Gera novo relatório de mercado on-demand."""
    try:
        from core.market_intelligence import MarketIntelligence
        mi = MarketIntelligence()
        report = mi.weekly_report()
        return jsonify(report)
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


# ── API: TRIGGER ───────────────────────────────────────────────────────────────

@app.route("/api/trigger", methods=["POST"])
def api_trigger():
    """Dispara ciclo de busca em background."""
    global _cycle_running

    with _cycle_lock:
        if _cycle_running:
            return jsonify({"ok": False, "msg": "Ciclo ja em execucao"}), 429
        _cycle_running = True

    def _run():
        global _cycle_running
        try:
            from core.models import init_db
            from core.agent import ciclo_completo
            init_db()
            ciclo_completo()
        except Exception as e:
            logging.getLogger(__name__).error(f"Ciclo manual: {e}")
        finally:
            _cycle_running = False

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({"ok": True, "msg": "Ciclo iniciado em background"})


# ── API: CONFIGURAÇÃO ──────────────────────────────────────────────────────────

@app.route("/api/config/profile")
def api_get_profile():
    """Lê o config/profile.yml como texto."""
    profile_path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"ok": True, "content": content})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/api/config/profile", methods=["POST"])
def api_save_profile():
    """Salva novo conteúdo do config/profile.yml."""
    data = request.get_json() or {}
    content = data.get("content", "")
    if not content:
        return jsonify({"ok": False, "erro": "Conteudo vazio"}), 400

    # Valida YAML antes de salvar
    try:
        import yaml
        yaml.safe_load(content)
    except Exception as e:
        return jsonify({"ok": False, "erro": f"YAML invalido: {e}"}), 400

    profile_path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/api/config/telegram-test", methods=["POST"])
def api_telegram_test():
    """Envia mensagem de teste via Telegram."""
    try:
        from notifiers.notifier_telegram import enviar_telegram
        ok = enviar_telegram("Teste de notificacao do Job Agent Dashboard - OK!")
        return jsonify({"ok": ok})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


# ── API: MANUTENÇÃO ────────────────────────────────────────────────────────────

@app.route("/api/maintenance", methods=["POST"])
def api_maintenance():
    """Executa manutenção do pipeline."""
    try:
        from core.pipeline_integrity import PipelineIntegrity
        pi = PipelineIntegrity()
        relatorio = pi.run_maintenance()
        return jsonify({"ok": True, "relatorio": relatorio})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


# ── ENDPOINTS LEGADOS (mantidos para compatibilidade) ──────────────────────────

@app.route("/api/perfil")
def api_perfil():
    try:
        from config.profile import PERFIL
        conn = _db()
        top_kw_raw = conn.execute(
            "SELECT palavras_chave FROM vagas WHERE palavras_chave IS NOT NULL "
            "AND palavras_chave != '' AND score >= 4 ORDER BY score DESC LIMIT 50"
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
        fortes  = [(k, v) for k, v in PERFIL["keywords"].items() if v == 3][:6]
        medios  = [(k, v) for k, v in PERFIL["keywords"].items() if v == 2][:6]

        return jsonify({
            "nome": PERFIL["nome"], "nivel": PERFIL["nivel"],
            "localizacao": PERFIL["localizacao"],
            "aceita_remoto": PERFIL["aceita_remoto"],
            "aceita_hibrido": PERFIL["aceita_hibrido"],
            "fortes": [k for k, _ in fortes],
            "medios": [k for k, _ in medios],
            "top_keywords_vagas": [{"kw": k, "count": c} for k, c in top_kws],
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    """Health check para monitoramento externo. Retorna 200 se OK, 503 se degradado."""
    status = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    try:
        conn = _db()
        count = conn.execute("SELECT COUNT(*) FROM vagas").fetchone()[0]
        conn.close()
        status["db"] = {"status": "ok", "total_jobs": count}
    except Exception as e:
        status["db"] = {"status": "error", "message": str(e)}
        status["status"] = "degraded"

    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    status["telegram"] = {"configured": bool(telegram_token)}
    status["anthropic"] = {"configured": bool(anthropic_key)}

    http_code = 200 if status["status"] == "ok" else 503
    return jsonify(status), http_code


# ── EXPORTAÇÃO CSV ─────────────────────────────────────────────────────────────

@app.route("/api/export/csv")
def export_csv():
    """Exporta todas as vagas como CSV para análise externa."""
    import csv, io
    conn = _db()
    try:
        jobs = conn.execute(
            """SELECT id, titulo, empresa, localizacao, score, score_grade,
                      status, url, data_encontrada, posted_at, is_early_applicant
               FROM vagas ORDER BY score DESC"""
        ).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Titulo", "Empresa", "Localizacao", "Score",
                     "Grade", "Status", "URL", "Encontrada em",
                     "Publicada em", "Janela Aberta"])
    for job in jobs:
        writer.writerow(list(job))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=pipeline.csv"},
    )


if __name__ == "__main__":
    if not os.path.exists(_DB_PATH):
        logging.getLogger(__name__).error(f"Banco nao encontrado: {_DB_PATH}. Execute 'python scheduler.py' primeiro.")
        sys.exit(1)
    logging.getLogger(__name__).info(f"Banco: {_DB_PATH}")
    logging.getLogger(__name__).info("Dashboard: http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("FLASK_PORT", 5000)))
