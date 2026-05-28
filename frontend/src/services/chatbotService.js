import axios from 'axios';

const BASE = 'http://localhost:8000/api/chatbot';

// ─────────────────────────────────────────────────────────────────────────────
// CHAT STANDARD
// ─────────────────────────────────────────────────────────────────────────────

export async function sendMessage({ message, sessionId, personality = 'pedagogue' }) {
  const res = await axios.post(`${BASE}/chat`, {
    message, session_id: sessionId, personality,
  });
  return res.data;
}

// ─────────────────────────────────────────────────────────────────────────────
// STREAM STANDARD
// ─────────────────────────────────────────────────────────────────────────────

export async function streamMessage({ message, sessionId, personality = 'pedagogue', onToken, onDone, onError }) {
  const response = await fetch(`${BASE}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, personality }),
  });
  if (!response.ok) { onError?.(await response.text()); return sessionId; }
  const returnedId = response.headers.get('X-Session-Id') || sessionId;
  await _readSSE(response, onToken, onDone, onError, returnedId);
  return returnedId;
}

// ─────────────────────────────────────────────────────────────────────────────
// STREAM AVEC CONTEXTE (AutoML / Migration)
// ─────────────────────────────────────────────────────────────────────────────

export async function streamWithContext({ message, context, sessionId, personality = 'expert', onToken, onDone, onError }) {
  const response = await fetch(`${BASE}/context-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, context, session_id: sessionId, personality }),
  });
  if (!response.ok) { onError?.(await response.text()); return sessionId; }
  const returnedId = response.headers.get('X-Session-Id') || sessionId;
  await _readSSE(response, onToken, onDone, onError, returnedId);
  return returnedId;
}

// ─────────────────────────────────────────────────────────────────────────────
// LECTURE SSE PARTAGÉE
// ─────────────────────────────────────────────────────────────────────────────

async function _readSSE(response, onToken, onDone, onError, sessionId) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      for (const line of text.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const data = JSON.parse(raw);
          if (data.error)      onError?.(data.error);
          else if (data.done)  onDone?.({ historyLength: data.history_length, sessionId });
          else if (data.token) onToken?.(data.token);
        } catch { /* ignore */ }
      }
    }
  } finally { reader.releaseLock(); }
}

// ─────────────────────────────────────────────────────────────────────────────
// SESSION
// ─────────────────────────────────────────────────────────────────────────────

export async function clearSession(sessionId) {
  const res = await axios.delete(`${BASE}/clear/${sessionId}`);
  return res.data;
}

export async function getSuggestions() {
  const res = await axios.get(`${BASE}/suggestions`);
  return res.data.suggestions;
}

export async function getPersonalities() {
  const res = await axios.get(`${BASE}/personalities`);
  return res.data.personalities;
}

// ─────────────────────────────────────────────────────────────────────────────
// PERSISTANCE LOCALSTORAGE
// ─────────────────────────────────────────────────────────────────────────────

const LS_CONVS = 'chatbot_conversations';

/** Retourne toutes les conversations sauvegardées */
export function loadConversations() {
  try {
    return JSON.parse(localStorage.getItem(LS_CONVS) || '{}');
  } catch { return {}; }
}

/** Sauvegarde toutes les conversations */
export function saveConversations(convs) {
  try { localStorage.setItem(LS_CONVS, JSON.stringify(convs)); } catch {}
}

/** Crée une nouvelle conversation */
export function createConversation(title = 'Nouvelle conversation') {
  const id = crypto.randomUUID();
  const conv = {
    id,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [],
    personality: 'pedagogue',
  };
  const convs = loadConversations();
  convs[id] = conv;
  saveConversations(convs);
  return conv;
}

/** Met à jour une conversation */
export function updateConversation(id, patch) {
  const convs = loadConversations();
  if (convs[id]) {
    convs[id] = { ...convs[id], ...patch, updatedAt: Date.now() };
    saveConversations(convs);
  }
  return convs[id];
}

/** Supprime une conversation */
export function deleteConversation(id) {
  const convs = loadConversations();
  delete convs[id];
  saveConversations(convs);
}

/** Retourne les conversations triées par date */
export function listConversations() {
  const convs = loadConversations();
  return Object.values(convs).sort((a, b) => b.updatedAt - a.updatedAt);
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT CONVERSATION
// ─────────────────────────────────────────────────────────────────────────────

/** Export en texte brut (.txt) */
export function exportAsText(messages, title = 'Conversation') {
  const lines = [
    `═══════════════════════════════════════`,
    `  ${title}`,
    `  Exporté le ${new Date().toLocaleString('fr-FR')}`,
    `═══════════════════════════════════════`,
    '',
  ];
  for (const msg of messages) {
    if (msg.role === 'user') {
      lines.push(`👤 Vous :`);
      lines.push(msg.content);
    } else if (msg.role === 'assistant') {
      lines.push(`🤖 Assistant :`);
      lines.push(msg.content);
      if (msg.rating) lines.push(`[Note : ${msg.rating === 'up' ? '👍' : '👎'}]`);
    }
    lines.push('─'.repeat(40));
    lines.push('');
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  _download(blob, `${title}_${_dateStr()}.txt`);
}

/** Export en HTML (affichage propre, imprimable comme PDF via Ctrl+P) */
export function exportAsHTML(messages, title = 'Conversation IA') {
  const rows = messages.map(msg => {
    if (msg.role === 'system') return '';
    const isBot = msg.role === 'assistant';
    const content = msg.content
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>');
    const rating = msg.rating ? `<span class="rating">${msg.rating === 'up' ? '👍' : '👎'}</span>` : '';
    return `
      <div class="msg ${isBot ? 'bot' : 'user'}">
        <div class="avatar">${isBot ? '🤖' : '👤'}</div>
        <div class="bubble">${content}${rating}</div>
      </div>`;
  }).join('');

  const html = `<!DOCTYPE html><html lang="fr"><head>
  <meta charset="UTF-8"><title>${title}</title>
  <style>
    body{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;padding:20px;background:#f5f5f5;color:#333}
    h1{color:#1a1a2e;border-bottom:3px solid #00d4aa;padding-bottom:10px}
    .meta{color:#666;font-size:13px;margin-bottom:30px}
    .msg{display:flex;gap:12px;margin:16px 0;align-items:flex-start}
    .msg.user{flex-direction:row-reverse}
    .avatar{font-size:24px;flex-shrink:0}
    .bubble{padding:12px 16px;border-radius:12px;max-width:80%;line-height:1.6;font-size:14px}
    .bot .bubble{background:#fff;border:1px solid #ddd;border-top-left-radius:4px}
    .user .bubble{background:#3d7fff;color:#fff;border-top-right-radius:4px}
    .rating{display:inline-block;margin-top:8px;font-size:16px}
    @media print{body{background:#fff}}
  </style></head><body>
  <h1>🤖 ${title}</h1>
  <p class="meta">Exporté le ${new Date().toLocaleString('fr-FR')} — ${messages.filter(m => m.role !== 'system').length} messages</p>
  ${rows}
  </body></html>`;

  const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
  _download(blob, `${title}_${_dateStr()}.html`);
}

function _dateStr() {
  return new Date().toISOString().slice(0, 10);
}
function _download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────────────────
// HELPERS CONTEXTE
// ─────────────────────────────────────────────────────────────────────────────

/** Formate le contexte AutoML pour l'injection dans le chatbot */
export function buildAutoMLContext(result) {
  if (!result) return '';
  const metrics = result.best_metrics || {};
  const metricsStr = Object.entries(metrics)
    .map(([k, v]) => `  - ${k}: ${typeof v === 'number' ? v.toFixed(4) : v}`)
    .join('\n');
  const models = (result.models_comparison || [])
    .map(m => `  - ${m.model}: ${JSON.stringify(m.metrics)}`)
    .join('\n');

  return [
    `=== Résultats Pipeline AutoML ===`,
    `Meilleur modèle : ${result.best_model || 'N/A'}`,
    `Statut : ${result.status || 'N/A'}`,
    ``,
    `Métriques du meilleur modèle :`,
    metricsStr || '  (aucune)',
    ``,
    `Modèles comparés :`,
    models || '  (aucun)',
    ``,
    result.conclusion ? `Conclusion de l'agent :\n${result.conclusion}` : '',
  ].join('\n');
}

/** Formate le contexte Migration pour l'injection dans le chatbot */
export function buildMigrationContext(res) {
  if (!res) return '';
  const mods = (res.modifications || [])
    .slice(0, 5)
    .map((m, i) => `  ${i + 1}. ${m.title} : ${m.explanation || ''}`)
    .join('\n');

  return [
    `=== Résultats Migration de Code ===`,
    `Langage : ${res.language || 'N/A'}`,
    `Score avant : ${res.score_before?.score ?? 'N/A'}/100 (${res.score_before?.grade ?? ''})`,
    `Score après : ${res.score_after?.score ?? 'N/A'}/100 (${res.score_after?.grade ?? ''})`,
    `Problèmes corrigés : ${res.improvement?.issues_fixed ?? 'N/A'}`,
    ``,
    `Résumé de la migration :`,
    res.summary || '(aucun)',
    ``,
    `Principales modifications effectuées :`,
    mods || '  (aucune)',
    ``,
    `Code original (extrait) :`,
    '```',
    (res.original_code || '').slice(0, 500),
    '```',
    `Code migré (extrait) :`,
    '```',
    (res.migrated_code || '').slice(0, 500),
    '```',
  ].join('\n');
}
