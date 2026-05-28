import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  streamMessage, streamWithContext, clearSession, getSuggestions, getPersonalities,
  createConversation, updateConversation, deleteConversation, listConversations,
  exportAsText, exportAsHTML,
} from '../../services/chatbotService';
import './ChatbotPage.css';

// ─── Icônes ──────────────────────────────────────────────────────────────────
const Icon = ({ d, size = 16, fill = "none", sw = 2 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke="currentColor" strokeWidth={sw}>
    {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
  </svg>
);
const SendIcon   = () => <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>;
const BotIcon    = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><circle cx="8" cy="16" r="1" fill="currentColor"/><circle cx="16" cy="16" r="1" fill="currentColor"/></svg>;
const TrashIcon  = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M9 6V4h6v2"/></svg>;
const CopyIcon   = () => <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>;
const PlusIcon   = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const EditIcon   = () => <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>;
const MicIcon    = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>;
const MicOffIcon = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V4a3 3 0 00-5.94-.6"/><path d="M17 16.95A7 7 0 015 12v-2m14 0v2a7 7 0 01-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>;
const UploadIcon = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
const DownloadIcon = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;

// ─── Composant Message ────────────────────────────────────────────────────────
function Message({ msg, onRate }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`chat-message ${msg.role}`}>
      {msg.role === 'assistant' && <div className="msg-avatar bot-avatar"><BotIcon /></div>}
      <div className="msg-bubble">
        {msg.role === 'assistant' ? (
          <ReactMarkdown components={{
            code({ inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              return !inline && match ? (
                <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div"
                  customStyle={{ borderRadius: '8px', fontSize: '13px', margin: '8px 0' }} {...props}>
                  {String(children).replace(/\n$/, '')}
                </SyntaxHighlighter>
              ) : <code className="inline-code" {...props}>{children}</code>;
            },
          }}>{msg.content}</ReactMarkdown>
        ) : (
          <p>{msg.content}</p>
        )}

        {/* Barre d'actions */}
        {msg.role === 'assistant' && msg.content && !msg.streaming && (
          <div className="msg-actions">
            <button className="action-btn" onClick={handleCopy}>
              <CopyIcon /> {copied ? 'Copié !' : 'Copier'}
            </button>
            <div className="rating-btns">
              <button
                className={`rate-btn ${msg.rating === 'up' ? 'active-up' : ''}`}
                onClick={() => onRate(msg.id, msg.rating === 'up' ? null : 'up')}
                title="Bonne réponse"
              >👍</button>
              <button
                className={`rate-btn ${msg.rating === 'down' ? 'active-down' : ''}`}
                onClick={() => onRate(msg.id, msg.rating === 'down' ? null : 'down')}
                title="Mauvaise réponse"
              >👎</button>
            </div>
          </div>
        )}

        {msg.streaming && <span className="typing-cursor">▋</span>}
      </div>
      {msg.role === 'user' && (
        <div className="msg-avatar user-avatar">
          {msg.content[0]?.toUpperCase() || 'U'}
        </div>
      )}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="chat-message assistant">
      <div className="msg-avatar bot-avatar"><BotIcon /></div>
      <div className="msg-bubble typing-indicator"><span/><span/><span/></div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SIDEBAR — liste des conversations
// ─────────────────────────────────────────────────────────────────────────────
function ConvSidebar({ convs, activeId, onSelect, onCreate, onDelete, onRename }) {
  const [editId, setEditId]   = useState(null);
  const [editVal, setEditVal] = useState('');

  const startEdit = (conv, e) => {
    e.stopPropagation();
    setEditId(conv.id);
    setEditVal(conv.title);
  };
  const submitEdit = (id) => {
    if (editVal.trim()) onRename(id, editVal.trim());
    setEditId(null);
  };

  return (
    <aside className="conv-sidebar">
      <div className="conv-sidebar-header">
        <span className="conv-sidebar-title">Conversations</span>
        <button className="new-conv-btn" onClick={onCreate} title="Nouvelle conversation">
          <PlusIcon />
        </button>
      </div>
      <div className="conv-list">
        {convs.length === 0 && (
          <p className="conv-empty">Aucune conversation</p>
        )}
        {convs.map(conv => (
          <div
            key={conv.id}
            className={`conv-item ${conv.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(conv.id)}
          >
            <div className="conv-item-icon">💬</div>
            <div className="conv-item-body">
              {editId === conv.id ? (
                <input
                  className="conv-edit-input"
                  value={editVal}
                  onChange={e => setEditVal(e.target.value)}
                  onBlur={() => submitEdit(conv.id)}
                  onKeyDown={e => e.key === 'Enter' && submitEdit(conv.id)}
                  autoFocus
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <span className="conv-item-title">{conv.title}</span>
              )}
              <span className="conv-item-date">
                {new Date(conv.updatedAt).toLocaleDateString('fr-FR')}
              </span>
            </div>
            <div className="conv-item-actions">
              <button className="conv-action" onClick={(e) => startEdit(conv, e)} title="Renommer">
                <EditIcon />
              </button>
              <button className="conv-action del" onClick={(e) => { e.stopPropagation(); onDelete(conv.id); }} title="Supprimer">
                <TrashIcon />
              </button>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PAGE PRINCIPALE
// ─────────────────────────────────────────────────────────────────────────────
export default function ChatbotPage() {
  // ── Conversations ──────────────────────────────────────────────────────────
  const [convs, setConvs]           = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);

  // ── Messages ───────────────────────────────────────────────────────────────
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState('');
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState(null);

  // ── Paramètres ─────────────────────────────────────────────────────────────
  const [personality, setPersonality]   = useState('pedagogue');
  const [personalities, setPersonalities] = useState([]);
  const [suggestions, setSuggestions]   = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(true);

  // ── UI ─────────────────────────────────────────────────────────────────────
  const [sidebarOpen, setSidebarOpen]   = useState(true);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // ── Voix ───────────────────────────────────────────────────────────────────
  const [listening, setListening]   = useState(false);
  const recognitionRef              = useRef(null);

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);
  const fileInputRef   = useRef(null);

  // ── Init ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    getSuggestions().then(setSuggestions).catch(() => {});
    getPersonalities().then(setPersonalities).catch(() => {});

    // Charger conversations depuis localStorage
    const saved = listConversations();
    let currentConvId;
    if (saved.length > 0) {
      setConvs(saved);
      setActiveConvId(saved[0].id);
      currentConvId = saved[0].id;
      setMessages(saved[0].messages || []);
      setPersonality(saved[0].personality || 'pedagogue');
      setShowSuggestions((saved[0].messages || []).length === 0);
    } else {
      const first = createConversation('Première conversation');
      setConvs([first]);
      setActiveConvId(first.id);
      currentConvId = first.id;
    }

    // Vérifier si on vient d'AutoML ou Migration avec un contexte
    const ctxFromExternal = sessionStorage.getItem('chatbot_context');
    const questionFromExternal = sessionStorage.getItem('chatbot_question');
    if (ctxFromExternal && questionFromExternal) {
      sessionStorage.removeItem('chatbot_context');
      sessionStorage.removeItem('chatbot_question');
      // Créer une nouvelle conversation pour ce contexte
      const ctxConv = createConversation('Analyse IA 🔗');
      setConvs(listConversations());
      setActiveConvId(ctxConv.id);
      setMessages([]);
      setPersonality('expert');
      setShowSuggestions(false);
      // Lancer le message avec contexte après un court délai
      setTimeout(() => {
        sendContextMessage(ctxConv.id, questionFromExternal, ctxFromExternal);
      }, 300);
    }
  }, []);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Sauvegarder messages quand ils changent ────────────────────────────────
  useEffect(() => {
    if (!activeConvId || messages.some(m => m.streaming)) return;
    updateConversation(activeConvId, { messages, personality });
    setConvs(listConversations());
  }, [messages, activeConvId]);

  // ── Changer de conversation ────────────────────────────────────────────────
  const selectConv = (id) => {
    const saved = listConversations();
    const conv = saved.find(c => c.id === id);
    if (!conv) return;
    setActiveConvId(id);
    setMessages(conv.messages || []);
    setPersonality(conv.personality || 'pedagogue');
    setShowSuggestions((conv.messages || []).length === 0);
    setError(null);
  };

  const newConv = () => {
    const conv = createConversation('Nouvelle conversation');
    setConvs(listConversations());
    setActiveConvId(conv.id);
    setMessages([]);
    setShowSuggestions(true);
    setError(null);
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  const deleteConv = (id) => {
    deleteConversation(id);
    const remaining = listConversations();
    setConvs(remaining);
    if (id === activeConvId) {
      if (remaining.length > 0) {
        selectConv(remaining[0].id);
      } else {
        const fresh = createConversation('Nouvelle conversation');
        setConvs(listConversations());
        setActiveConvId(fresh.id);
        setMessages([]);
        setShowSuggestions(true);
      }
    }
  };

  const renameConv = (id, title) => {
    updateConversation(id, { title });
    setConvs(listConversations());
  };

  // ── Message avec contexte externe (AutoML / Migration) ────────────────────
  const sendContextMessage = useCallback(async (convId, question, context) => {
    setShowSuggestions(false);
    const userMsg = { id: Date.now(), role: 'user', content: question };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const assistantId = Date.now() + 1;
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true }]);

    let accumulated = '';
    try {
      await streamWithContext({
        message: question,
        context,
        sessionId: convId,
        personality: 'expert',
        onToken: (token) => {
          accumulated += token;
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: accumulated, streaming: true } : m
          ));
        },
        onDone: () => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false } : m
          ));
        },
        onError: (err) => {
          setError(`Erreur : ${err}`);
          setMessages(prev => prev.filter(m => m.id !== assistantId));
        },
      });
    } catch (err) {
      setError(`Erreur : ${err.message}`);
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Rating ─────────────────────────────────────────────────────────────────
  const handleRate = useCallback((msgId, rating) => {
    setMessages(prev => prev.map(m => m.id === msgId ? { ...m, rating } : m));
  }, []);

  // ── Envoi message ──────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    const trimmed = (text ?? input).trim();
    if (!trimmed || loading) return;

    setError(null);
    setInput('');
    setShowSuggestions(false);

    // Auto-renommer la conversation à partir du premier message
    if (messages.length === 0 && activeConvId) {
      const title = trimmed.slice(0, 40) + (trimmed.length > 40 ? '…' : '');
      updateConversation(activeConvId, { title });
      setConvs(listConversations());
    }

    const userMsg = { id: Date.now(), role: 'user', content: trimmed };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const assistantId = Date.now() + 1;
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', streaming: true }]);

    let accumulated = '';
    try {
      await streamMessage({
        message: trimmed,
        sessionId: activeConvId,
        personality,
        onToken: (token) => {
          accumulated += token;
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, content: accumulated, streaming: true } : m
          ));
        },
        onDone: () => {
          setMessages(prev => prev.map(m =>
            m.id === assistantId ? { ...m, streaming: false } : m
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
  }, [input, loading, activeConvId, personality, messages.length]);

  // ── Effacer ────────────────────────────────────────────────────────────────
  const handleClear = async () => {
    try { await clearSession(activeConvId); } catch {}
    setMessages([]);
    updateConversation(activeConvId, { messages: [] });
    setConvs(listConversations());
    setShowSuggestions(true);
    setError(null);
  };

  // ── Voix (Speech-to-Text) ──────────────────────────────────────────────────
  const toggleVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Votre navigateur ne supporte pas la reconnaissance vocale."); return; }

    if (listening) {
      recognitionRef.current?.stop();
      setListening(false);
      return;
    }

    const rec = new SR();
    rec.lang = 'fr-FR';
    rec.continuous = false;
    rec.interimResults = true;
    recognitionRef.current = rec;

    rec.onresult = (e) => {
      const transcript = Array.from(e.results).map(r => r[0].transcript).join('');
      setInput(transcript);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);

    rec.start();
    setListening(true);
  };

  // ── Upload fichier de code ─────────────────────────────────────────────────
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = ev.target.result;
      const ext = file.name.split('.').pop();
      const msg = `Voici le contenu du fichier \`${file.name}\`:\n\`\`\`${ext}\n${content.slice(0, 3000)}\n\`\`\`\n\nPeux-tu analyser ce code et m'expliquer ce qu'il fait ?`;
      setInput(msg);
      inputRef.current?.focus();
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  // ── Export ─────────────────────────────────────────────────────────────────
  const currentConv = convs.find(c => c.id === activeConvId);
  const convTitle = currentConv?.title || 'Conversation IA';

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const currentPersonality = personalities.find(p => p.key === personality);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="chatbot-page">

      {/* ── SIDEBAR CONVERSATIONS ── */}
      {sidebarOpen && (
        <ConvSidebar
          convs={convs}
          activeId={activeConvId}
          onSelect={selectConv}
          onCreate={newConv}
          onDelete={deleteConv}
          onRename={renameConv}
        />
      )}

      {/* ── ZONE PRINCIPALE ── */}
      <div className="chatbot-main">

        {/* Header */}
        <div className="chatbot-header">
          <div className="chatbot-header-left">
            <button className="sidebar-toggle" onClick={() => setSidebarOpen(v => !v)} title="Conversations">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            </button>
            <div className="chatbot-logo"><BotIcon /></div>
            <div>
              <h1 className="chatbot-title">Assistant IA {currentPersonality?.emoji}</h1>
              <p className="chatbot-subtitle">Intelligence Artificielle · Machine Learning · Algorithmes</p>
            </div>
          </div>

          <div className="chatbot-header-right">
            {/* Personnalités */}
            <div className="personality-selector">
              {personalities.map(p => (
                <button
                  key={p.key}
                  className={`personality-btn ${personality === p.key ? 'active' : ''}`}
                  onClick={() => { setPersonality(p.key); updateConversation(activeConvId, { personality: p.key }); }}
                  title={p.description}
                >
                  <span>{p.emoji}</span>
                  <span>{p.label}</span>
                </button>
              ))}
            </div>

            {/* Export */}
            {messages.length > 0 && (
              <div className="export-wrapper">
                <button
                  className="header-btn"
                  onClick={() => setShowExportMenu(v => !v)}
                  title="Exporter la conversation"
                >
                  <DownloadIcon /> Exporter
                </button>
                {showExportMenu && (
                  <div className="export-menu" onMouseLeave={() => setShowExportMenu(false)}>
                    <button onClick={() => { exportAsText(messages, convTitle); setShowExportMenu(false); }}>
                      📄 Texte (.txt)
                    </button>
                    <button onClick={() => { exportAsHTML(messages, convTitle); setShowExportMenu(false); }}>
                      🌐 HTML / PDF
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Effacer */}
            {messages.length > 0 && (
              <button className="header-btn danger" onClick={handleClear}>
                <TrashIcon /> Effacer
              </button>
            )}
          </div>
        </div>

        {/* Zone messages */}
        <div className="chatbot-messages">
          {messages.length === 0 && showSuggestions && (
            <div className="chatbot-welcome">
              <div className="welcome-icon">🤖</div>
              <h2 className="welcome-title">Bonjour ! Je suis votre assistant IA</h2>
              <p className="welcome-subtitle">
                Posez-moi des questions sur l'IA, le ML, les algorithmes, ou uploadez du code à analyser.
              </p>
              <div className="suggestions-grid">
                {suggestions.slice(0, 8).map((s, i) => (
                  <button key={i} className="suggestion-chip" onClick={() => sendMessage(s.text)}>
                    <span>{s.icon}</span><span>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <Message key={msg.id} msg={msg} onRate={handleRate} />
          ))}

          {loading && messages[messages.length - 1]?.content === '' && <TypingIndicator />}

          {error && <div className="chat-error">⚠️ {error}</div>}

          <div ref={messagesEndRef} />
        </div>

        {/* Zone saisie */}
        <div className="chatbot-input-zone">
          {messages.length > 0 && suggestions.length > 0 && (
            <div className="quick-suggestions">
              {suggestions.slice(0, 4).map((s, i) => (
                <button key={i} className="quick-chip" onClick={() => sendMessage(s.text)} disabled={loading}>
                  {s.icon} {s.text}
                </button>
              ))}
            </div>
          )}

          <div className="input-row">
            {/* Upload fichier */}
            <button
              className="input-action-btn"
              onClick={() => fileInputRef.current?.click()}
              title="Uploader un fichier de code"
              disabled={loading}
            >
              <UploadIcon />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".py,.java,.js,.ts,.jsx,.tsx,.txt,.json,.yaml,.yml,.cpp,.c,.cs,.go,.rs"
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />

            <textarea
              ref={inputRef}
              className="chat-input"
              placeholder="Posez votre question sur l'IA, ou uploadez un fichier de code..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={loading}
            />

            {/* Voix */}
            <button
              className={`input-action-btn ${listening ? 'listening' : ''}`}
              onClick={toggleVoice}
              title={listening ? 'Arrêter la saisie vocale' : 'Saisie vocale'}
              disabled={loading}
            >
              {listening ? <MicOffIcon /> : <MicIcon />}
            </button>

            {/* Envoyer */}
            <button
              className={`send-btn ${(!input.trim() || loading) ? 'disabled' : ''}`}
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
            >
              {loading ? <span className="send-spinner" /> : <SendIcon />}
            </button>
          </div>

          <p className="input-hint">
            Entrée pour envoyer · Shift+Entrée pour un saut de ligne ·
            {' '}<kbd>📎</kbd> code · <kbd>🎙️</kbd> voix
          </p>
        </div>
      </div>
    </div>
  );
}
