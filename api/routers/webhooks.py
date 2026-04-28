"""
api/routers/webhooks.py — Endpoints de webhook do MailerLite.

Recebem eventos em tempo real e executam ações no sistema.

Webhooks configurados no MailerLite:
  POST /webhooks/mailerlite/subscriber  → criado, grupo, automação
  POST /webhooks/mailerlite/campaign    → campanha enviada
  POST /webhooks/mailerlite/unsubscribe → cancelamento / bounce
  GET  /webhooks/mailerlite/health      → status dos endpoints

Segurança: valida X-MailerLite-Signature com HMAC-SHA256.
Em modo desenvolvimento (ENV != production), aceita sem assinatura.
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header
from api.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Secrets dos webhooks — valores defaults são os da conta MailerLite
WEBHOOK_SECRETS = {
    "subscriber":  os.getenv("ML_WEBHOOK_SECRET_SUBSCRIBER", "RKI50uEPTv"),
    "campaign":    os.getenv("ML_WEBHOOK_SECRET_CAMPAIGN",   "xxhDAaU9K0"),
    "unsubscribe": os.getenv("ML_WEBHOOK_SECRET_UNSUBSCRIBE","BdI6Gg20XD"),
}


def _verify_signature(payload: bytes, signature: Optional[str], secret: str) -> bool:
    """Valida assinatura HMAC-SHA256 do MailerLite. Em dev, aceita sem assinatura."""
    if not signature:
        return os.getenv("ENV", "development") == "development"
    try:
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def _log_event(event_type: str, data: dict):
    """Persiste evento no banco para auditoria e visibilidade nos logs de agente."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO agent_logs (agent_name, action, status, details) VALUES (?, ?, ?, ?)",
            (
                "mailerlite_webhook",
                event_type,
                "received",
                json.dumps(data, ensure_ascii=False)[:1000],
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Falha ao logar webhook: {e}")


def _notify_new_subscriber(name: str, email: str):
    """Notifica Telegram quando novo subscriber é criado."""
    try:
        from notifiers.notifier_telegram import enviar_telegram
        enviar_telegram(
            f"*Novo subscriber — Job Agent!*\n\n"
            f"Nome: {name}\n"
            f"Email: {email}\n"
            f"Horario: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Sequencia de emails disparada automaticamente."
        )
    except Exception as e:
        logger.warning(f"Telegram notify falhou: {e}")


# ─────────────────────────────────────────────
# WEBHOOK 1 — Subscriber
# ─────────────────────────────────────────────

@router.post("/mailerlite/subscriber")
async def webhook_subscriber(
    request: Request,
    x_mailerlite_signature: Optional[str] = Header(None),
):
    """
    Eventos: subscriber.created, subscriber.added_to_group,
             subscriber.automation_triggered, subscriber.automation_completed
    """
    body = await request.body()

    if not _verify_signature(body, x_mailerlite_signature, WEBHOOK_SECRETS["subscriber"]):
        raise HTTPException(401, "Assinatura invalida")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "Payload invalido")

    event_type = payload.get("type", "unknown")
    data = payload.get("data", {})
    subscriber = data.get("subscriber", {})
    email = subscriber.get("email", "")
    name = (subscriber.get("fields") or {}).get("name", "")

    logger.info(f"Webhook MailerLite [{event_type}]: {email}")
    _log_event(event_type, {"email": email, "event": event_type})

    if event_type == "subscriber.created":
        logger.info(f"Novo subscriber: {name} <{email}>")
        _notify_new_subscriber(name, email)

    elif event_type == "subscriber.added_to_group":
        group_name = data.get("group", {}).get("name", "")
        logger.info(f"{email} adicionado ao grupo: {group_name}")

    elif event_type in ("subscriber.automation_triggered", "subscriber.automation_completed"):
        automation_name = data.get("automation", {}).get("name", "")
        logger.info(f"Automacao [{event_type}] para {email}: {automation_name}")

    return {"status": "ok", "event": event_type}


# ─────────────────────────────────────────────
# WEBHOOK 2 — Campaign
# ─────────────────────────────────────────────

@router.post("/mailerlite/campaign")
async def webhook_campaign(
    request: Request,
    x_mailerlite_signature: Optional[str] = Header(None),
):
    """Evento: campaign.sent"""
    body = await request.body()

    if not _verify_signature(body, x_mailerlite_signature, WEBHOOK_SECRETS["campaign"]):
        raise HTTPException(401, "Assinatura invalida")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "Payload invalido")

    event_type = payload.get("type", "unknown")
    campaign = payload.get("data", {}).get("campaign", {})
    name = campaign.get("name", "")
    sent = campaign.get("stats", {}).get("sent", 0)

    logger.info(f"Campanha enviada: {name} — {sent} destinatarios")
    _log_event(event_type, {"campaign": name, "sent": sent})

    return {"status": "ok", "event": event_type}


# ─────────────────────────────────────────────
# WEBHOOK 3 — Unsubscribe / Bounce
# ─────────────────────────────────────────────

@router.post("/mailerlite/unsubscribe")
async def webhook_unsubscribe(
    request: Request,
    x_mailerlite_signature: Optional[str] = Header(None),
):
    """Eventos: subscriber.unsubscribed, subscriber.bounced"""
    body = await request.body()

    if not _verify_signature(body, x_mailerlite_signature, WEBHOOK_SECRETS["unsubscribe"]):
        raise HTTPException(401, "Assinatura invalida")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "Payload invalido")

    event_type = payload.get("type", "unknown")
    email = payload.get("data", {}).get("subscriber", {}).get("email", "")

    logger.info(f"Webhook {event_type}: {email}")
    _log_event(event_type, {"email": email, "event": event_type})

    return {"status": "ok", "event": event_type}


# ─────────────────────────────────────────────
# HEALTH — verificação dos endpoints
# ─────────────────────────────────────────────

@router.get("/mailerlite/health")
def webhook_health():
    """Confirma que os endpoints de webhook estão registrados e ativos."""
    return {
        "status": "ok",
        "endpoints": [
            "/webhooks/mailerlite/subscriber",
            "/webhooks/mailerlite/campaign",
            "/webhooks/mailerlite/unsubscribe",
        ],
        "webhook_ids": {
            "subscriber":  "185947723042654020",
            "campaign":    "185947728340059568",
            "unsubscribe": "185947733847180420",
        },
        "webhooks_configured": 3,
        "timestamp": datetime.now().isoformat(),
    }
