"""Rota de perfil do usuário."""
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ProfileContent(BaseModel):
    content: str


@router.get("/")
def get_profile():
    path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {"ok": True, "profile": data}
    except FileNotFoundError:
        from config.profile import PERFIL
        return {"ok": True, "profile": PERFIL, "source": "profile.py"}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/")
def save_profile(body: ProfileContent):
    import yaml
    try:
        yaml.safe_load(body.content)
    except Exception as e:
        raise HTTPException(400, f"YAML invalido: {e}")
    path = os.path.join(_BASE_DIR, "config", "profile.yml")
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body.content)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))
