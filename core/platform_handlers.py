"""
platform_handlers.py — Handlers específicos por plataforma de vagas.
Cada handler implementa a lógica de candidatura otimizada para seu portal.
"""
import logging

logger = logging.getLogger(__name__)


class BaseHandler:
    def apply(self, job: dict, profile: dict) -> dict:
        raise NotImplementedError

    def _contact_fields(self, profile: dict) -> list[dict]:
        return [
            {"label": "Nome completo", "value": profile.get("name", ""), "type": "text"},
            {"label": "Cidade / Estado",
             "value": ", ".join(profile.get("location", {}).get("preferred", [])), "type": "text"},
            {"label": "Anos de experiência",
             "value": str(profile.get("experience_years", "")), "type": "text"},
            {"label": "Idiomas",
             "value": ", ".join(profile.get("languages", [])), "type": "text"},
        ]


class GupyHandler(BaseHandler):
    """
    Gupy: candidatura requer login no portal.
    Nível 2 gera pré-preenchimento para acelerar o processo.
    """

    def apply(self, job: dict, profile: dict) -> dict:
        url = job.get("url", "")
        fields = self._build_fields(job, profile)

        return {
            "ok": True,
            "platform": "gupy",
            "action": "assisted_fill",
            "url": url,
            "tip": (
                "Gupy requer login. Os dados abaixo foram preparados para você colar "
                "rapidamente nos campos do formulário. Abra a vaga e use Ctrl+C/Ctrl+V."
            ),
            "prefill_fields": fields,
            "steps": [
                "1. Clique em 'Abrir Vaga' para ir ao Gupy",
                "2. Faça login (ou cadastre-se gratuitamente)",
                "3. Clique em 'Candidatar-se'",
                "4. Use os dados preparados abaixo para preencher os campos",
                "5. Volte aqui e marque como 'Aplicada'",
            ],
        }

    def _build_fields(self, job: dict, profile: dict) -> list[dict]:
        hard = profile.get("skills", {}).get("hard", [])
        desc = (job.get("descricao") or "").lower()
        relevant = [s for s in hard if s.lower() in desc][:5] or hard[:5]
        about = profile.get("about", "")

        base = self._contact_fields(profile)
        base += [
            {"label": "Cargo pretendido", "value": job.get("titulo", profile.get("current_role", "")), "type": "text"},
            {"label": "Resumo / Sobre você", "value": about[:500], "type": "textarea"},
            {"label": "Competências relevantes", "value": ", ".join(relevant), "type": "text"},
        ]
        return base


class LinkedInHandler(BaseHandler):
    """
    LinkedIn: detecta Easy Apply e orienta o fluxo correto.
    """

    def apply(self, job: dict, profile: dict) -> dict:
        url = job.get("url", "")
        is_easy = self._is_easy_apply(job)

        base = {
            "ok": True,
            "platform": "linkedin",
            "url": url,
        }

        if is_easy:
            return {
                **base,
                "action": "easy_apply",
                "tip": (
                    "Esta vaga tem Easy Apply (Candidatura Simplificada). "
                    "Abra a vaga, clique no botão azul e use os dados abaixo."
                ),
                "prefill_fields": self._easy_apply_fields(profile),
                "steps": [
                    "1. Abra a vaga no LinkedIn",
                    "2. Clique em 'Candidatura Simplificada' (botão azul)",
                    "3. Preencha os campos (use os dados abaixo)",
                    "4. Confirme o envio",
                    "5. Marque como 'Aplicada' aqui no dashboard",
                ],
            }

        return {
            **base,
            "action": "external_apply",
            "tip": "Esta vaga redireciona para o site da empresa. Abra e aplique diretamente.",
            "prefill_fields": self._contact_fields(profile),
            "steps": [
                "1. Abra a vaga no LinkedIn",
                "2. Você será redirecionado ao site da empresa",
                "3. Preencha o formulário com os dados abaixo",
                "4. Marque como 'Aplicada' aqui no dashboard",
            ],
        }

    def _is_easy_apply(self, job: dict) -> bool:
        texto = ((job.get("descricao") or "") + (job.get("titulo") or "")).lower()
        return "easy apply" in texto or "candidatura simplificada" in texto

    def _easy_apply_fields(self, profile: dict) -> list[dict]:
        base = self._contact_fields(profile)
        base += [
            {"label": "Número de telefone", "value": "", "type": "text",
             "note": "Preencha seu celular com DDD"},
            {"label": "Pretensão salarial", "value": "", "type": "text",
             "note": "Opcional — 'A combinar' é aceito"},
        ]
        return base


class IndeedHandler(BaseHandler):
    """Indeed: maioria das vagas redireciona para site externo."""

    def apply(self, job: dict, profile: dict) -> dict:
        return {
            "ok": True,
            "platform": "indeed",
            "action": "external_redirect",
            "url": job.get("url", ""),
            "tip": (
                "Indeed geralmente redireciona para o site da empresa. "
                "Abra a vaga e aplique diretamente no portal indicado."
            ),
            "prefill_fields": self._contact_fields(profile),
            "steps": [
                "1. Abra a vaga no Indeed",
                "2. Clique em 'Candidate-se agora' (pode redirecionar)",
                "3. Preencha o formulário do empregador",
                "4. Marque como 'Aplicada' aqui no dashboard",
            ],
        }


class VagasHandler(BaseHandler):
    """Vagas.com: candidatura via portal com cadastro."""

    def apply(self, job: dict, profile: dict) -> dict:
        return {
            "ok": True,
            "platform": "vagas",
            "action": "portal_apply",
            "url": job.get("url", ""),
            "tip": "Vagas.com requer cadastro gratuito no portal.",
            "prefill_fields": self._contact_fields(profile) + [
                {"label": "Cargo desejado", "value": profile.get("current_role", ""), "type": "text"},
            ],
            "steps": [
                "1. Abra a vaga em Vagas.com",
                "2. Cadastre-se ou faça login (gratuito)",
                "3. Clique em 'Candidatar'",
                "4. Use os dados abaixo para preencher o perfil",
                "5. Marque como 'Aplicada' aqui no dashboard",
            ],
        }


_HANDLERS: dict[str, BaseHandler] = {
    "linkedin": LinkedInHandler(),
    "indeed": IndeedHandler(),
    "gupy": GupyHandler(),
    "vagas": VagasHandler(),
}


def get_handler(fonte: str) -> BaseHandler | None:
    key = fonte.lower().replace(".com", "").strip()
    return _HANDLERS.get(key)
