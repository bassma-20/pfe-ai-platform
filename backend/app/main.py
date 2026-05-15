from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.automl import router as automl_router
from app.routers.migration import router as migration_router
from app.automl.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="AI Platform - AutoML & Code Migration",
    version="2.0.0",
    description="Plateforme intelligente avec deux modules : AutoML avancé et Migration de code",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ Ne pas ajouter prefix ici — le router définit déjà prefix="/automl"
app.include_router(automl_router, prefix="/api")
app.include_router(migration_router, prefix="/api/migration", tags=["Migration Java"])


@app.get("/")
def root():
    return {
        "message": "AI Platform API is running",
        "version": "2.0.0",
        "modules": {
            "automl": {
                "prefix": "/api/automl",
                "docs": "/docs#/AutoML",
                "endpoints": [
                    # ── Upload & Summary ──
                    "POST   /api/automl/upload",
                    "GET    /api/automl/summary/{run_id}",
                    "GET    /api/automl/health",

                    # ── LLM Decision Bus ──
                    "GET    /api/automl/llm/suggest-target/{run_id}",
                    "POST   /api/automl/llm/decision-plan/{run_id}",
                    "POST   /api/automl/llm/apply-plan/{run_id}",
                    "POST   /api/automl/llm/train-with-plan/{run_id}",

                    # ── Pipeline complet ──
                    "POST   /api/automl/run-full-pipeline/{run_id}",

                    # ── Résultats ──
                    "GET    /api/automl/report/{run_id}",
                    "POST   /api/automl/predict/{run_id}",
                ],
            },
            "migration": {
                "prefix": "/api/migration",
                "docs": "/docs#/Migration Java",
            },
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}