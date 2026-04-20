"""
semantic_scorer.py — Avaliação semântica de vagas via Claude API.
Substitui keyword matching por análise LLM real com cache e rate limiting.
"""
import os
import json
import time
import sqlite3
from datetime import datetime
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

_ANTHROPIC_AVAILABLE = False
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    pass


def _score_to_grade(score: float) -> str:
    if score >= 9.0:
        return "A"
    if score >= 7.0:
        return "B"
    if score >= 5.0:
        return "C"
    if score >= 3.0:
        return "D"
    return "F"


def _load_profile() -> dict:
    """Carrega perfil do config/profile.yml com fallback para profile.py."""
    profile_path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        import yaml
        with open(profile_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Nao foi possivel carregar profile.yml: {e} — usando perfil legado")
        try:
            from config.profile import PERFIL
            return {
                "name": PERFIL.get("nome", ""),
                "current_role": "Analista de Importação",
                "target_roles": PERFIL.get("titulos_ideais", []),
                "skills": {
                    "hard": list(PERFIL.get("keywords", {}).keys()),
                    "soft": [],
                    "certifications": [],
                },
                "location": {
                    "preferred": ["São Paulo", "SP"],
                    "remote": PERFIL.get("aceita_remoto", True),
                    "hybrid": PERFIL.get("aceita_hibrido", True),
                },
                "experience_years": 5,
                "about": f"Profissional de Supply Chain e Comércio Exterior. {PERFIL.get('nome', '')}.",
                "proof_points": [],
                "what_to_avoid": PERFIL.get("titulos_ignorar", []),
                "languages": ["Português (nativo)"],
            }
        except Exception as e2:
            logger.error(f"Erro no fallback de perfil: {e2}")
            return {}


class SemanticScorer:
    """Avalia aderência de vagas ao perfil usando Claude API com cache e rate limiting."""

    def __init__(self):
        self._client = None
        self._last_requests: list[float] = []
        self._model = os.getenv("SEMANTIC_MODEL", "claude-haiku-4-5-20251001")
        self._profile = _load_profile()

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if _ANTHROPIC_AVAILABLE and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)
            logger.info(f"SemanticScorer inicializado com modelo {self._model}")
        else:
            logger.warning("ANTHROPIC_API_KEY nao configurada — SemanticScorer usara fallback keyword")

    def _enforce_rate_limit(self):
        """Garante no máximo 10 requisições por minuto com backoff."""
        now = time.time()
        self._last_requests = [t for t in self._last_requests if now - t < 60]

        if len(self._last_requests) >= 10:
            wait = 60 - (now - self._last_requests[0]) + 1
            if wait > 0:
                logger.info(f"Rate limit SemanticScorer: aguardando {wait:.1f}s...")
                time.sleep(wait)

        self._last_requests.append(time.time())

    def _get_cached(self, job_id: int) -> dict | None:
        """Retorna score semântico já calculado se existir no banco."""
        if not job_id:
            return None
        try:
            conn = sqlite3.connect(_DB_PATH)
            row = conn.execute(
                "SELECT score, score_grade, score_analysis FROM vagas "
                "WHERE id=? AND score_method='semantic' AND score > 0",
                (job_id,),
            ).fetchone()
            conn.close()
            if row and row[0]:
                return {
                    "score": row[0],
                    "grade": row[1] or _score_to_grade(row[0]),
                    "match_analysis": row[2] or "",
                    "gaps": [],
                    "highlights": [],
                    "recommendation": "ver_analise",
                    "score_method": "semantic",
                    "from_cache": True,
                }
        except Exception as e:
            logger.warning(f"Erro ao buscar cache semantico: {e}")
        return None

    def _build_prompt(self, job: dict) -> str:
        """Monta prompt de avaliação comparando vaga com perfil."""
        p = self._profile
        skills_hard = ", ".join(p.get("skills", {}).get("hard", [])[:20])
        skills_soft = ", ".join(p.get("skills", {}).get("soft", []))
        target_roles = ", ".join(p.get("target_roles", []))
        languages = ", ".join(p.get("languages", []))
        location_pref = ", ".join(p.get("location", {}).get("preferred", []))
        proof_points = "\n".join(f"- {pt}" for pt in p.get("proof_points", []))
        about = p.get("about", "")

        descricao = (job.get("descricao") or "")[:3000]

        return f"""Você é especialista em recrutamento para Comércio Exterior e Supply Chain.
Avalie a aderência entre o candidato e a vaga.

=== CANDIDATO ===
Nome: {p.get('name', '')}
Cargo atual: {p.get('current_role', '')}
Cargos alvo: {target_roles}
Experiência: {p.get('experience_years', 0)} anos
Localização preferida: {location_pref}
Aceita remoto: {p.get('location', {}).get('remote', True)}
Aceita híbrido: {p.get('location', {}).get('hybrid', True)}
Idiomas: {languages}

Competências técnicas: {skills_hard}
Competências comportamentais: {skills_soft}

Sobre: {about}

Realizações:
{proof_points}

=== VAGA ===
Título: {job.get('titulo', '')}
Empresa: {job.get('empresa', '')}
Localização: {job.get('localizacao', '')}
Modalidade: {job.get('modalidade', '')}
Descrição:
{descricao}

=== INSTRUÇÃO ===
Avalie a aderência e responda APENAS com JSON válido:
{{
  "score": <número 0.0 a 10.0, uma casa decimal>,
  "grade": "<A|B|C|D|F>",
  "match_analysis": "<análise em 2-3 frases explicando o score>",
  "gaps": ["<gap crítico 1>", "<gap 2>"],
  "highlights": ["<ponto forte 1>", "<ponto forte 2>"],
  "recommendation": "<aplicar|ignorar|aplicar_com_ressalvas>"
}}

Critérios:
- Fit cargo (0-3): título/nível corresponde?
- Fit skills (0-3): competências exigidas vs disponíveis
- Fit senioridade (0-2): nível exigido vs experiência do candidato
- Fit localização (0-2): localização vs preferências

Grade: A(9-10), B(7-8.9), C(5-6.9), D(3-4.9), F(0-2.9)"""

    def _keyword_fallback(self, job: dict) -> dict:
        """Fallback para keyword scoring quando API não está disponível."""
        try:
            from config.profile import calcular_score
            resultado = calcular_score(
                titulo=job.get("titulo", ""),
                descricao=job.get("descricao", ""),
                localizacao=job.get("localizacao", ""),
            )
            if isinstance(resultado, tuple):
                score, matched_kw = resultado
            else:
                score, matched_kw = resultado, []

            return {
                "score": float(score),
                "grade": _score_to_grade(float(score)),
                "match_analysis": f"Score por keywords: {len(matched_kw)} correspondencias encontradas.",
                "gaps": [],
                "highlights": matched_kw[:5],
                "recommendation": "aplicar" if score >= 6.0 else "ignorar",
                "score_method": "keyword",
            }
        except Exception as e:
            logger.error(f"Erro no keyword fallback: {e}")
            return {
                "score": 0.0, "grade": "F", "match_analysis": "Erro no scoring.",
                "gaps": [], "highlights": [], "recommendation": "ignorar",
                "score_method": "keyword",
            }

    def score_job(self, job: dict) -> dict:
        """
        Avalia aderência da vaga ao perfil.
        Usa cache, rate limiting e fallback automático.
        """
        job_id = job.get("id")

        cached = self._get_cached(job_id)
        if cached:
            logger.debug(f"Cache hit para vaga ID {job_id}")
            return cached

        if not self._client:
            return self._keyword_fallback(job)

        for attempt in range(3):
            try:
                self._enforce_rate_limit()

                prompt = self._build_prompt(job)
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}],
                )

                content = response.content[0].text.strip()

                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                data = json.loads(content)

                score = max(0.0, min(10.0, float(data.get("score", 0.0))))
                grade = data.get("grade", _score_to_grade(score))

                result = {
                    "score": round(score, 1),
                    "grade": grade,
                    "match_analysis": data.get("match_analysis", ""),
                    "gaps": data.get("gaps", []),
                    "highlights": data.get("highlights", []),
                    "recommendation": data.get("recommendation", ""),
                    "score_method": "semantic",
                    "from_cache": False,
                }
                logger.info(f"Score semantico: '{job.get('titulo', '')}' → {score} ({grade})")
                return result

            except json.JSONDecodeError as e:
                logger.warning(f"JSON invalido do Claude (tentativa {attempt + 1}): {e}")
                time.sleep((2 ** attempt) * 5)
            except Exception as e:
                logger.error(f"Erro API Claude (tentativa {attempt + 1}): {e}")
                time.sleep((2 ** attempt) * 5)

        logger.warning("Fallback para keyword scorer apos 3 falhas na API")
        return self._keyword_fallback(job)
