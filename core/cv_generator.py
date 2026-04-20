"""
cv_generator.py — Geração de CV em PDF customizado por vaga via Playwright.
Renderiza template HTML com keywords da JD integradas naturalmente.
"""
import os
import sqlite3
from datetime import datetime
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")
_OUTPUT_DIR = os.path.join(_BASE_DIR, "output")
_TEMPLATE_PATH = os.path.join(_BASE_DIR, "templates", "cv_template.html")

os.makedirs(_OUTPUT_DIR, exist_ok=True)


def _load_profile() -> dict:
    """Carrega perfil do config/profile.yml com fallback para profile.py."""
    profile_path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        import yaml
        with open(profile_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Nao foi possivel carregar profile.yml: {e}")
        try:
            from config.profile import PERFIL
            return {
                "name": PERFIL.get("nome", ""),
                "current_role": "Analista de Importação",
                "target_roles": PERFIL.get("titulos_ideais", []),
                "skills": {
                    "hard": list(PERFIL.get("keywords", {}).keys())[:20],
                    "soft": [],
                    "certifications": [],
                },
                "location": {"preferred": ["São Paulo", "SP"], "remote": True, "hybrid": True},
                "experience_years": 5,
                "about": PERFIL.get("nome", ""),
                "proof_points": [],
                "languages": ["Português (nativo)"],
            }
        except Exception:
            return {}


class CVGenerator:
    """Gera CVs em PDF customizados usando Playwright para renderização HTML→PDF."""

    def __init__(self):
        self._profile = _load_profile()

    def generate(self, job: dict, profile: dict | None = None) -> str | None:
        """
        Gera PDF do CV customizado para a vaga especificada.
        Retorna o caminho do arquivo gerado ou None em caso de erro.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright nao instalado. Execute: playwright install chromium")
            return None

        perfil = profile or self._profile
        if not perfil:
            logger.error("Perfil nao carregado — nao e possivel gerar CV")
            return None

        try:
            if not os.path.exists(_TEMPLATE_PATH):
                logger.error(f"Template de CV nao encontrado: {_TEMPLATE_PATH}")
                return None

            with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
                template_str = f.read()

            keywords_vaga = self._extract_jd_keywords(job, perfil)
            ctx = self._build_context(job, perfil, keywords_vaga)
            html = self._render_template(template_str, ctx)

            # Nome do arquivo
            job_id = job.get("id", "0")
            empresa = (job.get("empresa") or "empresa").replace(" ", "_")[:20]
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"cv_{job_id}_{empresa}_{ts}.pdf"
            filepath = os.path.join(_OUTPUT_DIR, filename)

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html, wait_until="networkidle")
                page.pdf(
                    path=filepath,
                    format="A4",
                    margin={"top": "1.5cm", "right": "1.5cm", "bottom": "1.5cm", "left": "1.5cm"},
                    print_background=True,
                )
                browser.close()

            self._register_export(job_id, filepath)
            logger.info(f"CV gerado com sucesso: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Erro ao gerar CV para '{job.get('titulo', '')}': {e}")
            return None

    def _extract_jd_keywords(self, job: dict, profile: dict) -> list[str]:
        """Identifica quais skills do perfil aparecem na descrição da vaga."""
        descricao = (job.get("descricao") or "").lower()
        if not descricao:
            return []

        skills = profile.get("skills", {}).get("hard", [])
        encontradas = [s for s in skills if s.lower() in descricao]
        return encontradas[:8]

    def _build_context(self, job: dict, profile: dict, keywords: list) -> dict:
        """Monta dicionário de contexto para o template Jinja2."""
        about = profile.get("about", "")
        if keywords:
            kws_str = ", ".join(keywords[:4])
            about = f"{about.rstrip('.')}. Competências diretamente aplicáveis a esta posição: {kws_str}."

        return {
            "nome": profile.get("name", ""),
            "cargo_alvo": job.get("titulo") or profile.get("current_role", ""),
            "empresa_alvo": job.get("empresa", ""),
            "localizacao": ", ".join(profile.get("location", {}).get("preferred", [])),
            "sobre": about,
            "skills_hard": profile.get("skills", {}).get("hard", []),
            "skills_soft": profile.get("skills", {}).get("soft", []),
            "certifications": profile.get("skills", {}).get("certifications", []),
            "languages": profile.get("languages", []),
            "experience_years": profile.get("experience_years", 0),
            "proof_points": profile.get("proof_points", []),
            "keywords_vaga": keywords,
            "data_geracao": datetime.now().strftime("%d/%m/%Y"),
        }

    def _render_template(self, template_str: str, ctx: dict) -> str:
        """Renderiza template Jinja2 com o contexto fornecido."""
        try:
            from jinja2 import Template
            return Template(template_str).render(**ctx)
        except ImportError:
            # Fallback manual para substituições simples
            result = template_str
            for k, v in ctx.items():
                result = result.replace("{{ " + k + " }}", str(v))
            return result

    def _register_export(self, job_id, filepath: str):
        """Registra CV exportado no banco de dados."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            conn.execute(
                "INSERT INTO cv_exports (job_id, file_path, created_at) VALUES (?, ?, ?)",
                (job_id, filepath, datetime.utcnow().isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao registrar exportacao de CV: {e}")

    def list_exports(self) -> list[dict]:
        """Lista todos os CVs gerados com status de existência do arquivo."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            rows = conn.execute(
                """SELECT ce.id, ce.job_id, ce.file_path, ce.created_at,
                          v.titulo, v.empresa, v.score
                   FROM cv_exports ce
                   LEFT JOIN vagas v ON v.id = ce.job_id
                   ORDER BY ce.created_at DESC""",
            ).fetchall()
            conn.close()

            return [
                {
                    "id": r[0],
                    "job_id": r[1],
                    "file_path": r[2],
                    "created_at": r[3],
                    "titulo": r[4] or "—",
                    "empresa": r[5] or "—",
                    "score": r[6] or 0,
                    "exists": os.path.exists(r[2]) if r[2] else False,
                    "filename": os.path.basename(r[2]) if r[2] else "",
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Erro ao listar CVs: {e}")
            return []
