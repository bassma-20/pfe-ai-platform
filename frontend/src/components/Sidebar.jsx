import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Upload, Settings, Bot, CheckCircle } from 'lucide-react';

const MANUAL_STEPS = [
  { id: 1, label: 'Upload', path: '/automl/upload',  icon: Upload,   param: false },
  { id: 2, label: 'Manuel', path: '/automl/manual',  icon: Settings, param: true  },
];

const AGENT_STEPS = [
  { id: 1, label: 'Upload', path: '/automl/upload', icon: Upload, param: false },
  { id: 2, label: 'Agent',  path: '/automl/agent',  icon: Bot,    param: true  },
];

function getActiveStep(pathname) {
  if (pathname.startsWith('/automl/agent'))  return 2;
  if (pathname.startsWith('/automl/manual')) return 2;
  return 1;
}

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const params   = useParams();

  const isAgent = location.pathname.startsWith('/automl/agent');
  const STEPS   = isAgent ? AGENT_STEPS : MANUAL_STEPS;

  const runId = params.runId || location.pathname.split('/').pop();
  const active = getActiveStep(location.pathname);

  function handleStep(step) {
    if (step.id > active) return;
    if (!step.param) {
      navigate(step.path);
    } else if (runId && runId.length >= 6) {
      navigate(`${step.path}/${runId}`);
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-title">Pipeline</div>

      {STEPS.map((step, idx) => {
        const Icon = step.icon;
        const isDone    = step.id < active;
        const isActive  = step.id === active;
        const isDisabled = step.id > active;
        const isLast    = idx === STEPS.length - 1;

        return (
          <div key={step.id}>
            <div
              className={`sidebar-step ${isActive ? 'active' : ''} ${isDone ? 'done' : ''} ${isDisabled ? 'disabled' : ''}`}
              onClick={() => !isDisabled && handleStep(step)}
            >
              <div className="step-number">
                {isDone
                  ? <CheckCircle size={13} />
                  : <span>{step.id}</span>
                }
              </div>
              <Icon size={15} style={{ flexShrink: 0 }} />
              <span>{step.label}</span>
            </div>

            {!isLast && (
              <div className={`sidebar-connector ${isDone ? 'done' : ''}`} />
            )}
          </div>
        );
      })}

      {/* Run ID display */}
      {runId && runId.length >= 6 && (
        <div style={{
          marginTop: 'auto',
          padding: '12px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
        }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: 4, letterSpacing: '0.08em', textTransform: 'uppercase', fontWeight: 600 }}>
            Run ID
          </div>
          <div style={{ fontSize: '12px', color: 'var(--teal)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
            {runId}
          </div>
        </div>
      )}
    </aside>
  );
}
