"""
quality_filter.py — Detecta vagas suspeitas/scam antes do scoring.
Filtra vagas de baixa qualidade para não consumir tokens da API desnecessariamente.
"""
import json
import sqlite3
import os
from datetime import datetime, timedelta
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

_PALAVRAS_SUSPEITAS = [
    "multinível", "multinivel", "mlm", "network marketing",
    "comissão pura", "comissao pura", "100% comissão",
    "sem experiência necessária", "sem experiencia necessaria",
    "trabalhe de casa e ganhe", "ganhe dinheiro rápido",
    "renda extra garantida", "renda passiva",
    "investimento inicial obrigatório", "investimento inicial",
    "seja seu próprio chefe", "empreendedor independente",
    "representante independente", "parceiro independente",
    "oportunidade única", "vaga exclusiva urgente",
]

_TITULOS_GENERICOS = {
    "analista", "consultor", "assistente", "coordenador",
    "gerente", "especialista", "profissional",
}


class QualityFilter:
    """Filtra vagas suspeitas ou de qualidade insuficiente."""

    def is_suspicious(self, job: dict) -> tuple[bool, list[str]]:
        """
        Analisa se uma vaga é suspeita.
        Retorna (is_suspicious, [razoes_detectadas]).
        """
        reasons = []
        titulo = (job.get("titulo") or "").lower().strip()
        empresa = (job.get("empresa") or "").lower().strip()
        descricao = (job.get("descricao") or "").lower()
        texto_completo = f"{titulo} {descricao}"

        # 1. Palavras-chave suspeitas
        for kw in _PALAVRAS_SUSPEITAS:
            if kw.lower() in texto_completo:
                reasons.append(f"Palavra suspeita detectada: '{kw}'")
                break

        # 2. Descrição muito curta (< 30 palavras quando existe)
        if descricao:
            num_palavras = len(descricao.split())
            if num_palavras < 30:
                reasons.append(f"Descricao insuficiente ({num_palavras} palavras)")

        # 3. Cargo excessivamente genérico (título isolado sem especificação)
        if titulo in _TITULOS_GENERICOS:
            reasons.append(f"Titulo excessivamente generico: '{titulo}'")

        # 4. Sem empresa identificada E sem URL verificável
        empresa_vazia = not empresa or empresa in ("", "—", "empresa confidencial", "confidencial", "n/a")
        url_vazia = not job.get("url")
        if empresa_vazia and url_vazia:
            reasons.append("Empresa e URL nao identificadas")

        # 5. Vaga duplicada recente (mesmo título + empresa, últimos 30 dias)
        if job.get("titulo") and empresa and not empresa_vazia:
            if self._is_recent_duplicate(job):
                reasons.append("Repostagem detectada: mesma vaga nos ultimos 30 dias")

        is_suspicious = len(reasons) >= 2

        if is_suspicious:
            logger.info(f"Vaga suspeita: '{job.get('titulo', '')}' [{len(reasons)} sinais] — {reasons}")
            self._register_flag(job, reasons)

        return is_suspicious, reasons

    def _is_recent_duplicate(self, job: dict) -> bool:
        """Verifica se mesma vaga foi registrada nos últimos 30 dias."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            limite = (datetime.utcnow() - timedelta(days=30)).isoformat()
            row = conn.execute(
                """SELECT COUNT(*) FROM vagas
                   WHERE LOWER(titulo)=? AND LOWER(COALESCE(empresa,''))=?
                   AND data_encontrada > ?
                   AND url != ?""",
                (
                    job.get("titulo", "").lower(),
                    job.get("empresa", "").lower(),
                    limite,
                    job.get("url", "__nenhum__"),
                ),
            ).fetchone()
            conn.close()
            return (row[0] if row else 0) > 0
        except Exception as e:
            logger.warning(f"Erro ao verificar duplicata: {e}")
            return False

    def _register_flag(self, job: dict, reasons: list[str]):
        """Registra flags no banco para auditoria."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            url = job.get("url", "")
            if url:
                row = conn.execute("SELECT id FROM vagas WHERE url=?", (url,)).fetchone()
                if row:
                    conn.execute(
                        "INSERT INTO quality_flags (job_id, flags_json, created_at) VALUES (?, ?, ?)",
                        (row[0], json.dumps(reasons, ensure_ascii=False), datetime.utcnow().isoformat()),
                    )
                    conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao registrar flag de qualidade: {e}")
