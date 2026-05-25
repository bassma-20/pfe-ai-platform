"""
chatbot/service.py — Service chatbot IA spécialisé en intelligence artificielle.

Fonctionnalités :
  - Historique de conversation par session
  - Streaming des réponses (SSE)
  - Personnalités multiples (Expert, Pédagogue, Débutant)
  - Suggestions de questions
  - Contexte spécialisé IA/ML
"""

from __future__ import annotations

import os
import json
import logging
from typing import AsyncGenerator, List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS PAR PERSONNALITÉ
# ─────────────────────────────────────────────────────────────────────────────

PERSONALITIES = {
    "expert": {
        "label": "Expert",
        "emoji": "🎓",
        "description": "Réponses techniques et approfondies",
        "system": """Tu es un expert en intelligence artificielle et machine learning.
Tu réponds à des questions techniques avec précision et profondeur.
Tu utilises la terminologie exacte du domaine.
Tu fournis des exemples de code Python quand c'est pertinent (sklearn, TensorFlow, PyTorch, etc.).
Tu parles des dernières avancées (Transformers, LLMs, Diffusion Models, etc.).
Quand tu donnes du code, utilise des blocs markdown ```python.
Réponds toujours en français sauf si on te demande autrement.""",
    },
    "pedagogue": {
        "label": "Pédagogue",
        "emoji": "📚",
        "description": "Explications claires avec analogies",
        "system": """Tu es un professeur pédagogue spécialisé en intelligence artificielle.
Tu expliques les concepts complexes avec des analogies simples et des exemples concrets.
Tu utilises des étapes numérotées pour les explications.
Tu vérifies la compréhension en proposant des exemples pratiques.
Tu évites le jargon inutile mais introduces progressivement les termes techniques.
Utilise des emojis pour rendre les explications plus visuelles.
Réponds toujours en français sauf si on te demande autrement.""",
    },
    "debutant": {
        "label": "Débutant",
        "emoji": "🌱",
        "description": "Langage simple, pas de jargon",
        "system": """Tu es un assistant IA très accessible pour les débutants complets.
Tu expliques l'intelligence artificielle avec un langage très simple, sans jargon technique.
Tu utilises beaucoup d'analogies avec la vie quotidienne.
Tu rassures l'utilisateur et l'encourage.
Tu divises les concepts en petites parties faciles à comprendre.
Tu ne dépasses jamais 3-4 paragraphes par réponse pour ne pas surcharger.
Utilise des exemples tirés de la vie de tous les jours.
Réponds toujours en français sauf si on te demande autrement.""",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# SUGGESTIONS DE QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────

SUGGESTIONS = [
    {"text": "C'est quoi le Machine Learning ?", "icon": "🤖"},
    {"text": "Comment fonctionne un réseau de neurones ?", "icon": "🧠"},
    {"text": "Quelle est la différence entre supervised et unsupervised learning ?", "icon": "📊"},
    {"text": "Qu'est-ce qu'un modèle Transformer ?", "icon": "⚡"},
    {"text": "Comment éviter l'overfitting ?", "icon": "🎯"},
    {"text": "C'est quoi le Deep Learning ?", "icon": "🔬"},
    {"text": "Comment fonctionne ChatGPT ?", "icon": "💬"},
    {"text": "Qu'est-ce que le Random Forest ?", "icon": "🌲"},
    {"text": "Comment choisir le bon algorithme ML ?", "icon": "🗺️"},
    {"text": "C'est quoi la régression linéaire ?", "icon": "📈"},
    {"text": "Comment fonctionne le clustering K-Means ?", "icon": "🔵"},
    {"text": "Qu'est-ce qu'une fonction de perte (loss) ?", "icon": "📉"},
]

# ─────────────────────────────────────────────────────────────────────────────
# MÉMOIRE DE SESSION (en mémoire, par session_id)
# ─────────────────────────────────────────────────────────────────────────────

# sessions[session_id] = list of {"role": ..., "content": ...}
_sessions: Dict[str, List[Dict]] = defaultdict(list)

MAX_HISTORY = 20  # Nombre max de messages gardés par session


def get_history(session_id: str) -> List[Dict]:
    return _sessions[session_id]


def clear_history(session_id: str) -> None:
    _sessions[session_id] = []
    logger.info(f"[Chatbot] Session {session_id} effacée.")


def _trim_history(session_id: str) -> None:
    """Garde seulement les MAX_HISTORY derniers messages."""
    if len(_sessions[session_id]) > MAX_HISTORY:
        _sessions[session_id] = _sessions[session_id][-MAX_HISTORY:]


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT OPENAI
# ─────────────────────────────────────────────────────────────────────────────

def _get_client():
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# CHAT STANDARD (réponse complète)
# ─────────────────────────────────────────────────────────────────────────────

async def chat(
    session_id: str,
    message: str,
    personality: str = "pedagogue",
) -> Dict:
    """
    Envoie un message et retourne la réponse complète.
    Maintient l'historique de la session.
    """
    personality_cfg = PERSONALITIES.get(personality, PERSONALITIES["pedagogue"])
    system_prompt = personality_cfg["system"]

    # Ajouter le message utilisateur à l'historique
    _sessions[session_id].append({"role": "user", "content": message})
    _trim_history(session_id)

    # Construire les messages pour l'API
    messages = [{"role": "system", "content": system_prompt}] + _sessions[session_id]

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
        )
        reply = response.choices[0].message.content

        # Sauvegarder la réponse dans l'historique
        _sessions[session_id].append({"role": "assistant", "content": reply})
        _trim_history(session_id)

        return {
            "reply": reply,
            "session_id": session_id,
            "history_length": len(_sessions[session_id]),
        }

    except Exception as e:
        logger.error(f"[Chatbot] Erreur LLM: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# CHAT STREAMING (SSE — Server-Sent Events)
# ─────────────────────────────────────────────────────────────────────────────

async def chat_stream(
    session_id: str,
    message: str,
    personality: str = "pedagogue",
) -> AsyncGenerator[str, None]:
    """
    Envoie un message et stream la réponse mot par mot (SSE).
    Yield des strings au format 'data: {...}\\n\\n'
    """
    personality_cfg = PERSONALITIES.get(personality, PERSONALITIES["pedagogue"])
    system_prompt = personality_cfg["system"]

    # Ajouter le message utilisateur
    _sessions[session_id].append({"role": "user", "content": message})
    _trim_history(session_id)

    messages = [{"role": "system", "content": system_prompt}] + _sessions[session_id]

    full_reply = ""

    try:
        client = _get_client()
        stream = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=messages,
            temperature=0.7,
            max_tokens=1500,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_reply += delta
                yield f"data: {json.dumps({'token': delta})}\n\n"

        # Sauvegarder la réponse complète dans l'historique
        _sessions[session_id].append({"role": "assistant", "content": full_reply})
        _trim_history(session_id)

        # Signal de fin
        yield f"data: {json.dumps({'done': True, 'history_length': len(_sessions[session_id])})}\n\n"

    except Exception as e:
        logger.error(f"[Chatbot] Erreur stream: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
