"""
scraper_vagas.py — Busca vagas no Vagas.com via scraping
"""
import re
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


def _clean_text(el) -> str:
    """Extrai texto de um elemento BeautifulSoup, normalizando espaços."""
    if not el:
        return ""
    return re.sub(r'\s+', ' ', el.get_text(separator=' ', strip=True)).strip()


def _find_empresa(card) -> str:
    """Tenta múltiplos seletores para extrair o nome da empresa."""
    candidates = [
        card.find("span", class_="empregador"),
        card.find("span", class_="empresa"),
        card.find("span", class_=lambda c: c and "company" in str(c).lower()),
        card.find("span", class_=lambda c: c and "employer" in str(c).lower()),
        card.find("a",    class_=lambda c: c and "empresa" in str(c).lower()),
        card.find("div",  class_=lambda c: c and "empresa" in str(c).lower()),
    ]
    for el in candidates:
        text = _clean_text(el)
        if text:
            return text
    return "Nao informado"


def _find_local(card) -> str:
    """Tenta múltiplos seletores para extrair a localização."""
    candidates = [
        card.find("span", class_="vaga-local"),
        card.find("span", class_="local"),
        card.find("span", class_=lambda c: c and "location" in str(c).lower()),
        card.find("span", class_=lambda c: c and "cidade" in str(c).lower()),
        card.find("div",  class_=lambda c: c and "local" in str(c).lower()),
        card.find("p",    class_=lambda c: c and "local" in str(c).lower()),
    ]
    for el in candidates:
        text = _clean_text(el)
        if text:
            return text
    return "Nao informado"


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
                titulo_el = card.find("a", class_="link-detalhes-vaga") or card.find("h2")
                desc_el   = card.find("p", class_="vaga-desc") or card.find("div", class_="detalhes")

                titulo  = _clean_text(titulo_el)
                empresa = _find_empresa(card)
                local   = _find_local(card)
                desc    = _clean_text(desc_el)
                href    = titulo_el.get("href", "") if titulo_el else ""
                link    = f"https://www.vagas.com.br{href}" if href.startswith("/") else href

                if titulo and link:
                    vagas.append({
                        "titulo":       titulo,
                        "empresa":      empresa,
                        "localizacao":  local,
                        "descricao":    desc,
                        "url":          link,
                        "fonte":        "vagas.com",
                        "data_encontrada": datetime.utcnow(),
                    })
            except Exception as e:
                logger.warning(f"Erro ao parsear card Vagas.com: {e}")
                continue

        time.sleep(random.uniform(3, 6))

    except Exception as e:
        logger.error(f"Erro na busca Vagas.com [{query}]: {e}")

    return vagas
