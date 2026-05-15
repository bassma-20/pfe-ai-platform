import { Upload, Bot, CheckCircle, Cpu, Zap } from 'lucide-react';

const STEPS = [
  { id: 1, label: 'Mode',     icon: Cpu },
  { id: 2, label: 'Upload',   icon: Upload },
  { id: 3, label: 'Pipeline', icon: Zap },
  { id: 4, label: 'Résultats',icon: CheckCircle },
];

export default function AutoMLStepBar({ current }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', marginBottom: 32 }}>
      {STEPS.map((s, i) => {
        const Icon  = s.icon;
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
