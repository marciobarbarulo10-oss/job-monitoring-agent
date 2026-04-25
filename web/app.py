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

from dotenv import load_dotenv
load_dotenv()

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


# ── HELPERS LOCAIS (sem API externa) ─────────────────────────────────────────

def _profile_local() -> dict:
    """Carrega config/profile.yml. Sem API, sem fallback externo."""
    try:
        import yaml
        path = os.path.join(_BASE_DIR, "config", "profile.yml")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _normalize_kw(text: str) -> str:
    if not text:
        return ""
    import unicodedata
    normalized = unicodedata.normalize('NFD', text)
    ascii_text = normalized.encode('ascii', 'ignore').decode('ascii')
    return ascii_text.lower().strip()


def _match_local(vaga: dict, profile: dict) -> dict:
    """Keyword matching 100% local — sem chamada de API."""
    hard = profile.get("skills", {}).get("hard", [])
    texto = _normalize_kw(
        f"{vaga.get('titulo') or ''} {vaga.get('descricao') or ''}"
    )
    matched, missing = [], []
    for skill in hard:
        (matched if _normalize_kw(skill) in texto else missing).append(skill)

    total = len(hard)
    pct   = round(len(matched) / total * 100) if total else 0

    if pct >= 60:
        analysis = f"Boa aderencia: {len(matched)}/{total} competencias encontradas na vaga."
        rec = "aplicar"
    elif pct >= 30:
        analysis = f"Aderencia parcial: {len(matched)}/{total} competencias mapeadas."
        rec = "aplicar_com_ressalvas"
    else:
        analysis = f"Baixa aderencia: apenas {len(matched)}/{total} competencias identificadas."
        rec = "avaliar"

    return {
        "matched": matched[:8], "missing": missing[:5],
        "match_pct": pct, "analysis": analysis,
        "recommendation": rec, "method": "keyword",
    }


def _platform_tip(fonte: str) -> dict:
    fonte = (fonte or "").lower().replace(".com", "").strip()
    tips = {
        "linkedin": {
            "tip": "Use o botao Easy Apply. Leva menos de 2 minutos.",
            "steps": [
                "1. Abra a vaga no LinkedIn pelo botao 'Abrir Vaga'",
                "2. Clique em 'Candidatura Simplificada' (botao azul)",
                "3. Preencha os campos e confirme",
                "4. Volte e clique em 'Confirmar Candidatura'",
            ],
        },
        "gupy": {
            "tip": "O processo tem etapas. Separe 10 minutos e salve o progresso.",
            "steps": [
                "1. Abra a vaga no Gupy pelo botao 'Abrir Vaga'",
                "2. Faca login ou cadastre-se (gratuito)",
                "3. Clique em 'Candidatar-se'",
                "4. Use os dados abaixo para preencher os campos",
                "5. Volte e clique em 'Confirmar Candidatura'",
            ],
        },
        "indeed": {
            "tip": "Voce sera redirecionado para o site da empresa.",
            "steps": [
                "1. Abra a vaga no Indeed pelo botao 'Abrir Vaga'",
                "2. Clique em 'Candidate-se agora'",
                "3. Preencha o formulario da empresa",
                "4. Volte e clique em 'Confirmar Candidatura'",
            ],
        },
        "vagas": {
            "tip": "Cadastre seu curriculo no site antes de aplicar.",
            "steps": [
                "1. Abra a vaga em Vagas.com pelo botao 'Abrir Vaga'",
                "2. Cadastre-se ou faca login (gratuito)",
                "3. Clique em 'Candidatar'",
                "4. Volte e clique em 'Confirmar Candidatura'",
            ],
        },
    }
    return tips.get(fonte, {
        "tip": "Acesse o link e siga as instrucoes da empresa.",
        "steps": [
            "1. Abra a vaga pelo botao 'Abrir Vaga'",
            "2. Siga as instrucoes da empresa no portal",
            "3. Volte e clique em 'Confirmar Candidatura'",
        ],
    })


def _template_answers(vaga: dict, profile: dict, matched: list) -> list:
    """Gera respostas por template Python — sem API, retorna lista de {pergunta, resposta}."""
    exp_anos  = profile.get("experience_years", 5)
    empresa   = vaga.get("empresa") or "empresa"
    titulo    = vaga.get("titulo") or "Analista"
    nivel     = "Pleno" if exp_anos >= 3 else "Junior"
    skills_str = ", ".join(matched[:4]) if matched else "Supply Chain e Comercio Exterior"
    about     = (profile.get("about") or "").strip()
    proof     = profile.get("proof_points", [])
    proof_str = proof[0] if proof else "melhoria continua de processos e resultados"
    cargo_base = titulo.split()[0] if titulo else "Analista"

    return [
        {
            "pergunta": "Por que voce quer essa vaga?",
            "resposta": (
                f"Tenho {exp_anos} anos de experiencia em {skills_str} e esta vaga em "
                f"{empresa} se alinha diretamente com minha trajetoria. Vejo uma "
                f"oportunidade concreta de contribuir com a posicao de {titulo}."
            ),
        },
        {
            "pergunta": "Qual seu maior diferencial?",
            "resposta": (
                f"Minha experiencia pratica em {skills_str} combinada com resultados "
                f"mensuraveis: {proof_str}."
            ),
        },
        {
            "pergunta": "Onde se ve em 5 anos?",
            "resposta": (
                f"Vejo-me como referencia tecnica em {cargo_base} {nivel}, liderando "
                f"projetos de melhoria e com responsabilidades crescentes na area."
            ),
        },
        {
            "pergunta": "Qual sua pretensao salarial?",
            "resposta": (
                f"Estou aberto a discutir uma remuneracao compativel com o mercado para "
                f"{nivel} com {exp_anos} anos de experiencia na area."
            ),
        },
        {
            "pergunta": "Conte sobre voce",
            "resposta": about[:500] if about else (
                f"Profissional com {exp_anos} anos de experiencia em {skills_str}, "
                f"focado em resultados e melhoria de processos."
            ),
        },
    ]


def _process_manual_profile(manual_data: dict, linkedin_url: str = "") -> dict:
    skills_raw = manual_data.get("skills", "")
    if isinstance(skills_raw, str):
        hard = [s.strip() for s in skills_raw.replace("\n", ",").split(",") if s.strip()]
    else:
        hard = list(skills_raw) if skills_raw else []
    loc = manual_data.get("location", "")
    idiomas_raw = manual_data.get("idiomas", "")
    idiomas = [i.strip() for i in idiomas_raw.split(",") if i.strip()] if idiomas_raw else []
    return {
        "name": manual_data.get("name", ""),
        "headline": manual_data.get("headline", ""),
        "current_role": manual_data.get("headline", ""),
        "location": {"preferred": [loc] if loc else []},
        "experience_years": int(manual_data.get("exp_years") or 0),
        "skills": {"hard": hard, "soft": []},
        "languages": idiomas,
        "about": manual_data.get("about", ""),
        "linkedin_url": linkedin_url,
        "method": "manual",
    }


def _save_profile_to_yml(extracted: dict) -> bool:
    try:
        import yaml
        path = os.path.join(_BASE_DIR, "config", "profile.yml")
        try:
            with open(path, "r", encoding="utf-8") as f:
                current = yaml.safe_load(f) or {}
        except Exception:
            current = {}
        if extracted.get("name"):
            current["name"] = extracted["name"]
        if extracted.get("headline") or extracted.get("current_role"):
            current["current_role"] = extracted.get("headline") or extracted.get("current_role")
        if extracted.get("experience_years"):
            current["experience_years"] = extracted["experience_years"]
        if extracted.get("about"):
            current["about"] = extracted["about"]
        hard = extracted.get("skills", {}).get("hard", [])
        if hard:
            current.setdefault("skills", {})["hard"] = hard
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(current, f, allow_unicode=True, default_flow_style=False)
        return True
    except Exception:
        return False


def _save_profile_to_db(extracted: dict, linkedin_url: str, source: str):
    conn = _db()
    try:
        conn.execute("UPDATE user_profiles SET is_active=0")
        conn.execute(
            "INSERT INTO user_profiles (source, linkedin_url, data_json, imported_at, is_active) "
            "VALUES (?, ?, ?, ?, 1)",
            (source, linkedin_url,
             json.dumps(extracted, ensure_ascii=False),
             datetime.utcnow().isoformat()),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


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
    proposta    = c.execute("SELECT COUNT(*) FROM vagas WHERE status='proposta'").fetchone()[0]
    rejeitadas  = c.execute("SELECT COUNT(*) FROM vagas WHERE status='rejeitada'").fetchone()[0]
    suspeitas   = c.execute("SELECT COUNT(*) FROM vagas WHERE status='suspeita'").fetchone()[0]
    cv_gerado   = c.execute("SELECT COUNT(*) FROM vagas WHERE status='cv_gerado'").fetchone()[0]
    aplic_status = c.execute("SELECT COUNT(*) FROM vagas WHERE status='aplicada'").fetchone()[0]
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

    # Acoes de hoje
    acoes_hoje = []
    try:
        novas_hoje = c.execute(
            "SELECT COUNT(*) FROM vagas WHERE status='nova' "
            "AND data_encontrada >= datetime('now', '-24 hours')"
        ).fetchone()[0]
        if novas_hoje > 0:
            acoes_hoje.append({
                "tipo": "vagas_novas",
                "texto": f"{novas_hoje} vagas novas nas ultimas 24h",
                "acao": "Ver vagas",
                "filtro": "nova",
            })
        sem_followup = c.execute(
            "SELECT COUNT(*) FROM vagas WHERE aplicada=1 "
            "AND status NOT IN ('rejeitada','encerrada','proposta') "
            "AND (last_check IS NULL OR last_check <= datetime('now', '-5 days'))"
        ).fetchone()[0]
        if sem_followup > 0:
            acoes_hoje.append({
                "tipo": "followup",
                "texto": f"{sem_followup} candidaturas sem atualizacao ha 5+ dias",
                "acao": "Ver candidaturas",
                "filtro": "aplicada",
            })
        janela_cnt = c.execute(
            "SELECT COUNT(*) FROM vagas WHERE is_early_applicant=1 AND status='nova'"
        ).fetchone()[0]
        if janela_cnt > 0:
            acoes_hoje.append({
                "tipo": "urgente",
                "texto": f"{janela_cnt} vagas com janela aberta — aplique agora",
                "acao": "Ver urgentes",
                "filtro": "nova",
            })
    except Exception:
        pass

    conn.close()

    media = round(sum(scores) / len(scores), 1) if scores else 0
    acima_6 = len([s for s in scores if s >= 6])
    pct_acima_6 = round(acima_6 / len(scores) * 100) if scores else 0
    taxa_conv = round(aplicadas / total * 100, 1) if total else 0
    em_processo_total = aplic_status + entrevista + proposta

    return jsonify({
        "total": total, "aplicadas": aplicadas, "novas": novas,
        "encerradas": encerradas, "em_analise": em_analise,
        "entrevista": entrevista, "rejeitadas": rejeitadas,
        "suspeitas": suspeitas, "cv_gerado": cv_gerado,
        "early_applicant": early, "high_score": high_score,
        "media_score": media, "pct_acima_6": pct_acima_6,
        "taxa_conversao": taxa_conv, "cvs_gerados": cvs_gerados,
        "feedbacks": feedbacks,
        "em_processo": {
            "total": em_processo_total,
            "breakdown": {"aplicada": aplic_status, "entrevista": entrevista, "proposta": proposta},
            "tooltip": "Total de candidaturas em andamento (aplicada + entrevista + proposta)",
        },
        "acoes_hoje": acoes_hoje,
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
        if status_filter == 'ignoradas':
            clauses.append("ignored=1")
        elif status_filter == 'encerrada':
            clauses.append("status=? AND (ignored IS NULL OR ignored=0)")
            params.append(status_filter)
        else:
            clauses.append("status=?"); params.append(status_filter)
    if grade_filter:
        clauses.append("score_grade=?"); params.append(grade_filter.upper())
    if fonte_filter and fonte_filter != 'todas':
        clauses.append("LOWER(COALESCE(fonte, '')) = ?")
        params.append(fonte_filter.lower())
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
        f"last_check, fonte, modalidade, is_early_applicant, score_method, favorited, ignored "
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
            "favorited": bool(r["favorited"]),
            "ignored": bool(r["ignored"]),
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
        "FROM vagas WHERE score_grade IN ('A','B') ORDER BY score DESC LIMIT 5"
    ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT id, titulo, empresa, localizacao, score, score_grade, url, status, "
            "aplicada, palavras_chave, is_early_applicant "
            "FROM vagas WHERE score > 0 ORDER BY score DESC LIMIT 5"
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
        if report and isinstance(report.get('top_keywords'), list):
            report['top_keywords'] = [
                kw for kw in report['top_keywords']
                if _kw_valid(kw.get('keyword', '') if isinstance(kw, dict) else str(kw))
            ]
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

_KW_STOPWORDS = {
    'li', 'di', 'ii', 'de', 'da', 'do', 'em', 'para', 'com', 'por', 'um', 'uma',
    'os', 'as', 'na', 'no', 'se', 'que', 'ou', 'e', 'a', 'o', 'the',
    'and', 'or', 'of', 'in', 'to', 'for', 'at', 'by', 'an', 'be', 'is',
    'linkedin', 'vagas', 'vaga', 'job', 'jobs', 'trabalho',
    'awb', 'sp', 'rj', 'mg',
}


def _kw_valid(kw: str) -> bool:
    kw = kw.strip().lower()
    if len(kw) < 3:
        return False
    if kw in _KW_STOPWORDS:
        return False
    if kw.isdigit():
        return False
    return True


def _dedup_by_norm(items: list) -> list:
    import unicodedata
    seen, result = set(), []
    for k in items:
        norm = unicodedata.normalize('NFD', k.lower().strip()).encode('ascii', 'ignore').decode('ascii')
        if norm not in seen:
            seen.add(norm)
            result.append(k)
    return result


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
                    if _kw_valid(k):
                        kw_count[k] = kw_count.get(k, 0) + 1
            except Exception:
                pass

        top_kws = sorted(kw_count.items(), key=lambda x: -x[1])[:12]

        fortes_raw = [k for k, v in PERFIL["keywords"].items() if v == 3]
        medios_raw = [k for k, v in PERFIL["keywords"].items() if v == 2]
        fortes = _dedup_by_norm([k for k in fortes_raw if _kw_valid(k)])[:6]
        medios = _dedup_by_norm([k for k in medios_raw if _kw_valid(k)])[:6]

        return jsonify({
            "nome": PERFIL["nome"], "nivel": PERFIL["nivel"],
            "localizacao": PERFIL["localizacao"],
            "aceita_remoto": PERFIL["aceita_remoto"],
            "aceita_hibrido": PERFIL["aceita_hibrido"],
            "fortes": fortes,
            "medios": medios,
            "top_keywords_vagas": [{"kw": k, "count": c} for k, c in top_kws],
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ── PERFIL LINKEDIN ───────────────────────────────────────────────────────────

@app.route("/api/profile/linkedin", methods=["POST"])
def api_import_linkedin():
    """Scraping publico com requests+BS4. Sem Playwright. Retorna blocked=true se LinkedIn bloquear."""
    data         = request.get_json() or {}
    linkedin_url = data.get("url", "").strip()
    manual_data  = data.get("manual")

    # ── Entrada manual ────────────────────────────────────────────────────────
    if manual_data:
        extracted = _process_manual_profile(manual_data, linkedin_url)
        saved = _save_profile_to_yml(extracted)
        _save_profile_to_db(extracted, linkedin_url, "manual")
        return jsonify({
            "ok": saved,
            "profile": extracted,
            "message": "Perfil salvo com sucesso!" if saved else "Falha ao salvar",
        })

    if not linkedin_url:
        return jsonify({"ok": False, "error": "url_or_manual_required"}), 400

    # ── Scraping publico (sem login) ──────────────────────────────────────────
    try:
        import requests as req
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
        resp = req.get(linkedin_url, headers=headers, timeout=10, allow_redirects=True)

        blocked = (
            resp.status_code == 999
            or resp.status_code != 200
            or "authwall" in resp.url
            or "/login" in resp.url
            or "checkpoint" in resp.url
        )
        if blocked:
            return jsonify({
                "ok": False,
                "blocked": True,
                "message": "LinkedIn requer login para extracao automatica.",
                "sugestao": "Use a Entrada Manual — leva 2 minutos e funciona sempre.",
            })

        soup  = BeautifulSoup(resp.text, "html.parser")
        name, headline, about = "", "", ""

        og_title = soup.find("meta", property="og:title")
        if og_title:
            raw = (og_title.get("content") or "").strip()
            if " - " in raw:
                parts    = raw.split(" - ", 1)
                name     = parts[0].strip()
                headline = parts[1].strip()
            else:
                name = raw

        if not name:
            title_tag = soup.find("title")
            if title_tag:
                name = title_tag.text.replace("| LinkedIn", "").strip()

        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            about = (og_desc.get("content") or "").strip()

        if not name:
            return jsonify({
                "ok": False,
                "blocked": True,
                "message": "Nao foi possivel extrair dados publicos do perfil.",
                "sugestao": "Use a Entrada Manual — leva 2 minutos e funciona sempre.",
            })

        extracted = {
            "name": name, "headline": headline, "about": about,
            "skills": {"hard": [], "soft": []},
            "linkedin_url": linkedin_url, "method": "public_scrape",
        }
        saved = _save_profile_to_yml(extracted)
        _save_profile_to_db(extracted, linkedin_url, "public_scrape")
        return jsonify({
            "ok": saved,
            "profile": extracted,
            "message": "Perfil extraido! Revise e complete os dados manualmente.",
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "blocked": True,
            "message": f"Erro ao acessar LinkedIn: {e}.",
            "sugestao": "Use a Entrada Manual — leva 2 minutos e funciona sempre.",
        })


@app.route("/api/profile/linkedin")
def api_get_linkedin_profile():
    """Retorna o perfil importado mais recente."""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT data_json, source, imported_at FROM user_profiles "
            "WHERE is_active=1 ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return jsonify({"ok": False, "message": "Nenhum perfil importado ainda."})

    try:
        data = json.loads(row["data_json"])
    except Exception:
        data = {}

    return jsonify({"ok": True, "profile": data, "source": row["source"],
                    "imported_at": row["imported_at"]})


# ── APLICAÇÃO ASSISTIDA ────────────────────────────────────────────────────────

@app.route("/api/apply/<int:job_id>", methods=["POST"])
def api_apply_assisted(job_id):
    """Candidatura assistida: marca como aplicada + retorna conteúdo de suporte."""
    data = request.get_json() or {}
    level = int(data.get("level", 1))

    conn = _db()
    try:
        vaga = conn.execute("SELECT * FROM vagas WHERE id=?", (job_id,)).fetchone()
        if not vaga:
            return jsonify({"ok": False, "error": "Vaga nao encontrada"}), 404

        vaga_dict = {
            "id": vaga["id"], "titulo": vaga["titulo"], "empresa": vaga["empresa"],
            "localizacao": vaga["localizacao"], "descricao": vaga["descricao"],
            "url": vaga["url"], "score": vaga["score"], "fonte": vaga["fonte"],
        }

        # Marca como aplicada
        conn.execute(
            "UPDATE vagas SET aplicada=1, status='aplicada', data_aplicacao=? WHERE id=?",
            (datetime.utcnow().isoformat(), job_id),
        )
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, 'nova', 'aplicada', ?, 'Aplicada via Assistente v3')",
            (job_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        from core.application_engine import ApplicationEngine
        engine = ApplicationEngine()
        result = engine.apply(vaga_dict, level=level)
        return jsonify({"ok": True, "applied": True, **result})
    except Exception as e:
        return jsonify({"ok": True, "applied": True, "level": 1,
                        "url": vaga_dict["url"],
                        "error": f"Erro no engine: {str(e)}"})


@app.route("/api/assist/<int:job_id>")
def api_get_assist(job_id):
    """Conteudo de assistencia 100% local — sem API externa, sem Playwright."""
    conn = _db()
    try:
        vaga = conn.execute("SELECT * FROM vagas WHERE id=?", (job_id,)).fetchone()
        if not vaga:
            return jsonify({"ok": False, "error": "Vaga nao encontrada"}), 404
        vaga_dict = dict(vaga)
    finally:
        conn.close()

    profile     = _profile_local()
    explanation = _match_local(vaga_dict, profile)
    platform    = _platform_tip(vaga_dict.get("fonte", ""))
    respostas   = _template_answers(vaga_dict, profile, explanation["matched"])

    hard    = profile.get("skills", {}).get("hard", [])
    matched = explanation["matched"]
    relevant = matched[:6] or hard[:6]
    about   = (profile.get("about") or "").strip()

    prefill_fields = [
        {"label": "Nome completo",        "value": profile.get("name", ""),                         "type": "text"},
        {"label": "Cargo pretendido",     "value": vaga_dict.get("titulo", profile.get("current_role", "")), "type": "text"},
        {"label": "Competencias relevantes", "value": ", ".join(relevant),                          "type": "text"},
        {"label": "Anos de experiencia",  "value": str(profile.get("experience_years", "")),        "type": "text"},
        {"label": "Idiomas",              "value": ", ".join(profile.get("languages", [])),         "type": "text"},
        {"label": "Resumo / Sobre voce",  "value": about[:400],                                     "type": "textarea"},
    ]

    assist = {
        "platform":        (vaga_dict.get("fonte") or "").lower(),
        "tip":             platform["tip"],
        "steps":           platform["steps"],
        "prefill_fields":  prefill_fields,
        "respostas_comuns": respostas,
    }

    return jsonify({"ok": True, "assist": assist, "explanation": explanation})


# ── AÇÕES RÁPIDAS ──────────────────────────────────────────────────────────────

@app.route("/api/vagas/<int:job_id>/favorite", methods=["POST"])
def api_toggle_favorite(job_id):
    """Alterna favorito de uma vaga."""
    conn = _db()
    try:
        row = conn.execute("SELECT favorited FROM vagas WHERE id=?", (job_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Vaga nao encontrada"}), 404
        new_val = 0 if row["favorited"] else 1
        conn.execute("UPDATE vagas SET favorited=? WHERE id=?", (new_val, job_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True, "favorito": bool(new_val)})


@app.route("/api/vagas/<int:job_id>/ignore", methods=["POST"])
def api_ignore_vaga(job_id):
    """Marca vaga como ignorada e atualiza status."""
    conn = _db()
    try:
        row = conn.execute("SELECT status FROM vagas WHERE id=?", (job_id,)).fetchone()
        old_status = row["status"] if row else "nova"
        conn.execute("UPDATE vagas SET ignored=1, status='encerrada' WHERE id=?", (job_id,))
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, ?, 'encerrada', ?, 'Ignorada pelo usuario')",
            (job_id, old_status, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/vagas/<int:job_id>/restore", methods=["POST"])
def api_restore_vaga(job_id):
    """Restaura vaga ignorada para status 'nova'."""
    conn = _db()
    try:
        conn.execute("UPDATE vagas SET ignored=0, status='nova' WHERE id=? AND ignored=1", (job_id,))
        conn.execute(
            "INSERT INTO status_history (vaga_id, status_old, status_new, timestamp, detalhes) "
            "VALUES (?, 'encerrada', 'nova', ?, 'Restaurada pelo usuario')",
            (job_id, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})


@app.route("/api/maintenance/dedup-preview")
def api_dedup_preview():
    """Retorna contagem de duplicatas antes da remocao."""
    conn = _db()
    try:
        dup_count = conn.execute(
            "SELECT COUNT(*) FROM vagas WHERE id NOT IN ("
            "SELECT MAX(id) FROM vagas GROUP BY LOWER(titulo), LOWER(empresa))"
        ).fetchone()[0]
    finally:
        conn.close()
    return jsonify({"duplicatas": dup_count})


# ── EVOLUÇÃO ───────────────────────────────────────────────────────────────────

@app.route("/api/stats/evolution")
def api_evolution():
    """Evolução semanal de candidaturas e resultados positivos."""
    conn = _db()
    try:
        rows = conn.execute(
            """SELECT strftime('%Y-W%W', data_aplicacao) as semana,
                      COUNT(*) as aplicadas,
                      SUM(CASE WHEN status IN ('entrevista','proposta') THEN 1 ELSE 0 END) as positivas
               FROM vagas
               WHERE aplicada=1 AND data_aplicacao IS NOT NULL
               GROUP BY semana ORDER BY semana DESC LIMIT 12"""
        ).fetchall()
    finally:
        conn.close()

    data = [{"semana": r[0], "aplicadas": r[1], "positivas": r[2]} for r in rows]
    data.reverse()
    return jsonify(data)


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
                      status, url, data_encontrada, posted_at, is_early_applicant,
                      data_aplicacao
               FROM vagas ORDER BY score DESC"""
        ).fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Titulo", "Empresa", "Localizacao", "Score",
                     "Grade", "Status", "URL", "Encontrada em",
                     "Publicada em", "Janela Aberta", "Aplicada em"])
    for job in jobs:
        writer.writerow(list(job))

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=pipeline.csv"},
    )


@app.route("/api/debug/fontes")
def debug_fontes():
    """Diagnóstico: contagem de vagas por valor de fonte no banco."""
    conn = _db()
    try:
        result = conn.execute(
            "SELECT COALESCE(fonte, 'NULL') as fonte, COUNT(*) as total "
            "FROM vagas GROUP BY fonte ORDER BY total DESC"
        ).fetchall()
    finally:
        conn.close()
    return jsonify([{"fonte": r[0], "total": r[1]} for r in result])


# ── SCHEDULER STATUS ──────────────────────────────────────────────────────────

@app.route("/api/scheduler/status")
def api_scheduler_status():
    """Retorna configuracao dos jobs agendados e proximas execucoes estimadas."""
    from datetime import timedelta

    interval_hours = int(os.getenv("CHECK_INTERVAL_HOURS", 6))
    now = datetime.now()

    def next_interval(hours):
        return (now + timedelta(hours=hours)).strftime("%d/%m/%Y %H:%M")

    def next_cron(hour, minute, day_of_week=None):
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if day_of_week is None:
            if target <= now:
                target += timedelta(days=1)
        else:
            days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            target_dow = days_map[day_of_week]
            days_ahead = target_dow - now.weekday()
            if days_ahead < 0 or (days_ahead == 0 and target <= now):
                days_ahead += 7
            target = target + timedelta(days=days_ahead)
        return target.strftime("%d/%m/%Y %H:%M")

    jobs = [
        {
            "id": "busca_vagas",
            "nome": "Busca de Vagas",
            "descricao": "Ciclo principal: busca, pontuacao e notificacao de novas vagas",
            "frequencia": f"A cada {interval_hours}h",
            "proxima_execucao": next_interval(interval_hours),
        },
        {
            "id": "resumo_diario",
            "nome": "Resumo Diario",
            "descricao": "Envia resumo das candidaturas via Telegram",
            "frequencia": "Diario as 08:00",
            "proxima_execucao": next_cron(8, 0),
        },
        {
            "id": "relatorio_mercado",
            "nome": "Relatorio de Mercado",
            "descricao": "Inteligencia de mercado semanal via Telegram",
            "frequencia": "Domingos as 18:00",
            "proxima_execucao": next_cron(18, 0, "sun"),
        },
        {
            "id": "manutencao_pipeline",
            "nome": "Manutencao do Pipeline",
            "descricao": "Deduplicacao, normalizacao e health check do banco",
            "frequencia": "Segundas as 07:00",
            "proxima_execucao": next_cron(7, 0, "mon"),
        },
        {
            "id": "calibracao_scoring",
            "nome": "Calibracao de Scoring",
            "descricao": "Recalibra o scoring baseado nos feedbacks registrados",
            "frequencia": "Quartas as 12:00",
            "proxima_execucao": next_cron(12, 0, "wed"),
        },
    ]

    return jsonify({
        "scheduler_running": True,
        "timezone": "America/Sao_Paulo",
        "total_jobs": len(jobs),
        "jobs": jobs,
    })


# ── CONFIG NUMERICO ────────────────────────────────────────────────────────────

@app.route("/api/config/settings", methods=["GET"])
def api_get_settings():
    """Retorna as configurações numéricas atuais."""
    return jsonify({
        "ok": True,
        "min_score_notify": float(os.getenv("MIN_SCORE_TO_NOTIFY", "6.0")),
        "min_score_cv": float(os.getenv("MIN_SCORE_AUTO_CV", "7.0")),
        "check_interval_hours": int(os.getenv("CHECK_INTERVAL_HOURS", "6")),
    })


@app.route("/api/config/settings", methods=["POST"])
def api_save_settings():
    """Salva configurações numéricas no arquivo .env e recarrega."""
    data = request.get_json() or {}
    min_score = data.get("min_score_notify")
    min_cv    = data.get("min_score_cv")
    interval  = data.get("check_interval_hours")

    env_path = os.path.join(_BASE_DIR, ".env")
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        else:
            lines = []

        def _set_var(lines, key, value):
            updated = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                    lines[i] = f"{key}={value}\n"
                    updated = True
                    break
            if not updated:
                lines.append(f"{key}={value}\n")
            return lines

        if min_score is not None:
            lines = _set_var(lines, "MIN_SCORE_TO_NOTIFY", float(min_score))
            os.environ["MIN_SCORE_TO_NOTIFY"] = str(float(min_score))
        if min_cv is not None:
            lines = _set_var(lines, "MIN_SCORE_AUTO_CV", float(min_cv))
            os.environ["MIN_SCORE_AUTO_CV"] = str(float(min_cv))
        if interval is not None:
            lines = _set_var(lines, "CHECK_INTERVAL_HOURS", int(interval))
            os.environ["CHECK_INTERVAL_HOURS"] = str(int(interval))

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return jsonify({"ok": True, "aviso": "Configuracao salva! O novo intervalo de busca sera aplicado no proximo ciclo automatico."})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


def _startup_tasks():
    """Roda tarefas de inicializacao em background."""
    try:
        if os.path.exists(_DB_PATH):
            from core.agent import _run_grade_migration
            _run_grade_migration()
    except Exception as e:
        logging.getLogger(__name__).debug(f"Startup grade migration: {e}")


threading.Thread(target=_startup_tasks, daemon=True).start()


if __name__ == "__main__":
    if not os.path.exists(_DB_PATH):
        logging.getLogger(__name__).error(f"Banco nao encontrado: {_DB_PATH}. Inicialize o banco primeiro.")
        sys.exit(1)
    logging.getLogger(__name__).info(f"Banco: {_DB_PATH}")
    logging.getLogger(__name__).info("Dashboard: http://localhost:5000")
    app.run(debug=False, host="0.0.0.0", port=int(os.getenv("FLASK_PORT", 5000)))
