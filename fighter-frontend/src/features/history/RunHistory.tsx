import { useMemo, useState } from 'react';
import { AlertCircle, Clock3, FileClock, Play, RefreshCw, Film, Swords, Target, CheckSquare, Square } from 'lucide-react';
import type { SavedRun, SimulationJob, SimulationKind } from '../../core/commands';

interface Props {
  practiceRuns: SavedRun[];
  fightRuns: SavedRun[];
  activeJobs: SimulationJob[];
  selected: { kind: SimulationKind; number: number } | null;
  busy: boolean;
  onSelect: (kind: SimulationKind, runNumber: number) => void;
  onCompile: (kind: SimulationKind, runNumber: number) => void;
  onRefresh: () => void;
}

function formatCreated(value?: string): string {
  if (!value) return 'Just now';
  const parsed = new Date(`${value.replace(' ', 'T')}Z`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function RunHistory({
  practiceRuns,
  fightRuns,
  activeJobs,
  selected,
  busy,
  onSelect,
  onCompile,
  onRefresh,
}: Props) {
  const [kind, setKind] = useState<SimulationKind>('fight');
  const [checkedRuns, setCheckedRuns] = useState<Set<number>>(new Set());

  const runs = useMemo(() => (kind === 'fight' ? fightRuns : practiceRuns), [kind, fightRuns, practiceRuns]);

  const uncompiledRuns = useMemo(() => {
    return runs.filter((r) => !r.replayStatus || r.replayStatus === 'not_compiled' || r.replayStatus === 'failed');
  }, [runs]);

  const relevantJobs = useMemo(() => {
    return activeJobs.filter((j) => j.kind === kind && j.state === 'running');
  }, [activeJobs, kind]);

  const toggleCheck = (num: number) => {
    setCheckedRuns((prev) => {
      const next = new Set(prev);
      if (next.has(num)) next.delete(num);
      else next.add(num);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (checkedRuns.size === uncompiledRuns.length) {
      setCheckedRuns(new Set());
    } else {
      setCheckedRuns(new Set(uncompiledRuns.map((r) => r.number)));
    }
  };

  const handleCompileSelected = () => {
    const targets = checkedRuns.size > 0
      ? Array.from(checkedRuns)
      : uncompiledRuns.map((r) => r.number);

    for (const num of targets) {
      onCompile(kind, num);
    }
    setCheckedRuns(new Set());
  };

  return (
    <section className="panel history-panel" aria-label="Simulation history">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">LIBRARY / 02</p>
          <h2>Simulations</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Refresh replay history"
          onClick={onRefresh}
          disabled={busy}
        >
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="history-tabs" role="tablist" aria-label="Replay type">
        <button
          type="button"
          role="tab"
          aria-selected={kind === 'fight'}
          className={kind === 'fight' ? 'is-active' : ''}
          onClick={() => {
            setKind('fight');
            setCheckedRuns(new Set());
          }}
        >
          <Swords size={12} />
          <span>Dual Tests</span>
          <span className="tab-count">{fightRuns.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={kind === 'practice'}
          className={kind === 'practice' ? 'is-active' : ''}
          onClick={() => {
            setKind('practice');
            setCheckedRuns(new Set());
          }}
        >
          <Target size={12} />
          <span>Practice Drills</span>
          <span className="tab-count">{practiceRuns.length}</span>
        </button>
      </div>

      {/* Batch compilation action bar */}
      {uncompiledRuns.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.4rem 0.6rem', background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: '0.75rem' }}>
          <button
            type="button"
            className="text-button"
            style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem', opacity: 0.8 }}
            onClick={toggleSelectAll}
          >
            {checkedRuns.size === uncompiledRuns.length && uncompiledRuns.length > 0 ? (
              <CheckSquare size={13} style={{ color: 'var(--color-primary, #3b82f6)' }} />
            ) : (
              <Square size={13} />
            )}
            <span>{checkedRuns.size > 0 ? `Selected (${checkedRuns.size})` : 'Select All'}</span>
          </button>

          <button
            type="button"
            className="button button--primary"
            style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem', height: '24px' }}
            onClick={handleCompileSelected}
            disabled={busy}
          >
            <Film size={12} style={{ marginRight: '0.3rem' }} />
            <span>
              {checkedRuns.size > 0
                ? `Compile Selected (${checkedRuns.size})`
                : `Compile All Uncompiled (${uncompiledRuns.length})`}
            </span>
          </button>
        </div>
      )}

      {relevantJobs.length === 0 && runs.length === 0 ? (
        <div className="empty-history">
          <FileClock size={22} strokeWidth={1.4} />
          <strong>No {kind} sessions yet</strong>
          <span>Running and completed simulations will appear here.</span>
        </div>
      ) : (
        <div className="history-list">
          {/* Active running simulation jobs */}
          {relevantJobs.map((job) => {
            let badgeText = 'RUNNING';
            if (job.stage === 'saving') badgeText = 'SAVING';
            else if (job.stage === 'decision' && job.decision) badgeText = `DECISION ${job.decision}/${job.targetDecisions || '?'}`;
            else if (job.percent !== undefined) badgeText = `RUNNING ${job.percent}%`;

            const idLabel = job.runNumber ? `#${job.runNumber}` : `Job ${job.id}`;
            return (
              <div key={`job-${job.id}`} className="history-item history-item--pending">
                <span className="history-item__number">{idLabel}</span>
                <span className="history-item__copy">
                  <span className="history-item__title">
                    <strong>{kind === 'fight' ? 'Fight' : 'Practice'} {idLabel}</strong>
                  </span>
                  <small>
                    <Clock3 size={11} /> {formatCreated(job.createdAt)} · Simulation in progress
                  </small>
                </span>
                <span className="status-badge status-badge--active">{badgeText}</span>
              </div>
            );
          })}

          {/* Saved runs */}
          {runs.map((run) => {
            const isSelected = selected?.kind === kind && selected.number === run.number;
            const status = run.replayStatus || 'not_compiled';
            const prog = run.replayProgress;

            const isReady = status === 'ready';
            const isCompiling = status === 'compiling' || status === 'queued' || status === 'validating';
            const isFailed = status === 'failed';
            const isUncompiled = status === 'not_compiled';
            const isChecked = checkedRuns.has(run.number);

            const resultLabel = kind === 'fight'
              ? (run.result ? `Winner: ${run.result}` : 'Draw')
              : `${run.frameCount} frames`;

            return (
              <div
                key={`run-${kind}-${run.number}`}
                className={`history-item ${isSelected ? 'is-selected' : ''} ${!isReady ? 'history-item--pending' : ''}`}
                style={{ flexDirection: 'column', alignItems: 'stretch', gap: '0.4rem' }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  {(isUncompiled || isFailed) && (
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', padding: '0 0.3rem 0 0', cursor: 'pointer', color: isChecked ? 'var(--color-primary, #3b82f6)' : 'inherit' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleCheck(run.number);
                      }}
                      title="Select for compilation"
                    >
                      {isChecked ? <CheckSquare size={14} /> : <Square size={14} style={{ opacity: 0.5 }} />}
                    </button>
                  )}
                  <span className="history-item__number">#{run.number}</span>
                  <div className="history-item__copy" style={{ flex: 1, marginLeft: '0.5rem' }}>
                    <div className="history-item__title">
                      <strong>{kind === 'fight' ? 'Fight' : 'Practice'} #{run.number}</strong>
                      {isFailed && <AlertCircle size={12} className="error-icon" style={{ color: 'var(--color-error, #f87171)', marginLeft: '0.3rem' }} />}
                    </div>
                    <small>
                      <Clock3 size={11} /> {formatCreated(run.createdAt)} · {resultLabel}
                    </small>
                  </div>

                  <span
                    className={`status-badge ${
                      isReady ? 'status-badge--ready' : isFailed ? 'status-badge--failed' : isCompiling ? 'status-badge--active' : ''
                    }`}
                    style={isUncompiled ? { background: 'rgba(255,255,255,0.1)', color: 'var(--text-secondary, #9ca3af)' } : undefined}
                  >
                    {isReady && 'READY'}
                    {isUncompiled && 'NOT COMPILED'}
                    {isCompiling && (status === 'validating' ? 'VALIDATING' : `COMPILING ${prog?.percent ? `${Math.round(prog.percent)}%` : ''}`)}
                    {isFailed && 'FAILED'}
                  </span>
                </div>

                {/* Compilation Progress Bar */}
                {isCompiling && (
                  <div style={{ width: '100%', marginTop: '0.2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', opacity: 0.8, marginBottom: '0.2rem' }}>
                      <span>{status === 'validating' ? 'Validating snapshots…' : `Frames ${prog?.framesGenerated || 0} / ${run.frameCount}`}</span>
                      <span>{prog?.percent ? `${Math.round(prog.percent)}%` : '0%'}</span>
                    </div>
                    <div style={{ height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min(100, Math.max(0, prog?.percent || 0))}%`,
                          background: 'var(--color-primary, #3b82f6)',
                          transition: 'width 0.3s ease',
                        }}
                      />
                    </div>
                  </div>
                )}

                {/* Error message detail for failed compilation */}
                {isFailed && prog?.error && (
                  <div style={{ fontSize: '0.72rem', color: '#f87171', background: 'rgba(248,113,113,0.1)', padding: '0.3rem 0.5rem', borderRadius: '4px' }}>
                    {prog.error}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.2rem', justifyContent: 'flex-end' }}>
                  {(isUncompiled || isFailed) && (
                    <button
                      type="button"
                      className="button button--primary"
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', height: 'auto' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onCompile(kind, run.number);
                      }}
                      disabled={busy}
                    >
                      <Film size={12} style={{ marginRight: '0.3rem' }} />
                      <span>{isFailed ? 'Retry Compile (30 FPS)' : 'Compile Replay (30 FPS)'}</span>
                    </button>
                  )}

                  {isReady && (
                    <button
                      type="button"
                      className="button"
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', height: 'auto', background: '#f0f1eb' }}
                      onClick={() => onSelect(kind, run.number)}
                      disabled={busy}
                    >
                      <Play size={12} style={{ marginRight: '0.3rem' }} />
                      <span>Watch Replay</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
