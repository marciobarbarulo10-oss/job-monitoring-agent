"""
cover_letter.py — Gerador de cartas de apresentação personalizadas por vaga.
Usa LLM quando disponível; fallback para template estático.
"""
import logging
import os
from intelligence.llm_client import get_llm_client

logger = logging.getLogger(__name__)

_SYSTEM = (
    "Voce e um especialista em redacao profissional para candidaturas no Brasil. "
    "Escreva cartas objetivas, profissionais e personalizadas. "
    "Tom: profissional mas humano. Sem cliches. Maximo 3 paragrafos."
)


def _load_profile() -> dict:
    try:
        import yaml
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "config", "profile.yml")
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        pass
    try:
        from config.profile import PERFIL
        return {
            "name": PERFIL.get("nome", ""),
            "experience_years": 5,
            "about": f"Profissional de Comercio Exterior e Supply Chain.",
            "skills": {"hard": list(PERFIL.get("keywords", {}).keys())[:10]},
        }
    except Exception:
        return {}


def generate_cover_letter(job: dict, score_data: dict) -> str:
    """
    Gera carta de apresentação personalizada para a vaga.
    Retorna texto pronto para copiar/enviar.
    """
    client = get_llm_client()
    profile = _load_profile()

    if not client.available:
        return _template_fallback(job, profile)

    strengths = score_data.get("strengths", [])
    gaps = score_data.get("gaps", [])
    hard_skills = profile.get("skills", {}).get("hard", [])

    prompt = f"""Escreva uma carta de apresentacao para esta candidatura:

CANDIDATO: {profile.get('name', 'Candidato')}
VAGA: {job.get('titulo', '')} na {job.get('empresa', '')}
PLATAFORMA: {job.get('fonte', '')}
SCORE DE MATCH: {score_data.get('match_pct', 0)}%
PONTOS FORTES: {', '.join(strengths[:3]) if strengths else ', '.join(hard_skills[:3])}
LACUNAS: {', '.join(gaps[:2]) if gaps else 'nenhuma identificada'}

PERFIL: {profile.get('about', '')}
EXPERIENCIA: {profile.get('experience_years', '')} anos

A carta deve ter exatamente 3 paragrafos:
1. Apresentacao e interesse genuino na vaga/empresa
2. Experiencias/habilidades diretamente aplicaveis (cite 2-3 especificas)
3. Encerramento com call-to-action profissional

Escreva apenas o corpo da carta, sem saudacao inicial nem assinatura."""

    result = client.complete(prompt, _SYSTEM, max_tokens=500)
    return result if result else _template_fallback(job, profile)


def _template_fallback(job: dict, profile: dict) -> str:
    titulo = job.get("titulo", "vaga")
    empresa = job.get("empresa", "empresa")
    exp = profile.get("experience_years", "")
    name = profile.get("name", "")
    hard = profile.get("skills", {}).get("hard", [])
    skills_str = ", ".join(hard[:3]) if hard else "Comercio Exterior e Supply Chain"

    return (
        f"Venho manifestar meu interesse na posicao de {titulo} na {empresa}.\n\n"
        f"Possuo {exp} anos de experiencia na area, com foco em {skills_str}. "
        f"Minha trajetoria profissional se alinha diretamente com os requisitos da posicao, "
        f"e estou convicto de que posso contribuir de forma significativa para os resultados da equipe.\n\n"
        f"Coloco-me a disposicao para uma conversa e agradeco a atencao.\n\n"
        f"Atenciosamente,\n{name}"
    )
