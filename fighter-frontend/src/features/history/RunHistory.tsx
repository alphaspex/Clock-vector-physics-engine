import { useMemo, useState } from 'react';
import { AlertCircle, Clock3, FileClock, RefreshCw, Swords, Target } from 'lucide-react';
import type { SavedRun, SimulationJob, SimulationKind } from '../../core/commands';

interface Props {
  practiceRuns: SavedRun[];
  fightRuns: SavedRun[];
  activeJobs: SimulationJob[];
  selected: { kind: SimulationKind; number: number } | null;
  busy: boolean;
  onSelect: (kind: SimulationKind, runNumber: number) => void;
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
  onRefresh,
}: Props) {
  const [kind, setKind] = useState<SimulationKind>('fight');

  const runs = useMemo(() => (kind === 'fight' ? fightRuns : practiceRuns), [kind, fightRuns, practiceRuns]);

  // Find active or recent jobs for this simulation kind
  const relevantJobs = useMemo(() => {
    return activeJobs.filter((j) => j.kind === kind);
  }, [activeJobs, kind]);

  // Combine jobs and runs into unified list
  const unifiedItems = useMemo(() => {
    const items: Array<{
      key: string;
      idLabel: string;
      runNumber?: number;
      kind: SimulationKind;
      status: 'running' | 'saving' | 'preparing_replay' | 'ready' | 'failed';
      badgeText: string;
      created: string;
      metaText: string;
      isClickable: boolean;
      errorMessage?: string;
    }> = [];

    // Active or in-progress jobs first
    for (const job of relevantJobs) {

      if (job.state === 'running' || job.stage === 'saving' || job.stage === 'preparing_replay') {
        let badgeText = 'RUNNING';
        let status: 'running' | 'saving' | 'preparing_replay' = 'running';

        if (job.stage === 'saving') {
          badgeText = 'SAVING';
          status = 'saving';
        } else if (job.stage === 'preparing_replay') {
          badgeText = 'PREPARING REPLAY';
          status = 'preparing_replay';
        } else if (job.stage === 'decision' && job.decision) {
          badgeText = `DECISION ${job.decision}/${job.targetDecisions || '?'}`;
        } else if (job.percent !== undefined) {
          badgeText = `RUNNING ${job.percent}%`;
        }

        const idLabel = job.runNumber ? `#${job.runNumber}` : `Job ${job.id}`;
        items.push({
          key: `job-${job.id}`,
          idLabel,
          runNumber: job.runNumber,
          kind,
          status,
          badgeText,
          created: formatCreated(job.createdAt),
          metaText: job.runNumber ? `Assigning run #${job.runNumber}` : `Simulation active (${job.elapsedMs ? `${Math.round(job.elapsedMs / 1000)}s` : 'starting'})`,
          isClickable: false,
        });
      } else if (job.state === 'error') {
        items.push({
          key: `job-${job.id}`,
          idLabel: job.runNumber ? `#${job.runNumber}` : `Job ${job.id}`,
          runNumber: job.runNumber,
          kind,
          status: 'failed',
          badgeText: 'FAILED',
          created: formatCreated(job.createdAt),
          metaText: job.errorMessage || 'Simulation failed',
          isClickable: false,
          errorMessage: job.errorMessage,
        });
      }
    }

    // Then saved ready runs
    for (const run of runs) {
      const resultLabel = kind === 'fight'
        ? (run.result ? `Winner: ${run.result}` : 'Draw')
        : `${run.frameCount} frames`;

      items.push({
        key: `run-${kind}-${run.number}`,
        idLabel: `#${run.number}`,
        runNumber: run.number,
        kind,
        status: 'ready',
        badgeText: 'READY',
        created: formatCreated(run.createdAt),
        metaText: resultLabel,
        isClickable: true,
      });
    }

    return items;
  }, [relevantJobs, runs, kind]);

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
          onClick={() => setKind('fight')}
        >
          <Swords size={12} />
          <span>Fights</span>
          <span className="tab-count">{fightRuns.length}</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={kind === 'practice'}
          className={kind === 'practice' ? 'is-active' : ''}
          onClick={() => setKind('practice')}
        >
          <Target size={12} />
          <span>Practice</span>
          <span className="tab-count">{practiceRuns.length}</span>
        </button>
      </div>

      {unifiedItems.length === 0 ? (
        <div className="empty-history">
          <FileClock size={22} strokeWidth={1.4} />
          <strong>No {kind} sessions yet</strong>
          <span>Running and completed simulations will appear here.</span>
        </div>
      ) : (
        <div className="history-list">
          {unifiedItems.map((item) => {
            const isSelected = item.runNumber && selected?.kind === kind && selected.number === item.runNumber;
            const isReady = item.status === 'ready';
            const isFailed = item.status === 'failed';

            return (
              <button
                type="button"
                key={item.key}
                className={`history-item ${isSelected ? 'is-selected' : ''} ${!isReady ? 'history-item--pending' : ''}`}
                onClick={() => {
                  if (item.isClickable && item.runNumber) {
                    onSelect(kind, item.runNumber);
                  }
                }}
                disabled={!item.isClickable || busy}
                title={item.errorMessage || (isReady ? `Click to load replay #${item.runNumber}` : item.badgeText)}
              >
                <span className="history-item__number">{item.idLabel}</span>
                <span className="history-item__copy">
                  <span className="history-item__title">
                    <strong>{kind === 'fight' ? 'Fight' : 'Practice'} {item.idLabel}</strong>
                    {isFailed && <AlertCircle size={11} className="error-icon" />}
                  </span>
                  <small>
                    <Clock3 size={11} /> {item.created} · {item.metaText}
                  </small>
                </span>
                <span
                  className={`status-badge ${
                    isReady ? 'status-badge--ready' : isFailed ? 'status-badge--failed' : 'status-badge--active'
                  }`}
                >
                  {item.badgeText}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
