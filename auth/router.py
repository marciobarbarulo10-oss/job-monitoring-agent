from fastapi import APIRouter, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from typing import Optional
import json
import os
from datetime import datetime
from auth.service import register_user, login_user, validate_session, get_user_profile
from auth.models import get_auth_connection

router = APIRouter()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CV_DIR = os.path.join(_BASE_DIR, "data", "cvs")


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    target_role: Optional[str] = None
    experience_years: Optional[int] = None
    location: Optional[str] = None
    keywords: Optional[list] = None
    languages: Optional[list] = None
    education: Optional[str] = None
    summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    min_score_notify: Optional[float] = None
    active_cv: Optional[str] = None


def get_current_user(authorization: Optional[str] = None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token necessário")
    user = validate_session(authorization.replace("Bearer ", ""))
    if not user:
        raise HTTPException(401, "Sessão expirada. Faça login novamente.")
    return user


@router.post("/register")
def register(body: RegisterRequest):
    result = register_user(body.name, body.email, body.password)
    if not result['success']:
        raise HTTPException(400, result['error'])
    lr = login_user(body.email, body.password)
    return {
        'success': True,
        'token': lr['token'],
        'user': lr['user'],
        'next_step': 'onboarding',
    }


@router.post("/login")
def login(body: LoginRequest):
    result = login_user(body.email, body.password)
    if not result['success']:
        raise HTTPException(401, result['error'])
    conn = get_auth_connection()
    p = conn.execute(
        "SELECT onboarding_completed FROM user_profiles WHERE user_id=?",
        (result['user']['id'],)
    ).fetchone()
    conn.close()
    done = p and p['onboarding_completed']
    return {
        'success': True,
        'token': result['token'],
        'user': result['user'],
        'next_step': 'dashboard' if done else 'onboarding',
    }


@router.post("/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        conn = get_auth_connection()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit()
        conn.close()
    return {'success': True}


@router.get("/me")
def get_me(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    profile = get_user_profile(user['id'])
    return {'user': user, 'profile': profile}


@router.put("/profile")
def update_profile(body: ProfileUpdate, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    conn = get_auth_connection()
    updates = {k: v for k, v in body.dict().items() if v is not None}
    for f in ['keywords', 'languages']:
        if f in updates and isinstance(updates[f], list):
            updates[f] = json.dumps(updates[f], ensure_ascii=False)
    updates['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE user_profiles SET {set_clause} WHERE user_id=?",
        list(updates.values()) + [user['id']]
    )
    conn.commit()
    conn.close()
    _sync_profile_py(user['id'])
    return {'success': True}


@router.post("/onboarding/complete")
def complete_onboarding(body: ProfileUpdate, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    conn = get_auth_connection()
    updates = {k: v for k, v in body.dict().items() if v is not None}
    for f in ['keywords', 'languages']:
        if f in updates and isinstance(updates[f], list):
            updates[f] = json.dumps(updates[f], ensure_ascii=False)
    updates['onboarding_completed'] = 1
    updates['updated_at'] = datetime.now().isoformat()
    set_clause = ', '.join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE user_profiles SET {set_clause} WHERE user_id=?",
        list(updates.values()) + [user['id']]
    )
    conn.commit()
    conn.close()
    _sync_profile_py(user['id'])
    return {'success': True, 'next_step': 'dashboard'}


@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...), authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    os.makedirs(CV_DIR, exist_ok=True)
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Apenas PDF é aceito")
    content = await file.read()
    if not content.startswith(b'%PDF'):
        raise HTTPException(400, "Arquivo PDF inválido")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "Arquivo maior que 5MB")
    safe = f"user_{user['id']}_" + "".join(
        c if c.isalnum() or c in '._-' else '_'
        for c in file.filename
    )
    with open(os.path.join(CV_DIR, safe), "wb") as f:
        f.write(content)
    return {"success": True, "filename": safe, "size_kb": round(len(content) / 1024, 1)}


@router.get("/cvs")
def list_cvs(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    os.makedirs(CV_DIR, exist_ok=True)
    prefix = f"user_{user['id']}_"
    files = [f for f in os.listdir(CV_DIR) if f.startswith(prefix) and f.endswith('.pdf')]
    profile = get_user_profile(user['id'])
    return {"files": files, "active": profile.get("active_cv", "")}


def _sync_profile_py(user_id: int):
    """Atualiza config/profile.py com dados do usuário para o scorer usar."""
    try:
        p = get_user_profile(user_id)
        if not p:
            return
        keywords = p.get('keywords', [])
        keywords_dict = {kw: 2 for kw in keywords}

        titulos_ideais, titulos_ignorar, queries_busca = [], [], []
        try:
            from config.profile import PERFIL as _OLD
            titulos_ideais = _OLD.get("titulos_ideais", [])
            titulos_ignorar = _OLD.get("titulos_ignorar", [])
            queries_busca = _OLD.get("queries_busca", [])
        except Exception:
            pass

        profile_path = os.path.join(_BASE_DIR, "config", "profile.py")
        content = f'''"""
Perfil sincronizado automaticamente da interface.
Usuário ID: {user_id} — {datetime.now().strftime("%Y-%m-%d %H:%M")}
NÃO edite manualmente — use a página Meu Perfil no dashboard.
"""

PROFILE = {{
    "name": {json.dumps(p.get("name", ""), ensure_ascii=False)},
    "target_role": {json.dumps(p.get("target_role", ""), ensure_ascii=False)},
    "experience_years": {p.get("experience_years", 0)},
    "location": {json.dumps(p.get("location", "São Paulo, SP"), ensure_ascii=False)},
    "summary": {json.dumps(p.get("summary", ""), ensure_ascii=False)},
    "keywords": {json.dumps(keywords, ensure_ascii=False)},
    "languages": {json.dumps(p.get("languages", []), ensure_ascii=False)},
    "education": {json.dumps(p.get("education", ""), ensure_ascii=False)},
    "linkedin_url": {json.dumps(p.get("linkedin_url", ""), ensure_ascii=False)},
    "active_cv": {json.dumps(p.get("active_cv", ""), ensure_ascii=False)},
    "min_score_notify": {p.get("min_score_notify", 6.0)},
}}

PERFIL = {{
    "nome": PROFILE["name"],
    "nivel": "pleno",
    "localizacao": PROFILE["location"],
    "aceita_remoto": True,
    "aceita_hibrido": True,
    "keywords": {json.dumps(keywords_dict, ensure_ascii=False)},
    "titulos_ideais": {json.dumps(titulos_ideais, ensure_ascii=False)},
    "titulos_ignorar": {json.dumps(titulos_ignorar, ensure_ascii=False)},
    "queries_busca": {json.dumps(queries_busca, ensure_ascii=False)},
}}


def calcular_score(titulo: str, descricao: str, localizacao: str = ""):
    texto = f"{{titulo}} {{descricao}}".lower()
    titulo_lower = titulo.lower()
    local_lower = localizacao.lower()

    max_pts = sum(v * 2 for v in PERFIL["keywords"].values())
    pts = 0
    matched = []
    for kw, peso in PERFIL["keywords"].items():
        if kw in texto:
            pts += peso
            matched.append(kw)
    keyword_score = min(6.0, (pts / max(max_pts * 0.15, 1)) * 6)

    titulo_score = 0.0
    for t in PERFIL["titulos_ideais"]:
        if t in titulo_lower:
            titulo_score = 2.5
            break
        palavras = t.split()
        m = sum(1 for p in palavras if p in titulo_lower)
        titulo_score = max(titulo_score, (m / len(palavras)) * 1.5)

    for ign in PERFIL["titulos_ignorar"]:
        if ign in titulo_lower:
            return 0.0, []

    local_score = 0.0
    if "são paulo" in local_lower or "sp" in local_lower:
        local_score = 1.5
    elif "remoto" in local_lower or "remote" in local_lower or "home office" in local_lower:
        local_score = 1.5
    elif "híbrido" in local_lower or "hibrido" in local_lower:
        local_score = 1.2
    elif "brasil" in local_lower:
        local_score = 1.0

    return round(min(10.0, keyword_score + titulo_score + local_score), 1), matched


def score_job(job: dict) -> float:
    score, _ = calcular_score(
        job.get("title", ""),
        job.get("description", ""),
        job.get("location", ""),
    )
    return score
'''
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"_sync_profile_py failed: {e}")
