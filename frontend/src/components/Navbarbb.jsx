import { useLocation, useNavigate } from 'react-router-dom';
import { Cpu, GitMerge, Zap, Bot } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();
  const navigate = useNavigate();

  const isAutoML    = location.pathname.startsWith('/automl');
  const isMigration = location.pathname.startsWith('/migration');
  const isChatbot   = location.pathname.startsWith('/chatbot');
  const isHome      = location.pathname === '/';

  return (
    <nav className="navbar">
      {/* Logo */}
      <div
        className="navbar-logo"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate('/')}
      >
        <div className="logo-icon">
          <Zap size={16} color="white" strokeWidth={2.5} />
        </div>
        <span>AI Platform</span>
      </div>

      {/* Links */}
      <div className="navbar-links">
        <div
          className={`navbar-link ${isHome ? 'active' : ''}`}
          onClick={() => navigate('/')}
        >
          <span className="link-dot" />
          Home
        </div>

        <div
          className={`navbar-link ${isAutoML ? 'active' : ''}`}
          onClick={() => navigate('/automl')}
        >
          <Cpu size={14} />
          AutoML
        </div>

        <div
          className={`navbar-link ${isMigration ? 'active' : ''}`}
          onClick={() => navigate('/migration')}
        >
          <GitMerge size={14} />
          Migration
        </div>

        <div
          className={`navbar-link ${isChatbot ? 'active' : ''}`}
          onClick={() => navigate('/chatbot')}
        >
          <Bot size={14} />
          Chatbot IA
        </div>
      </div>

      {/* Right — version tag */}
      <div style={{
        fontSize: '11px',
        color: 'var(--text-muted)',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        padding: '3px 10px',
        borderRadius: '99px',
        fontFamily: 'var(--font-display)',
        letterSpacing: '0.04em',
      }}>
        v2.0 PFE
      </div>
    </nav>
  );
}
