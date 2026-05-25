import axios from 'axios';

const BASE = 'http://localhost:8000/api/chatbot';

/**
 * Envoie un message et retourne la réponse complète.
 */
export async function sendMessage({ message, sessionId, personality = 'pedagogue' }) {
  const res = await axios.post(`${BASE}/chat`, {
    message,
    session_id: sessionId,
    personality,
  });
  return res.data; // { reply, session_id, history_length }
}

/**
 * Stream une réponse token par token via SSE.
 * onToken(token) appelé à chaque token reçu.
 * onDone({ historyLength }) appelé à la fin.
 * onError(err) appelé en cas d'erreur.
 * Retourne la sessionId utilisée.
 */
export async function streamMessage({ message, sessionId, personality = 'pedagogue', onToken, onDone, onError }) {
  const response = await fetch(`${BASE}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      personality,
    }),
  });

  if (!response.ok) {
    const err = await response.text();
    onError?.(err);
    return sessionId;
  }

  // Récupérer la session ID depuis les headers
  const returnedSessionId = response.headers.get('X-Session-Id') || sessionId;

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value, { stream: true });
      const lines = text.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        try {
          const data = JSON.parse(raw);
          if (data.error) {
            onError?.(data.error);
          } else if (data.done) {
            onDone?.({ historyLength: data.history_length, sessionId: returnedSessionId });
          } else if (data.token) {
            onToken?.(data.token);
          }
        } catch {
          // ignore parse errors
        }
      }
    }
  } finally {
    reader.releaseLock();
  }

  return returnedSessionId;
}

/**
 * Efface l'historique d'une session.
 */
export async function clearSession(sessionId) {
  const res = await axios.delete(`${BASE}/clear/${sessionId}`);
  return res.data;
}

/**
 * Récupère les suggestions de questions.
 */
export async function getSuggestions() {
  const res = await axios.get(`${BASE}/suggestions`);
  return res.data.suggestions;
}

/**
 * Récupère les personnalités disponibles.
 */
export async function getPersonalities() {
  const res = await axios.get(`${BASE}/personalities`);
  return res.data.personalities;
}
