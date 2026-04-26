"""
llm_client.py — Cliente centralizado para Anthropic API.
Usado por todos os agentes. Modo lite automático se API key ausente.
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_ANTHROPIC_AVAILABLE = False
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    pass


class LLMClient:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if _ANTHROPIC_AVAILABLE and api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.available = True
            logger.info("LLMClient inicializado")
        else:
            self.client = None
            self.available = False
            if not api_key:
                logger.warning("ANTHROPIC_API_KEY nao configurada — modo lite ativo")

        self.model = os.getenv("SEMANTIC_MODEL", "claude-haiku-4-5-20251001")
        self.model_pro = "claude-sonnet-4-6"

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1000,
                 use_pro: bool = False) -> Optional[str]:
        if not self.available:
            return None
        try:
            model = self.model_pro if use_pro else self.model
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system if system else "Voce e um assistente especializado.",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None

    def complete_json(self, prompt: str, system: str = "",
                      max_tokens: int = 1000) -> Optional[dict]:
        system_json = (system or "") + "\n\nRESPONDA APENAS COM JSON VALIDO. Sem texto adicional, sem markdown."
        result = self.complete(prompt, system_json, max_tokens)
        if result:
            try:
                clean = result.strip()
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0].strip()
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0].strip()
                return json.loads(clean)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e} | Raw: {result[:200]}")
        return None


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
