"""
Cliente MailerLite — integração direta com a API REST.
Usado pelos agentes para adicionar subscribers, criar campanhas
e disparar automações automaticamente.

Documentação: https://developers.mailerlite.com/docs
"""
import os
import logging
import requests
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

MAILERLITE_API = "https://connect.mailerlite.com/api"

GROUPS = {
    "novos_usuarios":    "185866558038345309",
    "usuarios_ativos":   "185866565658347071",
    "comunidade_github": "185866574904689757",
}

AUTOMATION_IDS = {
    "boas_vindas": "185866891176182916",
}


class MailerLiteClient:

    def __init__(self):
        self.api_key = os.getenv("MAILERLITE_API_KEY", "").strip()
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("MAILERLITE_API_KEY nao configurada — email marketing desativado")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            })

    def _post(self, endpoint: str, data: dict) -> Optional[dict]:
        if not self.available:
            return None
        try:
            r = self.session.post(f"{MAILERLITE_API}{endpoint}", json=data, timeout=15)
            r.raise_for_status()
            return r.json() if r.content else {}
        except requests.HTTPError as e:
            logger.error(f"MailerLite HTTP {endpoint}: {e.response.status_code} — {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"MailerLite POST {endpoint}: {e}")
            return None

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.available:
            return None
        try:
            r = self.session.get(f"{MAILERLITE_API}{endpoint}", params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.error(f"MailerLite GET {endpoint}: {e}")
            return None

    def add_new_user(self, name: str, email: str, profile: dict = None) -> bool:
        """
        Cria/atualiza subscriber e adiciona ao grupo Novos Usuários.
        O grupo trigger dispara a automação de boas-vindas (5 emails em 17 dias).
        """
        if not self.available:
            logger.info(f"[MailerLite SKIP] {email} — API key ausente")
            return False

        profile = profile or {}
        data = {
            "email": email.lower().strip(),
            "status": "active",
            "fields": {
                "name": name.strip(),
                "company": profile.get("target_role", ""),
                "city": profile.get("location", ""),
                "z_i_p": str(profile.get("experience_years", "")),
            },
            "groups": [GROUPS["novos_usuarios"]],
        }

        result = self._post("/subscribers", data)
        if not result:
            logger.error(f"Falha ao adicionar {email} no MailerLite")
            return False

        sub_id = result.get("data", {}).get("id")
        logger.info(f"MailerLite: {email} adicionado (ID: {sub_id})")
        return True

    def move_to_active(self, email: str) -> bool:
        """Move subscriber para o grupo Usuários Ativos (onboarding concluído)."""
        if not self.available:
            return False

        result = self._get(f"/subscribers/{email}")
        if not result:
            return False

        sub_id = result.get("data", {}).get("id")
        if not sub_id:
            return False

        self._post(f"/subscribers/{sub_id}/groups/{GROUPS['usuarios_ativos']}", {})
        logger.info(f"MailerLite: {email} movido para Usuarios Ativos")
        return True

    def add_to_github_community(self, email: str) -> bool:
        """Adiciona subscriber ao grupo Comunidade GitHub."""
        if not self.available:
            return False

        result = self._get(f"/subscribers/{email}")
        if not result:
            return False

        sub_id = result.get("data", {}).get("id")
        if sub_id:
            self._post(f"/subscribers/{sub_id}/groups/{GROUPS['comunidade_github']}", {})
            logger.info(f"MailerLite: {email} adicionado a Comunidade GitHub")
            return True
        return False

    def get_stats(self) -> dict:
        """Retorna estatísticas da conta para o dashboard."""
        if not self.available:
            return {}

        result = self._get("/subscribers", {"limit": 1})
        total = result.get("meta", {}).get("total", 0) if result else 0

        group_stats = {}
        for name, gid in GROUPS.items():
            r = self._get(f"/groups/{gid}")
            if r:
                group_stats[name] = r.get("data", {}).get("active_count", 0)

        return {
            "total_subscribers": total,
            "groups": group_stats,
            "automation_id": AUTOMATION_IDS["boas_vindas"],
            "timestamp": datetime.now().isoformat(),
        }

    def send_weekly_newsletter(self, subject: str, html_content: str,
                               sender_email: str = None,
                               sender_name: str = "Job Agent") -> bool:
        """
        Cria campanha e agenda envio imediato para o grupo Usuários Ativos.
        O conteúdo HTML é gerado pelo MarketerAgent com dados reais.
        """
        if not self.available:
            return False

        sender = sender_email or os.getenv("MAILERLITE_FROM_EMAIL", "")
        if not sender:
            logger.error("MAILERLITE_FROM_EMAIL nao configurado — newsletter abortada")
            return False

        week = datetime.now().strftime("%Y-W%U")
        campaign_data = {
            "name": f"Job Agent Newsletter {week}",
            "type": "regular",
            "status": "draft",
            "emails": [{
                "subject": subject,
                "from_name": sender_name,
                "from": sender,
                "content": html_content,
            }],
            "groups": [GROUPS["usuarios_ativos"]],
        }

        result = self._post("/campaigns", campaign_data)
        if not result:
            return False

        campaign_id = result.get("data", {}).get("id")
        if not campaign_id:
            return False

        logger.info(f"MailerLite: campanha criada (ID: {campaign_id})")
        self._post(f"/campaigns/{campaign_id}/schedule", {"delivery": "instant"})
        return True


_client: Optional[MailerLiteClient] = None


def get_mailerlite_client() -> MailerLiteClient:
    global _client
    if _client is None:
        _client = MailerLiteClient()
    return _client
