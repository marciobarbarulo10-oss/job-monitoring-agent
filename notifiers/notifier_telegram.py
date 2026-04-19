"""
notifier_telegram.py — Envio de notificações via Telegram Bot API (HTTP direto)
Usa requests puro — sem dependência de python-telegram-bot ou asyncio.
"""
import os
import requests
from loguru import logger
from datetime import datetime


def _get_config() -> tuple[str, str]:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env")
    if not chat_id:
        raise ValueError("TELEGRAM_CHAT_ID não configurado no .env")
    return token, chat_id


def enviar_telegram(mensagem: str) -> bool:
    """Envia mensagem via Telegram Bot API. Retorna True se enviou com sucesso."""
    print("[INFO] Enviando notificação Telegram...")
    try:
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
            logger.info("✅ Notificação Telegram enviada com sucesso")
            print("[INFO] Notificação Telegram enviada com sucesso")
            return True
        else:
            logger.error(f"Telegram retornou erro: {data}")
            print(f"[ERRO] Telegram retornou: {data}")
            return False
    except ValueError as e:
        logger.warning(f"Telegram não configurado: {e}")
        print(f"[ERRO] {e}")
        return False
    except requests.RequestException as e:
        logger.error(f"Falha ao enviar mensagem Telegram: {e}")
        print(f"[ERRO] Falha ao enviar mensagem Telegram: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado no Telegram: {e}")
        print(f"[ERRO] Erro inesperado no Telegram: {e}")
        return False


def notificar_nova_vaga(vaga: dict) -> bool:
    """Formata e envia notificação de nova vaga encontrada."""
    score = vaga.get("score", 0)
    stars = "⭐" * int(score // 2)

    msg = (
        f"🆕 *NOVA VAGA ENCONTRADA*\n"
        f"{stars} Score: *{score}/10*\n\n"
        f"💼 *{vaga.get('titulo', 'N/A')}*\n"
        f"🏢 {vaga.get('empresa', 'N/A')}\n"
        f"📍 {vaga.get('localizacao', 'N/A')}\n"
        f"🌐 Fonte: {vaga.get('fonte', '').upper()}\n\n"
        f"🔗 [Ver vaga]({vaga.get('url', '#')})\n"
        f"🕐 Encontrada em: {datetime.now().strftime('%d/%m %H:%M')}"
    )
    return enviar_telegram(msg)


def notificar_mudanca_status(vaga: dict, status_old: str, status_new: str) -> bool:
    """Notifica mudança de status em candidatura."""
    emoji_map = {
        "em_analise": "🔍",
        "entrevista": "🎯",
        "rejeitada": "❌",
        "encerrada": "🔒",
        "nova": "🆕",
        "aplicada": "📨",
    }
    emoji = emoji_map.get(status_new, "📌")

    msg = (
        f"{emoji} *ATUALIZAÇÃO DE CANDIDATURA*\n\n"
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
        f"📊 *RESUMO DIÁRIO — Job Agent*\n"
        f"📅 {datetime.now().strftime('%d/%m/%Y')}\n\n"
        f"🔎 Novas vagas encontradas: *{stats.get('novas', 0)}*\n"
        f"📨 Candidaturas ativas: *{stats.get('aplicadas', 0)}*\n"
        f"🔍 Em análise: *{stats.get('em_analise', 0)}*\n"
        f"🎯 Entrevistas: *{stats.get('entrevistas', 0)}*\n"
        f"❌ Rejeitadas: *{stats.get('rejeitadas', 0)}*\n"
        f"⭐ Vagas score ≥ 7: *{stats.get('high_score', 0)}*"
    )
    return enviar_telegram(msg)
