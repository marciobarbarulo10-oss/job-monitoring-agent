"""
models.py — Definição do banco de dados (SQLite via SQLAlchemy)
"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

# Caminho absoluto para o banco — funciona independente de onde o script é chamado
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DB_PATH = os.path.join(_BASE_DIR, "data", "job_agent.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)


class Vaga(Base):
    """Representa uma vaga encontrada ou aplicada."""
    __tablename__ = "vagas"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    titulo          = Column(String(300), nullable=False)
    empresa         = Column(String(200))
    localizacao     = Column(String(200))
    modalidade      = Column(String(50))
    fonte           = Column(String(50))
    url             = Column(String(500), unique=True)
    descricao       = Column(Text)
    palavras_chave  = Column(Text)
    score           = Column(Float, default=0.0)
    status          = Column(String(50), default="nova")
    # nova | aplicada | em_analise | entrevista | rejeitada | encerrada
    aplicada        = Column(Boolean, default=False)
    data_encontrada = Column(DateTime, default=datetime.utcnow)
    data_aplicacao  = Column(DateTime, nullable=True)
    data_update     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check      = Column(DateTime, nullable=True)
    notificada      = Column(Boolean, default=False)
    notas           = Column(Text)


class StatusHistory(Base):
    """Histórico de mudanças de status de cada vaga."""
    __tablename__ = "status_history"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    vaga_id    = Column(Integer)
    status_old = Column(String(50))
    status_new = Column(String(50))
    timestamp  = Column(DateTime, default=datetime.utcnow)
    detalhes   = Column(Text)


# ── Engine & Session ──────────────────────────────────────────────────────────
engine  = create_engine(f"sqlite:///{_DB_PATH}", echo=False)
Session = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
    _migrate_schema()
    print(f"[INFO] Banco de dados inicializado: {_DB_PATH}")


def _migrate_schema():
    """Aplica migrações incrementais sem perder dados existentes."""
    import sqlite3
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(vagas)")
    existing = {row[1] for row in cur.fetchall()}
    if "last_check" not in existing:
        cur.execute("ALTER TABLE vagas ADD COLUMN last_check DATETIME")
        conn.commit()
    conn.close()
