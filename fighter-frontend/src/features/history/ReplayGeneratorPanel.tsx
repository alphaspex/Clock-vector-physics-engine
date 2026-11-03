import { useMemo, useState } from 'react';
import { Film, Play, RefreshCw, AlertCircle, CheckCircle2, Zap } from 'lucide-react';
import type { SavedRun, SimulationKind } from '../../core/commands';

interface Props {
  practiceRuns: SavedRun[];
  fightRuns: SavedRun[];
  busy: boolean;
  onSelect: (kind: SimulationKind, runNumber: number) => void;
  onCompile: (kind: SimulationKind, runNumber: number) => void;
  onRefresh: () => void;
}

export default function ReplayGeneratorPanel({
  practiceRuns,
  fightRuns,
  busy,
  onSelect,
  onCompile,
  onRefresh,
}: Props) {
  const [filter, setFilter] = useState<'all' | 'uncompiled' | 'failed'>('uncompiled');

  const allRuns = useMemo(() => {
    const combined = [
      ...practiceRuns.map(r => ({ ...r, kind: 'practice' as SimulationKind })),
      ...fightRuns.map(r => ({ ...r, kind: 'fight' as SimulationKind }))
    ];
    return combined.sort((a, b) => {
      // Sort by status priority: failed > uncompiled > compiling > ready
      const statusWeight = (s: string) => {
        if (s === 'failed') return 0;
        if (s === 'not_compiled') return 1;
        if (['compiling', 'queued', 'validating'].includes(s)) return 2;
        return 3;
      };
      const weightA = statusWeight(a.replayStatus || 'not_compiled');
      const weightB = statusWeight(b.replayStatus || 'not_compiled');
      if (weightA !== weightB) return weightA - weightB;
      return b.number - a.number; // Then by number descending
    });
  }, [practiceRuns, fightRuns]);

  const filteredRuns = useMemo(() => {
    if (filter === 'all') return allRuns;
    if (filter === 'uncompiled') return allRuns.filter(r => (r.replayStatus || 'not_compiled') === 'not_compiled');
    if (filter === 'failed') return allRuns.filter(r => r.replayStatus === 'failed');
    return allRuns;
  }, [allRuns, filter]);

  const stats = useMemo(() => {
    const uncompiled = allRuns.filter(r => (r.replayStatus || 'not_compiled') === 'not_compiled').length;
    const failed = allRuns.filter(r => r.replayStatus === 'failed').length;
    const compiling = allRuns.filter(r => ['compiling', 'queued', 'validating'].includes(r.replayStatus || '')).length;
    const ready = allRuns.filter(r => r.replayStatus === 'ready').length;
    return { uncompiled, failed, compiling, ready };
  }, [allRuns]);

  return (
    <div className="control-room" aria-label="Replay Generation Center">
      <div className="monitoring-header">
        <div className="monitoring-header__info">
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Uncompiled Rounds</span>
            <span className="monitoring-stat__val">{stats.uncompiled}</span>
          </div>
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Failed Compilations</span>
            <span className={`monitoring-stat__val ${stats.failed > 0 ? 'text-bad' : ''}`}>{stats.failed}</span>
          </div>
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Active Workers</span>
            <span className="monitoring-stat__val">{stats.compiling}</span>
          </div>
        </div>

        <div className="monitoring-controls">
          <button
            type="button"
            className="icon-button"
            onClick={onRefresh}
            disabled={busy}
            title="Refresh history"
          >
            <RefreshCw size={13} className={busy ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <section className="monitoring-card" style={{ minHeight: '600px' }}>
        <div className="card-heading">
          <div className="flex items-center gap-2">
            <Film size={15} />
            <h3>Replay Generation Queue</h3>
          </div>
          <div className="flex gap-2">
            <button
              className={`db-tab ${filter === 'uncompiled' ? 'is-active' : ''}`}
              style={{ padding: '4px 10px', height: '28px', fontSize: '10px' }}
              onClick={() => setFilter('uncompiled')}
            >
              Uncompiled ({stats.uncompiled})
            </button>
            <button
              className={`db-tab ${filter === 'failed' ? 'is-active' : ''}`}
              style={{ padding: '4px 10px', height: '28px', fontSize: '10px' }}
              onClick={() => setFilter('failed')}
            >
              Failed ({stats.failed})
            </button>
            <button
              className={`db-tab ${filter === 'all' ? 'is-active' : ''}`}
              style={{ padding: '4px 10px', height: '28px', fontSize: '10px' }}
              onClick={() => setFilter('all')}
            >
              All Runs
            </button>
          </div>
        </div>

        {filteredRuns.length === 0 ? (
          <div className="empty-panel">
            <CheckCircle2 size={32} strokeWidth={1} className="text-good" style={{ marginBottom: '0.5rem' }} />
            <h3>All caught up</h3>
            <p>No rounds matching the current filter require compilation.</p>
          </div>
        ) : (
          <div className="db-table-wrap">
            <table className="db-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Kind</th>
                  <th>Created</th>
                  <th>Simulation Detail</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => {
                  const status = run.replayStatus || 'not_compiled';
                  const isReady = status === 'ready';
                  const isCompiling = ['compiling', 'queued', 'validating'].includes(status);
                  const isFailed = status === 'failed';
                  const isUncompiled = status === 'not_compiled';

                  return (
                    <tr key={`${run.kind}-${run.number}`} className={isCompiling ? 'is-selected' : ''}>
                      <td>
                        <span className="font-mono font-bold">#{run.number}</span>
                      </td>
                      <td>
                        <span className="badge badge--neutral" style={{ textTransform: 'capitalize' }}>{run.kind}</span>
                      </td>
                      <td>
                        <small className="font-mono" style={{ opacity: 0.7 }}>{run.createdAt}</small>
                      </td>
                      <td>
                        <div className="flex flex-col gap-1">
                          <span style={{ fontSize: '11px' }}>
                            {run.kind === 'fight' ? (run.result ? `Winner: ${run.result}` : 'Draw') : 'Practice Session'}
                          </span>
                          <span style={{ fontSize: '9px', opacity: 0.6 }}>{run.frameCount} frames recorded at 7 FPS</span>
                        </div>
                      </td>
                      <td>
                        <span className={`status-badge ${isReady ? 'status-badge--ready' : isCompiling ? 'status-badge--active' : isFailed ? 'status-badge--failed' : ''}`}>
                          {status.replace('_', ' ').toUpperCase()}
                          {isCompiling && run.replayProgress?.percent && ` ${Math.round(Number(run.replayProgress.percent))}%`}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="flex justify-end gap-2">
                          {(isUncompiled || isFailed) && (
                            <button
                              className="button button--primary"
                              style={{ padding: '4px 10px', height: '28px', fontSize: '10px' }}
                              onClick={() => onCompile(run.kind, run.number)}
                              disabled={busy || isCompiling}
                            >
                              <Zap size={11} fill="currentColor" />
                              <span>{isFailed ? 'Retry Compile' : 'Compile 30 FPS'}</span>
                            </button>
                          )}
                          {isReady && (
                            <button
                              className="button"
                              style={{ padding: '4px 10px', height: '28px', fontSize: '10px', background: '#f0f1eb' }}
                              onClick={() => onSelect(run.kind, run.number)}
                            >
                              <Play size={11} fill="currentColor" />
                              <span>Watch</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer className="form-hint" style={{ marginTop: '0' }}>
        <div className="flex items-center gap-2">
          <AlertCircle size={14} />
          <span> Replay snapshots are generated server-side at 30 FPS for high-fidelity viewing. This process is intensive and runs in the background.</span>
        </div>
      </footer>
    </div>
  );
}
