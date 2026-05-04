"""
api/main.py — Backend FastAPI do Job Agent v3.0.
Roda em porta 8000 separado do Flask (porta 5000).
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routers import jobs, applications, dashboard, insights, profile, health, webhooks
from auth.router import router as auth_router

app = FastAPI(
    title="Job Agent API",
    description="API REST do sistema de monitoramento de vagas — v8.0",
    version="8.0.0",
)


@app.on_event("startup")
def _startup():
    from core.models import init_db
    from auth.models import init_auth_db
    init_db()
    init_auth_db()

_cors_origins = [
    o.strip() for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:5174"
    ).split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Autenticação"])
app.include_router(jobs.router, prefix="/api/vagas", tags=["Vagas"])
app.include_router(applications.router, prefix="/api/candidaturas", tags=["Candidaturas"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(insights.router, prefix="/api/insights", tags=["Insights"])
app.include_router(profile.router, prefix="/api/profile", tags=["Perfil"])
app.include_router(health.router, prefix="/health", tags=["Health & QA"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks MailerLite"])


# Serve frontend buildado em produção
_frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("API_PORT", 8000)), reload=False)
