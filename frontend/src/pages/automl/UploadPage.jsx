import { useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Upload, FileText, CheckCircle, AlertCircle,
  Table, Hash, Layers, Bot, Settings,
  Database, ArrowRight, ChevronLeft,
} from 'lucide-react';
import { uploadDataset } from '../../services/automlApi';
import AutoMLStepBar from '../../components/AutoMLStepBar';

export default function UploadPage() {
  const navigate        = useNavigate();
  const [searchParams]  = useSearchParams();
  const mode            = searchParams.get('mode'); // 'agent' | 'manual' | null

  const fileRef    = useRef();
  const [dragging, setDragging] = useState(false);
  const [file,     setFile]     = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState(null);
  const [error,    setError]    = useState(null);

  function handleFile(f) {
    if (!f) return;
    const ext = f.name.split('.').pop().toLowerCase();
    if (!['csv', 'xlsx', 'xls'].includes(ext)) {
      setError('Format non supporté. Utilisez CSV ou Excel (.xlsx/.xls)');
      return;
    }
    setFile(f); setError(null); setResult(null);
  }

  function onDrop(e) {
    e.preventDefault(); setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  }

  async function handleUpload() {
    if (!file) return;
    setLoading(true); setError(null);
    try {
      const data = await uploadDataset(file);
      setResult(data);
      // If mode already chosen, navigate automatically
      if (mode === 'agent')  navigate(`/automl/agent/${data.run_id}`);
      if (mode === 'manual') navigate(`/automl/manual/${data.run_id}`);
    } catch (err) {
      setError(err?.response?.data?.detail || "Erreur lors de l'upload");
    } finally { setLoading(false); }
  }

  const cols   = result?.dataset_info?.columns || [];
  const dtypes = result?.dataset_info?.dtypes || {};
  const rows   = result?.dataset_info?.shape_after_cleaning?.[0];
  const ncols  = result?.dataset_info?.shape_after_cleaning?.[1];

  const rowsRemoved    = result ? (result.cleaning_report?.rows_removed ?? 0) : 0;
  const actionsApplied = result ? (result.cleaning_report?.cleaning_actions_applied?.length ?? 0) : 0;

  const modeLabel = mode === 'agent' ? 'Mode Agent' : mode === 'manual' ? 'Mode Manuel' : null;
  const modeColor = mode === 'agent' ? 'var(--accent)' : 'var(--purple)';
  const ModeIcon  = mode === 'agent' ? Bot : Settings;

  return (
    <div className="page-content page-enter" style={{ maxWidth: 720, margin: '0 auto' }}>

      <AutoMLStepBar current={2} />

      {/* Back + mode indicator */}
      <div className="fade-up" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
        <button
          className="btn btn-secondary"
          style={{ fontSize: 13, padding: '6px 14px' }}
          onClick={() => navigate('/automl')}
        >
          <ChevronLeft size={14} /> Choisir le mode
        </button>

        {modeLabel && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '6px 14px', borderRadius: 99,
            background: `${modeColor}15`,
            border: `1px solid ${modeColor}35`,
            fontSize: 12, fontWeight: 600, color: modeColor,
          }}>
            <ModeIcon size={13} />
            {modeLabel} sélectionné
          </div>
        )}
      </div>

      {/* Hero header */}
      <div className="fade-up" style={{ marginBottom: 32, textAlign: 'center' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 18,
          background: 'linear-gradient(135deg, var(--accent-dim), var(--teal-dim))',
          border: '1px solid rgba(61,127,255,0.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 18px',
          boxShadow: '0 0 40px var(--accent-glow)',
        }}>
          <Database size={28} color="var(--accent)" />
        </div>
        <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-0.5px', marginBottom: 8 }}>
          Chargez votre Dataset
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 15, maxWidth: 400, margin: '0 auto' }}>
          Importez un fichier CSV ou Excel pour démarrer votre pipeline AutoML
        </p>
      </div>

      {/* Drop zone */}
      {!result && (
        <div
          className={`drop-zone fade-up fade-up-1 ${dragging ? 'dragging' : ''}`}
          onClick={() => fileRef.current.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          style={{
            cursor: 'pointer',
            padding: '48px 32px',
            marginBottom: 16,
            background: dragging
              ? 'linear-gradient(135deg, rgba(61,127,255,0.08), rgba(0,212,170,0.06))'
              : 'var(--bg-elevated)',
            borderColor: dragging ? 'var(--accent)' : undefined,
            transition: 'all 0.2s ease',
          }}
        >
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />

          {file ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                width: 72, height: 72, borderRadius: 18,
                background: 'var(--accent-dim)',
                border: '1px solid rgba(61,127,255,0.4)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 16px',
                boxShadow: '0 0 32px var(--accent-glow)',
              }}>
                <FileText size={32} color="var(--accent)" />
              </div>
              <div style={{ fontWeight: 700, fontSize: 17, marginBottom: 4 }}>{file.name}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 13, marginBottom: 14 }}>
                {file.size > 1024 * 1024
                  ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
                  : `${(file.size / 1024).toFixed(1)} KB`}
              </div>
              <span
                style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer', textDecoration: 'underline' }}
                onClick={e => { e.stopPropagation(); setFile(null); }}
              >
                Changer de fichier
              </span>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <div style={{
                width: 72, height: 72, borderRadius: 18,
                background: dragging ? 'rgba(61,127,255,0.12)' : 'var(--bg-base)',
                border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                margin: '0 auto 20px',
                transition: 'all 0.2s',
              }}>
                <Upload size={30} color={dragging ? 'var(--accent)' : 'var(--text-muted)'} />
              </div>
              <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6 }}>
                {dragging ? 'Relâchez pour importer' : 'Glissez votre fichier ici'}
              </div>
              <div style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
                ou cliquez pour parcourir vos fichiers
              </div>
              <div style={{ display: 'inline-flex', gap: 8 }}>
                {['CSV', 'XLSX', 'XLS'].map(f => (
                  <span key={f} style={{
                    padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600,
                    background: 'var(--bg-hover)', border: '1px solid var(--border)',
                    color: 'var(--text-secondary)', letterSpacing: '0.05em',
                  }}>{f}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Formats info */}
      {!file && !result && (
        <div className="fade-up fade-up-2" style={{ display: 'flex', justifyContent: 'center', gap: 28, marginBottom: 24 }}>
          {[
            { icon: CheckCircle, text: 'Max 100 MB',     color: 'var(--green)' },
            { icon: CheckCircle, text: 'CSV, Excel',     color: 'var(--teal)' },
            { icon: CheckCircle, text: 'Nettoyage auto', color: 'var(--accent)' },
          ].map(({ icon: Icon, text, color }) => (
            <div key={text} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-muted)' }}>
              <Icon size={13} color={color} /> {text}
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="alert alert-error fade-up" style={{ marginBottom: 16 }}>
          <AlertCircle size={15} style={{ flexShrink: 0 }} /> {error}
        </div>
      )}

      {/* Upload button */}
      {file && !result && (
        <button
          className="btn btn-primary btn-lg fade-up"
          style={{ width: '100%', marginBottom: 16 }}
          onClick={handleUpload}
          disabled={loading}
        >
          {loading
            ? <><div className="spinner" /> Analyse et nettoyage en cours…</>
            : <><Upload size={16} /> Uploader et analyser</>}
        </button>
      )}

      {/* ── Results (only shown when no mode was pre-selected) ── */}
      {result && !mode && (
        <div className="fade-up">

          {/* Success banner */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 14,
            padding: '16px 20px',
            background: 'linear-gradient(135deg, rgba(34,197,94,0.08), rgba(0,212,170,0.06))',
            border: '1px solid rgba(34,197,94,0.25)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: 24,
          }}>
            <div style={{ width: 42, height: 42, borderRadius: 11, background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <CheckCircle size={20} color="var(--green)" />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 2 }}>Dataset chargé avec succès</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Run ID : <span style={{ fontFamily: 'monospace', color: 'var(--teal)' }}>{result.run_id}</span>
                {actionsApplied > 0 && <span style={{ marginLeft: 12 }}>· {actionsApplied} action(s) de nettoyage appliquées</span>}
                {rowsRemoved > 0 && <span style={{ color: 'var(--amber)', marginLeft: 8 }}>· {rowsRemoved} ligne(s) supprimées</span>}
              </div>
            </div>
            <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 14px' }} onClick={() => { setResult(null); setFile(null); }}>
              Nouveau fichier
            </button>
          </div>

          {/* Stats */}
          <div className="grid-3" style={{ marginBottom: 20 }}>
            {[
              { icon: Table,  value: rows?.toLocaleString(),  label: 'Lignes',   color: 'var(--accent)' },
              { icon: Layers, value: ncols,                   label: 'Colonnes', color: 'var(--teal)' },
              { icon: Hash,   value: cols.length,             label: 'Features', color: 'var(--purple)' },
            ].map(({ icon: Icon, value, label, color }) => (
              <div key={label} className="stat-card">
                <div className="stat-icon" style={{ background: `${color}18`, border: `1px solid ${color}30` }}>
                  <Icon size={16} color={color} />
                </div>
                <div className="stat-value" style={{ color }}>{value}</div>
                <div className="stat-label">{label}</div>
              </div>
            ))}
          </div>

          {/* Colonnes détectées */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
              Colonnes détectées
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {cols.map(col => {
                const dtype = dtypes[col] || '';
                const isNum = dtype.includes('int') || dtype.includes('float');
                return (
                  <span key={col} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    padding: '5px 12px', borderRadius: 8, fontSize: 12, fontWeight: 500,
                    background: isNum ? 'rgba(61,127,255,0.07)' : 'rgba(0,212,170,0.07)',
                    border: `1px solid ${isNum ? 'rgba(61,127,255,0.2)' : 'rgba(0,212,170,0.2)'}`,
                    color: isNum ? 'var(--accent)' : 'var(--teal)',
                  }}>
                    {col}
                    <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '1px 5px', borderRadius: 4 }}>
                      {dtype.replace('object', 'str').replace('int64', 'int').replace('float64', 'float').replace('int32', 'int')}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>

          {/* Mode selection cards (only when no mode pre-selected) */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 14, textAlign: 'center' }}>
              Choisissez votre mode d'analyse
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>

              {/* Mode Agent */}
              <div
                onClick={() => navigate(`/automl/agent/${result.run_id}`)}
                style={{
                  padding: '22px 20px', borderRadius: 'var(--radius-lg)', cursor: 'pointer',
                  background: 'linear-gradient(135deg, rgba(61,127,255,0.1), rgba(0,212,170,0.07))',
                  border: '1.5px solid rgba(61,127,255,0.3)',
                  transition: 'all 0.2s', position: 'relative', overflow: 'hidden',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 32px rgba(61,127,255,0.15)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(61,127,255,0.3)'; e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
              >
                <div style={{ position: 'absolute', top: 12, right: 12, fontSize: 9, padding: '2px 7px', borderRadius: 99, background: 'var(--accent)', color: '#fff', fontWeight: 800, letterSpacing: '0.05em' }}>
                  RECOMMANDÉ
                </div>
                <div style={{ width: 44, height: 44, borderRadius: 12, background: 'var(--accent-dim)', border: '1px solid rgba(61,127,255,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14, boxShadow: '0 0 20px var(--accent-glow)' }}>
                  <Bot size={22} color="var(--accent)" />
                </div>
                <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 8 }}>Mode Agent</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 14 }}>
                  L'agent IA analyse et entraîne <strong style={{ color: 'var(--text-secondary)' }}>automatiquement</strong> — résultats fiables sans configuration.
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>
                  Lancer l'agent <ArrowRight size={14} />
                </div>
              </div>

              {/* Mode Manuel */}
              <div
                onClick={() => navigate(`/automl/manual/${result.run_id}`)}
                style={{
                  padding: '22px 20px', borderRadius: 'var(--radius-lg)', cursor: 'pointer',
                  background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(168,85,247,0.4)'; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 32px rgba(168,85,247,0.1)'; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
              >
                <div style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14 }}>
                  <Settings size={22} color="var(--purple)" />
                </div>
                <div style={{ fontWeight: 800, fontSize: 16, marginBottom: 8 }}>Mode Manuel</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6, marginBottom: 14 }}>
                  Contrôlez chaque étape — explorez les données, choisissez vos features et configurez l'entraînement.
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: 'var(--purple)' }}>
                  Configurer manuellement <ArrowRight size={14} />
                </div>
              </div>

            </div>
          </div>

        </div>
      )}

      {/* Loading overlay when mode was pre-selected (navigates automatically) */}
      {loading && mode && (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: 14 }}>
          <div className="spinner" style={{ margin: '0 auto 12px', width: 28, height: 28 }} />
          Analyse et nettoyage en cours…
        </div>
      )}

    </div>
  );
}
