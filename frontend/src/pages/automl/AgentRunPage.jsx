import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Bot, Play, BarChart2, Brain, TrendingUp, CheckCircle,
  ChevronDown, ChevronRight, AlertCircle, Zap, Layers,
  Trophy, BookOpen, Hash, Sparkles, Table, Code,
} from 'lucide-react';
import { agentRun, predictValue } from '../../services/automlApi';
import AutoMLStepBar from '../../components/AutoMLStepBar';

// ─── Méta outils ─────────────────────────────────────────────────────────────
const TOOL_META = {
  analyze_dataset:  { label: 'Analyse du dataset',       icon: BarChart2,  color: 'var(--accent)' },
  decide_plan:      { label: 'Génération du plan',        icon: Brain,      color: 'var(--purple)' },
  apply_cleaning:   { label: 'Nettoyage & feature eng.',  icon: Sparkles,   color: 'var(--teal)' },
  train_models:     { label: 'Entraînement des modèles',  icon: Play,       color: 'var(--amber)' },
  evaluate_results: { label: 'Évaluation des résultats',  icon: TrendingUp, color: '#22c55e' },
  finalize:         { label: 'Finalisation',              icon: CheckCircle,color: 'var(--green)' },
};

const LOADING_STEPS = [
  'Analyse du dataset...',
  'Génération du plan ML...',
  'Nettoyage & feature engineering...',
  'Entraînement des modèles...',
  'Évaluation et sélection...',
  'Finalisation du rapport...',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────
function SectionTitle({ icon: Icon, label, color = 'var(--accent)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
      <div style={{ width: 30, height: 30, borderRadius: 8, background: `${color}18`, border: `1px solid ${color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={14} color={color} />
      </div>
      <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: 15 }}>{label}</span>
    </div>
  );
}

function StatMini({ label, value, color = 'var(--text-primary)' }) {
  return (
    <div style={{ textAlign: 'center', padding: '12px 16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
      <div style={{ fontSize: 18, fontWeight: 800, color, fontFamily: 'var(--font-display)' }}>{value ?? '—'}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
    </div>
  );
}

function MetricVal({ v }) {
  if (v === null || v === undefined) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{typeof v === 'number' ? v.toFixed(4) : v}</span>;
}

// ─── Étape trace ──────────────────────────────────────────────────────────────
function TraceStep({ step, index }) {
  const [open, setOpen] = useState(false);
  const meta = TOOL_META[step.tool] || { label: step.tool, icon: Bot, color: 'var(--text-muted)' };
  const Icon = meta.icon;
  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginBottom: 8, overflow: 'hidden' }}>
      <div onClick={() => setOpen(o => !o)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', cursor: 'pointer', background: open ? 'var(--bg-elevated)' : 'transparent' }}>
        <div style={{ width: 26, height: 26, borderRadius: 6, background: `${meta.color}18`, border: `1px solid ${meta.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={12} color={meta.color} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{meta.label}</div>
          {step.thought && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, fontStyle: 'italic' }}>{step.thought.slice(0, 110)}{step.thought.length > 110 ? '…' : ''}</div>}
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 4 }}>#{index + 1}</span>
        {open ? <ChevronDown size={13} color="var(--text-muted)" /> : <ChevronRight size={13} color="var(--text-muted)" />}
      </div>
      {open && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg-base)' }}>
          {step.thought && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 4 }}>Raisonnement</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{step.thought}</div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 4 }}>Observation</div>
            <pre style={{ margin: 0, fontSize: 11, color: 'var(--teal)', background: 'var(--bg-elevated)', borderRadius: 6, padding: '10px 12px', overflowX: 'auto', lineHeight: 1.6, maxHeight: 200, overflowY: 'auto' }}>
              {JSON.stringify(step.observation, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page principale ──────────────────────────────────────────────────────────
export default function AgentRunPage() {
  const { runId } = useParams();

  const [targetCol,   setTargetCol]   = useState('');
  const [problemType, setProblemType] = useState('');
  const [maxSteps,    setMaxSteps]    = useState(10);
  const [loading,     setLoading]     = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [result,      setResult]      = useState(null);
  const [error,       setError]       = useState(null);
  const [traceOpen,   setTraceOpen]   = useState(false);

  // Prédiction inline
  const [jsonInput,   setJsonInput]   = useState('{\n  \n}');
  const [jsonError,   setJsonError]   = useState(null);
  const [predLoading, setPredLoading] = useState(false);
  const [predResult,  setPredResult]  = useState(null);
  const [predError,   setPredError]   = useState(null);

  const timerRef = useRef(null);

  useEffect(() => {
    if (loading) {
      let i = 0;
      timerRef.current = setInterval(() => { i = (i + 1) % LOADING_STEPS.length; setLoadingStep(i); }, 4000);
    } else {
      clearInterval(timerRef.current);
      setLoadingStep(0);
    }
    return () => clearInterval(timerRef.current);
  }, [loading]);

  async function handleRun() {
    setLoading(true); setError(null); setResult(null); setPredResult(null);
    try {
      const data = await agentRun(runId, { targetColumn: targetCol || undefined, problemType: problemType || undefined, maxSteps });
      setResult(data);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.response?.data?.error || "Erreur lors de l'exécution de l'agent.");
    } finally {
      setLoading(false);
    }
  }

  function handleJsonChange(val) {
    setJsonInput(val); setJsonError(null);
    try { JSON.parse(val); } catch { setJsonError('JSON invalide'); }
  }

  async function handlePredict() {
    let data;
    try { data = JSON.parse(jsonInput); } catch { setJsonError('JSON invalide'); return; }
    setPredLoading(true); setPredError(null); setPredResult(null);
    try {
      const r = await predictValue({ run_id: runId, data });
      setPredResult(r);
    } catch (e) {
      setPredError(e?.response?.data?.detail || 'Erreur de prédiction');
    } finally {
      setPredLoading(false);
    }
  }

  // ── Extraction des observations de la trace ──────────────────────────────
  const trace       = result?.agent_trace;
  const allSteps    = trace?.steps || [];
  const actionSteps = allSteps.filter(s => s.type === 'action');

  const obs = (tool) => actionSteps.find(s => s.tool === tool)?.observation || {};

  const edaObs    = obs('analyze_dataset');   // shape, columns, total_null_pct, duplicate_rows
  const planObs   = obs('decide_plan');       // target, problem_type, cleaning/feature actions detail
  const cleanObs  = obs('apply_cleaning');    // shape_before, shape_after, actions_detail
  const evalObs   = obs('evaluate_results');  // models_comparison, best_model, best_metrics, feature_importance
  const trainObs  = obs('train_models');      // best_model, best_metrics, models_evaluated

  const metrics      = result?.best_metrics || {};
  const modelsComp   = evalObs?.models_comparison || [];
  const featImp      = evalObs?.feature_importance || result?.training_result?.feature_importance || {};
  const metricKeys   = modelsComp[0] ? Object.keys(modelsComp[0].metrics || {}) : [];

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>

      <AutoMLStepBar current={result ? 4 : 3} />

      {/* ── Header ── */}
      <div className="fade-up" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, background: 'linear-gradient(135deg,var(--accent-dim),var(--teal-dim))', border: '1px solid rgba(61,127,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px var(--accent-glow)' }}>
            <Bot size={22} color="var(--accent)" />
          </div>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.5px', marginBottom: 0 }}>Agent AutoML</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 2 }}>Run ID : <span style={{ fontFamily: 'monospace', color: 'var(--teal)' }}>{runId}</span></p>
          </div>
        </div>
        <div className="alert alert-info" style={{ marginTop: 8 }}>
          <Bot size={14} style={{ flexShrink: 0 }} />
          L'agent ReAct analyse, planifie, nettoie, entraîne et évalue automatiquement.
        </div>
      </div>

      {/* ── Config ── */}
      {!result && (
        <div className="card fade-up fade-up-1" style={{ marginBottom: 20 }}>
          <SectionTitle icon={Brain} label="Configuration (optionnelle)" />
          <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
            <div className="form-group">
              <label className="form-label">Colonne cible</label>
              <input className="form-input" placeholder="ex: price, survived… (laissez vide = auto)" value={targetCol} onChange={e => setTargetCol(e.target.value)} disabled={loading} />
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>L'agent détermine la target automatiquement si vide.</div>
            </div>
            <div className="form-group">
              <label className="form-label">Type de problème</label>
              <select className="form-select" value={problemType} onChange={e => setProblemType(e.target.value)} disabled={loading}>
                <option value="">Auto-détection</option>
                <option value="binary_classification">Classification binaire</option>
                <option value="multiclass_classification">Classification multi-classes</option>
                <option value="regression">Régression</option>
              </select>
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">Nombre max d'étapes</label>
            <select className="form-select" style={{ maxWidth: 180 }} value={maxSteps} onChange={e => setMaxSteps(Number(e.target.value))} disabled={loading}>
              {[6, 8, 10, 15].map(v => <option key={v} value={v}>{v} étapes</option>)}
            </select>
          </div>
        </div>
      )}

      {error && <div className="alert alert-error fade-up" style={{ marginBottom: 16 }}><AlertCircle size={15} style={{ flexShrink: 0 }} /> {error}</div>}

      {/* ── Bouton lancer ── */}
      {!result && (
        <button className="btn btn-primary btn-lg fade-up fade-up-2" style={{ width: '100%', marginBottom: 24 }} onClick={handleRun} disabled={loading}>
          {loading ? <><div className="spinner" /> {LOADING_STEPS[loadingStep]}</> : <><Bot size={16} /> Lancer l'Agent AutoML</>}
        </button>
      )}

      {/* ── Barre de progression ── */}
      {loading && (
        <div className="card fade-up" style={{ marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 14, color: 'var(--text-secondary)' }}>Pipeline en cours…</div>
          {LOADING_STEPS.map((label, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', opacity: i > loadingStep ? 0.3 : 1, transition: 'opacity 0.4s' }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: i < loadingStep ? 'var(--green-dim)' : i === loadingStep ? 'var(--accent-dim)' : 'var(--bg-elevated)', border: `1px solid ${i < loadingStep ? 'rgba(34,197,94,0.4)' : i === loadingStep ? 'rgba(61,127,255,0.4)' : 'var(--border)'}` }}>
                {i < loadingStep ? <CheckCircle size={11} color="var(--green)" /> : i === loadingStep ? <div className="spinner" style={{ width: 10, height: 10 }} /> : <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>{i + 1}</span>}
              </div>
              <span style={{ fontSize: 13, color: i < loadingStep ? 'var(--green)' : i === loadingStep ? 'var(--accent)' : 'var(--text-muted)' }}>{label}</span>
            </div>
          ))}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          RÉSULTATS
      ══════════════════════════════════════════════════════════════════════ */}
      {result && (
        <div className="fade-up">

          {/* Status + mémoire */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 13px', borderRadius: 99, background: result.status === 'completed' ? 'rgba(34,197,94,0.1)' : 'rgba(245,158,11,0.1)', border: `1px solid ${result.status === 'completed' ? 'rgba(34,197,94,0.3)' : 'rgba(245,158,11,0.3)'}`, fontSize: 12, fontWeight: 700, color: result.status === 'completed' ? 'var(--green)' : 'var(--amber)' }}>
              {result.status === 'completed' ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
              {result.status === 'completed' ? 'Pipeline complété' : 'Max étapes atteint'}
            </div>
            {trace?.memory_used && (
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 12px', borderRadius: 99, background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.3)', fontSize: 12, color: 'var(--purple)' }}>
                <BookOpen size={12} /> Mémoire utilisée
              </div>
            )}
            <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>{trace?.total_steps}/{trace?.max_steps} étapes</div>
          </div>

          {/* Conclusion */}
          {result.conclusion && (
            <div style={{ padding: '16px 20px', background: 'linear-gradient(135deg,rgba(61,127,255,0.07),rgba(0,212,170,0.05))', border: '1px solid rgba(61,127,255,0.2)', borderRadius: 'var(--radius-lg)', marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginBottom: 6 }}>Conclusion de l'agent</div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.7 }}>{result.conclusion}</div>
            </div>
          )}

          {/* ══════════════════════════════════════════════════════
              RAPPORT COMPLET DE L'AGENT
          ══════════════════════════════════════════════════════ */}

          {/* ── R1. Analyse détaillée des colonnes ── */}
          {edaObs?.columns?.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <SectionTitle icon={BarChart2} label="Analyse détaillée des colonnes" color="var(--accent)" />

              {/* Stats globales */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 16 }}>
                <StatMini label="Lignes"    value={edaObs.shape?.[0]?.toLocaleString()} color="var(--accent)" />
                <StatMini label="Colonnes"  value={edaObs.shape?.[1]}                   color="var(--teal)" />
                <StatMini label="Null %"    value={`${edaObs.total_null_pct ?? 0}%`}    color={edaObs.total_null_pct > 10 ? 'var(--amber)' : 'var(--green)'} />
                <StatMini label="Doublons"  value={edaObs.duplicate_rows ?? 0}           color={edaObs.duplicate_rows > 0 ? 'var(--red)' : 'var(--green)'} />
              </div>

              {edaObs.target_column && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, padding: '8px 12px', background: 'rgba(61,127,255,0.06)', borderRadius: 8, border: '1px solid rgba(61,127,255,0.15)' }}>
                  <Trophy size={13} color="var(--accent)" />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Colonne cible détectée :</span>
                  <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', fontFamily: 'monospace' }}>{edaObs.target_column}</span>
                  {edaObs.problem_type && <span style={{ marginLeft: 'auto', fontSize: 11, padding: '2px 8px', borderRadius: 99, background: 'var(--accent-dim)', color: 'var(--accent)', fontWeight: 600 }}>{edaObs.problem_type}</span>}
                </div>
              )}

              {/* Table per-colonne */}
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)' }}>
                      {['Colonne', 'Type', 'Null', 'Min', 'Max', 'Moy / Top valeurs', 'Outliers', 'Asymétrie'].map(h => (
                        <th key={h} style={{ padding: '7px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {edaObs.columns.map((col, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: col.name === edaObs.target_column ? 'rgba(61,127,255,0.04)' : 'transparent' }}>

                        {/* Colonne */}
                        <td style={{ padding: '8px 10px', fontWeight: 700, color: col.name === edaObs.target_column ? 'var(--accent)' : 'var(--text-primary)', fontFamily: 'monospace', fontSize: 12, whiteSpace: 'nowrap' }}>
                          {col.name === edaObs.target_column && '⭐ '}{col.name}
                        </td>

                        {/* Type */}
                        <td style={{ padding: '8px 10px' }}>
                          <span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700, background: col.is_numeric ? 'rgba(61,127,255,0.1)' : 'rgba(0,212,170,0.1)', color: col.is_numeric ? 'var(--accent)' : 'var(--teal)' }}>
                            {col.is_numeric ? 'num' : 'cat'} · {col.dtype?.replace('int64','int').replace('float64','float').replace('object','str')}
                          </span>
                        </td>

                        {/* Null */}
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11 }}>
                          {col.null_pct > 0
                            ? <span style={{ color: col.null_pct > 10 ? 'var(--red)' : 'var(--amber)', fontWeight: 600 }}>{col.null_pct}% <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>({col.null_count})</span></span>
                            : <span style={{ color: 'var(--green)' }}>✓</span>}
                        </td>

                        {/* Min */}
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, color: col.min != null && col.iqr_lower != null && col.min < col.iqr_lower ? 'var(--red)' : 'var(--text-muted)' }}>
                          {col.min != null ? col.min.toLocaleString() : '—'}
                        </td>

                        {/* Max */}
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, color: col.max != null && col.iqr_upper != null && col.max > col.iqr_upper ? 'var(--red)' : 'var(--text-muted)' }}>
                          {col.max != null ? col.max.toLocaleString() : '—'}
                        </td>

                        {/* Moy / Top valeurs */}
                        <td style={{ padding: '8px 10px', fontSize: 11, maxWidth: 180 }}>
                          {col.is_numeric && col.mean != null
                            ? <span style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>{col.mean.toLocaleString()}</span>
                            : col.top_values
                              ? <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
                                  {col.top_values.slice(0, 3).map((tv, j) => (
                                    <span key={j} style={{ padding: '1px 6px', borderRadius: 4, fontSize: 10, background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                      {tv.value} <span style={{ color: 'var(--text-muted)' }}>×{tv.count}</span>
                                    </span>
                                  ))}
                                </div>
                              : <span style={{ color: 'var(--text-muted)' }}>—</span>
                          }
                        </td>

                        {/* Outliers */}
                        <td style={{ padding: '8px 10px' }}>
                          {col.has_outliers === true
                            ? <div>
                                <span style={{ fontSize: 10, color: 'var(--amber)', fontWeight: 700 }}>⚠ {col.n_outliers ?? '?'} lignes</span>
                                {col.iqr_lower != null && <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'monospace', marginTop: 2 }}>[{col.iqr_lower.toLocaleString()} – {col.iqr_upper?.toLocaleString()}]</div>}
                              </div>
                            : col.has_outliers === false
                              ? <span style={{ fontSize: 10, color: 'var(--green)' }}>✓ aucun</span>
                              : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                        </td>

                        {/* Asymétrie */}
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: 11, color: col.skewness != null && Math.abs(col.skewness) > 1 ? 'var(--amber)' : 'var(--text-muted)' }}>
                          {col.skewness != null ? col.skewness.toFixed(2) : '—'}
                        </td>

                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Class balance */}
              {edaObs.class_balance && Object.keys(edaObs.class_balance).length > 0 && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 8 }}>Distribution de la cible</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {Object.entries(edaObs.class_balance).map(([cls, pct]) => (
                      <div key={cls} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, background: 'var(--bg-elevated)', border: '1px solid var(--border)', fontSize: 12 }}>
                        <span style={{ fontWeight: 600 }}>{cls}</span>
                        <span style={{ color: 'var(--teal)' }}>{(pct * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── R2. Plan décidé par l'agent ── */}
          {planObs?.target_column && (
            <div className="card" style={{ marginBottom: 20 }}>
              <SectionTitle icon={Brain} label="Plan décidé par l'agent" color="var(--purple)" />

              {/* En-tête plan */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 16 }}>
                <StatMini label="Source"        value={planObs.plan_source === 'llm' ? 'LLM'  : 'Fallback'} color={planObs.plan_source === 'llm' ? 'var(--teal)' : 'var(--amber)'} />
                <StatMini label="Confiance"     value={planObs.confidence != null ? `${(planObs.confidence * 100).toFixed(0)}%` : '—'} color="var(--accent)" />
                <StatMini label="Optimisation"  value={planObs.use_optuna ? `Optuna · ${planObs.optuna_trials} trials` : 'Sans Optuna'} color="var(--purple)" />
              </div>

              {planObs.reasoning_summary && (
                <div style={{ padding: '10px 14px', background: 'rgba(168,85,247,0.06)', border: '1px solid rgba(168,85,247,0.2)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 14 }}>
                  {planObs.reasoning_summary}
                </div>
              )}

              {/* Modèles sélectionnés */}
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 8 }}>Modèles sélectionnés</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(planObs.models_to_try || []).map((m, i) => (
                    <span key={i} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, background: 'rgba(61,127,255,0.08)', border: '1px solid rgba(61,127,255,0.2)', color: 'var(--accent)' }}>{m}</span>
                  ))}
                </div>
                {planObs.model_reason && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{planObs.model_reason}</div>}
              </div>

              {/* Actions de nettoyage planifiées */}
              {(planObs.cleaning_actions_detail || []).length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 8 }}>
                    Nettoyage planifié — {planObs.cleaning_actions_detail.length} action(s)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {planObs.cleaning_actions_detail.map((a, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '7px 10px', background: 'var(--bg-elevated)', borderRadius: 6, border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, fontWeight: 700, background: 'rgba(0,212,170,0.1)', color: 'var(--teal)', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>{a.action}</span>
                        {(a.column || a.columns) && <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'monospace' }}>{Array.isArray(a.columns) ? a.columns.join(', ') : a.column}</span>}
                        {a.reason && <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>{a.reason}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Actions de feature engineering planifiées */}
              {(planObs.feature_actions_detail || []).length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 8 }}>
                    Feature Engineering planifié — {planObs.feature_actions_detail.length} action(s)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {planObs.feature_actions_detail.map((a, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '7px 10px', background: 'var(--bg-elevated)', borderRadius: 6, border: '1px solid var(--border)' }}>
                        <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, fontWeight: 700, background: 'rgba(168,85,247,0.1)', color: 'var(--purple)', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>{a.action}</span>
                        {(a.column || a.columns || a.new_feature) && (
                          <span style={{ fontSize: 12, color: 'var(--accent)', fontFamily: 'monospace' }}>
                            {a.new_feature ? `${a.new_feature} ← ` : ''}{a.col1 && a.col2 ? `${a.col1}, ${a.col2}` : Array.isArray(a.columns) ? a.columns.join(', ') : a.column}
                          </span>
                        )}
                        {a.reason && <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1 }}>{a.reason}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {(planObs.data_warnings || []).length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 8 }}>Avertissements détectés</div>
                  {planObs.data_warnings.map((w, i) => (
                    <div key={i} className="alert alert-warning" style={{ padding: '6px 12px', fontSize: 12, marginBottom: 4 }}>
                      <AlertCircle size={11} style={{ flexShrink: 0 }} /> {w}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── R3. Exécution du nettoyage ── */}
          {cleanObs?.shape_before && (
            <div className="card" style={{ marginBottom: 20 }}>
              <SectionTitle icon={Sparkles} label="Exécution du nettoyage" color="var(--teal)" />

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10, marginBottom: 14 }}>
                <StatMini label="Avant"           value={`${cleanObs.shape_before?.[0]} × ${cleanObs.shape_before?.[1]}`} color="var(--text-muted)" />
                <StatMini label="Après"           value={`${cleanObs.shape_after?.[0]} × ${cleanObs.shape_after?.[1]}`}   color="var(--teal)" />
                <StatMini label="Lignes supprimées" value={cleanObs.rows_removed ?? 0}   color={cleanObs.rows_removed > 0 ? 'var(--amber)' : 'var(--green)'} />
                <StatMini label="Succès"          value={`${cleanObs.successful_actions}/${(cleanObs.successful_actions ?? 0) + (cleanObs.failed_actions ?? 0)}`} color="var(--green)" />
              </div>

              {(cleanObs.actions_detail || []).length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border)' }}>
                        {['Action', 'Colonne', 'Statut', 'Lignes affectées', 'Message'].map(h => (
                          <th key={h} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {cleanObs.actions_detail.map((a, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '6px 10px' }}>
                            <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4, fontWeight: 700, fontFamily: 'monospace', background: 'rgba(0,212,170,0.08)', color: 'var(--teal)' }}>{a.action}</span>
                          </td>
                          <td style={{ padding: '6px 10px', fontFamily: 'monospace', color: 'var(--accent)', fontSize: 11 }}>{a.column || '—'}</td>
                          <td style={{ padding: '6px 10px' }}>
                            <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 99, fontWeight: 700,
                              background: a.status === 'success' ? 'rgba(34,197,94,0.1)' : a.status === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                              color: a.status === 'success' ? 'var(--green)' : a.status === 'error' ? 'var(--red)' : 'var(--amber)',
                            }}>{a.status}</span>
                          </td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 11 }}>{a.rows_affected != null ? a.rows_affected : '—'}</td>
                          <td style={{ padding: '6px 10px', color: 'var(--text-muted)', fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.message || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}


          {/* ── R4. Comparaison des modèles ── */}
          {modelsComp.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <SectionTitle icon={Table} label="Comparaison des modèles" color="var(--purple)" />
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '8px 12px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Modèle</th>
                      {metricKeys.map(k => (
                        <th key={k} style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</th>
                      ))}
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>CV Mean</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Temps</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelsComp.map((m, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: m.model === result.best_model ? 'rgba(61,127,255,0.04)' : 'transparent' }}>
                        <td style={{ padding: '8px 12px', fontWeight: m.model === result.best_model ? 700 : 400, color: m.model === result.best_model ? 'var(--accent)' : 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                          {m.model === result.best_model && <Trophy size={12} color="var(--accent)" />}
                          {m.model}
                        </td>
                        {metricKeys.map(k => (
                          <td key={k} style={{ padding: '8px 12px', textAlign: 'right' }}>
                            <MetricVal v={m.metrics?.[k]} />
                          </td>
                        ))}
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}><MetricVal v={m.cv_mean} /></td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12 }}>{m.training_time_s ? `${m.training_time_s.toFixed(1)}s` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── R5. Meilleur modèle + métriques ── */}
          <div className="grid-2" style={{ gap: 16, marginBottom: 20 }}>
            <div style={{ padding: '18px 20px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 44, height: 44, borderRadius: 11, background: 'var(--accent-dim)', border: '1px solid rgba(61,127,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 16px var(--accent-glow)' }}>
                <Trophy size={20} color="var(--accent)" />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>Meilleur modèle</div>
                <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'var(--font-display)', marginTop: 2 }}>{result.best_model || '—'}</div>
              </div>
            </div>
            <div style={{ padding: '18px 20px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600, marginBottom: 10 }}>Métriques finales</div>
              {Object.entries(metrics).length > 0
                ? Object.entries(metrics).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{k}</span>
                      <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'monospace', color: 'var(--teal)' }}>{typeof v === 'number' ? v.toFixed(4) : v}</span>
                    </div>
                  ))
                : <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>—</span>
              }
            </div>
          </div>

          {/* ── R6. Feature Importance ── */}
          {Object.keys(featImp).length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <SectionTitle icon={Layers} label="Feature Importance" color="var(--purple)" />
              {Object.entries(featImp).slice(0, 10).map(([feat, imp], i) => {
                const maxImp = Object.values(featImp)[0] || 1;
                const pct = ((imp / maxImp) * 100).toFixed(1);
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
                    <div style={{ width: 130, fontSize: 12, fontFamily: 'monospace', color: 'var(--text-secondary)', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{feat}</div>
                    <div style={{ flex: 1 }}>
                      <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,var(--purple),var(--accent))' }} /></div>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', width: 60, textAlign: 'right', fontFamily: 'monospace' }}>{Number(imp).toFixed(4)}</div>
                  </div>
                );
              })}
            </div>
          )}

          {/* ── R7. Trace agent (collapsible) ── */}
          {actionSteps.length > 0 && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: traceOpen ? 14 : 0, cursor: 'pointer' }} onClick={() => setTraceOpen(o => !o)}>
                <Bot size={15} color="var(--accent)" />
                <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', flex: 1 }}>Trace de l'agent — {actionSteps.length} actions</span>
                {traceOpen ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronRight size={14} color="var(--text-muted)" />}
              </div>
              {traceOpen && actionSteps.map((step, i) => <TraceStep key={i} step={step} index={i} />)}
            </div>
          )}

          {/* ── R8. Prédiction inline ── */}
          <div className="card" style={{ marginBottom: 12 }}>
            <SectionTitle icon={Zap} label="Prédiction" color="var(--teal)" />

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Code size={14} color="var(--accent)" />
              <span style={{ fontSize: 13, fontWeight: 600 }}>Données d'entrée (JSON)</span>
              {jsonError && <span style={{ fontSize: 12, color: 'var(--red)', marginLeft: 'auto' }}>{jsonError}</span>}
            </div>

            <textarea
              className="form-textarea"
              style={{ minHeight: 140, background: 'var(--bg-base)', color: 'var(--teal)', fontFamily: "'DM Mono','Fira Code',monospace", fontSize: 12, lineHeight: 1.7, border: jsonError ? '1px solid var(--red)' : '1px solid var(--border)', marginBottom: 10 }}
              value={jsonInput}
              onChange={e => handleJsonChange(e.target.value)}
              spellCheck={false}
            />

            <div className="alert alert-info" style={{ marginBottom: 12, fontSize: 12 }}>
              <AlertCircle size={13} style={{ flexShrink: 0 }} />
              Renseignez les features utilisées lors de l'entraînement (sans la colonne target).
            </div>

            {predError && <div className="alert alert-error" style={{ marginBottom: 10 }}><AlertCircle size={14} style={{ flexShrink: 0 }} /> {predError}</div>}

            <button className="btn btn-primary" style={{ width: '100%' }} onClick={handlePredict} disabled={predLoading || !!jsonError}>
              {predLoading ? <><div className="spinner" /> Calcul en cours...</> : <><Zap size={14} /> Lancer la prédiction</>}
            </button>

            {predResult && (
              <div style={{ marginTop: 16, padding: '20px', background: 'linear-gradient(135deg,rgba(0,212,170,0.08),rgba(61,127,255,0.06))', border: '1px solid rgba(0,212,170,0.3)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6 }}>Résultat — {predResult.task}</div>
                <div style={{ fontSize: 'clamp(28px,5vw,42px)', fontWeight: 800, fontFamily: 'var(--font-display)', color: 'var(--teal)', letterSpacing: '-1px', marginBottom: 6 }}>
                  {String(predResult.prediction)}
                </div>
                {predResult.confidence != null && (
                  <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                    Confiance : <strong style={{ color: 'var(--text-primary)' }}>{(predResult.confidence * 100).toFixed(1)}%</strong>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Relancer */}
          <button className="btn btn-secondary" style={{ width: '100%', marginTop: 8 }} onClick={() => { setResult(null); setError(null); setPredResult(null); }}>
            Relancer l'agent
          </button>

        </div>
      )}
    </div>
  );
}
