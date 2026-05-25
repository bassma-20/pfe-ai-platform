"""
chatbot/routes.py — Endpoints FastAPI pour le chatbot IA.

Routes :
  POST /api/chatbot/chat          — Réponse complète
  POST /api/chatbot/stream        — Réponse en streaming (SSE)
  DELETE /api/chatbot/clear/{id}  — Effacer l'historique d'une session
  GET  /api/chatbot/history/{id}  — Récupérer l'historique
  GET  /api/chatbot/suggestions   — Liste des suggestions de questions
  GET  /api/chatbot/personalities — Liste des personnalités disponibles
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.chatbot.service import (
    chat,
    chat_stream,
    clear_history,
    get_history,
    SUGGESTIONS,
    PERSONALITIES,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Chatbot IA"])


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Message de l'utilisateur")
    session_id: Optional[str] = Field(None, description="ID de session (généré auto si absent)")
    personality: Optional[str] = Field("pedagogue", description="Personnalité : expert | pedagogue | debutant")


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    history_length: int


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Envoie un message et retourne une réponse complète."""
    session_id = req.session_id or str(uuid.uuid4())

    if req.personality not in PERSONALITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Personnalité invalide. Valeurs acceptées : {list(PERSONALITIES.keys())}"
        )

    try:
        result = await chat(
            session_id=session_id,
            message=req.message,
            personality=req.personality,
        )
        return ChatResponse(**result)
    except Exception as e:
        logger.error(f"[Chatbot] Erreur chat: {e}")
        raise HTTPException(status_code=502, detail=f"Erreur LLM : {str(e)}")


@router.post("/stream")
async def stream_endpoint(req: ChatRequest):
    """Envoie un message et stream la réponse token par token (SSE)."""
    session_id = req.session_id or str(uuid.uuid4())

    if req.personality not in PERSONALITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Personnalité invalide. Valeurs acceptées : {list(PERSONALITIES.keys())}"
        )

    return StreamingResponse(
        chat_stream(
            session_id=session_id,
            message=req.message,
            personality=req.personality,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,
        },
    )


@router.delete("/clear/{session_id}")
async def clear_session(session_id: str):
    """Efface l'historique d'une session."""
    clear_history(session_id)
    return {"message": "Historique effacé.", "session_id": session_id}


@router.get("/history/{session_id}")
async def get_session_history(session_id: str):
    """Récupère l'historique de conversation d'une session."""
    history = get_history(session_id)
    return {
        "session_id": session_id,
        "history": history,
        "message_count": len(history),
    }


@router.get("/suggestions")
async def get_suggestions():
    """Retourne la liste des suggestions de questions."""
    return {"suggestions": SUGGESTIONS}


@router.get("/personalities")
async def get_personalities():
    """Retourne les personnalités disponibles."""
    return {
        "personalities": [
            {
                "key": key,
                "label": val["label"],
                "emoji": val["emoji"],
                "description": val["description"],
            }
            for key, val in PERSONALITIES.items()
        ]
    }
