"""
agent.py — Orquestrador principal do Job Agent
Coordena scraping, scoring, persistência e notificações.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import requests as _requests
from loguru import logger
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
import json

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
)

MIN_SCORE = float(os.getenv("MIN_SCORE_TO_NOTIFY", 6.0))

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger.add(
    os.path.join(_BASE_DIR, "logs", "agent_{time:YYYY-MM-DD}.log"),
    rotation="1 day",
    retention="7 days",
    level="INFO",
)


# ── BUSCA DE NOVAS VAGAS ──────────────────────────────────────────────────────

def buscar_todas_fontes() -> list[dict]:
    """Executa busca em todas as fontes e retorna lista unificada."""
    print("[INFO] Buscando vagas em todas as fontes...")
    todas = []
    queries = PERFIL["queries_busca"]

    for query in queries:
        logger.info(f"🔍 Buscando: '{query}'")

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

    logger.info(f"📦 Total após deduplicação: {len(unicas)} vagas")
    print(f"[INFO] {len(unicas)} vagas únicas encontradas")
    return unicas


# ── SCORING & PERSISTÊNCIA ────────────────────────────────────────────────────

def processar_e_salvar(vagas_raw: list[dict]) -> dict:
    """Calcula score, filtra relevantes e salva no banco."""
    db: DBSession = Session()
    stats = {"novas": 0, "ignoradas": 0, "duplicadas": 0, "notificadas": 0}

    try:
        for v in vagas_raw:
            existente = db.query(Vaga).filter_by(url=v["url"]).first()
            if existente:
                stats["duplicadas"] += 1
                continue

            if v.get("fonte") == "linkedin" and not v.get("descricao"):
                v["descricao"] = buscar_descricao_linkedin(v["url"])

            resultado = calcular_score(
                titulo=v.get("titulo", ""),
                descricao=v.get("descricao", ""),
                localizacao=v.get("localizacao", ""),
            )

            if isinstance(resultado, tuple):
                score, matched_kw = resultado
            else:
                score, matched_kw = resultado, []

            if score < 2.0:
                stats["ignoradas"] += 1
                continue

            nova_vaga = Vaga(
                titulo=v.get("titulo", "")[:300],
                empresa=v.get("empresa", "")[:200],
                localizacao=v.get("localizacao", "")[:200],
                modalidade=v.get("modalidade", ""),
                fonte=v.get("fonte", ""),
                url=v.get("url", "")[:500],
                descricao=v.get("descricao", ""),
                palavras_chave=json.dumps(matched_kw, ensure_ascii=False),
                score=score,
                status="nova",
                data_encontrada=datetime.utcnow(),
            )
            db.add(nova_vaga)
            db.commit()
            stats["novas"] += 1

            if score >= MIN_SCORE:
                vaga_dict = {
                    "titulo": nova_vaga.titulo,
                    "empresa": nova_vaga.empresa,
                    "localizacao": nova_vaga.localizacao,
                    "fonte": nova_vaga.fonte,
                    "url": nova_vaga.url,
                    "score": nova_vaga.score,
                }
                notificar_nova_vaga(vaga_dict)
                nova_vaga.notificada = True
                db.commit()
                stats["notificadas"] += 1

        logger.info(f"✅ Processamento concluído: {stats}")

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar vagas: {e}")
    finally:
        db.close()

    return stats


# ── MONITORAMENTO DE CANDIDATURAS ─────────────────────────────────────────────

def verificar_status_candidaturas():
    """
    Verifica candidaturas ativas: se URL retornar 404/410, marca como encerrada.
    """
    db: DBSession = Session()
    print("[INFO] Verificando status das candidaturas ativas...")

    try:
        candidaturas = db.query(Vaga).filter(
            Vaga.aplicada == True,
            Vaga.status.notin_(["rejeitada", "encerrada"])
        ).all()

        logger.info(f"🔄 Verificando {len(candidaturas)} candidaturas ativas...")

        for vaga in candidaturas:
            try:
                resp = _requests.head(vaga.url, timeout=10, allow_redirects=True)
                novo_status = None

                if resp.status_code in (404, 410):
                    novo_status = "encerrada"

                if novo_status and novo_status != vaga.status:
                    status_old = vaga.status
                    hist = StatusHistory(
                        vaga_id=vaga.id,
                        status_old=status_old,
                        status_new=novo_status,
                        timestamp=datetime.utcnow(),
                        detalhes="Vaga não encontrada (404/410)",
                    )
                    db.add(hist)
                    vaga.status = novo_status
                    vaga.last_check = datetime.utcnow()
                    db.commit()

                    notificar_mudanca_status(
                        {"titulo": vaga.titulo, "empresa": vaga.empresa, "url": vaga.url},
                        status_old,
                        novo_status,
                    )
                    logger.info(f"📌 {vaga.titulo} → {novo_status}")
                else:
                    vaga.last_check = datetime.utcnow()
                    db.commit()

            except Exception as e:
                logger.warning(f"Erro ao verificar {vaga.url}: {e}")
                continue

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
            "total": total,
            "novas": novas,
            "aplicadas": aplicadas,
            "em_analise": em_analise,
            "entrevistas": entrevista,
            "rejeitadas": rejeitadas,
            "high_score": high_score,
        }
    finally:
        db.close()


# ── MARCAR COMO APLICADA ──────────────────────────────────────────────────────

def marcar_aplicada(url: str, notas: str = ""):
    """
    Marca vaga como aplicada. Se a URL não estiver no banco, cria um registro
    com dados mínimos para que o monitoramento comece imediatamente.
    """
    db: DBSession = Session()
    try:
        vaga = db.query(Vaga).filter_by(url=url).first()

        if not vaga:
            logger.info(f"URL não encontrada no banco — criando registro: {url}")
            print(f"[INFO] Vaga não estava no banco — adicionando para monitoramento: {url}")
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
        logger.info(f"✅ Vaga marcada como aplicada: {vaga.titulo} — {url}")
        print(f"[INFO] Vaga salva como 'aplicada' — monitoramento ativado")
    finally:
        db.close()


# ── CICLO COMPLETO ────────────────────────────────────────────────────────────

def ciclo_completo():
    """Executa busca + scoring + persistência + verificação de candidaturas."""
    print("[INFO] Iniciando ciclo completo do Job Agent...")
    logger.info("🚀 Iniciando ciclo completo do Job Agent")

    vagas_raw = buscar_todas_fontes()
    stats = processar_e_salvar(vagas_raw)
    verificar_status_candidaturas()

    logger.info(f"✅ Ciclo concluído: {stats}")
    print(f"[INFO] Ciclo concluído: {stats}")
    return stats


if __name__ == "__main__":
    init_db()
    ciclo_completo()
