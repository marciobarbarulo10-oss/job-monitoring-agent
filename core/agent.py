"""
agent.py — Orquestrador principal do Job Agent v2.0
Fluxo: Scrapers → Dedup → QualityFilter → OpportunityDetector → SemanticScorer → Persist → Notify → CV
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
import sqlite3 as _sqlite3
import requests as _requests
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from core.models import Vaga, StatusHistory, Session, init_db
from config.profile import PERFIL, calcular_score
from scrapers.scraper_indeed import buscar_indeed
from scrapers.scraper_linkedin import buscar_linkedin, buscar_descricao_linkedin
from scrapers.scraper_gupy import buscar_gupy
from scrapers.scraper_vagas import buscar_vagas_com
from notifiers.notifier_telegram import (
    notificar_nova_vaga,
    notificar_mudanca_status,
    notificar_resumo_diario,
    notify_early_opportunity,
    notify_cv_generated,
    notify_pipeline_health,
)

MIN_SCORE = float(os.getenv("MIN_SCORE_TO_NOTIFY", 6.0))
MIN_SCORE_CV = float(os.getenv("MIN_SCORE_AUTO_CV", 7.0))  # FIX v2.0: env var alinhada com .env.example
ENABLE_SEMANTIC = os.getenv("ENABLE_SEMANTIC_SCORING", "true").lower() == "true"

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger.add(
    os.path.join(_BASE_DIR, "logs", "agent_{time:YYYY-MM-DD}.log"),
    rotation="1 day",
    retention="7 days",
    level="INFO",
)

# Instâncias compartilhadas (inicializadas lazy)
_semantic_scorer = None
_quality_filter = None
_opportunity_detector = None
_cv_generator = None


def _get_semantic_scorer():
    global _semantic_scorer
    if _semantic_scorer is None:
        from core.semantic_scorer import SemanticScorer
        _semantic_scorer = SemanticScorer()
    return _semantic_scorer


def _get_quality_filter():
    global _quality_filter
    if _quality_filter is None:
        from core.quality_filter import QualityFilter
        _quality_filter = QualityFilter()
    return _quality_filter


def _get_opportunity_detector():
    global _opportunity_detector
    if _opportunity_detector is None:
        from core.opportunity_detector import OpportunityDetector
        _opportunity_detector = OpportunityDetector()
    return _opportunity_detector


def _get_cv_generator():
    global _cv_generator
    if _cv_generator is None:
        from core.cv_generator import CVGenerator
        _cv_generator = CVGenerator()
    return _cv_generator


# ── BUSCA ─────────────────────────────────────────────────────────────────────

def buscar_todas_fontes() -> list[dict]:
    """Executa busca em todas as fontes e retorna lista unificada."""
    logger.info("Iniciando busca em todas as fontes...")
    todas = []
    queries = PERFIL["queries_busca"]

    for query in queries:
        logger.info(f"Buscando: '{query}'")

        for nome, fn in [
            ("Indeed",    lambda q: buscar_indeed(q)),
            ("LinkedIn",  lambda q: buscar_linkedin(q)),
            ("Gupy",      lambda q: buscar_gupy(q)),
            ("Vagas.com", lambda q: buscar_vagas_com(q)),
        ]:
            try:
                vagas = fn(query)
                todas.extend(vagas)
                logger.info(f"  {nome}: +{len(vagas)}")
            except Exception as e:
                logger.error(f"  {nome} falhou: {e}")

    seen = set()
    unicas = []
    for v in todas:
        if v.get("url") and v["url"] not in seen:
            seen.add(v["url"])
            unicas.append(v)

    logger.info(f"Total apos deduplicacao inicial: {len(unicas)} vagas")
    return unicas


# ── PROCESSAMENTO & PERSISTÊNCIA ──────────────────────────────────────────────

def processar_e_salvar(vagas_raw: list[dict]) -> dict:
    """
    Executa o pipeline completo: dedup → quality → oportunidade → score → persist → notify → cv.
    """
    db: DBSession = Session()
    stats = {
        "novas": 0, "ignoradas": 0, "duplicadas": 0,
        "notificadas": 0, "suspeitas": 0, "cvs_gerados": 0,
    }

    quality_filter = _get_quality_filter()
    opp_detector = _get_opportunity_detector()
    scorer = _get_semantic_scorer() if ENABLE_SEMANTIC else None
    cv_gen = _get_cv_generator()

    try:
        for v in vagas_raw:
            # 1. Deduplicação por URL
            existente = db.query(Vaga).filter_by(url=v["url"]).first()
            if existente:
                stats["duplicadas"] += 1
                continue

            # 2. Busca descrição para LinkedIn
            if v.get("fonte") == "linkedin" and not v.get("descricao"):
                try:
                    v["descricao"] = buscar_descricao_linkedin(v["url"])
                except Exception as e:
                    logger.warning(f"Erro ao buscar descricao LinkedIn: {e}")

            # 3. Filtro de qualidade (scam/suspeita)
            try:
                is_suspicious, reasons = quality_filter.is_suspicious(v)
            except Exception as e:
                logger.warning(f"Erro no quality filter: {e}")
                is_suspicious, reasons = False, []

            if is_suspicious:
                # Salva como suspeita sem scoring
                _salvar_suspeita(db, v, reasons)
                stats["suspeitas"] += 1
                continue

            # 4. Detecção de janela de oportunidade
            is_early = False
            try:
                is_early = opp_detector.check_early_window(v)
            except Exception as e:
                logger.warning(f"Erro no opportunity detector: {e}")

            # 5. Scoring
            score_result = {}
            try:
                if scorer:
                    score_result = scorer.score_job(v)
                else:
                    resultado = calcular_score(
                        titulo=v.get("titulo", ""),
                        descricao=v.get("descricao", ""),
                        localizacao=v.get("localizacao", ""),
                    )
                    if isinstance(resultado, tuple):
                        sc, kws = resultado
                    else:
                        sc, kws = resultado, []
                    score_result = {
                        "score": sc, "grade": _score_to_grade(sc),
                        "match_analysis": "", "highlights": kws,
                        "gaps": [], "score_method": "keyword",
                    }
            except Exception as e:
                logger.error(f"Erro no scoring: {e}")
                score_result = {"score": 0.0, "grade": "F", "score_method": "keyword"}

            score = score_result.get("score", 0.0)

            # 6. Aplica boost para janela de oportunidade
            if is_early:
                score = opp_detector.apply_boost(score, True)
                score_result["score"] = score

            # 7. Descarta vagas com score muito baixo
            if score < 2.0:
                stats["ignoradas"] += 1
                continue

            # 8. Persiste no banco
            try:
                highlights = score_result.get("highlights", [])
                nova_vaga = Vaga(
                    titulo=v.get("titulo", "")[:300],
                    empresa=v.get("empresa", "")[:200],
                    localizacao=v.get("localizacao", "")[:200],
                    modalidade=v.get("modalidade", ""),
                    fonte=v.get("fonte", ""),
                    url=v.get("url", "")[:500],
                    descricao=v.get("descricao", ""),
                    palavras_chave=json.dumps(highlights, ensure_ascii=False),
                    score=score,
                    score_method=score_result.get("score_method", "keyword"),
                    score_grade=score_result.get("grade", ""),
                    score_analysis=score_result.get("match_analysis", ""),
                    posted_at=v.get("posted_at"),
                    is_early_applicant=is_early,
                    status="nova",
                    data_encontrada=datetime.utcnow(),
                )
                db.add(nova_vaga)
                db.commit()
                stats["novas"] += 1
            except Exception as e:
                db.rollback()
                logger.error(f"Erro ao salvar vaga '{v.get('titulo', '')}': {e}")
                continue

            # 9. Notificação de vaga relevante
            if score >= MIN_SCORE:
                vaga_dict = {
                    "titulo": nova_vaga.titulo,
                    "empresa": nova_vaga.empresa,
                    "localizacao": nova_vaga.localizacao,
                    "fonte": nova_vaga.fonte,
                    "url": nova_vaga.url,
                    "score": nova_vaga.score,
                    "grade": nova_vaga.score_grade,
                }
                try:
                    notificar_nova_vaga(vaga_dict)
                    nova_vaga.notificada = True
                    db.commit()
                    stats["notificadas"] += 1
                except Exception as e:
                    logger.error(f"Erro ao notificar vaga: {e}")

            # 10. Notificação especial para janela aberta
            if is_early and nova_vaga.notificada:
                try:
                    horas_publicada = _calcular_horas_publicada(v.get("posted_at"))
                    vaga_dict["horas_publicada"] = horas_publicada
                    notify_early_opportunity(vaga_dict)

                    # Marca alerta como notificado
                    from core.models import _DB_PATH
                    conn = _sqlite3.connect(_DB_PATH)  # FIX v2.0: removido import sqlite3 duplicado
                    conn.execute(
                        "UPDATE opportunity_alerts SET notified_at=? WHERE job_id=?",
                        (datetime.utcnow().isoformat(), nova_vaga.id),
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.error(f"Erro ao notificar janela de oportunidade: {e}")

            # 11. Geração automática de CV para vagas de alto score
            if score >= MIN_SCORE_CV:
                try:
                    vaga_dict_cv = {
                        "id": nova_vaga.id,
                        "titulo": nova_vaga.titulo,
                        "empresa": nova_vaga.empresa,
                        "localizacao": nova_vaga.localizacao,
                        "descricao": nova_vaga.descricao,
                        "url": nova_vaga.url,
                        "score": nova_vaga.score,
                        "grade": nova_vaga.score_grade,
                    }
                    cv_path = cv_gen.generate(vaga_dict_cv)
                    if cv_path:
                        nova_vaga.status = "cv_gerado"
                        db.commit()
                        stats["cvs_gerados"] += 1
                        notify_cv_generated(vaga_dict_cv, cv_path)
                        logger.info(f"CV gerado automaticamente para '{nova_vaga.titulo}'")
                except Exception as e:
                    logger.error(f"Erro ao gerar CV automatico: {e}")

        logger.info(f"Processamento concluido: {stats}")

    except Exception as e:
        db.rollback()
        logger.error(f"Erro geral no processamento: {e}")
    finally:
        db.close()

    return stats


def _salvar_suspeita(db: DBSession, v: dict, reasons: list):
    """Salva vaga suspeita no banco com score 0 e status 'suspeita'."""
    try:
        nova = Vaga(
            titulo=v.get("titulo", "")[:300],
            empresa=v.get("empresa", "")[:200],
            localizacao=v.get("localizacao", "")[:200],
            fonte=v.get("fonte", ""),
            url=v.get("url", "")[:500],
            score=0.0,
            score_method="keyword",
            status="suspeita",
            notas="; ".join(reasons),
            data_encontrada=datetime.utcnow(),
        )
        db.add(nova)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Erro ao salvar vaga suspeita: {e}")


def _score_to_grade(score: float) -> str:
    if score >= 9.0:
        return "A"
    if score >= 7.0:
        return "B"
    if score >= 5.0:
        return "C"
    if score >= 3.0:
        return "D"
    return "F"


def _calcular_horas_publicada(posted_at) -> str:
    if not posted_at:
        return "?"
    if isinstance(posted_at, str):
        try:
            posted_at = datetime.fromisoformat(posted_at)
        except Exception:
            return "?"
    diff = datetime.utcnow() - posted_at
    return str(round(diff.total_seconds() / 3600, 1))


# ── MONITORAMENTO DE CANDIDATURAS ─────────────────────────────────────────────

def verificar_status_candidaturas():
    """Verifica candidaturas ativas: se URL retornar 404/410, marca como encerrada."""
    db: DBSession = Session()
    try:
        candidaturas = db.query(Vaga).filter(
            Vaga.aplicada == True,
            Vaga.status.notin_(["rejeitada", "encerrada"]),
        ).all()

        logger.info(f"Verificando {len(candidaturas)} candidaturas ativas...")

        for vaga in candidaturas:
            try:
                resp = _requests.head(vaga.url, timeout=10, allow_redirects=True)
                if resp.status_code in (404, 410):
                    status_old = vaga.status
                    hist = StatusHistory(
                        vaga_id=vaga.id,
                        status_old=status_old,
                        status_new="encerrada",
                        timestamp=datetime.utcnow(),
                        detalhes="Vaga nao encontrada (404/410)",
                    )
                    db.add(hist)
                    vaga.status = "encerrada"
                    vaga.last_check = datetime.utcnow()
                    db.commit()
                    notificar_mudanca_status(
                        {"titulo": vaga.titulo, "empresa": vaga.empresa, "url": vaga.url},
                        status_old, "encerrada",
                    )
                else:
                    vaga.last_check = datetime.utcnow()
                    db.commit()
            except Exception as e:
                logger.warning(f"Erro ao verificar {vaga.url}: {e}")
    finally:
        db.close()


# ── RELATÓRIO ─────────────────────────────────────────────────────────────────

def gerar_resumo() -> dict:
    db: DBSession = Session()
    try:
        total      = db.query(Vaga).count()
        aplicadas  = db.query(Vaga).filter_by(aplicada=True).count()
        em_analise = db.query(Vaga).filter_by(status="em_analise").count()
        entrevista = db.query(Vaga).filter_by(status="entrevista").count()
        rejeitadas = db.query(Vaga).filter_by(status="rejeitada").count()
        novas      = db.query(Vaga).filter_by(status="nova", notificada=False).count()
        high_score = db.query(Vaga).filter(Vaga.score >= 7.0).count()

        return {
            "total": total, "novas": novas, "aplicadas": aplicadas,
            "em_analise": em_analise, "entrevistas": entrevista,
            "rejeitadas": rejeitadas, "high_score": high_score,
        }
    finally:
        db.close()


# ── MARCAR COMO APLICADA ──────────────────────────────────────────────────────

def marcar_aplicada(url: str, notas: str = ""):
    """Marca vaga como aplicada. Cria registro mínimo se URL não estiver no banco."""
    db: DBSession = Session()
    try:
        vaga = db.query(Vaga).filter_by(url=url).first()

        if not vaga:
            logger.info(f"URL nao encontrada no banco — criando registro: {url}")
            vaga = Vaga(
                titulo="Vaga adicionada manualmente",
                empresa="",
                localizacao="",
                fonte="manual",
                url=url[:500],
                score=0.0,
                status="nova",
                data_encontrada=datetime.utcnow(),
            )
            db.add(vaga)
            db.commit()

        vaga.aplicada = True
        vaga.status = "aplicada"
        vaga.data_aplicacao = datetime.utcnow()
        vaga.last_check = datetime.utcnow()
        if notas:
            vaga.notas = notas

        hist = StatusHistory(
            vaga_id=vaga.id,
            status_old="nova",
            status_new="aplicada",
            timestamp=datetime.utcnow(),
            detalhes=f"Marcada via CLI. Notas: {notas}" if notas else "Marcada via CLI",
        )
        db.add(hist)
        db.commit()
        logger.info(f"Vaga marcada como aplicada: {vaga.titulo} — {url}")
    finally:
        db.close()


# ── CICLO COMPLETO ────────────────────────────────────────────────────────────

def ciclo_completo():
    """Executa busca + pipeline completo + verificação de candidaturas."""
    logger.info("Iniciando ciclo completo do Job Agent v2.0")

    vagas_raw = buscar_todas_fontes()
    stats = processar_e_salvar(vagas_raw)
    verificar_status_candidaturas()

    try:
        notify_pipeline_health(stats)
    except Exception as e:
        logger.error(f"Erro ao enviar resumo de ciclo: {e}")

    logger.info(f"Ciclo concluido: {stats}")
    return stats


if __name__ == "__main__":
    init_db()
    ciclo_completo()
