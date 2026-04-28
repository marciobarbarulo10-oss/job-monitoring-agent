"""
Agente de Sequência de Emails — controla e envia a sequência de 5 emails
para cada novo subscriber do Job Agent.

Sequência:
  Dia 0  → Boas-vindas + agente ativo
  Dia 3  → Primeiras vagas com score alto
  Dia 7  → Insights de mercado da semana
  Dia 10 → Convite para estrela no GitHub
  Dia 17 → Resumo mensal
"""
import os
import logging
import requests
import time
from datetime import datetime, timedelta

from agents import BaseAgent
from core.models import get_connection

logger = logging.getLogger(__name__)

MAILERLITE_API = "https://connect.mailerlite.com/api"

EMAIL_SEQUENCE = [
    {
        "day": 0,
        "subject": "Seu agente de vagas esta ativo!",
        "html": """<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden">
<tr><td style="background:#1D9E75;padding:32px;text-align:center">
<div style="font-size:48px">Robot</div>
<h1 style="color:white;margin:12px 0 4px;font-size:24px">Job Agent</h1>
<p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px">Seu agente autonomo de busca de emprego</p>
</td></tr>
<tr><td style="padding:32px">
<h2 style="color:#1a1a1a;font-size:20px;margin:0 0 16px">Seu agente esta ativo!</h2>
<p style="color:#444;line-height:1.7;margin:0 0 16px">Seu Job Agent esta rodando <strong>24 horas por dia, 7 dias por semana</strong>, buscando as melhores vagas automaticamente no LinkedIn, Gupy e Vagas.com.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0faf6;border-radius:12px;margin:0 0 28px">
<tr><td style="padding:20px"><table width="100%" cellpadding="8">
<tr><td style="font-size:13px;color:#333">Busca automatica em multiplos portais</td></tr>
<tr><td style="font-size:13px;color:#333">Score de aderencia calculado por IA para cada vaga</td></tr>
<tr><td style="font-size:13px;color:#333">Carta de apresentacao gerada automaticamente</td></tr>
<tr><td style="font-size:13px;color:#333">Alertas no Telegram quando o score for alto</td></tr>
</table></td></tr></table>
<table width="100%"><tr><td align="center">
<a href="http://localhost:5173" style="display:inline-block;background:#1D9E75;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:bold">Acessar meu dashboard</a>
</td></tr></table></td></tr>
<tr><td style="background:#f9f9f9;padding:20px;text-align:center;border-top:1px solid #eee">
<a href="https://github.com/marciobarbarulo10-oss/job-monitoring-agent" style="color:#1D9E75;font-size:12px">Ver no GitHub</a>
</td></tr></table></td></tr></table></body></html>"""
    },
    {
        "day": 3,
        "subject": "Suas primeiras vagas com score alto — confira agora",
        "html": """<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden">
<tr><td style="background:#1D9E75;padding:28px;text-align:center">
<h1 style="color:white;margin:0;font-size:22px">Suas primeiras vagas com score alto</h1>
<p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px">Seu agente ja trabalhou — veja o resultado</p>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#444;line-height:1.7;margin:0 0 24px">Seu agente coletou dezenas de vagas e calculou o score de aderencia. As vagas com <strong>grade A</strong> tem mais de 70% de compatibilidade com seu perfil.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="border-radius:12px;overflow:hidden;margin:0 0 28px;border:1px solid #eee">
<tr><td style="padding:14px 16px;font-size:13px;color:#333;border-bottom:1px solid #f0f0f0">
<span style="background:#E8F5E9;color:#1D9E75;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:bold;margin-right:8px">GRADE A</span>Vagas com maxima compatibilidade com seu perfil</td></tr>
<tr><td style="padding:14px 16px;font-size:13px;color:#333;border-bottom:1px solid #f0f0f0">
<span style="background:#E3F2FD;color:#1565C0;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:bold;margin-right:8px">CARTA</span>Carta de apresentacao gerada automaticamente para cada vaga</td></tr>
<tr><td style="padding:14px 16px;font-size:13px;color:#333">
<span style="background:#F3E5F5;color:#6A1B9A;border-radius:4px;padding:2px 8px;font-size:11px;font-weight:bold;margin-right:8px">FUNIL</span>Kanban para rastrear cada candidatura ate a oferta</td></tr>
</table>
<table width="100%"><tr><td align="center">
<a href="http://localhost:5173/jobs" style="display:inline-block;background:#1D9E75;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:bold">Ver vagas com score alto</a>
</td></tr></table></td></tr>
<tr><td style="background:#f9f9f9;padding:20px;text-align:center;border-top:1px solid #eee">
<a href="https://github.com/marciobarbarulo10-oss/job-monitoring-agent" style="color:#1D9E75;font-size:12px">Job Agent no GitHub</a>
</td></tr></table></td></tr></table></body></html>"""
    },
    {
        "day": 7,
        "subject": "Insights do mercado da sua area esta semana",
        "html": """<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden">
<tr><td style="background:#2C3E50;padding:28px;text-align:center">
<h1 style="color:white;margin:0;font-size:22px">Inteligencia de mercado</h1>
<p style="color:rgba(255,255,255,0.75);margin:8px 0 0;font-size:14px">O que esta acontecendo na sua area esta semana</p>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#444;line-height:1.7;margin:0 0 24px">Seu agente nao apenas busca vagas — ele analisa <strong>tendencias do mercado</strong> automaticamente toda semana.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px">
<tr>
<td width="48%" style="background:#f0faf6;border-radius:12px;padding:20px;vertical-align:top">
<div style="font-size:13px;font-weight:bold;color:#1D9E75;margin-bottom:8px">Keywords em alta</div>
<div style="font-size:12px;color:#555;line-height:1.6">Palavras-chave que mais aparecem nas descricoes de vagas da sua area.</div>
</td>
<td width="4%"></td>
<td width="48%" style="background:#f0f4fa;border-radius:12px;padding:20px;vertical-align:top">
<div style="font-size:13px;font-weight:bold;color:#2C3E50;margin-bottom:8px">Empresas contratando</div>
<div style="font-size:12px;color:#555;line-height:1.6">Empresas que mais abriram vagas na semana.</div>
</td>
</tr></table>
<table width="100%"><tr><td align="center">
<a href="http://localhost:5173/insights" style="display:inline-block;background:#2C3E50;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:bold">Ver insights completos</a>
</td></tr></table></td></tr>
<tr><td style="background:#f9f9f9;padding:20px;text-align:center;border-top:1px solid #eee">
<a href="https://github.com/marciobarbarulo10-oss/job-monitoring-agent" style="color:#1D9E75;font-size:12px">Job Agent no GitHub</a>
</td></tr></table></td></tr></table></body></html>"""
    },
    {
        "day": 10,
        "subject": "O projeto que te ajuda e open source — que tal uma estrela?",
        "html": """<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden">
<tr><td style="background:#F39C12;padding:28px;text-align:center">
<h1 style="color:white;margin:8px 0 4px;font-size:22px">O projeto que te ajuda e open source</h1>
<p style="color:rgba(255,255,255,0.9);margin:0;font-size:14px">E voce pode ajudar ele a crescer</p>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#444;line-height:1.7;margin:0 0 16px">O Job Agent que busca vagas para voce e <strong>100% gratuito, open source</strong> e esta no GitHub para qualquer pessoa usar.</p>
<p style="color:#444;line-height:1.7;margin:0 0 24px">Se ele esta sendo util, uma <strong>estrela no repositorio</strong> faz muita diferenca para o projeto crescer.</p>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFDE7;border-radius:12px;margin:0 0 28px">
<tr><td style="padding:20px"><table width="100%" cellpadding="8">
<tr><td style="font-size:13px;color:#333">Da uma estrela — leva 5 segundos</td></tr>
<tr><td style="font-size:13px;color:#333">Compartilha com quem esta em busca de emprego</td></tr>
<tr><td style="font-size:13px;color:#333">Reporta bugs ou sugere melhorias nas Issues</td></tr>
</table></td></tr></table>
<table width="100%"><tr><td align="center">
<a href="https://github.com/marciobarbarulo10-oss/job-monitoring-agent" style="display:inline-block;background:#24292e;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:bold">Dar estrela no GitHub</a>
</td></tr></table></td></tr>
<tr><td style="background:#f9f9f9;padding:20px;text-align:center;border-top:1px solid #eee">
<p style="color:#999;font-size:12px;margin:0">Obrigado por usar o Job Agent!</p>
</td></tr></table></td></tr></table></body></html>"""
    },
    {
        "day": 17,
        "subject": "Resumo mensal: suas candidaturas e o mercado",
        "html": """<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px">
<table width="600" cellpadding="0" cellspacing="0" style="background:white;border-radius:16px;overflow:hidden">
<tr><td style="background:#6C3483;padding:28px;text-align:center">
<h1 style="color:white;margin:8px 0 4px;font-size:22px">Resumo mensal do seu agente</h1>
<p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px">Um mes de buscas automaticas para voce</p>
</td></tr>
<tr><td style="padding:32px">
<p style="color:#444;line-height:1.7;margin:0 0 24px">Seu Job Agent trabalhou durante todo o mes buscando oportunidades automaticamente. Acesse o dashboard para ver o relatorio completo:</p>
<table width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px">
<tr>
<td width="50%" style="padding:8px"><div style="background:#f0faf6;border-radius:10px;padding:16px;text-align:center">
<div style="font-size:13px;font-weight:bold;color:#1D9E75">Vagas monitoradas</div>
<div style="font-size:11px;color:#666;margin-top:4px">Ver no dashboard</div>
</div></td>
<td width="50%" style="padding:8px"><div style="background:#f0f0fa;border-radius:10px;padding:16px;text-align:center">
<div style="font-size:13px;font-weight:bold;color:#6C3483">Candidaturas</div>
<div style="font-size:11px;color:#666;margin-top:4px">Ver no kanban</div>
</div></td>
</tr></table>
<table width="100%"><tr><td align="center">
<a href="http://localhost:5173" style="display:inline-block;background:#6C3483;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:15px;font-weight:bold">Ver resumo completo</a>
</td></tr></table></td></tr>
<tr><td style="background:#f9f9f9;padding:20px;text-align:center;border-top:1px solid #eee">
<p style="color:#999;font-size:12px;margin:0">Continue usando o Job Agent — seu proximo emprego pode estar na proxima busca.</p>
<a href="https://github.com/marciobarbarulo10-oss/job-monitoring-agent" style="color:#1D9E75;font-size:12px">Job Agent no GitHub</a>
</td></tr></table></td></tr></table></body></html>"""
    },
]

SEQUENCE_DAYS = [e["day"] for e in EMAIL_SEQUENCE]
SEQUENCE_MAP = {e["day"]: e for e in EMAIL_SEQUENCE}


class EmailSequenceAgent(BaseAgent):
    """Controla e envia a sequência de emails para cada subscriber. Roda a cada hora."""

    def __init__(self):
        super().__init__("email_sequence")
        self.api_key = os.getenv("MAILERLITE_API_KEY", "")
        self.available = bool(self.api_key)
        self.from_email = os.getenv("MAILERLITE_FROM_EMAIL", "marciobarbarulo10@gmail.com")
        self.from_name = "Job Agent"
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    # ── Cadastro ──────────────────────────────────────────────────────────

    def register_subscriber(self, email: str, name: str = "") -> bool:
        """Registra novo subscriber para receber a sequência."""
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now()
        try:
            cursor.execute(
                """INSERT OR IGNORE INTO email_sequence
                       (email, name, subscribed_at, sequence_day, next_email_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (email.lower().strip(), name, now.isoformat(), 0, now.isoformat()),
            )
            conn.commit()
            inserted = cursor.rowcount > 0
            conn.close()
            if inserted:
                self.logger.info(f"Subscriber registrado na sequencia: {email}")
            else:
                self.logger.info(f"Subscriber ja existe na sequencia: {email}")
            return inserted
        except Exception as e:
            self.logger.error(f"Erro ao registrar subscriber {email}: {e}")
            conn.close()
            return False

    def unsubscribe(self, email: str):
        """Marca subscriber como cancelado."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE email_sequence SET unsubscribed=1, updated_at=datetime('now') WHERE email=?",
            (email.lower().strip(),),
        )
        conn.commit()
        conn.close()
        self.logger.info(f"Subscriber removido da sequencia: {email}")

    # ── Envio via API MailerLite ──────────────────────────────────────────

    def _send_email(self, to_email: str, to_name: str, subject: str, html: str) -> bool:
        """Cria campanha temporária e envia imediatamente via API MailerLite."""
        if not self.available:
            self.logger.warning(f"[EMAIL SKIP] {to_email} — MAILERLITE_API_KEY ausente")
            return False

        try:
            campaign_name = f"[SEQ] {subject[:40]} — {to_email[:20]}"
            r = self.session.post(
                f"{MAILERLITE_API}/campaigns",
                json={
                    "name": campaign_name,
                    "type": "regular",
                    "emails": [{
                        "subject": subject,
                        "from_name": self.from_name,
                        "from": self.from_email,
                        "content": html,
                    }],
                    "filter": [[{"operator": "eq", "args": ["email", to_email]}]],
                },
                timeout=15,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Criar campanha falhou: {r.status_code} {r.text[:200]}")
                return False

            campaign_id = r.json().get("data", {}).get("id")
            if not campaign_id:
                return False

            r2 = self.session.post(
                f"{MAILERLITE_API}/campaigns/{campaign_id}/schedule",
                json={"delivery": "instant"},
                timeout=15,
            )

            success = r2.status_code in (200, 201, 204)
            if success:
                self.logger.info(f"Email enviado: {subject[:50]} -> {to_email}")
            else:
                self.logger.error(f"Schedule falhou: {r2.status_code} {r2.text[:200]}")
            return success

        except Exception as e:
            self.logger.error(f"Erro ao enviar email para {to_email}: {e}")
            return False

    # ── Fila ─────────────────────────────────────────────────────────────

    def _get_pending_sends(self) -> list:
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            """SELECT email, name, sequence_day, emails_sent
               FROM email_sequence
               WHERE completed=0 AND unsubscribed=0 AND next_email_at <= ?
               ORDER BY next_email_at ASC LIMIT 50""",
            (now,),
        )
        rows = cursor.fetchall()
        conn.close()
        return rows

    def _advance_sequence(self, email: str, current_day: int, emails_sent: int):
        conn = get_connection()
        cursor = conn.cursor()
        remaining = [d for d in SEQUENCE_DAYS if d > current_day]
        if not remaining:
            cursor.execute(
                "UPDATE email_sequence SET completed=1, emails_sent=?, updated_at=datetime('now') WHERE email=?",
                (emails_sent + 1, email),
            )
        else:
            next_day = remaining[0]
            next_send = (datetime.now() + timedelta(days=next_day - current_day)).isoformat()
            cursor.execute(
                """UPDATE email_sequence SET sequence_day=?, next_email_at=?, emails_sent=?,
                   updated_at=datetime('now') WHERE email=?""",
                (next_day, next_send, emails_sent + 1, email),
            )
        conn.commit()
        conn.close()

    def _log_send(self, email: str, day: int, subject: str, status: str, error: str = None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO email_sequence_log (email, sequence_day, subject, status, error) VALUES (?,?,?,?,?)",
            (email, day, subject, status, error),
        )
        conn.commit()
        conn.close()

    # ── Execução principal ────────────────────────────────────────────────

    def run(self, context: dict = None) -> dict:
        """Verifica a fila e envia emails pendentes. Roda a cada hora via scheduler."""
        if not self.available:
            self.logger.warning("Email sequence: MAILERLITE_API_KEY ausente — envios suspensos")
            return {"sent": 0, "failed": 0, "skipped": 0, "reason": "no_api_key"}

        pending = self._get_pending_sends()

        if not pending:
            self.logger.debug("Email sequence: nenhum envio pendente")
            return {"sent": 0, "failed": 0, "skipped": 0}

        self.logger.info(f"Email sequence: {len(pending)} envios pendentes")
        sent = failed = skipped = 0

        for email, name, current_day, emails_sent in pending:
            email_data = SEQUENCE_MAP.get(current_day)
            if not email_data:
                self.logger.warning(f"Dia {current_day} nao encontrado na sequencia para {email}")
                skipped += 1
                continue

            ok = self._send_email(
                to_email=email,
                to_name=name or email.split("@")[0],
                subject=email_data["subject"],
                html=email_data["html"],
            )

            if ok:
                sent += 1
                self._log_send(email, current_day, email_data["subject"], "sent")
                self._advance_sequence(email, current_day, emails_sent)
            else:
                failed += 1
                self._log_send(email, current_day, email_data["subject"], "failed")

            time.sleep(0.5)

        result = {"sent": sent, "failed": failed, "skipped": skipped, "total_processed": len(pending)}
        self.log_action("email_sequence_run", "success" if failed == 0 else "partial", result)
        self.logger.info(f"Email sequence concluido: {sent} enviados, {failed} falhos")
        return result

    def get_stats(self) -> dict:
        """Estatísticas da sequência para o dashboard."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM email_sequence WHERE unsubscribed=0")
        active = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM email_sequence WHERE completed=1")
        completed = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM email_sequence_log WHERE status='sent'")
        total_sent = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM email_sequence WHERE completed=0 AND unsubscribed=0 AND next_email_at <= datetime('now')"
        )
        pending = cursor.fetchone()[0]
        conn.close()
        return {
            "active_subscribers": active,
            "completed_sequences": completed,
            "total_emails_sent": total_sent,
            "pending_sends": pending,
        }
