import { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Clock,
  Cpu,
  Layers,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Zap,
} from 'lucide-react';
import type { ActivityEvent, SimulationJob } from '../../core/commands';

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

  // Auto-polling interval every 1.5 seconds when active
  useEffect(() => {
    if (!autoPoll || !adminToken.trim() || !backendOnline) return;
    const interval = setInterval(() => {
      onRefresh();
    }, 1500);
    return () => clearInterval(interval);
  }, [autoPoll, adminToken, backendOnline, onRefresh]);

  const activeJobs = jobs.filter((j) => j.state === 'running');
  const recentJobs = jobs.slice(0, 10);

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
            onClick={onRefresh}
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
          <span>Enter the admin token in the TV launcher panel to access live operational monitoring and event feeds.</span>
        </div>
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
