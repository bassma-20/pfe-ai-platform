import { useNavigate } from 'react-router-dom';
import { Bot, Settings, ArrowRight, Zap, Brain, BarChart2, Sparkles, Sliders, Upload, Database } from 'lucide-react';
import AutoMLStepBar from '../../components/AutoMLStepBar';

const FEATURES_AGENT = [
  { icon: Sparkles, text: 'Analyse automatique du dataset' },
  { icon: Brain,    text: 'Nettoyage et preprocessing intelligent' },
  { icon: BarChart2,text: 'Sélection du meilleur modèle auto' },
  { icon: Zap,      text: 'Résultats complets en une page' },
];

const FEATURES_MANUAL = [
  { icon: Database, text: 'Exploration EDA & visualisations' },
  { icon: Sliders,  text: 'Sélection manuelle des features' },
  { icon: Settings, text: 'Configuration fine du pipeline' },
  { icon: BarChart2,text: 'Contrôle total de l\'entraînement' },
];

function ModeCard({ title, subtitle, description, icon: Icon, features, accentColor, glowColor, btnLabel, badge, onClick, delay }) {
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
        position: 'absolute', top: -40, right: -40,
        width: 220, height: 220, borderRadius: '50%',
        background: `radial-gradient(circle, ${glowColor} 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      {/* Badge */}
      {badge && (
        <div style={{
          position: 'absolute', top: 20, right: 20,
          fontSize: 9, padding: '3px 9px', borderRadius: 99,
          background: accentColor, color: '#fff',
          fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase',
        }}>
          {badge}
        </div>
      )}

      {/* Icon */}
      <div style={{
        width: 56, height: 56, borderRadius: 14,
        background: `${accentColor}18`,
        border: `1px solid ${accentColor}35`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
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

export default function AutoMLHome() {
  const navigate = useNavigate();

  return (
    <div className="page-content page-enter" style={{ paddingTop: 48, paddingBottom: 64 }}>

      <AutoMLStepBar current={1} />

      {/* Hero */}
      <div className="fade-up" style={{ textAlign: 'center', marginBottom: 56 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 16px',
          background: 'var(--accent-dim)',
          border: '1px solid rgba(61,127,255,0.25)',
          borderRadius: 99, fontSize: 12,
          color: 'var(--accent)', fontWeight: 600,
          letterSpacing: '0.06em', textTransform: 'uppercase',
          marginBottom: 28, fontFamily: 'var(--font-display)',
        }}>
          <Zap size={12} />
          AutoML — Machine Learning Automatisé
        </div>

        <h1 style={{
          fontSize: 'clamp(32px, 5vw, 58px)',
          fontWeight: 800, letterSpacing: '-2px',
          lineHeight: 1.05, marginBottom: 16,
          background: 'linear-gradient(135deg, #f0f4ff 0%, #8b9ac0 100%)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        }}>
          Choisissez votre mode<br />
          <span style={{
            background: 'linear-gradient(135deg, var(--accent) 0%, var(--teal) 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>d'analyse</span>
        </h1>

        <p style={{ fontSize: 16, color: 'var(--text-secondary)', maxWidth: 480, margin: '0 auto', lineHeight: 1.7 }}>
          Uploadez votre dataset et laissez l'IA travailler, ou prenez le contrôle de chaque étape du pipeline.
        </p>

        {/* Upload step indicator */}
        <div className="fade-up fade-up-2" style={{
          display: 'inline-flex', alignItems: 'center', gap: 10,
          marginTop: 28, padding: '10px 20px',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 99,
        }}>
          <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--accent-dim)', border: '1px solid rgba(61,127,255,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--accent)' }}>1</div>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Choisir le mode</span>
          <div style={{ width: 24, height: 1, background: 'var(--border)' }} />
          <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>2</div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Uploader le dataset</span>
          <div style={{ width: 24, height: 1, background: 'var(--border)' }} />
          <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'var(--bg-elevated)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>3</div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Analyser & prédire</span>
        </div>
      </div>

      {/* Mode Cards */}
      <div className="grid-2" style={{ maxWidth: 900, margin: '0 auto', gap: 24 }}>
        <ModeCard
          delay={0.1}
          title="Mode Agent"
          subtitle="Automatique & intelligent"
          description="L'agent IA analyse, planifie, nettoie et entraîne automatiquement votre modèle — résultats fiables sans aucune configuration."
          icon={Bot}
          features={FEATURES_AGENT}
          accentColor="var(--accent)"
          glowColor="rgba(61,127,255,0.15)"
          btnLabel="Lancer le mode Agent"
          badge="RECOMMANDÉ"
          onClick={() => navigate('/automl/upload?mode=agent')}
        />
        <ModeCard
          delay={0.18}
          title="Mode Manuel"
          subtitle="Contrôle & personnalisation"
          description="Explorez vos données, choisissez vos features et configurez l'entraînement à votre convenance — chaque étape sous votre contrôle."
          icon={Settings}
          features={FEATURES_MANUAL}
          accentColor="var(--purple)"
          glowColor="rgba(168,85,247,0.15)"
          btnLabel="Configurer manuellement"
          onClick={() => navigate('/automl/upload?mode=manual')}
        />
      </div>

    </div>
  );
}
