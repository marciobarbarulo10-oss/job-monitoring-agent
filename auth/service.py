import hashlib
import secrets
import json
from datetime import datetime, timedelta
from auth.models import get_auth_connection


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, h = hashed.split(':', 1)
        return hashlib.pbkdf2_hmac(
            'sha256', password.encode(), salt.encode(), 100000
        ).hex() == h
    except Exception:
        return False


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(hours=72)).isoformat()
    conn = get_auth_connection()
    conn.execute(
        "DELETE FROM sessions WHERE user_id=? AND expires_at<?",
        (user_id, datetime.now().isoformat())
    )
    conn.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires)
    )
    conn.commit()
    conn.close()
    return token


def validate_session(token: str):
    if not token:
        return None
    conn = get_auth_connection()
    row = conn.execute("""
        SELECT u.id, u.name, u.email, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
    """, (token, datetime.now().isoformat())).fetchone()
    conn.close()
    return dict(row) if row else None


def register_user(name: str, email: str, password: str) -> dict:
    if len(password) < 6:
        return {'success': False, 'error': 'Senha mínima: 6 caracteres'}
    conn = get_auth_connection()
    if conn.execute("SELECT id FROM users WHERE email=?", (email.lower(),)).fetchone():
        conn.close()
        return {'success': False, 'error': 'E-mail já cadastrado'}
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name.strip(), email.lower().strip(), hash_password(password))
    )
    user_id = cur.lastrowid
    conn.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    return {'success': True, 'user_id': user_id}


def login_user(email: str, password: str) -> dict:
    conn = get_auth_connection()
    user = conn.execute(
        "SELECT id, name, email, password_hash, role, is_active FROM users WHERE email=?",
        (email.lower().strip(),)
    ).fetchone()
    if not user or not user['is_active']:
        conn.close()
        return {'success': False, 'error': 'E-mail ou senha incorretos'}
    if not verify_password(password, user['password_hash']):
        conn.close()
        return {'success': False, 'error': 'E-mail ou senha incorretos'}
    conn.execute(
        "UPDATE users SET last_login=? WHERE id=?",
        (datetime.now().isoformat(), user['id'])
    )
    conn.commit()
    conn.close()
    token = create_session(user['id'])
    return {
        'success': True,
        'token': token,
        'user': {
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role'],
        }
    }


def get_user_profile(user_id: int) -> dict:
    conn = get_auth_connection()
    row = conn.execute("""
        SELECT p.*, u.name
        FROM user_profiles p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    if not row:
        return {}
    p = dict(row)
    for field in ['keywords', 'languages']:
        try:
            p[field] = json.loads(p[field]) if p[field] else []
        except Exception:
            p[field] = []
    return p
