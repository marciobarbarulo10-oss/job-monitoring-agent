"""
market_intelligence.py — Análise de tendências de mercado a partir dos dados coletados.
Gera relatório semanal com keywords, empresas, modalidades e evolução.
"""
import json
import sqlite3
import os
from collections import Counter
from datetime import datetime, timedelta
from loguru import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")

_STOP_WORDS = {
    "de", "da", "do", "dos", "das", "e", "em", "para", "com", "por", "um",
    "uma", "que", "se", "na", "no", "os", "as", "ao", "a", "o", "é", "ou",
    "seu", "sua", "seus", "suas", "mais", "como", "mas", "também", "será",
    "pode", "será", "ter", "tem", "são", "foi", "ser",
}


class MarketIntelligence:
    """Gera relatórios de inteligência de mercado a partir dos dados coletados."""

    def weekly_report(self) -> dict:
        """Gera relatório semanal completo de tendências de mercado."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            conn.row_factory = sqlite3.Row

            semana_passada = (datetime.utcnow() - timedelta(days=7)).isoformat()
            duas_semanas = (datetime.utcnow() - timedelta(days=14)).isoformat()

            vagas_semana = conn.execute(
                "SELECT * FROM vagas WHERE data_encontrada > ?", (semana_passada,)
            ).fetchall()

            total = len(vagas_semana)

            # Score médio da semana
            scores = [v["score"] for v in vagas_semana if v["score"] and v["score"] > 0]
            score_medio = round(sum(scores) / len(scores), 1) if scores else 0.0

            # Keywords mais frequentes (de palavras_chave + títulos)
            kw_counter = Counter()
            for v in vagas_semana:
                if v["palavras_chave"]:
                    try:
                        kws = json.loads(v["palavras_chave"])
                        kw_counter.update(kws)
                    except Exception:
                        pass
                if v["titulo"]:
                    palavras = [
                        p.strip(".,;:()[]").lower()
                        for p in v["titulo"].split()
                        if len(p) > 4 and p.lower() not in _STOP_WORDS
                    ]
                    kw_counter.update(palavras)

            top_keywords = [
                {"keyword": k, "count": c}
                for k, c in kw_counter.most_common(20)
            ]

            # Top empresas
            empresa_counter = Counter()
            for v in vagas_semana:
                if v["empresa"] and v["empresa"] not in ("", "—", None):
                    empresa_counter[v["empresa"]] += 1
            top_empresas = [
                {"empresa": e, "vagas": c}
                for e, c in empresa_counter.most_common(10)
            ]

            # Senioridade mais demandada
            senioridade = {"junior": 0, "pleno": 0, "senior": 0, "gestao": 0, "nao_informado": 0}
            for v in vagas_semana:
                texto = f"{v['titulo'] or ''} {v['descricao'] or ''}".lower()
                if any(t in texto for t in ["júnior", "junior", "jr", " i ", "entry"]):
                    senioridade["junior"] += 1
                elif any(t in texto for t in ["pleno", "pl ", " ii ", "mid-level", "mid level"]):
                    senioridade["pleno"] += 1
                elif any(t in texto for t in ["sênior", "senior", "sr", " iii ", "specialist", "especialista"]):
                    senioridade["senior"] += 1
                elif any(t in texto for t in ["gerente", "coordenador", "gestor", "líder", "lider", "manager"]):
                    senioridade["gestao"] += 1
                else:
                    senioridade["nao_informado"] += 1

            # Distribuição modalidade
            modalidade = {"remoto": 0, "hibrido": 0, "presencial": 0, "nao_informado": 0}
            for v in vagas_semana:
                texto = f"{v['modalidade'] or ''} {v['localizacao'] or ''}".lower()
                if any(t in texto for t in ["remoto", "remote", "home office"]):
                    modalidade["remoto"] += 1
                elif any(t in texto for t in ["híbrido", "hibrido", "hybrid"]):
                    modalidade["hibrido"] += 1
                elif any(t in texto for t in ["presencial", "on-site", "onsite", "in-office"]):
                    modalidade["presencial"] += 1
                else:
                    modalidade["nao_informado"] += 1

            # Por fonte
            fonte_counter = Counter()
            for v in vagas_semana:
                if v["fonte"]:
                    fonte_counter[v["fonte"]] += 1

            # Comparação semana anterior
            total_anterior = conn.execute(
                "SELECT COUNT(*) FROM vagas WHERE data_encontrada > ? AND data_encontrada <= ?",
                (duas_semanas, semana_passada),
            ).fetchone()[0]

            variacao_pct = 0.0
            if total_anterior > 0:
                variacao_pct = round(((total - total_anterior) / total_anterior) * 100, 1)

            # Destaques da semana (vagas com score >= 8)
            destaques = [
                {
                    "titulo": v["titulo"],
                    "empresa": v["empresa"],
                    "score": v["score"],
                }
                for v in vagas_semana
                if v["score"] and v["score"] >= 8.0
            ][:5]

            conn.close()

            report = {
                "semana": datetime.utcnow().strftime("%Y-W%W"),
                "gerado_em": datetime.utcnow().isoformat(),
                "total_vagas": total,
                "score_medio": score_medio,
                "top_keywords": top_keywords,
                "top_empresas": top_empresas,
                "senioridade": senioridade,
                "modalidade": modalidade,
                "fontes": dict(fonte_counter),
                "variacao_semana_pct": variacao_pct,
                "total_semana_anterior": total_anterior,
                "destaques": destaques,
            }

            self._save_report(report)
            logger.info(f"Relatorio de mercado gerado: {total} vagas, score medio {score_medio}")
            return report

        except Exception as e:
            logger.error(f"Erro ao gerar relatorio de mercado: {e}")
            return {}

    def get_latest_report(self) -> dict:
        """Recupera o relatório mais recente salvo no banco."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            row = conn.execute(
                "SELECT report_json FROM market_reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.warning(f"Erro ao buscar relatorio: {e}")
        return {}

    def _save_report(self, report: dict):
        """Persiste relatório no banco (substitui da mesma semana se existir)."""
        try:
            conn = sqlite3.connect(_DB_PATH)
            semana = report.get("semana", "")
            conn.execute(
                "INSERT OR REPLACE INTO market_reports (week, report_json, created_at) VALUES (?, ?, ?)",
                (semana, json.dumps(report, ensure_ascii=False), datetime.utcnow().isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Erro ao salvar relatorio de mercado: {e}")
