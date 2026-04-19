"""
scraper_indeed.py — Busca vagas no Indeed via API/scraping
"""
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
import time, random, json
from datetime import datetime


HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def get_headers():
    ua = UserAgent()
    return {**HEADERS_BASE, "User-Agent": ua.random}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
def buscar_indeed(query: str, localizacao: str = "São Paulo, SP", max_vagas: int = 20) -> list[dict]:
    """
    Busca vagas no Indeed Brasil por query e localização.
    Retorna lista de dicts com dados da vaga.
    """
    vagas = []
    url = "https://br.indeed.com/jobs"
    params = {
        "q": query,
        "l": localizacao,
        "sort": "date",
        "fromage": "3",  # últimos 3 dias
    }

    try:
        session = requests.Session()
        resp = session.get(url, params=params, headers=get_headers(), timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("div", class_=lambda c: c and "job_seen_beacon" in c)

        if not cards:
            # Fallback: tenta seletor alternativo
            cards = soup.find_all("div", attrs={"data-testid": "slider_item"})

        logger.info(f"Indeed [{query}]: {len(cards)} cards encontrados")

        for card in cards[:max_vagas]:
            try:
                titulo_el  = card.find("h2", class_=lambda c: c and "jobTitle" in c)
                empresa_el = card.find("span", attrs={"data-testid": "company-name"})
                local_el   = card.find("div", attrs={"data-testid": "text-location"})
                link_el    = titulo_el.find("a") if titulo_el else None
                desc_el    = card.find("div", class_=lambda c: c and "job-snippet" in c)

                titulo  = titulo_el.get_text(strip=True) if titulo_el else ""
                empresa = empresa_el.get_text(strip=True) if empresa_el else ""
                local   = local_el.get_text(strip=True) if local_el else ""
                desc    = desc_el.get_text(strip=True) if desc_el else ""
                link    = "https://br.indeed.com" + link_el["href"] if link_el and link_el.get("href") else ""

                if titulo and link:
                    vagas.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "localizacao": local,
                        "descricao": desc,
                        "url": link,
                        "fonte": "indeed",
                        "data_encontrada": datetime.utcnow(),
                    })
            except Exception as e:
                logger.warning(f"Erro ao parsear card Indeed: {e}")
                continue

        # Anti-bot: pausa aleatória
        time.sleep(random.uniform(3, 7))

    except Exception as e:
        logger.error(f"Erro na busca Indeed [{query}]: {e}")

    return vagas
