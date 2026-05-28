import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, Play, Download, GitMerge, CheckCircle, AlertCircle,
  AlertTriangle, ArrowRight, Clock, FileText, Zap, Shield,
  TrendingUp, Code, ChevronDown, ChevronUp, History, Copy, Check,
  Brain, Users, RefreshCw, Bot,
} from 'lucide-react';
import {
  uploadFile,
  migrateFile,
  migrateFileAgent,
  migrateFileMultiAgent,
  downloadMigratedFile,
  getMigrationHistory,
  getDownloadUrl,
} from '../../services/migrationService';
import { buildMigrationContext } from '../../services/chatbotService';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const JAVA_VERSIONS = ['8', '11', '17', '21'];
const PYTHON_VERSIONS = ['3.8', '3.10', '3.12'];

const JAVA_VERSION_FEATURES = {
  '8':  'Lambdas, Stream API, Optional, java.time',
  '11': 'var, String.strip(), HTTP Client',
  '17': 'Records, Sealed classes, Pattern matching, Text blocks',
  '21': 'Virtual threads, Record patterns, Switch patterns',
};

const PYTHON_VERSION_FEATURES = {
  '3.8':  'Walrus operator :=, f-strings, typing, pathlib, dataclasses',
  '3.10': 'match/case, parenthesized context managers, better errors',
  '3.12': 'type aliases, @override, improved f-strings, better perf',
};

const LANG_ICON = { java: '☕', python: '🐍' };
const LANG_LABEL = { java: 'Java', python: 'Python' };

const AGENT_MODES = [
  {
    id: 'standard',
    label: 'Standard',
    icon: Zap,
    color: 'var(--accent)',
    description: 'Migration LLM directe — rapide et efficace',
  },
  {
    id: 'reflection',
    label: 'Réflexion',
    icon: RefreshCw,
    color: 'var(--teal)',
    description: "L'agent analyse et se corrige jusqu'à 3 fois",
  },
  {
    id: 'multi_agent',
    label: 'Multi-Agents',
    icon: Users,
    color: '#a78bfa',
    description: 'Analyste + Migrateur + Vérificateur coordonnés',
  },
];

const SEVERITY_COLOR = {
  critical: { bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)',   text: '#fca5a5', dot: '#ef4444' },
  high:     { bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)',  text: '#fcd34d', dot: '#f59e0b' },
  medium:   { bg: 'rgba(61,127,255,0.1)',  border: 'rgba(61,127,255,0.25)', text: '#93b4ff', dot: '#3d7fff' },
  low:      { bg: 'rgba(34,197,94,0.08)',  border: 'rgba(34,197,94,0.2)',   text: '#86efac', dot: '#22c55e' },
};

const GRADE_COLOR = { A: '#22c55e', B: '#3d7fff', C: '#f59e0b', D: '#f97316', F: '#ef4444' };

const AGENT_COLOR = {
  AnalyzerAgent:    { bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.25)', text: '#c4b5fd', dot: '#a78bfa' },
  MigratorAgent:    { bg: 'rgba(61,127,255,0.1)',  border: 'rgba(61,127,255,0.25)', text: '#93b4ff', dot: '#3d7fff' },
  VerifierAgent:    { bg: 'rgba(0,212,170,0.1)',   border: 'rgba(0,212,170,0.25)',  text: '#5eead4', dot: '#00d4aa' },
  Orchestrateur:    { bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)', text: '#fcd34d', dot: '#f59e0b' },
  default:          { bg: 'rgba(99,102,241,0.1)',  border: 'rgba(99,102,241,0.25)', text: '#a5b4fc', dot: '#6366f1' },
};

// ─── Composants réutilisables ─────────────────────────────────────────────────

function SeverityBadge({ severity }) {
  const c = SEVERITY_COLOR[severity] || SEVERITY_COLOR.low;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 9px', borderRadius: 99, fontSize: 11, fontWeight: 700,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      fontFamily: 'var(--font-display)', letterSpacing: '0.04em', textTransform: 'uppercase',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.dot, flexShrink: 0 }} />
      {severity}
    </span>
  );
}

function ScoreRing({ score, grade, label }) {
  const color = GRADE_COLOR[grade] || 'var(--accent)';
  const r = 36, circ = 2 * Math.PI * r;
  const filled = (score / 100) * circ;
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ position: 'relative', width: 96, height: 96, margin: '0 auto 8px' }}>
        <svg width="96" height="96" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="48" cy="48" r={r} fill="none" stroke="var(--bg-elevated)" strokeWidth="7" />
          <circle cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="7"
            strokeDasharray={`${filled} ${circ}`} strokeLinecap="round"
            style={{ transition: 'stroke-dasharray 0.8s cubic-bezier(0.4,0,0.2,1)' }}
          />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--font-display)', color, lineHeight: 1 }}>{score}</span>
          <span style={{ fontSize: 16, fontWeight: 700, color }}>{grade}</span>
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>{label}</div>
    </div>
  );
}

function IssueRow({ issue }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '60px 1fr auto',
      gap: 12, padding: '12px 0', borderBottom: '1px solid var(--border)', alignItems: 'start',
    }}>
      <div>
        <span style={{ fontSize: 11, fontFamily: 'monospace', color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4 }}>
          {issue.code}
        </span>
      </div>
      <div>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3 }}>{issue.title}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{issue.description}</div>
        <div style={{ fontSize: 12, color: 'var(--teal)', marginTop: 4 }}>→ {issue.suggestion}</div>
        {issue.line > 0 && (
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>Ligne {issue.line}</div>
        )}
      </div>
      <SeverityBadge severity={issue.severity} />
    </div>
  );
}

function CodeDiff({ before, after, title, explanation }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', overflow: 'hidden', marginBottom: 8 }}>
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--bg-elevated)', cursor: 'pointer' }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontWeight: 600, fontSize: 13 }}>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{explanation?.slice(0, 60)}{explanation?.length > 60 ? '…' : ''}</span>
          {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </div>
      {open && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
          <div style={{ padding: 12, background: 'rgba(239,68,68,0.04)', borderRight: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: '#fca5a5', marginBottom: 6, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Avant</div>
            <pre style={{ fontSize: 12, color: '#fca5a5', fontFamily: 'monospace', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{before}</pre>
          </div>
          <div style={{ padding: 12, background: 'rgba(34,197,94,0.04)' }}>
            <div style={{ fontSize: 10, color: '#86efac', marginBottom: 6, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Après</div>
            <pre style={{ fontSize: 12, color: '#86efac', fontFamily: 'monospace', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>{after}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

function HighlightedCode({ code, language, maxHeight = 320 }) {
  const ref = useRef(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (ref.current && window.hljs) {
      ref.current.removeAttribute('data-highlighted');
      window.hljs.highlightElement(ref.current);
    }
  }, [code, language]);

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={handleCopy}
        title="Copier le code"
        style={{
          position: 'absolute', top: 8, right: 8, zIndex: 2,
          background: 'var(--bg-elevated)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '4px 8px', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 4,
          fontSize: 11, color: copied ? 'var(--teal)' : 'var(--text-muted)',
          transition: 'color 0.2s',
        }}
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? 'Copié !' : 'Copier'}
      </button>
      <pre style={{ maxHeight, overflow: 'auto', margin: 0, borderRadius: 'var(--radius)', fontSize: 13 }}>
        <code ref={ref} className={`language-${language}`} style={{ fontFamily: 'monospace' }}>
          {code}
        </code>
      </pre>
    </div>
  );
}

function MetricsGrid({ before, after, language }) {
  const m = before?.metrics || {};
  const ma = after?.metrics || {};

  const javaItems = [
    { label: 'Lignes de code', key: 'code_lines', icon: '📄' },
    { label: 'Classes',        key: 'class_count', icon: '🧱' },
    { label: 'Méthodes',       key: 'method_count', icon: '🔧' },
    { label: 'Imports',        key: 'import_count', icon: '📦' },
    { label: 'Try/catch',      key: 'try_catch_count', icon: '🛡️' },
    { label: 'Boucles for',    key: 'for_loop_count', icon: '🔁' },
    { label: 'Null checks',    key: 'null_checks', icon: '❓' },
  ];

  const javaFlags = [
    { label: 'Lambdas',   key: 'has_lambda' },
    { label: 'Streams',   key: 'has_streams' },
    { label: 'Optional',  key: 'has_optional' },
    { label: 'Generics',  key: 'has_generics' },
    { label: 'Records',   key: 'has_records' },
  ];

  const pythonItems = [
    { label: 'Lignes de code',      key: 'code_lines', icon: '📄' },
    { label: 'Classes',             key: 'class_count', icon: '🧱' },
    { label: 'Fonctions',           key: 'function_count', icon: '🔧' },
    { label: 'Imports',             key: 'import_count', icon: '📦' },
    { label: 'Try/except',          key: 'try_except_count', icon: '🛡️' },
    { label: 'Boucles for',         key: 'for_loop_count', icon: '🔁' },
    { label: 'List comprehensions', key: 'list_comprehension_count', icon: '📝' },
  ];

  const pythonFlags = [
    { label: 'Type hints',  key: 'has_type_hints' },
    { label: 'Dataclasses', key: 'has_dataclasses' },
    { label: 'Async/await', key: 'has_async' },
    { label: 'F-strings',   key: 'has_fstrings' },
    { label: 'Walrus :=',   key: 'has_walrus' },
  ];

  const items = language === 'python' ? pythonItems : javaItems;
  const flags = language === 'python' ? pythonFlags : javaFlags;

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        {items.map(({ label, key, icon }) => {
          const valB = m[key] ?? '–';
          const valA = ma[key] ?? '–';
          const changed = valB !== valA && valA !== '–';
          return (
            <div key={key} style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', padding: '10px 12px', border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{icon} {label}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ fontWeight: 700, fontSize: 18, fontFamily: 'var(--font-display)' }}>{valB}</span>
                {changed && (
                  <>
                    <ArrowRight size={12} color="var(--text-muted)" />
                    <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--teal)' }}>{valA}</span>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {flags.map(({ label, key }) => {
          const wasPresent = !!m[key];
          const isPresent  = !!ma[key];
          const color  = isPresent ? 'var(--teal)' : 'var(--text-muted)';
          const bg     = isPresent ? 'var(--teal-dim)' : 'var(--bg-elevated)';
          const border = isPresent ? 'rgba(0,212,170,0.3)' : 'var(--border)';
          return (
            <div key={key} style={{ padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600, background: bg, border: `1px solid ${border}`, color, display: 'flex', alignItems: 'center', gap: 5 }}>
              {isPresent ? '✓' : '✗'} {label}
              {!wasPresent && isPresent && <span style={{ fontSize: 10, color: 'var(--teal)', fontWeight: 400 }}> (ajouté)</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Trace agent ──────────────────────────────────────────────────────────────

function AgentBadge({ agent }) {
  const c = AGENT_COLOR[agent] || AGENT_COLOR.default;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
      background: c.bg, border: `1px solid ${c.border}`, color: c.text,
      fontFamily: 'var(--font-display)', letterSpacing: '0.04em', textTransform: 'uppercase',
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: c.dot, flexShrink: 0 }} />
      {agent}
    </span>
  );
}

function AgentTracePanel({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace) return null;

  const mode = trace.mode === 'multi_agent' ? 'Multi-Agents' : 'Réflexion';
  const steps = trace.steps || trace.iterations || [];
  const attempts = trace.attempts || trace.iterations_used || 0;
  const memUsed = trace.memory_used;

  return (
    <div className="card" style={{ marginBottom: 20, border: '1px solid rgba(167,139,250,0.2)', background: 'rgba(167,139,250,0.03)' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
        onClick={() => setOpen(!open)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Brain size={16} color="#a78bfa" />
          <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: 15 }}>
            Trace de l'agent — mode {mode}
          </span>
          <span style={{ padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700, background: 'rgba(167,139,250,0.15)', color: '#c4b5fd', border: '1px solid rgba(167,139,250,0.25)' }}>
            {attempts} tentative{attempts > 1 ? 's' : ''}
          </span>
          {memUsed && (
            <span style={{ padding: '2px 8px', borderRadius: 99, fontSize: 11, fontWeight: 700, background: 'rgba(0,212,170,0.1)', color: 'var(--teal)', border: '1px solid rgba(0,212,170,0.2)' }}>
              🧠 Mémoire utilisée
            </span>
          )}
        </div>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </div>

      {open && (
        <div style={{ marginTop: 16 }}>
          {/* Mode réflexion : liste des itérations */}
          {trace.mode === 'reflection' && steps.map((iter, i) => (
            <div key={i} style={{
              padding: '12px 14px', marginBottom: 8, borderRadius: 'var(--radius)',
              background: 'var(--bg-elevated)', border: '1px solid var(--border)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: 13, color: '#c4b5fd' }}>
                  Itération {iter.iteration}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {iter.issues_before} problème{iter.issues_before !== 1 ? 's' : ''} →{' '}
                  <span style={{ color: iter.issues_after === 0 ? 'var(--teal)' : 'var(--text-secondary)' }}>
                    {iter.issues_after}
                  </span>
                </span>
                <span style={{ padding: '1px 7px', borderRadius: 99, fontSize: 10, fontWeight: 700, background: 'rgba(0,212,170,0.1)', color: 'var(--teal)', border: '1px solid rgba(0,212,170,0.2)' }}>
                  Score : {iter.score ?? '?'}
                </span>
              </div>
              {iter.summary && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{iter.summary}</div>
              )}
            </div>
          ))}

          {/* Mode multi-agents : liste des étapes */}
          {trace.mode === 'multi_agent' && steps.map((step, i) => (
            <div key={i} style={{
              display: 'flex', gap: 12, padding: '10px 0',
              borderBottom: i < steps.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', flexShrink: 0 }}>
                {i + 1}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                  <AgentBadge agent={step.agent} />
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{step.action}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{step.result}</div>
              </div>
            </div>
          ))}

          {/* Enrichissement sémantique (multi-agent) */}
          {trace.enriched && (
            <div style={{ marginTop: 14, padding: '12px 14px', background: 'rgba(167,139,250,0.05)', borderRadius: 'var(--radius)', border: '1px solid rgba(167,139,250,0.15)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#c4b5fd', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                Analyse sémantique — AnalyzerAgent
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 12px', fontSize: 12 }}>
                <span style={{ color: 'var(--text-muted)' }}>Complexité</span>
                <span style={{ color: 'var(--text-primary)' }}>{trace.enriched.complexity}</span>
                <span style={{ color: 'var(--text-muted)' }}>Risque</span>
                <span style={{ color: '#fcd34d' }}>{trace.enriched.risk_summary}</span>
                {trace.enriched.patterns?.length > 0 && (
                  <>
                    <span style={{ color: 'var(--text-muted)' }}>Patterns</span>
                    <span style={{ color: 'var(--text-primary)' }}>{trace.enriched.patterns.join(', ')}</span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Stepper ──────────────────────────────────────────────────────────────────

const STEPS = [
  { id: 1, label: 'Upload',    icon: Upload },
  { id: 2, label: 'Analyser', icon: Zap },
  { id: 3, label: 'Migrer',   icon: GitMerge },
  { id: 4, label: 'Résultats', icon: CheckCircle },
];

function StepBar({ current }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 32 }}>
      {STEPS.map((s, i) => {
        const Icon = s.icon;
        const done   = s.id < current;
        const active = s.id === current;
        const color  = done ? 'var(--teal)' : active ? 'var(--accent)' : 'var(--text-muted)';
        return (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? 1 : 'none' }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%',
                background: done ? 'var(--teal-dim)' : active ? 'var(--accent-dim)' : 'var(--bg-elevated)',
                border: `2px solid ${color}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: active ? '0 0 16px var(--accent-glow)' : 'none',
                transition: 'all 0.3s',
              }}>
                {done ? <CheckCircle size={16} color="var(--teal)" /> : <Icon size={15} color={color} />}
              </div>
              <span style={{ fontSize: 11, color, fontWeight: active ? 600 : 400, whiteSpace: 'nowrap' }}>{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ flex: 1, height: 2, background: done ? 'var(--teal)' : 'var(--border)', margin: '0 6px', marginBottom: 20, transition: 'background 0.3s', opacity: done ? 0.5 : 1 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── COMPOSANT PRINCIPAL ──────────────────────────────────────────────────────

export default function MigrationHome() {
  const fileRef = useRef();

  const [step,           setStep]          = useState(1);
  const [file,           setFile]          = useState(null);
  const [language,       setLanguage]      = useState('java');
  const [dragging,       setDragging]      = useState(false);
  const [targetVersion,  setTargetVersion] = useState('17');
  const [agentMode,      setAgentMode]     = useState('standard');
  const [uploadResult,   setUploadResult]  = useState(null);
  const [migrateResult,  setMigrateResult] = useState(null);
  const [history,        setHistory]       = useState(null);
  const [loadingUpload,  setLoadingUpload] = useState(false);
  const [loadingMigrate, setLoadingMigrate] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error,          setError]         = useState(null);
  const [codeTab,        setCodeTab]       = useState('migrated');
  const [showOriginal,   setShowOriginal]  = useState(false);
  const [showMigrated,   setShowMigrated]  = useState(false);
  const [activeTab,      setActiveTab]     = useState('modifications');
  const navigate = useNavigate();

  useEffect(() => {
    setLoadingHistory(true);
    getMigrationHistory()
      .then(setHistory)
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, []);

  function handleFile(f) {
    if (!f) return;
    const isPy   = f.name.endsWith('.py');
    const isJava = f.name.endsWith('.java');
    if (!isPy && !isJava) {
      setError('Seuls les fichiers .java et .py sont acceptés');
      return;
    }
    const lang = isPy ? 'python' : 'java';
    setFile(f);
    setLanguage(lang);
    setTargetVersion(lang === 'python' ? '3.10' : '17');
    setError(null);
    setUploadResult(null);
    setMigrateResult(null);
    setStep(1);
  }

  async function handleUpload() {
    if (!file) return;
    setLoadingUpload(true);
    setError(null);
    try {
      const r = await uploadFile(file);
      setUploadResult(r);
      setStep(2);
    } catch (e) {
      setError(e?.response?.data?.detail || 'Erreur upload');
    } finally {
      setLoadingUpload(false);
    }
  }

  async function handleMigrate() {
    if (!uploadResult) return;
    setLoadingMigrate(true);
    setError(null);
    setStep(3);
    try {
      let r;
      if (agentMode === 'reflection') {
        r = await migrateFileAgent(uploadResult.filename, targetVersion, 3);
      } else if (agentMode === 'multi_agent') {
        r = await migrateFileMultiAgent(uploadResult.filename, targetVersion, 2);
      } else {
        r = await migrateFile(uploadResult.filename, targetVersion);
      }
      setMigrateResult(r);
      setStep(4);
      getMigrationHistory().then(setHistory).catch(() => {});
    } catch (e) {
      setError(e?.response?.data?.detail || 'Erreur migration');
      setStep(2);
    } finally {
      setLoadingMigrate(false);
    }
  }

  function reset() {
    setStep(1); setFile(null); setUploadResult(null); setMigrateResult(null);
    setError(null); setShowOriginal(false); setShowMigrated(false); setCodeTab('migrated');
    setLanguage('java'); setTargetVersion('17'); setAgentMode('standard');
  }

  const res      = migrateResult;
  const sb       = res?.score_before;
  const sa       = res?.score_after;
  const imp      = res?.improvement;
  const abIssues = res?.analysis_before?.issues || [];
  const aaIssues = res?.analysis_after?.issues  || [];
  const resLang  = res?.language || language;

  const versions        = language === 'python' ? PYTHON_VERSIONS : JAVA_VERSIONS;
  const versionFeatures = language === 'python' ? PYTHON_VERSION_FEATURES : JAVA_VERSION_FEATURES;

  const selectedMode = AGENT_MODES.find(m => m.id === agentMode) || AGENT_MODES[0];

  return (
    <div className="page-content page-enter" style={{ paddingTop: 32, paddingBottom: 64, maxWidth: 960 }}>

      {/* Header */}
      <div className="fade-up" style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '4px 12px', background: 'var(--teal-dim)', border: '1px solid rgba(0,212,170,0.25)', borderRadius: 99, fontSize: 11, color: 'var(--teal)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 12, fontFamily: 'var(--font-display)' }}>
              <GitMerge size={11} /> Migration de code
            </div>
            <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-1px', marginBottom: 6 }}>
              Migration Java & Python
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
              Uploadez un fichier{' '}
              <code style={{ background: 'var(--bg-elevated)', padding: '1px 6px', borderRadius: 4, fontSize: 13 }}>.java</code>
              {' '}ou{' '}
              <code style={{ background: 'var(--bg-elevated)', padding: '1px 6px', borderRadius: 4, fontSize: 13 }}>.py</code>
              {' '}— analyse statique + migration LLM agentique.
            </p>
          </div>
          {history?.count > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', flexShrink: 0 }}>
              <History size={14} color="var(--text-muted)" />
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{history.count} fichier{history.count > 1 ? 's' : ''} migré{history.count > 1 ? 's' : ''}</span>
            </div>
          )}
        </div>
      </div>

      {/* Stepper */}
      <div className="fade-up fade-up-1"><StepBar current={step} /></div>

      {/* ── ÉTAPE 1 & 2 : Upload + Config ── */}
      {step <= 2 && (
        <div className="fade-up fade-up-2" style={{ marginBottom: 20 }}>

          {/* Drop zone */}
          <div
            className={`drop-zone ${dragging ? 'dragging' : ''}`}
            style={{ marginBottom: 20 }}
            onClick={() => !uploadResult && fileRef.current.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]); }}
          >
            <input ref={fileRef} type="file" accept=".java,.py" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
            <div style={{ position: 'relative', zIndex: 1 }}>
              {file ? (
                <>
                  <div style={{ width: 56, height: 56, borderRadius: 14, background: 'var(--teal-dim)', border: '1px solid rgba(0,212,170,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', boxShadow: '0 0 28px var(--teal-glow)', fontSize: 26 }}>
                    {LANG_ICON[language]}
                  </div>
                  <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>{file.name}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                    {LANG_LABEL[language]} · {(file.size / 1024).toFixed(1)} KB
                  </div>
                  {!uploadResult && (
                    <div style={{ marginTop: 10, fontSize: 13, color: 'var(--text-muted)', cursor: 'pointer' }} onClick={e => { e.stopPropagation(); setFile(null); }}>
                      Changer de fichier
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div className="drop-zone-icon"><Upload size={26} color="var(--accent)" /></div>
                  <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 8 }}>Glissez votre fichier ici</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 12 }}>ou cliquez pour parcourir</div>
                  <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                    <span className="chip">☕ .java</span>
                    <span className="chip">🐍 .py</span>
                  </div>
                </>
              )}
            </div>
          </div>

          {uploadResult && (
            <div className="alert alert-success" style={{ marginBottom: 16 }}>
              <CheckCircle size={15} style={{ flexShrink: 0 }} />
              <span><strong>{uploadResult.filename}</strong> uploadé — {(uploadResult.size_bytes / 1024).toFixed(1)} KB · {LANG_LABEL[language]}</span>
            </div>
          )}

          {error && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <AlertCircle size={15} style={{ flexShrink: 0 }} /> {error}
            </div>
          )}

          {file && !uploadResult && (
            <button className="btn btn-primary btn-lg" style={{ width: '100%', marginBottom: 16 }} onClick={handleUpload} disabled={loadingUpload}>
              {loadingUpload ? <><div className="spinner" /> Upload en cours...</> : <><Upload size={15} /> Uploader le fichier</>}
            </button>
          )}

          {/* Config migration */}
          {uploadResult && (
            <div className="card">
              <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Zap size={16} color="var(--teal)" /> Configuration — {LANG_ICON[language]} {LANG_LABEL[language]}
              </div>

              {/* Mode agent */}
              <div className="form-group" style={{ marginBottom: 20 }}>
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Brain size={13} color="#a78bfa" /> Mode de migration
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  {AGENT_MODES.map(mode => {
                    const ModeIcon = mode.icon;
                    const active = agentMode === mode.id;
                    return (
                      <div
                        key={mode.id}
                        onClick={() => setAgentMode(mode.id)}
                        style={{
                          padding: '12px 10px', borderRadius: 'var(--radius)', cursor: 'pointer',
                          background: active ? `${mode.color}14` : 'var(--bg-elevated)',
                          border: `1.5px solid ${active ? mode.color : 'var(--border)'}`,
                          transition: 'all 0.2s',
                          boxShadow: active ? `0 0 14px ${mode.color}33` : 'none',
                          textAlign: 'center',
                        }}
                      >
                        <ModeIcon size={18} color={active ? mode.color : 'var(--text-muted)'} style={{ margin: '0 auto 6px', display: 'block' }} />
                        <div style={{ fontWeight: 700, fontSize: 13, color: active ? mode.color : 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                          {mode.label}
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                          {mode.description}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Version cible */}
              <div className="form-group" style={{ marginBottom: 20 }}>
                <label className="form-label">Version cible</label>
                <div style={{ display: 'grid', gridTemplateColumns: `repeat(${versions.length}, 1fr)`, gap: 10 }}>
                  {versions.map(v => (
                    <div
                      key={v}
                      onClick={() => setTargetVersion(v)}
                      style={{
                        padding: '12px 8px', borderRadius: 'var(--radius)', textAlign: 'center', cursor: 'pointer',
                        background: targetVersion === v ? 'var(--teal-dim)' : 'var(--bg-elevated)',
                        border: `1.5px solid ${targetVersion === v ? 'var(--teal)' : 'var(--border)'}`,
                        transition: 'all 0.2s',
                        boxShadow: targetVersion === v ? '0 0 16px var(--teal-glow)' : 'none',
                      }}
                    >
                      <div style={{ fontWeight: 800, fontSize: 16, fontFamily: 'var(--font-display)', color: targetVersion === v ? 'var(--teal)' : 'var(--text-primary)' }}>
                        {language === 'python' ? `Py ${v}` : `Java ${v}`}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.4 }}>
                        {versionFeatures[v]?.split(',')[0]}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="alert alert-info" style={{ marginTop: 10 }}>
                  <Zap size={13} style={{ flexShrink: 0 }} />
                  {LANG_LABEL[language]} {targetVersion} — {versionFeatures[targetVersion]}
                </div>
              </div>

              <button
                className="btn btn-lg"
                style={{
                  width: '100%',
                  background: agentMode === 'multi_agent'
                    ? 'linear-gradient(135deg, #a78bfa, #7c3aed)'
                    : agentMode === 'reflection'
                    ? 'linear-gradient(135deg, var(--teal), #059669)'
                    : 'linear-gradient(135deg, var(--teal), var(--accent))',
                  color: 'white',
                  boxShadow: `0 0 24px ${selectedMode.color}44`,
                  border: 'none',
                }}
                onClick={handleMigrate}
                disabled={loadingMigrate}
              >
                {loadingMigrate
                  ? <><div className="spinner" /> Migration en cours…</>
                  : <><selectedMode.icon size={16} /> Lancer via {selectedMode.label} — {LANG_LABEL[language]} {targetVersion}</>
                }
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── ÉTAPE 3 : Loading ── */}
      {step === 3 && loadingMigrate && (
        <div className="card fade-up" style={{ textAlign: 'center', padding: 52 }}>
          <div style={{ width: 64, height: 64, margin: '0 auto 20px', borderRadius: '50%', background: `${selectedMode.color}18`, border: `1px solid ${selectedMode.color}44`, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'pulse-glow 2s infinite', fontSize: 28 }}>
            {LANG_ICON[language]}
          </div>
          <h3 style={{ marginBottom: 8, fontSize: 20 }}>Migration en cours — mode {selectedMode.label}</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, maxWidth: 480, margin: '0 auto 24px' }}>
            {agentMode === 'multi_agent'
              ? "Analyste → Migrateur → Vérificateur coordonnés par l'orchestrateur"
              : agentMode === 'reflection'
              ? "L'agent migre, analyse son résultat et se corrige si nécessaire"
              : `GPT-4o analyse et migre le code ${LANG_LABEL[language]} vers la version ${targetVersion}`
            }
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 24, flexWrap: 'wrap' }}>
            {(agentMode === 'multi_agent'
              ? ['AnalyzerAgent', 'MigratorAgent', 'VerifierAgent']
              : agentMode === 'reflection'
              ? ['Analyse statique', 'Migration LLM', 'Auto-correction']
              : ['Analyse statique', 'Appel LLM', 'Score qualité']
            ).map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-muted)' }}>
                <div className="spinner" style={{ width: 12, height: 12, borderWidth: 2 }} />
                {s}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── ÉTAPE 4 : Résultats ── */}
      {step === 4 && res && (
        <div className="fade-up">

          {/* Badge mode */}
          {res.mode && res.mode !== 'standard' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <span style={{ padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 700, background: agentMode === 'multi_agent' ? 'rgba(167,139,250,0.15)' : 'rgba(0,212,170,0.1)', color: agentMode === 'multi_agent' ? '#c4b5fd' : 'var(--teal)', border: `1px solid ${agentMode === 'multi_agent' ? 'rgba(167,139,250,0.3)' : 'rgba(0,212,170,0.25)'}`, fontFamily: 'var(--font-display)', display: 'flex', alignItems: 'center', gap: 6 }}>
                {agentMode === 'multi_agent' ? <Users size={13} /> : <RefreshCw size={13} />}
                {agentMode === 'multi_agent' ? 'Multi-Agents' : 'Agent Réflexion'}
              </span>
            </div>
          )}

          {/* Trace agent */}
          {res.agent_trace && <AgentTracePanel trace={res.agent_trace} />}

          {/* Scores */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={16} color="var(--teal)" /> Score qualité — {LANG_ICON[resLang]} {LANG_LABEL[resLang]}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'center' }}>
              <ScoreRing score={sb?.score ?? 0} grade={sb?.grade ?? '?'} label="Avant migration" />
              <div style={{ textAlign: 'center', padding: '0 16px' }}>
                <div style={{ fontSize: 28, fontWeight: 800, fontFamily: 'var(--font-display)', color: imp?.improved ? 'var(--teal)' : 'var(--red)' }}>
                  {imp?.label || '—'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                  {imp?.issues_fixed > 0 && <div style={{ color: 'var(--green)' }}>✓ {imp.issues_fixed} problème{imp.issues_fixed > 1 ? 's' : ''} corrigé{imp.issues_fixed > 1 ? 's' : ''}</div>}
                </div>
                <ArrowRight size={20} color="var(--text-muted)" style={{ marginTop: 8 }} />
              </div>
              <ScoreRing score={sa?.score ?? 0} grade={sa?.grade ?? '?'} label="Après migration" />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 20 }}>
              {[
                { label: 'Risque avant', val: imp?.risk_before, color: 'var(--red)' },
                { label: 'Risque après', val: imp?.risk_after,  color: 'var(--green)' },
              ].map((r, i) => (
                <div key={i} style={{ padding: '10px 14px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', textAlign: 'center' }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 4 }}>{r.label}</div>
                  <div style={{ fontWeight: 700, color: r.color, fontFamily: 'var(--font-display)', textTransform: 'capitalize' }}>{r.val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary */}
          {res.summary && (
            <div className="alert alert-success fade-up" style={{ marginBottom: 20 }}>
              <CheckCircle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Résumé de la migration</div>
                <div style={{ fontSize: 13, lineHeight: 1.6 }}>{res.summary}</div>
              </div>
              {/* Bouton Expliquer avec l'IA */}
              <button
                onClick={() => {
                  const ctx = buildMigrationContext(res);
                  sessionStorage.setItem('chatbot_context', ctx);
                  sessionStorage.setItem('chatbot_question', 'Peux-tu m\'expliquer en détail cette migration de code ? Quelles sont les améliorations les plus importantes et pourquoi ?');
                  navigate('/chatbot');
                }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 14px', borderRadius: 8,
                  border: '1px solid var(--teal)', background: 'var(--teal-dim)',
                  color: 'var(--teal)', fontSize: 12, fontWeight: 600,
                  cursor: 'pointer', flexShrink: 0, whiteSpace: 'nowrap',
                  transition: 'all 0.2s',
                }}
                onMouseOver={e => e.currentTarget.style.background = 'rgba(0,212,170,0.2)'}
                onMouseOut={e => e.currentTarget.style.background = 'var(--teal-dim)'}
              >
                <Bot size={13} /> Expliquer avec l'IA
              </button>
            </div>
          )}

          {/* Métriques du code */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Code size={16} color="var(--accent)" /> Métriques du code
            </div>
            <MetricsGrid
              before={res.analysis_before}
              after={res.analysis_after}
              language={resLang}
            />
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4, marginBottom: 16, background: 'var(--bg-elevated)', padding: 4, borderRadius: 'var(--radius)', width: 'fit-content' }}>
            {[
              { id: 'modifications', label: `Modifications (${res.modifications?.length ?? 0})`, icon: Code },
              { id: 'issues_before', label: `Problèmes avant (${abIssues.length})`, icon: AlertTriangle },
              { id: 'issues_after',  label: `Problèmes après (${aaIssues.length})`, icon: Shield },
            ].map(t => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  className="btn btn-sm"
                  style={{
                    background: activeTab === t.id ? 'var(--bg-card)' : 'transparent',
                    color: activeTab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
                    border: activeTab === t.id ? '1px solid var(--border)' : '1px solid transparent',
                    gap: 6,
                  }}
                >
                  <Icon size={13} /> {t.label}
                </button>
              );
            })}
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            {activeTab === 'modifications' && (
              res.modifications?.length > 0
                ? res.modifications.map((m, i) => <CodeDiff key={i} {...m} />)
                : <div className="empty-state"><p style={{ color: 'var(--text-muted)' }}>Aucune modification listée</p></div>
            )}
            {activeTab === 'issues_before' && (
              abIssues.length > 0
                ? abIssues.map((issue, i) => <IssueRow key={i} issue={issue} />)
                : <div className="empty-state" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>✓ Aucun problème détecté</div>
            )}
            {activeTab === 'issues_after' && (
              aaIssues.length > 0
                ? aaIssues.map((issue, i) => <IssueRow key={i} issue={issue} />)
                : <div style={{ textAlign: 'center', padding: 32 }}>
                    <CheckCircle size={32} color="var(--teal)" style={{ marginBottom: 8 }} />
                    <div style={{ color: 'var(--teal)', fontWeight: 600 }}>Aucun problème détecté dans le code migré !</div>
                  </div>
            )}
          </div>

          {/* ── Code Output ── */}
          <div className="card" style={{ marginBottom: 20, padding: 0, overflow: 'hidden' }}>

            {/* Header avec onglets */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px',
              background: 'var(--bg-elevated)',
              borderBottom: '1px solid var(--border)',
            }}>
              {/* Onglets */}
              <div style={{ display: 'flex', gap: 2, background: 'var(--bg-base)', borderRadius: 8, padding: 3 }}>
                {[
                  { id: 'migrated', label: 'Code migré',   icon: GitMerge, color: 'var(--teal)'   },
                  { id: 'original', label: 'Code original', icon: Code,    color: 'var(--accent)' },
                ].map(t => {
                  const Icon = t.icon;
                  const active = codeTab === t.id;
                  return (
                    <button
                      key={t.id}
                      onClick={() => setCodeTab(t.id)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer',
                        fontSize: 12, fontWeight: active ? 700 : 400,
                        background: active ? 'var(--bg-card)' : 'transparent',
                        color: active ? t.color : 'var(--text-muted)',
                        boxShadow: active ? '0 1px 4px rgba(0,0,0,0.2)' : 'none',
                        transition: 'all 0.15s',
                      }}
                    >
                      <Icon size={13} /> {t.label}
                    </button>
                  );
                })}
              </div>

              {/* Infos + download */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                  {LANG_ICON[resLang]} {LANG_LABEL[resLang]} {codeTab === 'migrated' ? targetVersion : ''}
                </span>
                <button
                  className="btn btn-sm"
                  style={{ background: 'rgba(0,212,170,0.1)', color: 'var(--teal)', border: '1px solid rgba(0,212,170,0.3)', fontSize: 12 }}
                  onClick={() => downloadMigratedFile(res.filename || uploadResult?.filename)}
                >
                  <Download size={13} /> Télécharger
                </button>
              </div>
            </div>

            {/* Badge version cible sur le code migré */}
            {codeTab === 'migrated' && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 16px',
                background: 'linear-gradient(90deg, rgba(0,212,170,0.06), transparent)',
                borderBottom: '1px solid rgba(0,212,170,0.15)',
              }}>
                <CheckCircle size={13} color="var(--teal)" />
                <span style={{ fontSize: 12, color: 'var(--teal)', fontWeight: 600 }}>
                  Migration terminée — {LANG_LABEL[resLang]} → version {targetVersion}
                </span>
                {res.analysis_after?.code_lines && (
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
                    {res.analysis_after.code_lines} lignes
                  </span>
                )}
              </div>
            )}

            {codeTab === 'original' && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 16px',
                background: 'linear-gradient(90deg, rgba(61,127,255,0.06), transparent)',
                borderBottom: '1px solid rgba(61,127,255,0.15)',
              }}>
                <Code size={13} color="var(--accent)" />
                <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>
                  Code source original — {LANG_LABEL[resLang]}
                </span>
                {res.analysis_before?.code_lines && (
                  <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
                    {res.analysis_before.code_lines} lignes
                  </span>
                )}
              </div>
            )}

            {/* Code content */}
            <div style={{ padding: '0' }}>
              {codeTab === 'migrated' && res.migrated_code && (
                <HighlightedCode code={res.migrated_code} language={resLang} maxHeight={520} />
              )}
              {codeTab === 'original' && res.original_code && (
                <HighlightedCode code={res.original_code} language={resLang} maxHeight={520} />
              )}
            </div>
          </div>



          {/* Actions */}
          <div style={{ display: 'flex', gap: 12 }}>
            <button
              className="btn btn-teal btn-lg"
              style={{ flex: 1 }}
              onClick={() => downloadMigratedFile(res.filename || uploadResult?.filename)}
            >
              <Download size={16} /> Télécharger le code migré
            </button>
            <button className="btn btn-secondary btn-lg" onClick={reset}>
              Nouvelle migration
            </button>
          </div>
        </div>
      )}

      {/* ── Historique ── */}
      {history?.count > 0 && step <= 2 && (
        <div className="card fade-up fade-up-4" style={{ marginTop: 32 }}>
          <div style={{ fontWeight: 700, fontFamily: 'var(--font-display)', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
            <History size={15} color="var(--text-secondary)" /> Migrations précédentes
          </div>
          {history.files.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 0', borderBottom: i < history.files.length - 1 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 18 }}>{LANG_ICON[f.language] || '📄'}</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{f.filename}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{LANG_LABEL[f.language] || ''} · {(f.size_bytes / 1024).toFixed(1)} KB</div>
                </div>
              </div>
              <a href={f.download_url} download style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }} className="btn btn-sm btn-teal">
                <Download size={12} /> Télécharger
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
