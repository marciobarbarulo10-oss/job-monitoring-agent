"""
scraper_linkedin.py — Busca vagas no LinkedIn Jobs (sem login)
Usa a API pública de busca do LinkedIn que não requer autenticação.
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
        "Referer": "https://www.linkedin.com/",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=5, max=25))
def buscar_linkedin(query: str, localizacao: str = "São Paulo", max_vagas: int = 25) -> list[dict]:
    """
    Busca vagas no LinkedIn Jobs (endpoint público, sem login).
    Retorna lista de dicts.
    """
    vagas = []

    # LinkedIn Jobs API pública (não oficial mas funcional)
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": query,
        "location": localizacao,
        "f_TPR": "r259200",  # últimas 72 horas
        "f_E": "3,4",        # Mid-Senior, Associate
        "start": 0,
        "count": max_vagas,
    }

    try:
        resp = requests.get(url, params=params, headers=get_headers(), timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.find_all("li")

        logger.info(f"LinkedIn [{query}]: {len(cards)} cards encontrados")

        for card in cards:
            try:
                titulo_el  = card.find("h3", class_="base-search-card__title")
                empresa_el = card.find("h4", class_="base-search-card__subtitle")
                local_el   = card.find("span", class_="job-search-card__location")
                link_el    = card.find("a", class_="base-card__full-link")
                data_el    = card.find("time")

                titulo  = titulo_el.get_text(strip=True) if titulo_el else ""
                empresa = empresa_el.get_text(strip=True) if empresa_el else ""
                local   = local_el.get_text(strip=True) if local_el else ""
                link    = link_el["href"].split("?")[0] if link_el else ""

                if titulo and link:
                    vagas.append({
                        "titulo": titulo,
                        "empresa": empresa,
                        "localizacao": local,
                        "descricao": "",  # descrição completa requer acesso à página
                        "url": link,
                        "fonte": "linkedin",
                        "data_encontrada": datetime.utcnow(),
                    })
            except Exception as e:
                logger.warning(f"Erro ao parsear card LinkedIn: {e}")
                continue

        time.sleep(random.uniform(4, 9))

    except Exception as e:
        logger.error(f"Erro na busca LinkedIn [{query}]: {e}")

    return vagas


def buscar_descricao_linkedin(url: str) -> str:
    """Busca a descrição completa de uma vaga LinkedIn."""
    try:
        resp = requests.get(url, headers=get_headers(), timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = soup.find("div", class_="show-more-less-html__markup")
        return desc.get_text(separator=" ", strip=True) if desc else ""
    except Exception as e:
        logger.warning(f"Erro ao buscar descrição LinkedIn: {e}")
        return ""
