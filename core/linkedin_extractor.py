"""
linkedin_extractor.py — Extração de perfil público do LinkedIn via Playwright.
Fallback para entrada manual se o scraping for bloqueado.
"""
import re
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent
PROFILE_YML_PATH = BASE_DIR / "config" / "profile.yml"


class LinkedInExtractor:
    """Extrai dados do perfil público do LinkedIn."""

    def extract(self, linkedin_url: str) -> dict:
        """
        Tenta extrair perfil via Playwright (headless).
        Retorna dict com dados ou {"error": motivo} em caso de falha.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {"error": "playwright_not_installed", "message": "Execute: playwright install chromium"}

        logger.info(f"Extraindo perfil LinkedIn: {linkedin_url}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                    locale="pt-BR",
                )
                page = ctx.new_page()
                page.goto(linkedin_url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                if "login" in page.url or "authwall" in page.url or "checkpoint" in page.url:
                    browser.close()
                    return {"error": "login_required", "url": linkedin_url,
                            "message": "LinkedIn exige login para ver este perfil. Use a entrada manual."}

                profile = self._extract_from_page(page)
                browser.close()

                if not profile.get("name") and not profile.get("headline"):
                    return {"error": "no_data",
                            "message": "Não foi possível extrair dados. Use a entrada manual."}

                profile.update({"linkedin_url": linkedin_url,
                                "extracted_at": datetime.utcnow().isoformat(),
                                "method": "playwright"})
                logger.info(f"Perfil extraído: {profile.get('name')} / {profile.get('headline')}")
                return profile

        except Exception as e:
            logger.error(f"Erro ao extrair LinkedIn: {e}")
            return {"error": str(e), "message": "Falha no scraping. Use a entrada manual."}

    def _extract_from_page(self, page) -> dict:
        profile = {}
        selectors = {
            "name": [
                "h1.text-heading-xlarge",
                "h1[class*='top-card__title']",
                ".pv-text-details__left-panel h1",
            ],
            "headline": [
                "div.text-body-medium.break-words",
                ".pv-text-details__left-panel .text-body-medium",
                "div[class*='top-card-layout__headline']",
            ],
            "location": [
                "span.text-body-small.inline.t-black--light.break-words",
                ".pv-text-details__left-panel span.t-black--light",
            ],
        }

        for field, sels in selectors.items():
            for sel in sels:
                try:
                    el = page.query_selector(sel)
                    if el:
                        text = el.inner_text().strip()
                        if text:
                            profile[field] = text
                            break
                except Exception:
                    continue

        # About
        for sel in ["div[data-generated-suggestion-target] span[aria-hidden='true']",
                    "section[data-section='summary'] p",
                    ".pv-shared-text-with-see-more span[aria-hidden='true']"]:
            try:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if len(text) > 30:
                        profile["about"] = text[:1200]
                        break
            except Exception:
                continue

        # Skills
        skills = []
        for sel in [
            "li[class*='pv-skill-category-entity'] span.pv-skill-category-entity__name",
            "div[class*='pvs-list__outer-container'] span[aria-hidden='true']",
            "span[class*='skill-category-entity__name']",
        ]:
            try:
                els = page.query_selector_all(sel)
                for el in els[:25]:
                    t = el.inner_text().strip()
                    if t and 2 < len(t) < 60 and t not in skills:
                        skills.append(t)
                if skills:
                    break
            except Exception:
                continue
        if skills:
            profile["skills"] = skills

        return profile

    def from_manual(self, data: dict) -> dict:
        """
        Processa dados inseridos manualmente pelo usuário.
        data: {name, headline, location, about, skills (str, separado por vírgula)}
        """
        skills_raw = data.get("skills", "")
        if isinstance(skills_raw, str):
            skills = [s.strip() for s in re.split(r"[,\n]", skills_raw) if s.strip()]
        else:
            skills = skills_raw

        return {
            "name": data.get("name", "").strip(),
            "headline": data.get("headline", "").strip(),
            "location": data.get("location", "").strip(),
            "about": data.get("about", "").strip(),
            "skills": skills,
            "linkedin_url": data.get("linkedin_url", ""),
            "extracted_at": datetime.utcnow().isoformat(),
            "method": "manual",
        }

    def build_profile_yml(self, extracted: dict, current: dict = None) -> dict:
        """Converte dados extraídos para formato profile.yml, mesclando com perfil atual."""
        base = current or {}
        name = extracted.get("name") or base.get("name", "")
        headline = extracted.get("headline") or base.get("current_role", "")
        location_str = extracted.get("location", "")
        about = extracted.get("about") or base.get("about", "")
        skills_raw = extracted.get("skills", [])

        city = location_str.split(",")[0].strip() if location_str else "São Paulo"

        nivel = "pleno"
        hl = headline.lower()
        if any(w in hl for w in ["sênior", "senior", "sr.", " sr "]):
            nivel = "senior"
        elif any(w in hl for w in ["júnior", "junior", "jr."]):
            nivel = "junior"
        elif any(w in hl for w in ["coordenador", "gerente", "manager", "lead"]):
            nivel = "gestao"

        existing_hard = base.get("skills", {}).get("hard", [])
        merged_skills = list(dict.fromkeys(skills_raw[:20] + existing_hard))

        return {
            "name": name,
            "current_role": headline,
            "nivel": nivel,
            "target_roles": base.get("target_roles", [headline] if headline else []),
            "skills": {
                "hard": merged_skills[:30],
                "soft": base.get("skills", {}).get("soft", []),
                "certifications": base.get("skills", {}).get("certifications", []),
            },
            "location": {
                "preferred": [city] if city else base.get("location", {}).get("preferred", ["São Paulo"]),
                "remote": base.get("location", {}).get("remote", True),
                "hybrid": base.get("location", {}).get("hybrid", True),
            },
            "experience_years": base.get("experience_years", 3),
            "languages": base.get("languages", ["Português (nativo)"]),
            "about": about,
            "proof_points": base.get("proof_points", []),
            "what_to_avoid": base.get("what_to_avoid", []),
            "linkedin_url": extracted.get("linkedin_url", base.get("linkedin_url", "")),
        }

    def save_to_yml(self, extracted: dict) -> bool:
        """Salva perfil mesclado em config/profile.yml."""
        try:
            import yaml
            current = {}
            if PROFILE_YML_PATH.exists():
                with open(PROFILE_YML_PATH, "r", encoding="utf-8") as f:
                    current = yaml.safe_load(f) or {}
            merged = self.build_profile_yml(extracted, current)
            with open(PROFILE_YML_PATH, "w", encoding="utf-8") as f:
                yaml.dump(merged, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            logger.info(f"Perfil salvo: {PROFILE_YML_PATH}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar perfil: {e}")
            return False
