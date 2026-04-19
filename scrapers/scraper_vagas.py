"""
scraper_vagas.py — Busca vagas no Vagas.com via scraping
"""
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
import time, random
from datetime import datetime


def get_headers():
    ua = UserAgent()
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=20))
def buscar_vagas_com(query: str, localizacao: str = "sao-paulo-sp", max_vagas: int = 20) -> list[dict]:
    """
    Busca vagas no Vagas.com.
    """
    vagas = []
    query_slug = query.lower().replace(" ", "-")
    url = f"https://www.vagas.com.br/vagas-de-{query_slug}"

    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("li", class_=lambda c: c and "vaga" in str(c).lower())

        if not cards:
            cards = soup.find_all("article", class_="vaga")

        logger.info(f"Vagas.com [{query}]: {len(cards)} cards encontrados")

        for card in cards[:max_vagas]:
            try:
                titulo_el  = card.find("a", class_="link-detalhes-vaga") or card.find("h2")
                empresa_el = card.find("span", class_="emporegador") or card.find("span", class_="empresa")
                local_el   = card.find("span", class_="vaga-local") or card.find("span", class_="local")
                desc_el    = card.find("p", class_="vaga-desc") or card.find("div", class_="detalhes")

                titulo  = titulo_el.get_text(strip=True) if titulo_el else ""
                empresa = empresa_el.get_text(strip=True) if empresa_el else ""
                local   = local_el.get_text(strip=True) if local_el else ""
                desc    = desc_el.get_text(strip=True) if desc_el else ""
                href    = titulo_el.get("href", "") if titulo_el else ""
                link    = f"https://www.vagas.com.br{href}" if href.startswith("/") else href

                if titulo and link:
                    vagas.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "localizacao": local,
                        "descricao": desc,
                        "url": link,
                        "fonte": "vagas.com",
                        "data_encontrada": datetime.utcnow(),
                    })
            except Exception as e:
                logger.warning(f"Erro ao parsear card Vagas.com: {e}")
                continue

        time.sleep(random.uniform(3, 6))

    except Exception as e:
        logger.error(f"Erro na busca Vagas.com [{query}]: {e}")

    return vagas
