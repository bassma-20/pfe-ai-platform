import { useState, useEffect, useRef, useCallback } from 'react';
import { streamMessage, clearSession, getSuggestions, getPersonalities } from '../../services/chatbotService';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './ChatbotPage.css';

// ─── Icônes SVG inline ───────────────────────────────────────────────────────
const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
const TrashIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6m4-6v6"/>
    <path d="M9 6V4h6v2"/>
  </svg>
);
const CopyIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
  </svg>
);
const BotIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/>
    <path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>
    <circle cx="8" cy="16" r="1" fill="currentColor"/><circle cx="16" cy="16" r="1" fill="currentColor"/>
  </svg>
);

// ─── Composant Message ───────────────────────────────────────────────────────
function Message({ msg }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`chat-message ${msg.role}`}>
      {msg.role === 'assistant' && (
        <div className="msg-avatar bot-avatar">
          <BotIcon />
        </div>
      )}
      <div className="msg-bubble">
        {msg.role === 'assistant' ? (
          <ReactMarkdown
            components={{
              code({ node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{ borderRadius: '8px', fontSize: '13px', margin: '8px 0' }}
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className="inline-code" {...props}>{children}</code>
                );
              },
            }}
          >
            {msg.content}
          </ReactMarkdown>
        ) : (
          <p>{msg.content}</p>
        )}

        {msg.role === 'assistant' && msg.content && !msg.streaming && (
          <button className="copy-btn" onClick={handleCopy} title="Copier">
            <CopyIcon /> {copied ? 'Copié !' : 'Copier'}
          </button>
        )}

        {msg.streaming && (
          <span className="typing-cursor">▋</span>
        )}
      </div>
      {msg.role === 'user' && (
        <div className="msg-avatar user-avatar">
          {msg.content[0]?.toUpperCase() || 'U'}
        </div>
      )}
    </div>
  );
}

// ─── Composant Typing indicator ──────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="chat-message assistant">
      <div className="msg-avatar bot-avatar"><BotIcon /></div>
      <div className="msg-bubble typing-indicator">
        <span/><span/><span/>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PAGE PRINCIPALE
// ─────────────────────────────────────────────────────────────────────────────
export default function ChatbotPage() {
  const [messages, setMessages]       = useState([]);
  const [input, setInput]             = useState('');
  const [loading, setLoading]         = useState(false);
  const [sessionId, setSessionId]     = useState(() => crypto.randomUUID());
  const [personality, setPersonality] = useState('pedagogue');
  const [personalities, setPersonalities] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [error, setError]             = useState(null);

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  // Charger les données initiales
  useEffect(() => {
    getSuggestions().then(setSuggestions).catch(() => {});
    getPersonalities().then(setPersonalities).catch(() => {});
    inputRef.current?.focus();
  }, []);

  // Auto-scroll vers le bas
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Envoi du message ─────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    const trimmed = text?.trim() || input.trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput('');
    setShowSuggestions(false);

    // Ajouter le message utilisateur
    const userMsg = { id: Date.now(), role: 'user', content: trimmed };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    // Préparer le message assistant (streaming)
    const assistantId = Date.now() + 1;
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      streaming: true,
    }]);

    try {
      let accumulated = '';

      await streamMessage({
        message: trimmed,
        sessionId,
        personality,
        onToken: (token) => {
          accumulated += token;
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, content: accumulated, streaming: true }
              : m
          ));
        },
        onDone: ({ sessionId: newSessionId }) => {
          if (newSessionId && newSessionId !== sessionId) {
            setSessionId(newSessionId);
          }
          setMessages(prev => prev.map(m =>
            m.id === assistantId
              ? { ...m, streaming: false }
              : m
          ));
        },
        onError: (err) => {
          setError(`Erreur : ${err}`);
          setMessages(prev => prev.filter(m => m.id !== assistantId));
        },
      });
    } catch (err) {
      setError(`Erreur de connexion : ${err.message}`);
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }, [input, loading, sessionId, personality]);

  // ── Effacer la conversation ──────────────────────────────────────────────
  const handleClear = async () => {
    try {
      await clearSession(sessionId);
    } catch {}
    setMessages([]);
    setShowSuggestions(true);
    setError(null);
    inputRef.current?.focus();
  };

  // ── Touche Entrée ────────────────────────────────────────────────────────
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const currentPersonality = personalities.find(p => p.key === personality);

  return (
    <div className="chatbot-page">

      {/* ── HEADER ── */}
      <div className="chatbot-header">
        <div className="chatbot-header-left">
          <div className="chatbot-logo">
            <BotIcon />
          </div>
          <div>
            <h1 className="chatbot-title">Assistant IA</h1>
            <p className="chatbot-subtitle">
              Posez vos questions sur l'intelligence artificielle
            </p>
          </div>
        </div>

        <div className="chatbot-header-right">
          {/* Sélecteur de personnalité */}
          <div className="personality-selector">
            {personalities.map(p => (
              <button
                key={p.key}
                className={`personality-btn ${personality === p.key ? 'active' : ''}`}
                onClick={() => setPersonality(p.key)}
                title={p.description}
              >
                <span>{p.emoji}</span>
                <span>{p.label}</span>
              </button>
            ))}
          </div>

          {/* Bouton effacer */}
          {messages.length > 0 && (
            <button className="clear-btn" onClick={handleClear} title="Effacer la conversation">
              <TrashIcon /> Effacer
            </button>
          )}
        </div>
      </div>

      {/* ── ZONE DE MESSAGES ── */}
      <div className="chatbot-messages">

        {/* État vide — suggestions */}
        {messages.length === 0 && showSuggestions && (
          <div className="chatbot-welcome">
            <div className="welcome-icon">🤖</div>
            <h2 className="welcome-title">
              Bonjour ! Je suis votre assistant IA {currentPersonality?.emoji}
            </h2>
            <p className="welcome-subtitle">
              Posez-moi n'importe quelle question sur l'intelligence artificielle,
              le machine learning, les algorithmes, ou les concepts IA.
            </p>

            <div className="suggestions-grid">
              {suggestions.slice(0, 8).map((s, i) => (
                <button
                  key={i}
                  className="suggestion-chip"
                  onClick={() => sendMessage(s.text)}
                >
                  <span>{s.icon}</span>
                  <span>{s.text}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map(msg => (
          <Message key={msg.id} msg={msg} />
        ))}

        {/* Typing indicator (avant le streaming) */}
        {loading && messages[messages.length - 1]?.content === '' && (
          <TypingIndicator />
        )}

        {/* Erreur */}
        {error && (
          <div className="chat-error">
            ⚠️ {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── ZONE DE SAISIE ── */}
      <div className="chatbot-input-zone">
        {/* Suggestions rapides (après messages) */}
        {messages.length > 0 && suggestions.length > 0 && (
          <div className="quick-suggestions">
            {suggestions.slice(0, 4).map((s, i) => (
              <button
                key={i}
                className="quick-chip"
                onClick={() => sendMessage(s.text)}
                disabled={loading}
              >
                {s.icon} {s.text}
              </button>
            ))}
          </div>
        )}

        <div className="input-row">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Posez votre question sur l'IA..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button
            className={`send-btn ${(!input.trim() || loading) ? 'disabled' : ''}`}
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading}
          >
            {loading ? (
              <span className="send-spinner" />
            ) : (
              <SendIcon />
            )}
          </button>
        </div>
        <p className="input-hint">
          Entrée pour envoyer · Shift+Entrée pour un retour à la ligne
        </p>
      </div>

    </div>
  );
}
