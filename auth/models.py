"""Banco de autenticação separado do banco de vagas."""
import sqlite3
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH_DB = os.path.join(_BASE_DIR, "data", "auth.db")


def get_auth_connection():
    os.makedirs(os.path.dirname(AUTH_DB), exist_ok=True)
    conn = sqlite3.connect(AUTH_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = get_auth_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            role TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            target_role TEXT DEFAULT '',
            experience_years INTEGER DEFAULT 0,
            location TEXT DEFAULT 'São Paulo, SP',
            keywords TEXT DEFAULT '[]',
            languages TEXT DEFAULT '[]',
            education TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            linkedin_url TEXT DEFAULT '',
            telegram_chat_id TEXT DEFAULT '',
            min_score_notify REAL DEFAULT 6.0,
            active_cv TEXT DEFAULT '',
            onboarding_completed BOOLEAN DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()
