"""
API de perfil do usuário — salva e carrega configurações reais.
Substitui o config/profile.py estático por dados dinâmicos do banco.
"""
import os
import json
import shutil
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from api.db import get_db
from datetime import datetime

router = APIRouter()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CV_UPLOAD_DIR = os.path.join(_BASE_DIR, "data", "cvs")
os.makedirs(CV_UPLOAD_DIR, exist_ok=True)


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    target_role: Optional[str] = None
    experience_years: Optional[int] = None
    location: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    education: Optional[str] = None
    linkedin_url: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    min_score_notify: Optional[float] = None
    active_cv: Optional[str] = None


def _get_profile_from_db() -> dict:
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT profile_data FROM user_profile_snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    except Exception:
        row = None

    if row and row["profile_data"]:
        try:
            return json.loads(row["profile_data"])
        except Exception:
            pass

    # Fallback: lê do profile.py estático
    try:
        from config.profile import PERFIL
        return {
            "name": PERFIL.get("nome", ""),
            "target_role": "",
            "experience_years": 0,
            "location": PERFIL.get("localizacao", "São Paulo, SP"),
            "summary": "",
            "keywords": list(PERFIL.get("keywords", {}).keys()),
            "languages": [],
            "education": "",
            "linkedin_url": "",
            "telegram_chat_id": "",
            "min_score_notify": 6.0,
            "active_cv": "",
        }
    except Exception:
        return {}


def _save_profile_to_db(profile: dict):
    conn = get_db()
    conn.execute(
        "INSERT INTO user_profile_snapshots (profile_data, source) VALUES (?, 'ui')",
        (json.dumps(profile, ensure_ascii=False),),
    )
    conn.commit()
    conn.close()
    _update_profile_py(profile)


def _update_profile_py(profile: dict):
    """
    Atualiza config/profile.py mantendo compatibilidade com agentes existentes.
    Converte a lista de keywords do novo formato para o dict ponderado do scorer.
    """
    keywords_list = profile.get("keywords", [])
    keywords_dict = {kw: 2 for kw in keywords_list}

    # Preserva titulos_ideais / titulos_ignorar do PERFIL existente
    titulos_ideais = []
    titulos_ignorar = []
    queries_busca = []
    try:
        from config.profile import PERFIL as _OLD
        titulos_ideais = _OLD.get("titulos_ideais", [])
        titulos_ignorar = _OLD.get("titulos_ignorar", [])
        queries_busca = _OLD.get("queries_busca", [])
    except Exception:
        pass

    keywords_json = json.dumps(keywords_dict, ensure_ascii=False)
    titulos_ideais_json = json.dumps(titulos_ideais, ensure_ascii=False)
    titulos_ignorar_json = json.dumps(titulos_ignorar, ensure_ascii=False)
    queries_busca_json = json.dumps(queries_busca, ensure_ascii=False)
    keywords_list_json = json.dumps(keywords_list, ensure_ascii=False)
    languages_json = json.dumps(profile.get("languages", []), ensure_ascii=False)

    content = f'''"""
Perfil do usuário — gerado automaticamente pela interface.
Última atualização: {datetime.now().strftime("%Y-%m-%d %H:%M")}
NÃO edite manualmente — use a página Meu Perfil no dashboard.
"""

# Novo formato — editado via interface
PROFILE = {{
    "name": {json.dumps(profile.get("name", ""), ensure_ascii=False)},
    "target_role": {json.dumps(profile.get("target_role", ""), ensure_ascii=False)},
    "experience_years": {profile.get("experience_years", 0)},
    "location": {json.dumps(profile.get("location", "São Paulo, SP"), ensure_ascii=False)},
    "summary": {json.dumps(profile.get("summary", ""), ensure_ascii=False)},
    "keywords": {keywords_list_json},
    "languages": {languages_json},
    "education": {json.dumps(profile.get("education", ""), ensure_ascii=False)},
    "linkedin_url": {json.dumps(profile.get("linkedin_url", ""), ensure_ascii=False)},
    "telegram_chat_id": {json.dumps(profile.get("telegram_chat_id", ""), ensure_ascii=False)},
    "min_score_notify": {profile.get("min_score_notify", 6.0)},
    "active_cv": {json.dumps(profile.get("active_cv", ""), ensure_ascii=False)},
}}

# Compatibilidade com agentes existentes
PERFIL = {{
    "nome": PROFILE["name"],
    "nivel": "pleno",
    "localizacao": PROFILE["location"],
    "aceita_remoto": True,
    "aceita_hibrido": True,
    "keywords": {keywords_json},
    "titulos_ideais": {titulos_ideais_json},
    "titulos_ignorar": {titulos_ignorar_json},
    "queries_busca": {queries_busca_json},
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

    path = os.path.join(_BASE_DIR, "config", "profile.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
def get_profile():
    profile = _get_profile_from_db()
    cvs = [f for f in os.listdir(CV_UPLOAD_DIR) if f.endswith(".pdf")] if os.path.exists(CV_UPLOAD_DIR) else []
    profile["cv_files"] = cvs
    return profile


@router.put("/")
def update_profile(body: ProfileUpdate):
    current = _get_profile_from_db()
    updates = body.dict(exclude_none=True)
    current.update(updates)
    current["updated_at"] = datetime.now().isoformat()
    _save_profile_to_db(current)
    return {
        "success": True,
        "message": "Perfil salvo. O scorer já está usando seus novos dados.",
        "profile": current,
    }


@router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos")

    safe_name = file.filename.replace(" ", "_").replace("/", "_")
    dest = os.path.join(CV_UPLOAD_DIR, safe_name)

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"success": True, "filename": safe_name, "path": dest}


@router.get("/cvs")
def list_cvs():
    files = [f for f in os.listdir(CV_UPLOAD_DIR) if f.endswith(".pdf")] if os.path.exists(CV_UPLOAD_DIR) else []
    profile = _get_profile_from_db()
    active = profile.get("active_cv", files[0] if files else "")
    return {"files": files, "active": active}


@router.delete("/cvs/{filename}")
def delete_cv(filename: str):
    path = os.path.join(CV_UPLOAD_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Arquivo não encontrado")
    os.remove(path)
    return {"success": True}
