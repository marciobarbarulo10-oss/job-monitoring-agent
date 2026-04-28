"""
Atualiza as URLs dos webhooks no MailerLite quando o servidor
for publicado com URL pública (ngrok, VPS, domínio próprio).

Uso:
  python scripts/update_webhook_urls.py https://seudominio.com
  python scripts/update_webhook_urls.py https://abc123.ngrok.io
"""
import sys
import os
import requests

WEBHOOKS = [
    {
        "id": "185947723042654020",
        "name": "subscriber",
        "path": "/webhooks/mailerlite/subscriber",
    },
    {
        "id": "185947728340059568",
        "name": "campaign",
        "path": "/webhooks/mailerlite/campaign",
    },
    {
        "id": "185947733847180420",
        "name": "unsubscribe",
        "path": "/webhooks/mailerlite/unsubscribe",
    },
]


def update_webhooks(base_url: str):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("MAILERLITE_API_KEY", "").strip()
    if not api_key:
        print("Configure MAILERLITE_API_KEY no .env")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"Atualizando webhooks para: {base_url}")
    print()

    for wh in WEBHOOKS:
        url = f"{base_url}{wh['path']}"
        try:
            r = requests.put(
                f"https://connect.mailerlite.com/api/webhooks/{wh['id']}",
                json={"url": url},
                headers=headers,
                timeout=10,
            )
            if r.status_code in (200, 201):
                print(f"OK  {wh['name']}: {url}")
            else:
                print(f"FAIL {wh['name']}: HTTP {r.status_code} — {r.text[:100]}")
        except Exception as e:
            print(f"ERR  {wh['name']}: {e}")

    print()
    print("URLs dos webhooks atualizadas no MailerLite.")
    print("Verifique em: https://dashboard.mailerlite.com/integrations/webhooks")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/update_webhook_urls.py https://seudominio.com")
        sys.exit(1)
    update_webhooks(sys.argv[1].rstrip("/"))
