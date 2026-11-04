import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Cpu,
  Edit3,
  Layers,
  Loader2,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Save,
  Zap,
} from 'lucide-react';
import type { ActivityEvent, SimulationJob } from '../../core/commands';
import { api } from '../../io/client';
import type { ProviderConfigWire, ApiCheckWireResponse } from '../../io/contracts';

interface Props {
  jobs: SimulationJob[];
  events: ActivityEvent[];
  backendOnline: boolean;
  lastHealthCheck: string | null;
  adminToken: string;
  onRefresh: () => void;
}

export default function ControlRoomPanel({
  jobs,
  events,
  backendOnline,
  lastHealthCheck,
  adminToken,
  onRefresh,
}: Props) {
  const [autoPoll, setAutoPoll] = useState(true);
  const [config, setConfig] = useState<Record<string, ProviderConfigWire>>({});
  const [diagnosticResults, setDiagnosticResults] = useState<Record<string, ApiCheckWireResponse & { checking?: boolean }>>({});
  const [editModel, setEditModel] = useState<{ preset: string; val: string } | null>(null);

  const loadConfig = useCallback(async () => {
    if (!adminToken.trim() || !backendOnline) return;
    try {
      const res = await api.getConfig(adminToken.trim());
      setConfig(res);
    } catch { /* ignore */ }
  }, [adminToken, backendOnline]);

  // Auto-polling interval every 1.5 seconds when active
  useEffect(() => {
    if (!autoPoll || !adminToken.trim() || !backendOnline) return;
    const interval = setInterval(() => {
      onRefresh();
    }, 1500);
    return () => clearInterval(interval);
  }, [autoPoll, adminToken, backendOnline, onRefresh]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const activeJobs = jobs.filter((j) => j.state === 'running');
  const recentJobs = jobs.slice(0, 10);

  const handleCheckApi = async (preset: string) => {
    setDiagnosticResults(prev => ({ ...prev, [preset]: { ...prev[preset], checking: true, model: config[preset]?.model || '' } }));
    try {
      const res = await api.checkApi(adminToken.trim(), preset);
      setDiagnosticResults(prev => ({ ...prev, [preset]: { ...res, checking: false } }));
    } catch (err) {
      setDiagnosticResults(prev => ({
        ...prev,
        [preset]: { ok: false, error: err instanceof Error ? err.message : 'Unknown error', checking: false, model: config[preset]?.model || '' }
      }));
    }
  };

  const handleSaveModel = async () => {
    if (!editModel) return;
    try {
      await api.setModelOverride(adminToken.trim(), editModel.preset, editModel.val);
      setEditModel(null);
      await loadConfig();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to save model override');
    }
  };

  return (
    <div className="control-room" aria-label="Control room & live monitoring">
      {/* Top status bar */}
      <div className="monitoring-header">
        <div className="monitoring-header__info">
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Backend Connectivity</span>
            <span className={`monitoring-stat__val ${backendOnline ? 'text-good' : 'text-bad'}`}>
              <Radio size={13} /> {backendOnline ? 'Online' : 'Offline'}
            </span>
          </div>
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Last Health Ping</span>
            <span className="monitoring-stat__val">{lastHealthCheck || 'Checking...'}</span>
          </div>
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Active Simulations</span>
            <span className="monitoring-stat__val">{activeJobs.length} running</span>
          </div>
        </div>

        <div className="monitoring-controls">
          <button
            type="button"
            className={`button button--small ${autoPoll ? 'button--active' : ''}`}
            onClick={() => setAutoPoll(!autoPoll)}
            title={autoPoll ? 'Pause auto-polling' : 'Resume auto-polling'}
          >
            {autoPoll ? <Pause size={12} /> : <Play size={12} />}
            <span>{autoPoll ? 'Auto (1.5s)' : 'Paused'}</span>
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => { onRefresh(); void loadConfig(); }}
            title="Refresh now"
            aria-label="Refresh monitoring data"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {!adminToken.trim() && (
        <div className="notice-banner">
          <AlertTriangle size={15} />
          <span>Enter the admin token in the TV launcher panel to access live operational monitoring, event feeds, and API diagnostics.</span>
        </div>
      )}

      {/* Diagnostic & Model Config Section */}
      {adminToken.trim() && backendOnline && (
        <section className="monitoring-card monitoring-card--diagnostic" aria-label="API Diagnostics & Configuration">
          <div className="card-heading">
            <div className="flex items-center gap-2">
              <Zap size={15} className="text-yellow-500" />
              <h3>API diagnostics & model configuration</h3>
            </div>
            <button className="button button--small" onClick={() => void loadConfig()}><RefreshCw size={11} /> Refresh config</button>
          </div>

          <div className="diagnostic-grid">
            {Object.entries(config).map(([preset, p]) => {
              const result = diagnosticResults[preset];
              const isEditing = editModel?.preset === preset;

              return (
                <div key={preset} className={`diagnostic-card ${result?.ok === false ? 'diagnostic-card--err' : result?.ok ? 'diagnostic-card--ok' : ''}`}>
                  <div className="diagnostic-card__head">
                    <div className="flex flex-col">
                      <strong className="preset-name">{preset}</strong>
                      <span className="base-url">{p.base}</span>
                    </div>
                    <div className="flex gap-1">
                      <button
                        className="icon-button icon-button--small"
                        onClick={() => handleCheckApi(preset)}
                        disabled={result?.checking}
                        title="Fast check this provider"
                      >
                        {result?.checking ? <Loader2 size={12} className="animate-spin" /> : <Activity size={12} />}
                      </button>
                      <button
                        className={`icon-button icon-button--small ${p.overridden ? 'text-blue-500' : ''}`}
                        onClick={() => setEditModel(isEditing ? null : { preset, val: p.model })}
                        title="Override model identifier"
                      >
                        <Edit3 size={12} />
                      </button>
                    </div>
                  </div>

                  <div className="diagnostic-card__body">
                    <div className="model-display">
                      <span className="label">Active Model:</span>
                      {isEditing ? (
                        <div className="flex gap-1 mt-1">
                          <input
                            className="text-input text-input--compact"
                            value={editModel.val}
                            onChange={e => setEditModel({ ...editModel, val: e.target.value })}
                            autoFocus
                          />
                          <button className="icon-button icon-button--small icon-button--good" onClick={handleSaveModel}>
                            <Save size={12} />
                          </button>
                        </div>
                      ) : (
                        <code className={`model-id ${p.overridden ? 'model-id--overridden' : ''}`}>{p.model}</code>
                      )}
                    </div>

                    {result && !result.checking && (
                      <div className={`check-result ${result.ok ? 'check-result--ok' : 'check-result--err'}`}>
                        {result.ok ? (
                          <>
                            <CheckCircle2 size={12} />
                            <span>OK ({result.elapsed_ms}ms): "{result.text}"</span>
                          </>
                        ) : (
                          <>
                            <AlertCircle size={12} />
                            <span className="error-text">FAIL: {result.error}</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Main monitoring grid */}
      <div className="monitoring-grid">
        {/* Active & Recent Jobs Column */}
        <section className="monitoring-card" aria-label="Simulations lifecycle">
          <div className="card-heading">
            <div className="flex items-center gap-2">
              <Activity size={15} />
              <h3>Simulations in progress</h3>
            </div>
            <span className="badge badge--neutral">{activeJobs.length} active</span>
          </div>

          {jobs.length === 0 ? (
            <div className="empty-panel">
              <Clock size={20} />
              <p>No recorded simulation jobs yet.</p>
            </div>
          ) : (
            <div className="jobs-feed">
              {recentJobs.map((job) => {
                const isActive = job.state === 'running';
                const isFailed = job.state === 'error';
                const elapsedSec = job.elapsedMs ? Math.round(job.elapsedMs / 1000) : 0;

                return (
                  <div
                    key={job.id}
                    className={`job-card ${isActive ? 'job-card--active' : isFailed ? 'job-card--failed' : 'job-card--done'}`}
                  >
                    <div className="job-card__header">
                      <span className="job-badge">{job.kind.toUpperCase()}</span>
                      <strong className="job-id">Job {job.id}</strong>
                      {job.runNumber && <span className="run-tag">Run #{job.runNumber}</span>}
                      <span
                        className={`status-pill ${
                          isActive ? 'status-pill--active' : isFailed ? 'status-pill--failed' : 'status-pill--ready'
                        }`}
                      >
                        {job.stage.toUpperCase()}
                      </span>
                    </div>

                    <div className="job-card__meta">
                      <span>Started: {job.createdAt || 'Recent'}</span>
                      <span>Elapsed: {elapsedSec}s</span>
                      {Boolean(job.params?.duration_minutes) && (
                        <span>Configured: {String(job.params?.duration_minutes)}m</span>
                      )}
                    </div>

                    {/* Stage & Progress bar */}
                    {isActive && (
                      <div className="job-progress">
                        <div className="job-progress__bar">
                          <div
                            className="job-progress__fill"
                            style={{ width: `${Math.min(100, Math.max(5, job.percent || 15))}%` }}
                          />
                        </div>
                        <div className="job-progress__labels">
                          <span>
                            Stage: <strong>{job.stage}</strong>
                            {job.decision ? ` (decision ${job.decision}/${job.targetDecisions || '?'})` : ''}
                          </span>
                          <span>{job.percent !== undefined ? `${job.percent}%` : 'Advancing...'}</span>
                        </div>
                      </div>
                    )}

                    {/* Model & Providers */}
                    <div className="job-models">
                      {Boolean(job.params?.preset) && (
                        <span className="model-chip">
                          <Cpu size={10} /> Preset: {String(job.params?.preset)}
                        </span>
                      )}
                      {Array.isArray(job.params?.presets) && (
                        <div className="flex gap-1">
                          <span className="model-chip">A: {String(job.params?.presets[0])}</span>
                          <span className="model-chip">B: {String(job.params?.presets[1])}</span>
                        </div>
                      )}
                      {job.usage && (
                        <span className="token-chip">
                          <Zap size={10} /> Tokens: {job.usage.prompt + job.usage.completion} (reasoning: {job.usage.reasoning})
                        </span>
                      )}
                    </div>

                    {/* Section 10: Visible INTERVAL DESCRIPTION (THINKING) Process */}
                    {(job.latestThinking || (job.thinkingHistory && job.thinkingHistory.length > 0)) && (
                      <div className="job-thinking-panel" style={{ marginTop: '0.6rem', padding: '0.6rem', background: '#182030', borderRadius: '6px', border: '1px solid #2a364f' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.05em', color: '#38bdf8' }}>
                            INTERVAL DESCRIPTION (THINKING)
                          </span>
                          {job.latestThinking?.wordCount && (
                            <span style={{ fontSize: '0.68rem', color: job.latestThinking.wordCount === 20 ? '#34d399' : '#f59e0b' }}>
                              {job.latestThinking.wordCount} words {job.latestThinking.wordCount === 20 ? '✓' : '(20 required)'}
                            </span>
                          )}
                        </div>
                        {job.latestThinking && (
                          <div style={{ fontSize: '0.82rem', fontStyle: 'italic', color: '#e2e8f0', lineHeight: 1.4, marginBottom: '0.4rem' }}>
                            "{job.latestThinking.text}"
                          </div>
                        )}
                        {job.thinkingHistory && job.thinkingHistory.length > 1 && (
                          <details style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                            <summary style={{ cursor: 'pointer', outline: 'none' }}>
                              View history ({job.thinkingHistory.length} intervals)
                            </summary>
                            <ol style={{ paddingLeft: '1.2rem', marginTop: '0.3rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                              {job.thinkingHistory.map((th, thIdx) => (
                                <li key={thIdx}>
                                  <span style={{ color: '#64748b' }}>[Frame {th.frame || '?'}] Fighter {th.fighter}: </span>
                                  <span>{th.text}</span>
                                </li>
                              ))}
                            </ol>
                          </details>
                        )}
                      </div>
                    )}

                    {job.errorMessage && (
                      <div className="job-error">
                        <AlertTriangle size={12} />
                        <span>{job.errorMessage}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Chronological Event Log Column */}
        <section className="monitoring-card" aria-label="Chronological event log">
          <div className="card-heading">
            <div className="flex items-center gap-2">
              <Layers size={15} />
              <h3>Activity event feed</h3>
            </div>
            <span className="badge badge--neutral">{events.length} events</span>
          </div>

          {events.length === 0 ? (
            <div className="empty-panel">
              <Activity size={20} />
              <p>No activity events recorded yet.</p>
            </div>
          ) : (
            <div className="events-stream">
              {events.slice(0, 50).map((ev) => {
                const isError = ev.severity === 'error';
                const isWarn = ev.severity === 'warn';

                return (
                  <div
                    key={ev.id}
                    className={`event-entry ${isError ? 'event-entry--error' : isWarn ? 'event-entry--warn' : ''}`}
                  >
                    <div className="event-entry__head">
                      <span className="event-time">
                        {ev.createdAt ? ev.createdAt.split(' ')[1] || ev.createdAt : 'Now'}
                      </span>
                      <span className={`severity-tag severity-tag--${ev.severity}`}>
                        {ev.severity.toUpperCase()}
                      </span>
                      <span className="stage-tag">{ev.stage}</span>
                      {ev.jobId && <span className="job-ref">{ev.jobId}</span>}
                    </div>
                    <div className="event-entry__message">{ev.message}</div>
                    {ev.metadata && Object.keys(ev.metadata).length > 0 && (
                      <details className="event-metadata">
                        <summary>Metadata payload</summary>
                        <pre>{JSON.stringify(ev.metadata, null, 2)}</pre>
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
