import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  BarChart2, Brain, Zap, AlertTriangle, Copy, Layers, Hash,
  TrendingUp, Play, Settings, Trophy, CheckCircle, AlertCircle,
  Code, ChevronDown, ChevronRight,
} from 'lucide-react';
import { getEda, analyzeFeatures, trainModel, predictValue } from '../../services/automlApi';
import AutoMLStepBar from '../../components/AutoMLStepBar';

// ─── helpers ─────────────────────────────────────────────────────────────────

function SectionHeader({ icon: Icon, color = 'var(--accent)', title, badge }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: `${color}18`, border: `1px solid ${color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={15} color={color} />
      </div>
      <span style={{ fontWeight: 700, fontFamily: 'var(--font-display)', fontSize: 16 }}>{title}</span>
      {badge && <span style={{ fontSize: 11, padding: '2px 8px', background: `${color}18`, color, borderRadius: 99, border: `1px solid ${color}30`, marginLeft: 4 }}>{badge}</span>}
    </div>
  );
}

function StatCard({ icon: Icon, value, label, color }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
        <Icon size={16} color={color} />
      </div>
      <div className="stat-value" style={{ color }}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function MissingBar({ col, count, total }) {
  const pct = total > 0 ? (count / total * 100) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ width: 130, fontSize: 12, color: 'var(--text-secondary)', flexShrink: 0, fontFamily: 'monospace' }}>{col}</div>
      <div style={{ flex: 1 }}>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${Math.max(pct, pct > 0 ? 2 : 0)}%`, background: pct > 20 ? 'var(--red)' : pct > 5 ? 'var(--amber)' : 'var(--teal)' }} />
        </div>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', width: 50, textAlign: 'right' }}>{pct.toFixed(1)}%</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', width: 35, textAlign: 'right' }}>{count}</div>
    </div>
  );
}

function MetricCell({ value }) {
  if (value === null || value === undefined) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
  return <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>{typeof value === 'number' ? value.toFixed(4) : value}</span>;
}

function QualityBadge({ quality }) {
  const map = { excellent: 'badge-excellent', good: 'badge-good', weak: 'badge-weak', poor: 'badge-poor' };
  return <span className={`badge ${map[quality] || 'badge-poor'}`}>{quality}</span>;
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function ManualPage() {
  const { runId } = useParams();

  // EDA
  const [eda,         setEda]         = useState(null);
  const [edaLoading,  setEdaLoading]  = useState(true);
  const [edaError,    setEdaError]    = useState(null);
  const [edaOpen,     setEdaOpen]     = useState(true);

  // Train config
  const [target,      setTarget]      = useState('');
  const [featureStr,  setFeatureStr]  = useState('');
  const [task,        setTask]        = useState('auto');
  const [testSize,    setTestSize]    = useState(0.2);
  const [cvFolds,     setCvFolds]     = useState(5);
  const [useOptuna,   setUseOptuna]   = useState(true);
  const [optunaTrials,setOptunaTrials]= useState(40);

  // Analysis
  const [analysisResult,  setAnalysisResult]  = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError,   setAnalysisError]   = useState(null);
  const [trainOpen,       setTrainOpen]       = useState(true);

  // Train result
  const [trainResult,   setTrainResult]   = useState(null);
  const [loadingTrain,  setLoadingTrain]  = useState(false);
  const [trainError,    setTrainError]    = useState(null);
  const [resultsOpen,   setResultsOpen]   = useState(true);

  // Predict
  const [jsonInput,   setJsonInput]   = useState('{\n  \n}');
  const [jsonError,   setJsonError]   = useState(null);
  const [predLoading, setPredLoading] = useState(false);
  const [predResult,  setPredResult]  = useState(null);
  const [predError,   setPredError]   = useState(null);
  const [predictOpen, setPredictOpen] = useState(true);

  const features = featureStr.split(',').map(s => s.trim()).filter(Boolean);

  // ── Load EDA on mount ────────────────────────────────────────────────────
  useEffect(() => {
    getEda(runId)
      .then(d => { setEda(d); setEdaLoading(false); })
      .catch(e => { setEdaError(e?.response?.data?.detail || 'Erreur EDA'); setEdaLoading(false); });
  }, [runId]);

  // ── Analyze features ─────────────────────────────────────────────────────
  async function handleAnalyze() {
    if (!target || features.length === 0) { setAnalysisError('Renseignez le target et au moins une feature'); return; }
    setLoadingAnalysis(true); setAnalysisError(null);
    try {
      const r = await analyzeFeatures({ run_id: runId, target, features });
      setAnalysisResult(r);
    } catch (e) {
      setAnalysisError(e?.response?.data?.detail || 'Erreur analyse');
    } finally { setLoadingAnalysis(false); }
  }

  // ── Train ────────────────────────────────────────────────────────────────
  async function handleTrain() {
    if (!target || features.length === 0) { setTrainError('Renseignez le target et les features'); return; }
    setLoadingTrain(true); setTrainError(null);
    try {
      const r = await trainModel({ run_id: runId, target, features, task, test_size: parseFloat(testSize), cv_folds: parseInt(cvFolds), use_optuna: useOptuna, optuna_trials: parseInt(optunaTrials) });
      setTrainResult(r);
      // Préfill JSON predict avec les features
      const ex = {};
      features.forEach(f => { ex[f] = ''; });
      setJsonInput(JSON.stringify(ex, null, 2));
    } catch (e) {
      setTrainError(e?.response?.data?.detail || "Erreur d'entraînement");
    } finally { setLoadingTrain(false); }
  }

  // ── Predict ──────────────────────────────────────────────────────────────
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
    } finally { setPredLoading(false); }
  }

  // ── Computed ─────────────────────────────────────────────────────────────
  const missingCols = Object.entries(eda?.missing_by_column || {}).filter(([, v]) => v > 0);
  const totalRows = eda?.shape?.rows || 1;

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      <AutoMLStepBar current={trainResult ? 4 : 3} />

      {/* Header */}
      <div className="fade-up" style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.5px', marginBottom: 4 }}>Pipeline Manuel</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
          Run ID : <span style={{ fontFamily: 'monospace', color: 'var(--teal)' }}>{runId}</span>
        </p>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          SECTION 1 — EDA
      ══════════════════════════════════════════════════════════════════ */}
      <div className="card fade-up fade-up-1" style={{ marginBottom: 20 }}>
        {/* titre cliquable */}
        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', marginBottom: edaOpen ? 18 : 0 }} onClick={() => setEdaOpen(o => !o)}>
          <SectionHeader icon={BarChart2} color="var(--accent)" title="Exploratory Data Analysis" badge={eda ? `${eda.shape?.rows} lignes × ${eda.shape?.columns} col.` : undefined} />
          <div style={{ marginLeft: 'auto', marginBottom: 18 }}>
            {edaOpen ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
          </div>
        </div>

        {edaOpen && (
          <>
            {edaLoading && <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', padding: '12px 0' }}><div className="spinner" /> Analyse en cours…</div>}
            {edaError  && <div className="alert alert-error">{edaError}</div>}

            {eda && (
              <>
                {/* Stats */}
                <div className="grid-4" style={{ marginBottom: 20 }}>
                  <StatCard icon={Layers}        value={eda.shape?.rows?.toLocaleString()} label="Lignes"         color="var(--accent)" />
                  <StatCard icon={Hash}           value={eda.shape?.columns}                label="Colonnes"       color="var(--teal)" />
                  <StatCard icon={AlertTriangle}  value={eda.missing_total}                 label="Valeurs manq."  color={eda.missing_total > 0 ? 'var(--amber)' : 'var(--green)'} />
                  <StatCard icon={Copy}           value={eda.duplicate_rows}                label="Doublons"       color={eda.duplicate_rows > 0 ? 'var(--red)' : 'var(--green)'} />
                </div>

                {/* Colonnes numériques / catégorielles */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                      Numériques ({eda.numeric_columns?.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {eda.numeric_columns?.map(c => <span key={c} className="chip" style={{ borderColor: 'rgba(61,127,255,0.25)', color: 'var(--accent)', fontSize: 11 }}>{c}</span>)}
                      {!eda.numeric_columns?.length && <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Aucune</span>}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--teal)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                      Catégorielles ({eda.categorical_columns?.length})
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {eda.categorical_columns?.map(c => <span key={c} className="chip" style={{ borderColor: 'rgba(0,212,170,0.25)', color: 'var(--teal)', fontSize: 11 }}>{c}</span>)}
                      {!eda.categorical_columns?.length && <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Aucune</span>}
                    </div>
                  </div>
                </div>

                {/* Outliers */}
                {eda.outliers?.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, fontSize: 12, fontWeight: 600, color: 'var(--amber)' }}>
                      <AlertTriangle size={13} /> Outliers détectés
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {eda.outliers.map((o, i) => (
                        <div key={i} style={{ padding: '5px 10px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 7, fontSize: 12 }}>
                          <span style={{ color: 'var(--amber)', fontWeight: 600 }}>{o.column}</span>
                          <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>IQR:{o.iqr_outliers} Z:{o.zscore_outliers} ({o.pct})</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Valeurs manquantes */}
                {missingCols.length > 0 && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                      <TrendingUp size={12} style={{ marginRight: 5 }} />Valeurs manquantes par colonne
                    </div>
                    {missingCols.map(([col, count]) => <MissingBar key={col} col={col} count={count} total={totalRows} />)}
                  </div>
                )}

                {/* Avertissements */}
                {(eda.constant_columns?.length > 0 || eda.high_cardinality_columns?.length > 0) && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 14 }}>
                    {eda.constant_columns?.length > 0 && <div className="alert alert-warning"><AlertTriangle size={13} style={{ flexShrink: 0 }} /> Colonnes constantes : {eda.constant_columns.join(', ')}</div>}
                    {eda.high_cardinality_columns?.length > 0 && <div className="alert alert-info"><BarChart2 size={13} style={{ flexShrink: 0 }} /> Haute cardinalité : {eda.high_cardinality_columns.join(', ')}</div>}
                  </div>
                )}

                {/* Aperçu */}
                {eda.sample_rows?.length > 0 && (
                  <div style={{ overflowX: 'auto' }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Aperçu — 5 premières lignes</div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)' }}>
                          {Object.keys(eda.sample_rows[0]).map(col => (
                            <th key={col} style={{ padding: '6px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {eda.sample_rows.map((row, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                            {Object.values(row).map((v, j) => (
                              <td key={j} style={{ padding: '6px 10px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 12 }}>
                                {v === null || v === undefined ? <span style={{ color: 'var(--text-muted)' }}>null</span> : String(v)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          SECTION 2 — TRAIN
      ══════════════════════════════════════════════════════════════════ */}
      <div className="card fade-up fade-up-2" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', marginBottom: trainOpen ? 18 : 0 }} onClick={() => setTrainOpen(o => !o)}>
          <SectionHeader icon={Settings} color="var(--purple)" title="Configuration & Entraînement" badge={trainResult ? `✓ ${trainResult.best_model?.name}` : undefined} />
          <div style={{ marginLeft: 'auto', marginBottom: 18 }}>
            {trainOpen ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
          </div>
        </div>

        {trainOpen && (
          <>
            {/* Colonnes cible + type */}
            <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label">Colonne cible (target) *</label>
                <input className="form-input" placeholder="ex: price, survived, churn" value={target} onChange={e => setTarget(e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Type de tâche</label>
                <select className="form-select" value={task} onChange={e => setTask(e.target.value)}>
                  <option value="auto">Auto-détection</option>
                  <option value="classification">Classification</option>
                  <option value="regression">Régression</option>
                </select>
              </div>
            </div>

            {/* Features */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Features (séparées par des virgules) *</label>
              <input className="form-input" placeholder="col1, col2, col3, …" value={featureStr} onChange={e => setFeatureStr(e.target.value)} />
              {features.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                  {features.map(f => <span key={f} className="chip selected">{f}</span>)}
                </div>
              )}
            </div>

            {/* Test size + CV */}
            <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
              <div className="form-group">
                <label className="form-label">Test size</label>
                <select className="form-select" value={testSize} onChange={e => setTestSize(e.target.value)}>
                  {[0.1, 0.15, 0.2, 0.25, 0.3].map(v => <option key={v} value={v}>{Math.round(v * 100)}%</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">CV Folds</label>
                <select className="form-select" value={cvFolds} onChange={e => setCvFolds(e.target.value)}>
                  {[3, 5, 7, 10].map(v => <option key={v} value={v}>{v} folds</option>)}
                </select>
              </div>
            </div>

            {/* Optuna toggle */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: 16 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Zap size={14} color="var(--amber)" /> Optuna Hyperparameter Tuning
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>Recherche bayésienne des meilleurs hyperparamètres</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {useOptuna && (
                  <input type="number" className="form-input" style={{ width: 75 }} value={optunaTrials} min={10} max={200} onChange={e => setOptunaTrials(e.target.value)} />
                )}
                <div onClick={() => setUseOptuna(!useOptuna)} style={{ width: 44, height: 24, borderRadius: 99, background: useOptuna ? 'var(--accent)' : 'var(--bg-hover)', cursor: 'pointer', transition: 'var(--transition)', position: 'relative', flexShrink: 0, boxShadow: useOptuna ? '0 0 12px var(--accent-glow)' : 'none' }}>
                  <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'white', position: 'absolute', top: 3, left: useOptuna ? 23 : 3, transition: 'var(--transition)' }} />
                </div>
              </div>
            </div>

            {/* Bouton analyser */}
            {analysisError && <div className="alert alert-error" style={{ marginBottom: 10 }}><AlertCircle size={13} style={{ flexShrink: 0 }} /> {analysisError}</div>}
            <div style={{ display: 'flex', gap: 10, marginBottom: analysisResult ? 16 : 0 }}>
              <button className="btn btn-secondary" onClick={handleAnalyze} disabled={loadingAnalysis || !target || features.length === 0}>
                {loadingAnalysis ? <><div className="spinner" /> Analyse…</> : <><BarChart2 size={14} /> Analyser les features</>}
              </button>
            </div>

            {/* Résultats analyse */}
            {analysisResult && (
              <div style={{ marginTop: 16, padding: '14px 16px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <TrendingUp size={14} color="var(--teal)" />
                  <span style={{ fontWeight: 600, fontSize: 13 }}>Analyse des features</span>
                  <span style={{ fontSize: 11, padding: '2px 8px', background: 'var(--teal-dim)', color: 'var(--teal)', borderRadius: 99, border: '1px solid rgba(0,212,170,0.2)' }}>
                    {analysisResult.task_detected}
                  </span>
                </div>
                {analysisResult.feature_analysis?.warnings?.map((w, i) => (
                  <div key={i} className="alert alert-warning" style={{ marginBottom: 6, fontSize: 12 }}><AlertCircle size={12} style={{ flexShrink: 0 }} /> {w}</div>
                ))}
                {analysisResult.feature_analysis?.recommended_features?.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginTop: 8 }}>
                    {analysisResult.feature_analysis.recommended_features.map(f => (
                      <div key={f.feature} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 10px', background: 'var(--green-dim)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 7, fontSize: 12 }}>
                        <span style={{ color: 'var(--green)', fontWeight: 600 }}>{f.feature}</span>
                        <span style={{ color: 'var(--text-muted)' }}>r={f.correlation}</span>
                      </div>
                    ))}
                  </div>
                )}
                {analysisResult.imbalance_info?.imbalanced && (
                  <div className="alert alert-warning" style={{ marginTop: 10, fontSize: 12 }}>
                    <AlertCircle size={12} style={{ flexShrink: 0 }} />
                    Classes déséquilibrées (ratio {analysisResult.imbalance_info.ratio}x) · {analysisResult.imbalance_info.recommendation}
                  </div>
                )}
              </div>
            )}

            {/* Bouton entraîner */}
            {trainError && <div className="alert alert-error" style={{ marginBottom: 10 }}><AlertCircle size={13} style={{ flexShrink: 0 }} /> {trainError}</div>}
            <button className="btn btn-primary btn-lg" style={{ width: '100%' }} onClick={handleTrain} disabled={loadingTrain || !target || features.length === 0}>
              {loadingTrain
                ? <><div className="spinner" /> Entraînement en cours{useOptuna ? ' (Optuna actif)' : ''}…</>
                : <><Play size={15} /> Lancer l'entraînement</>}
            </button>
          </>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          SECTION 3 — RÉSULTATS
      ══════════════════════════════════════════════════════════════════ */}
      {trainResult && (
        <div className="card fade-up" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', marginBottom: resultsOpen ? 18 : 0 }} onClick={() => setResultsOpen(o => !o)}>
            <SectionHeader icon={Trophy} color="var(--amber)" title="Résultats d'entraînement" badge={trainResult.best_model?.name} />
            <div style={{ marginLeft: 'auto', marginBottom: 18 }}>
              {resultsOpen ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
            </div>
          </div>

          {resultsOpen && (
            <>
              {/* Best model banner */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', background: 'linear-gradient(135deg,rgba(61,127,255,0.1),rgba(0,212,170,0.08))', border: '1px solid rgba(61,127,255,0.25)', borderRadius: 'var(--radius-lg)', marginBottom: 18 }}>
                <div style={{ width: 44, height: 44, borderRadius: 11, background: 'var(--accent-dim)', border: '1px solid rgba(61,127,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 20px var(--accent-glow)' }}>
                  <Trophy size={20} color="var(--accent)" />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Meilleur modèle</div>
                  <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--font-display)', marginTop: 2 }}>{trainResult.best_model?.name}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <QualityBadge quality={trainResult.best_model?.quality} />
                  {trainResult.optuna_used && <div style={{ fontSize: 11, color: 'var(--amber)', marginTop: 4, display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'flex-end' }}><Zap size={10} /> Optuna optimisé</div>}
                </div>
              </div>

              {trainResult.recommendation && (
                <div className="alert alert-info" style={{ marginBottom: 18 }}>
                  <CheckCircle size={14} style={{ flexShrink: 0 }} /> {trainResult.recommendation}
                </div>
              )}

              {/* Leaderboard */}
              <div style={{ overflowX: 'auto', marginBottom: 18 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Leaderboard</div>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '7px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>#</th>
                      <th style={{ padding: '7px 10px', textAlign: 'left', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Modèle</th>
                      {trainResult.task === 'classification' ? (
                        <><th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>F1</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Accuracy</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>CV F1</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>ROC-AUC</th></>
                      ) : (
                        <><th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>R²</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>RMSE</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>MAE</th>
                          <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>CV RMSE</th></>
                      )}
                      <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Temps</th>
                      <th style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11, textTransform: 'uppercase' }}>Qualité</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trainResult.leaderboard?.map((m, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i === 0 ? 'rgba(61,127,255,0.04)' : 'transparent' }}>
                        <td style={{ padding: '7px 10px', color: i === 0 ? 'var(--accent)' : 'var(--text-muted)', fontWeight: i === 0 ? 700 : 400 }}>{i + 1}</td>
                        <td style={{ padding: '7px 10px', fontWeight: i === 0 ? 700 : 400, color: i === 0 ? 'var(--accent)' : 'var(--text-primary)' }}>{m.model}</td>
                        {trainResult.task === 'classification' ? (
                          <><td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.f1_weighted} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.accuracy} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.cv_f1_weighted} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.roc_auc} /></td></>
                        ) : (
                          <><td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.r2} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.rmse} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.mae} /></td>
                            <td style={{ padding: '7px 10px', textAlign: 'right' }}><MetricCell value={m.cv_rmse} /></td></>
                        )}
                        <td style={{ padding: '7px 10px', textAlign: 'right', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: 12 }}>{m.training_time_sec}s</td>
                        <td style={{ padding: '7px 10px', textAlign: 'right' }}><QualityBadge quality={m.model_quality} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Feature importance */}
              {trainResult.feature_importance?.available && (
                <div style={{ marginBottom: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.07em', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Brain size={13} color="var(--purple)" /> Feature Importance
                  </div>
                  {trainResult.feature_importance.items?.slice(0, 10).map((item, i) => {
                    const maxImp = trainResult.feature_importance.items[0]?.importance || 1;
                    const pct = (item.importance / maxImp * 100).toFixed(1);
                    return (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                        <div style={{ width: 120, fontSize: 11, fontFamily: 'monospace', color: 'var(--text-secondary)', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.feature}</div>
                        <div style={{ flex: 1 }}>
                          <div className="progress-bar"><div className="progress-fill" style={{ width: `${pct}%`, background: 'linear-gradient(90deg,var(--purple),var(--accent))' }} /></div>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', width: 55, textAlign: 'right', fontFamily: 'monospace' }}>{item.importance.toFixed(4)}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          SECTION 4 — PRÉDICTION
      ══════════════════════════════════════════════════════════════════ */}
      {trainResult && (
        <div className="card fade-up" style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', marginBottom: predictOpen ? 18 : 0 }} onClick={() => setPredictOpen(o => !o)}>
            <SectionHeader icon={Zap} color="var(--teal)" title="Prédiction" />
            <div style={{ marginLeft: 'auto', marginBottom: 18 }}>
              {predictOpen ? <ChevronDown size={16} color="var(--text-muted)" /> : <ChevronRight size={16} color="var(--text-muted)" />}
            </div>
          </div>

          {predictOpen && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
                <Code size={14} color="var(--accent)" />
                <span style={{ fontSize: 13, fontWeight: 600 }}>Données d'entrée (JSON)</span>
                {jsonError && <span style={{ fontSize: 12, color: 'var(--red)', marginLeft: 'auto' }}>{jsonError}</span>}
              </div>

              <textarea
                className="form-textarea"
                style={{ minHeight: 150, background: 'var(--bg-base)', color: 'var(--teal)', fontFamily: "'DM Mono','Fira Code',monospace", fontSize: 12, lineHeight: 1.7, border: jsonError ? '1px solid var(--red)' : '1px solid var(--border)', marginBottom: 10 }}
                value={jsonInput}
                onChange={e => handleJsonChange(e.target.value)}
                spellCheck={false}
              />

              <div className="alert alert-info" style={{ marginBottom: 12, fontSize: 12 }}>
                <AlertCircle size={13} style={{ flexShrink: 0 }} />
                Renseignez les mêmes colonnes que lors de l'entraînement (features uniquement, sans le target).
              </div>

              {predError && <div className="alert alert-error" style={{ marginBottom: 10 }}><AlertCircle size={13} style={{ flexShrink: 0 }} /> {predError}</div>}

              <button className="btn btn-primary btn-lg" style={{ width: '100%' }} onClick={handlePredict} disabled={predLoading || !!jsonError}>
                {predLoading ? <><div className="spinner" /> Calcul en cours…</> : <><Zap size={15} /> Lancer la prédiction</>}
              </button>

              {predResult && (
                <div style={{ marginTop: 18, padding: '24px', background: 'linear-gradient(135deg,rgba(0,212,170,0.08),rgba(61,127,255,0.06))', border: '1px solid rgba(0,212,170,0.3)', borderRadius: 'var(--radius-xl)', textAlign: 'center' }}>
                  <div style={{ width: 52, height: 52, borderRadius: 13, background: 'var(--teal-dim)', border: '1px solid rgba(0,212,170,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', boxShadow: '0 0 28px var(--teal-glow)' }}>
                    <CheckCircle size={24} color="var(--teal)" />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600, marginBottom: 6 }}>Résultat — {predResult.task}</div>
                  <div style={{ fontSize: 'clamp(28px,5vw,46px)', fontWeight: 800, fontFamily: 'var(--font-display)', color: 'var(--teal)', letterSpacing: '-1px', marginBottom: 6 }}>
                    {String(predResult.prediction)}
                  </div>
                  {predResult.confidence != null && (
                    <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                      Confiance : <strong style={{ color: 'var(--text-primary)' }}>{(predResult.confidence * 100).toFixed(1)}%</strong>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

    </div>
  );
}
