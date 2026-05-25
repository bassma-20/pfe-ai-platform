import { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { streamMessage, clearSession } from '../services/chatbotService';
import './ChatBubble.css';

const BotIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="11" width="18" height="10" rx="2"/>
    <circle cx="12" cy="5" r="2"/>
    <path d="M12 7v4"/>
    <circle cx="8" cy="16" r="1" fill="currentColor"/>
    <circle cx="16" cy="16" r="1" fill="currentColor"/>
  </svg>
);
const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
);
const SendIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);
const ExpandIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
  </svg>
);

// Messages de bienvenue tournants
const WELCOME_MSGS = [
  "Bonjour ! 👋 Une question sur l'IA ?",
  "Besoin d'aide avec le ML ? 🤖",
  "Posez-moi vos questions IA ! 🧠",
];

export default function ChatBubble() {
  const [open, setOpen]           = useState(false);
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const [sessionId]               = useState(() => 'bubble-' + crypto.randomUUID());
  const [hasUnread, setHasUnread] = useState(false);
  const [welcomeIdx]              = useState(() => Math.floor(Math.random() * WELCOME_MSGS.length));

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  useEffect(() => {
    if (open) {
      setHasUnread(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMsg = useCallback(async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setInput('');
    const userMsg = { id: Date.now(), role: 'user', content: trimmed };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const assistantId = Date.now() + 1;
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true }]);

    let accumulated = '';

    try {
      await streamMessage({
        message: trimmed,
        sessionId,
        personality: 'pedagogue',
        onToken: (token) => {
          accumulated += token;
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: accumulated } : m
          ));
        },
        onDone: () => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false } : m
          ));
          if (!open) setHasUnread(true);
        },
        onError: () => {
          setMessages(prev => prev.filter(m => m.id !== assistantId));
        },
      });
    } catch {
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, open]);

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  };

  const handleClear = async () => {
    try { await clearSession(sessionId); } catch {}
    setMessages([]);
  };

  return (
    <>
      {/* ── BULLE FLOTTANTE ── */}
      <button
        className={`chat-bubble-btn ${open ? 'open' : ''}`}
        onClick={() => setOpen(v => !v)}
        aria-label="Ouvrir l'assistant IA"
      >
        {open ? <CloseIcon /> : <BotIcon />}
        {!open && hasUnread && <span className="unread-dot" />}
      </button>

      {/* ── TOOLTIP ── */}
      {!open && (
        <div className="bubble-tooltip">{WELCOME_MSGS[welcomeIdx]}</div>
      )}

      {/* ── PANNEAU CHAT ── */}
      {open && (
        <div className="bubble-panel">
          {/* Header */}
          <div className="bubble-header">
            <div className="bubble-header-left">
              <div className="bubble-avatar"><BotIcon /></div>
              <div>
                <span className="bubble-title">Assistant IA</span>
                <span className="bubble-status">
                  <span className="status-dot" />
                  En ligne
                </span>
              </div>
            </div>
            <div className="bubble-header-actions">
              {messages.length > 0 && (
                <button className="bubble-clear" onClick={handleClear} title="Effacer">
                  🗑️
                </button>
              )}
              <a href="/chatbot" className="bubble-expand" title="Ouvrir en plein écran">
                <ExpandIcon />
              </a>
              <button className="bubble-close" onClick={() => setOpen(false)}>
                <CloseIcon />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="bubble-messages">
            {messages.length === 0 && (
              <div className="bubble-empty">
                <span>🤖</span>
                <p>Bonjour ! Posez-moi une question sur l'IA, le ML ou les algorithmes.</p>
              </div>
            )}

            {messages.map(msg => (
              <div key={msg.id} className={`bubble-msg ${msg.role}`}>
                <div className="bubble-msg-content">
                  {msg.role === 'assistant' ? (
                    <>
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                      {msg.streaming && <span className="bubble-cursor">▋</span>}
                    </>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {loading && messages[messages.length - 1]?.content === '' && (
              <div className="bubble-msg assistant">
                <div className="bubble-msg-content bubble-typing">
                  <span/><span/><span/>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="bubble-input-row">
            <input
              ref={inputRef}
              className="bubble-input"
              placeholder="Votre question..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              disabled={loading}
            />
            <button
              className={`bubble-send ${(!input.trim() || loading) ? 'off' : ''}`}
              onClick={sendMsg}
              disabled={!input.trim() || loading}
            >
              {loading ? <span className="bubble-spinner" /> : <SendIcon />}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
