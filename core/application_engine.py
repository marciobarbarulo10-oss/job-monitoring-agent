"""
application_engine.py — Orquestrador de candidaturas com 3 níveis.

Nível 1 (Assistido): marca como aplicada + abre URL + gera sugestões
Nível 2 (Automatização leve): pré-preenchimento por plataforma
Nível 3 (Automação avançada): reservado para plataformas que permitem
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).parent.parent


def _load_profile() -> dict:
    try:
        import yaml
        with open(BASE_DIR / "config" / "profile.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


class ApplicationEngine:
    """Gerencia candidaturas com diferentes níveis de automação."""

    def __init__(self):
        self._profile = _load_profile()

    def get_assist_content(self, job: dict) -> dict:
        """
        Gera conteúdo de assistência personalizado para a vaga:
        resumo adaptado, skills relevantes, respostas para perguntas comuns.
        """
        profile = self._profile
        descricao = (job.get("descricao") or "").lower()
        titulo = job.get("titulo", "")
        empresa = job.get("empresa", "")

        hard = profile.get("skills", {}).get("hard", [])
        relevant = [s for s in hard if s.lower() in descricao][:8]
        if not relevant:
            relevant = hard[:6]

        about = profile.get("about", "")
        proof = profile.get("proof_points", [])

        relevant_proof = [p for p in proof if any(s.lower() in p.lower() for s in relevant)]
        if not relevant_proof:
            relevant_proof = proof[:3]

        skills_str = ", ".join(relevant[:4]) if relevant else "Supply Chain e Comércio Exterior"
        exp_anos = profile.get("experience_years", 5)
        nome = profile.get("name", "")

        resumo = about
        if relevant:
            resumo = f"{about.rstrip('.')}. Para esta posição destaco: {skills_str}."

        respostas = {
            "Por que você quer trabalhar aqui?": (
                f"Tenho interesse na {empresa or 'empresa'} pela oportunidade de aplicar minha "
                f"experiência em {skills_str}. Acredito que posso contribuir diretamente para "
                f"os desafios da posição de {titulo or 'Analista'}."
            ),
            "Qual é sua pretensão salarial?": (
                f"Estou aberto a discutir remuneração compatível com o mercado para o nível "
                f"{'Pleno' if exp_anos >= 3 else 'Junior'} com {exp_anos} anos de experiência."
            ),
            "Por que você é o candidato ideal?": (
                f"Minha experiência em {skills_str} se alinha diretamente com os requisitos. "
                + (f"Destaco: {relevant_proof[0]}" if relevant_proof else "")
            ),
            "Conte sobre você": resumo,
            "Descreva sua experiência com [área da vaga]": (
                f"Ao longo de {exp_anos} anos, trabalhei com "
                f"{skills_str}. " +
                (relevant_proof[0] if relevant_proof else
                 "Desenvolvi processos eficientes e melhoria contínua na área.")
            ),
        }

        return {
            "nome": nome,
            "cargo_alvo": titulo,
            "empresa": empresa,
            "resumo_adaptado": resumo,
            "skills_relevantes": relevant,
            "skills_nao_encontradas": [s for s in hard[:10] if s not in relevant][:4],
            "proof_points": relevant_proof[:3],
            "respostas_comuns": respostas,
            "experiencia_anos": exp_anos,
            "idiomas": profile.get("languages", []),
            "localizacao": ", ".join(profile.get("location", {}).get("preferred", [])),
        }

    def apply(self, job: dict, level: int = 1) -> dict:
        """Entry point: executa candidatura no nível especificado."""
        assist = self.get_assist_content(job)

        if level >= 2:
            platform_result = self._apply_platform(job)
            return {**platform_result, "level": level, "assist": assist}

        return {
            "ok": True,
            "level": 1,
            "action": "open_and_track",
            "url": job.get("url", ""),
            "platform": (job.get("fonte") or "").lower(),
            "assist": assist,
            "message": "Vaga marcada. Use as sugestões abaixo para sua candidatura.",
        }

    def _apply_platform(self, job: dict) -> dict:
        """Delega para o handler da plataforma."""
        from core.platform_handlers import get_handler
        fonte = (job.get("fonte") or "").lower()
        handler = get_handler(fonte)
        if handler:
            try:
                return handler.apply(job, self._profile)
            except Exception as e:
                logger.warning(f"Handler {fonte} falhou: {e} — usando level 1")
        return {"ok": True, "action": "open_and_track", "url": job.get("url", ""),
                "platform": fonte, "tip": "Abrir e aplicar manualmente."}
