"""
notifier_telegram.py — Envio de notificações via Telegram Bot API (HTTP direto).
Suporta retry com backoff, rate limiting e múltiplos tipos de notificação.
"""
import os
import time
import threading
import requests
from loguru import logger
from datetime import datetime

# Rate limiting: máximo 20 msgs/min
_rate_lock = threading.Lock()
_msg_timestamps: list[float] = []
_MAX_MSGS_PER_MIN = 20


def _get_config() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN nao configurado no .env")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID nao configurado no .env")
    return token, chat_id


def _enforce_rate_limit():
    """Garante no máximo 20 mensagens por minuto."""
    with _rate_lock:
        now = time.time()
        _msg_timestamps[:] = [t for t in _msg_timestamps if now - t < 60]
        if len(_msg_timestamps) >= _MAX_MSGS_PER_MIN:
            wait = 60 - (now - _msg_timestamps[0]) + 1
            if wait > 0:
                logger.info(f"Rate limit Telegram: aguardando {wait:.1f}s...")
                time.sleep(wait)
        _msg_timestamps.append(time.time())


def enviar_telegram(mensagem: str) -> bool:
    """
    Envia mensagem via Telegram Bot API.
    Retry automático: 3 tentativas com espera 5s/15s/30s.
    """
    WAITS = [5, 15, 30]

    for attempt, wait in enumerate(WAITS):
        try:
            _enforce_rate_limit()
            token, chat_id = _get_config()
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": mensagem,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("ok"):
                logger.info("Notificacao Telegram enviada com sucesso")
                return True
            else:
                logger.error(f"Telegram retornou erro: {data}")
                return False

        except ValueError as e:
            logger.warning(f"Telegram nao configurado: {e}")
            return False
        except requests.RequestException as e:
            logger.error(f"Falha ao enviar Telegram (tentativa {attempt + 1}): {e}")
            if attempt < len(WAITS) - 1:
                time.sleep(wait)
        except Exception as e:
            logger.error(f"Erro inesperado no Telegram (tentativa {attempt + 1}): {e}")
            if attempt < len(WAITS) - 1:
                time.sleep(wait)

    logger.error("Telegram: todas as tentativas falharam")
    return False


# ── NOTIFICAÇÕES EXISTENTES ───────────────────────────────────────────────────

def notificar_nova_vaga(vaga: dict) -> bool:
    """Notifica nova vaga encontrada com score relevante."""
    score = vaga.get("score", 0)
    grade = vaga.get("grade", "")
    stars = "★" * min(int(score // 2), 5)
    grade_str = f" [{grade}]" if grade else ""

    msg = (
        f"🆕 *NOVA VAGA ENCONTRADA*{grade_str}\n"
        f"{stars} Score: *{score}/10*\n\n"
        f"💼 *{vaga.get('titulo', 'N/A')}*\n"
        f"🏢 {vaga.get('empresa', 'N/A')}\n"
        f"📍 {vaga.get('localizacao', 'N/A')}\n"
        f"🌐 Fonte: {(vaga.get('fonte') or '').upper()}\n\n"
        f"🔗 [Ver vaga]({vaga.get('url', '#')})\n"
        f"🕐 {datetime.now().strftime('%d/%m %H:%M')}"
    )
    return enviar_telegram(msg)


def notificar_mudanca_status(vaga: dict, status_old: str, status_new: str) -> bool:
    """Notifica mudança de status em candidatura ativa."""
    emoji_map = {
        "em_analise": "🔍", "entrevista": "🎯", "rejeitada": "❌",
        "encerrada": "🔒", "nova": "🆕", "aplicada": "📨", "proposta": "💰",
    }
    emoji = emoji_map.get(status_new, "📌")

    msg = (
        f"{emoji} *ATUALIZACAO DE CANDIDATURA*\n\n"
        f"💼 *{vaga.get('titulo', 'N/A')}*\n"
        f"🏢 {vaga.get('empresa', 'N/A')}\n\n"
        f"📊 Status: `{status_old}` → `{status_new}`\n"
        f"🔗 [Ver vaga]({vaga.get('url', '#')})\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )
    return enviar_telegram(msg)


def notificar_resumo_diario(stats: dict) -> bool:
    """Envia resumo diário das candidaturas."""
    msg = (
        f"📊 *RESUMO DIARIO — Job Agent*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"🔎 Novas vagas: *{stats.get('novas', 0)}*\n"
        f"📨 Candidaturas ativas: *{stats.get('aplicadas', 0)}*\n"
        f"🔍 Em analise: *{stats.get('em_analise', 0)}*\n"
        f"🎯 Entrevistas: *{stats.get('entrevistas', 0)}*\n"
        f"❌ Rejeitadas: *{stats.get('rejeitadas', 0)}*\n"
        f"⭐ Score >= 7: *{stats.get('high_score', 0)}*"
    )
    return enviar_telegram(msg)


# ── NOVAS NOTIFICAÇÕES v2.0 ───────────────────────────────────────────────────

def notify_early_opportunity(job: dict) -> bool:
    """Alerta especial para vaga publicada há menos de 48h."""
    horas = job.get("horas_publicada", "?")
    score = job.get("score", 0)
    grade = job.get("grade", "")

    msg = (
        f"🚨 *[JANELA ABERTA]* Candidatura precoce!\n\n"
        f"💼 *{job.get('titulo', 'N/A')}*\n"
        f"🏢 {job.get('empresa', 'N/A')}\n"
        f"📍 {job.get('localizacao', 'N/A')}\n\n"
        f"⏱ Publicada ha *{horas}h* | Score: *{score}/10* [{grade}]\n"
        f"🔗 [Aplicar agora]({job.get('url', '#')})\n"
        f"📌 Candidatos precoces tem vantagem competitiva!"
    )
    return enviar_telegram(msg)


def notify_cv_generated(job: dict, cv_path: str) -> bool:
    """Notifica geração automática de CV customizado."""
    score = job.get("score", 0)
    grade = job.get("grade", "")
    filename = cv_path.split("\\")[-1].split("/")[-1] if cv_path else "cv.pdf"

    msg = (
        f"📄 *CV GERADO AUTOMATICAMENTE*\n\n"
        f"💼 *{job.get('titulo', 'N/A')}*\n"
        f"🏢 {job.get('empresa', 'N/A')}\n"
        f"⭐ Score: *{score}/10* [{grade}]\n\n"
        f"📁 Arquivo: `{filename}`\n\n"
        f"✅ Proximo passo: revisar o CV e aplicar!\n"
        f"🔗 [Ver vaga]({job.get('url', '#')})"
    )
    return enviar_telegram(msg)


def notify_weekly_market(report: dict) -> bool:
    """Envia resumo semanal do mercado de vagas."""
    total = report.get("total_vagas", 0)
    score_medio = report.get("score_medio", 0)
    variacao = report.get("variacao_semana_pct", 0)
    variacao_str = f"+{variacao}%" if variacao >= 0 else f"{variacao}%"

    top3_empresas = [e["empresa"] for e in report.get("top_empresas", [])[:3]]
    top3_kws = [k["keyword"] for k in report.get("top_keywords", [])[:5]]

    empresas_str = ", ".join(top3_empresas) if top3_empresas else "—"
    kws_str = ", ".join(top3_kws) if top3_kws else "—"

    destaques = report.get("destaques", [])
    destaque_str = ""
    if destaques:
        d = destaques[0]
        destaque_str = f"\n\n🏆 Destaque: *{d.get('titulo', '')}* @ {d.get('empresa', '')} (score {d.get('score', 0)})"

    msg = (
        f"📊 *RELATORIO SEMANAL DE MERCADO*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"📦 Vagas coletadas: *{total}* ({variacao_str} vs semana anterior)\n"
        f"⭐ Score medio: *{score_medio}/10*\n\n"
        f"🏢 Top empresas: {empresas_str}\n"
        f"🔑 Keywords em alta: {kws_str}"
        f"{destaque_str}"
    )
    return enviar_telegram(msg)


def notify_feedback_insight(insight: str, amostras: int = 0) -> bool:
    """Notifica insight gerado pela recalibração do FeedbackEngine."""
    msg = (
        f"🧠 *INSIGHT DE CALIBRACAO*\n\n"
        f"{insight}\n\n"
        f"📈 Baseado em {amostras} candidaturas registradas."
    )
    return enviar_telegram(msg)


def notify_pipeline_health(stats: dict) -> bool:
    """Resume o ciclo de coleta com métricas de saúde do pipeline."""
    novas = stats.get("novas", 0)
    duplicadas = stats.get("duplicadas", 0)
    ignoradas = stats.get("ignoradas", 0)
    suspeitas = stats.get("suspeitas", 0)
    notificadas = stats.get("notificadas", 0)
    cvs_gerados = stats.get("cvs_gerados", 0)

    msg = (
        f"✅ *CICLO CONCLUIDO*\n"
        f"🕐 {datetime.now().strftime('%d/%m %H:%M')}\n\n"
        f"📥 Vagas novas: *{novas}*\n"
        f"🔔 Notificadas: *{notificadas}*\n"
        f"📄 CVs gerados: *{cvs_gerados}*\n"
        f"🚫 Suspeitas: *{suspeitas}* | Duplicadas: *{duplicadas}* | Baixo score: *{ignoradas}*"
    )
    return enviar_telegram(msg)


def notify_maintenance_report(relatorio: dict) -> bool:
    """Resume execução da manutenção semanal do pipeline."""
    saude = relatorio.get("saude", {})
    msg = (
        f"🔧 *MANUTENCAO SEMANAL CONCLUIDA*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"🗑 Duplicatas removidas: *{relatorio.get('duplicatas_removidas', 0)}*\n"
        f"🔄 Status normalizados: *{relatorio.get('status_normalizados', 0)}*\n"
        f"📊 Total no banco: *{saude.get('total_jobs', 0)}*\n"
        f"❤️ Saude: *{saude.get('status', 'desconhecido')}*"
    )
    return enviar_telegram(msg)
