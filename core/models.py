"""
models.py — Definição do banco de dados (SQLite via SQLAlchemy)
"""
import os
import sqlite3
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

logger = logging.getLogger(__name__)

Base = declarative_base()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


class Vaga(Base):
    """Representa uma vaga encontrada ou aplicada."""
    __tablename__ = "vagas"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    titulo           = Column(String(300), nullable=False)
    empresa          = Column(String(200))
    localizacao      = Column(String(200))
    modalidade       = Column(String(50))
    fonte            = Column(String(50))
    url              = Column(String(500), unique=True)
    descricao        = Column(Text)
    palavras_chave   = Column(Text)
    score            = Column(Float, default=0.0)
    score_method     = Column(String(20), default="keyword")
    score_grade      = Column(String(2))
    score_analysis   = Column(Text)
    status           = Column(String(50), default="nova")
    aplicada         = Column(Boolean, default=False)
    notificada       = Column(Boolean, default=False)
    is_early_applicant = Column(Boolean, default=False)
    posted_at        = Column(DateTime, nullable=True)
    data_encontrada  = Column(DateTime, default=datetime.utcnow)
    data_aplicacao   = Column(DateTime, nullable=True)
    data_update      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check       = Column(DateTime, nullable=True)
    notas            = Column(Text)
    favorited        = Column(Boolean, default=False)
    ignored          = Column(Boolean, default=False)
    score_matched_kws = Column(Text)
    score_missing_kws = Column(Text)


class UserProfile(Base):
    """Perfil do usuário importado do LinkedIn ou inserido manualmente."""
    __tablename__ = "user_profiles"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    source      = Column(String(50))
    linkedin_url = Column(String(500))
    data_json   = Column(Text)
    imported_at = Column(DateTime, default=datetime.utcnow)
    is_active   = Column(Boolean, default=True)


class StatusHistory(Base):
    """Histórico de mudanças de status de cada vaga."""
    __tablename__ = "status_history"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    vaga_id    = Column(Integer)
    status_old = Column(String(50))
    status_new = Column(String(50))
    timestamp  = Column(DateTime, default=datetime.utcnow)
    detalhes   = Column(Text)


class CVExport(Base):
    """Registro de CVs gerados por vaga."""
    __tablename__ = "cv_exports"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(Integer)
    file_path  = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackOutcome(Base):
    """Outcomes registrados pelo usuário (entrevista, rejeição, etc.)."""
    __tablename__ = "feedback_outcomes"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    job_id       = Column(Integer)
    outcome      = Column(String(30))
    outcome_date = Column(DateTime, default=datetime.utcnow)
    notes        = Column(Text)


class OpportunityAlert(Base):
    """Alertas de janela de oportunidade (vagas < 48h)."""
    __tablename__ = "opportunity_alerts"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(Integer)
    detected_at = Column(DateTime, default=datetime.utcnow)
    notified_at = Column(DateTime, nullable=True)


class MarketReport(Base):
    """Relatórios semanais de inteligência de mercado."""
    __tablename__ = "market_reports"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    week        = Column(String(20), unique=True)
    report_json = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)


class QualityFlag(Base):
    """Flags de qualidade em vagas suspeitas."""
    __tablename__ = "quality_flags"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(Integer)
    flags_json = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScoreCalibration(Base):
    """Pesos calibrados pelo FeedbackEngine."""
    __tablename__ = "score_calibration"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    feature     = Column(String(100), unique=True)
    weight      = Column(Float)
    updated_at  = Column(DateTime, default=datetime.utcnow)
    sample_size = Column(Integer)


# ── Engine & Session ──────────────────────────────────────────────────────────
engine  = create_engine(f"sqlite:///{_DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
    run_migrations()
    logger.info(f"Banco inicializado: {_DB_PATH}")


def run_migrations():
    """Executa migrações incrementais seguras na inicialização."""
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()

    # Colunas novas na tabela vagas
    cur.execute("PRAGMA table_info(vagas)")
    colunas_vagas = {row[1] for row in cur.fetchall()}

    _safe_add_column(cur, "vagas", "last_check", "DATETIME", colunas_vagas)
    _safe_add_column(cur, "vagas", "posted_at", "DATETIME", colunas_vagas)
    _safe_add_column(cur, "vagas", "is_early_applicant", "BOOLEAN DEFAULT 0", colunas_vagas)
    _safe_add_column(cur, "vagas", "score_method", "TEXT DEFAULT 'keyword'", colunas_vagas)
    _safe_add_column(cur, "vagas", "score_grade", "TEXT", colunas_vagas)
    _safe_add_column(cur, "vagas", "score_analysis", "TEXT", colunas_vagas)
    _safe_add_column(cur, "vagas", "favorited", "BOOLEAN DEFAULT 0", colunas_vagas)
    _safe_add_column(cur, "vagas", "ignored", "BOOLEAN DEFAULT 0", colunas_vagas)
    _safe_add_column(cur, "vagas", "score_matched_kws", "TEXT", colunas_vagas)
    _safe_add_column(cur, "vagas", "score_missing_kws", "TEXT", colunas_vagas)
    # v3.0 — multi-agent columns
    _safe_add_column(cur, "vagas", "cover_letter", "TEXT", colunas_vagas)
    _safe_add_column(cur, "vagas", "cv_recommended", "TEXT", colunas_vagas)
    _safe_add_column(cur, "vagas", "is_verified", "BOOLEAN DEFAULT 1", colunas_vagas)
    _safe_add_column(cur, "vagas", "last_verified_at", "DATETIME", colunas_vagas)

    # Novas tabelas (via CREATE TABLE IF NOT EXISTS)
    _DDL_NOVAS_TABELAS = [
        """CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            linkedin_url TEXT,
            data_json TEXT,
            imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS cv_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES vagas(id),
            file_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS feedback_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES vagas(id),
            outcome TEXT CHECK(outcome IN ('entrevista','rejeicao','sem_resposta','proposta')),
            outcome_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS opportunity_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES vagas(id),
            detected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notified_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS market_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week TEXT UNIQUE,
            report_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS quality_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER REFERENCES vagas(id),
            flags_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
        """CREATE TABLE IF NOT EXISTS score_calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature TEXT UNIQUE,
            weight REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            sample_size INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            duration_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )""",
    ]

    for ddl in _DDL_NOVAS_TABELAS:
        try:
            cur.execute(ddl)
        except Exception as e:
            logger.warning(f"Migration DDL ignorada: {e}")

    conn.commit()
    conn.close()


def _safe_add_column(cur, tabela: str, coluna: str, tipo: str, existentes: set):
    """Adiciona coluna apenas se não existir (SQLite não suporta IF NOT EXISTS em ALTER)."""
    if coluna not in existentes:
        try:
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
        except Exception as e:
            logger.warning(f"Nao foi possivel adicionar coluna {coluna}: {e}")
