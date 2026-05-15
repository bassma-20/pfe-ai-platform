import { useNavigate } from 'react-router-dom';
import { Cpu, GitMerge, ArrowRight, Zap, BarChart2, Brain, Shield } from 'lucide-react';

const FEATURES_AUTOML = [
  { icon: BarChart2, text: 'EDA avancée + outliers' },
  { icon: Brain,     text: 'Optuna hyperparameter tuning' },
  { icon: Zap,       text: 'SHAP explainability' },
  { icon: Shield,    text: 'LLM insights & rapport auto' },
];

const FEATURES_MIGRATION = [
  { icon: GitMerge,  text: 'Analyse de code source' },
  { icon: Zap,       text: 'Migration LLM intelligente' },
  { icon: Shield,    text: 'Validation automatique' },
  { icon: BarChart2, text: 'Rapport de migration' },
];

function ModuleCard({ title, subtitle, description, icon: Icon, features, accentColor, glowColor, btnLabel, onClick, delay }) {
  return (
    <div
      className="fade-up"
      style={{
        animationDelay: `${delay}s`,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: 24,
        padding: '36px 32px',
        cursor: 'pointer',
        transition: 'all 0.3s cubic-bezier(0.4,0,0.2,1)',
        position: 'relative',
        overflow: 'hidden',
      }}
      onClick={onClick}
      onMouseEnter={e => {
        e.currentTarget.style.borderColor = accentColor + '60';
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.boxShadow = `0 20px 60px ${glowColor}`;
      }}
      onMouseLeave={e => {
        e.currentTarget.style.borderColor = 'var(--border)';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {/* Background glow */}
      <div style={{
        position: 'absolute',
        top: -40,
        right: -40,
        width: 200,
        height: 200,
        borderRadius: '50%',
        background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      {/* Icon */}
      <div style={{
        width: 56,
        height: 56,
        borderRadius: 14,
        background: `${accentColor}18`,
        border: `1px solid ${accentColor}35`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 20,
        boxShadow: `0 0 24px ${glowColor}`,
      }}>
        <Icon size={24} color={accentColor} strokeWidth={1.8} />
      </div>

      {/* Header */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: '11px', letterSpacing: '0.12em', textTransform: 'uppercase', color: accentColor, fontWeight: 600, marginBottom: 6, fontFamily: 'var(--font-display)' }}>
          {subtitle}
        </div>
        <h2 style={{ fontSize: 26, fontWeight: 800, marginBottom: 10, letterSpacing: '-0.5px' }}>
          {title}
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.65 }}>
          {description}
        </p>
      </div>

      {/* Features */}
      <div style={{ margin: '24px 0', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {features.map((f, i) => {
          const FIcon = f.icon;
          return (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: 'var(--text-secondary)' }}>
              <div style={{ width: 24, height: 24, borderRadius: 6, background: `${accentColor}12`, border: `1px solid ${accentColor}20`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <FIcon size={13} color={accentColor} />
              </div>
              {f.text}
            </div>
          );
        })}
      </div>

      {/* Button */}
      <button
        className="btn btn-lg"
        style={{
          width: '100%',
          background: `${accentColor}18`,
          color: accentColor,
          border: `1px solid ${accentColor}35`,
          justifyContent: 'space-between',
        }}
      >
        {btnLabel}
        <ArrowRight size={16} />
      </button>
    </div>
  );
}

export default function Home() {
  const navigate = useNavigate();

  return (
    <div className="page-content page-enter" style={{ paddingTop: 48, paddingBottom: 64 }}>

      {/* Hero */}
      <div className="fade-up" style={{ textAlign: 'center', marginBottom: 64 }}>
        {/* Badge */}
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 16px',
          background: 'var(--accent-dim)',
          border: '1px solid rgba(61,127,255,0.25)',
          borderRadius: 99,
          fontSize: 12,
          color: 'var(--accent)',
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          marginBottom: 28,
          fontFamily: 'var(--font-display)',
        }}>
          <Zap size={12} />
          Projet PFE — Plateforme AI
        </div>

        <h1 style={{
          fontSize: 'clamp(36px, 6vw, 68px)',
          fontWeight: 800,
          letterSpacing: '-2px',
          lineHeight: 1.05,
          marginBottom: 20,
          background: 'linear-gradient(135deg, #f0f4ff 0%, #8b9ac0 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          Intelligence Artificielle<br />
          <span style={{
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--teal) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>à portée de clic</span>
        </h1>

        <p style={{ fontSize: 17, color: 'var(--text-secondary)', maxWidth: 540, margin: '0 auto', lineHeight: 1.7 }}>
          Deux modules intégrés pour automatiser le Machine Learning
          et la migration de code grâce aux LLMs.
        </p>

        {/* Stats bar */}
        <div className="fade-up fade-up-2" style={{
          display: 'inline-flex',
          gap: 32,
          marginTop: 36,
          padding: '14px 28px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: 99,
        }}>
          {[
            { val: '7+',    label: 'Modèles ML' },
            { val: 'Optuna', label: 'Tuning auto' },
            { val: 'SHAP',  label: 'Explainability' },
            { val: 'GPT-4o',label: 'LLM intégré' },
          ].map((s, i) => (
            <div key={i} style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-display)', color: 'var(--text-primary)' }}>{s.val}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', letterSpacing: '0.04em' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid-2" style={{ maxWidth: 900, margin: '0 auto', gap: 24 }}>
        <ModuleCard
          delay={0.1}
          title="AutoML"
          subtitle="Machine Learning automatisé"
          description="Uploadez un dataset CSV, lancez l'EDA, entraînez plusieurs modèles avec optimisation Optuna, visualisez les résultats SHAP et générez un rapport via GPT-4o."
          icon={Cpu}
          features={FEATURES_AUTOML}
          accentColor="var(--accent)"
          glowColor="rgba(61,127,255,0.15)"
          btnLabel="Lancer AutoML"
          onClick={() => navigate('/automl')}
        />
        <ModuleCard
          delay={0.18}
          title="Migration"
          subtitle="Migration de code LLM"
          description="Analysez votre code source, lancez une migration intelligente assistée par LLM, validez le résultat et exportez un rapport détaillé du processus."
          icon={GitMerge}
          features={FEATURES_MIGRATION}
          accentColor="var(--teal)"
          glowColor="rgba(0,212,170,0.15)"
          btnLabel="Lancer Migration"
          onClick={() => navigate('/migration')}
        />
      </div>

      {/* Bottom tagline */}
      <div className="fade-up fade-up-4" style={{ textAlign: 'center', marginTop: 56, color: 'var(--text-muted)', fontSize: 13 }}>
        Plateforme développée dans le cadre du Projet de Fin d'Études · FastAPI + React + OpenAI
      </div>
    </div>
  );
}
