"""
scraper_gupy.py — Busca vagas via API pública da Gupy
A Gupy expõe uma API REST pública para listagem de vagas — sem scraping.
"""
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import time, random
from datetime import datetime


GUPY_API = "https://portal.api.gupy.io/api/v1/jobs"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)",
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=3, max=15))
def buscar_gupy(query: str, max_vagas: int = 30) -> list[dict]:
    """
    Busca vagas na Gupy via API pública.
    Retorna lista de dicts.
    """
    vagas = []

    params = {
        "jobName": query,
        "limit": max_vagas,
        "offset": 0,
    }

    try:
        resp = requests.get(GUPY_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        jobs = data.get("data", [])
        logger.info(f"Gupy [{query}]: {len(jobs)} vagas encontradas")

        for job in jobs:
            try:
                # Monta URL da vaga
                company_slug = job.get("careerPageUrl", "")
                job_id = job.get("id", "")
                url = f"{company_slug}?jobId={job_id}" if company_slug else ""

                vagas.append({
                    "titulo": job.get("name", ""),
                    "empresa": job.get("careerPageName", ""),
                    "localizacao": f"{job.get('city', '')} {job.get('state', '')}".strip(),
                    "descricao": job.get("description", "") or "",
                    "modalidade": job.get("workplaceType", ""),
                    "url": url or f"https://portal.gupy.io/job/{job_id}",
                    "fonte": "gupy",
                    "data_encontrada": datetime.utcnow(),
                })
            except Exception as e:
                logger.warning(f"Erro ao processar vaga Gupy: {e}")
                continue

        time.sleep(random.uniform(1, 3))

    except Exception as e:
        logger.error(f"Erro na busca Gupy [{query}]: {e}")

    return vagas
