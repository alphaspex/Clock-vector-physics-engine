import { useMemo, useState } from 'react';
import { Clock3, FileClock, RefreshCw } from 'lucide-react';
import type { SavedRun, SimulationKind } from '../../core/commands';

interface Props {
  practiceRuns: SavedRun[];
  fightRuns: SavedRun[];
  selected: { kind: SimulationKind; number: number } | null;
  busy: boolean;
  onSelect: (kind: SimulationKind, runNumber: number) => void;
  onRefresh: () => void;
}

function formatCreated(value: string): string {
  // The Python backend stores UTC as a plain timestamp string.
  const parsed = new Date(`${value.replace(' ', 'T')}Z`);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

export default function RunHistory({ practiceRuns, fightRuns, selected, busy, onSelect, onRefresh }: Props) {
  const [kind, setKind] = useState<SimulationKind>('fight');
  const runs = useMemo(() => kind === 'fight' ? fightRuns : practiceRuns, [kind, fightRuns, practiceRuns]);

  return (
    <section className="panel history-panel" aria-label="Saved replays">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">LIBRARY / 02</p>
          <h2>Saved replays</h2>
        </div>
        <button className="icon-button" type="button" aria-label="Refresh replay history" onClick={onRefresh} disabled={busy}>
          <RefreshCw size={15} />
        </button>
      </div>

      <div className="history-tabs" role="tablist" aria-label="Replay type">
        <button type="button" role="tab" aria-selected={kind === 'fight'} className={kind === 'fight' ? 'is-active' : ''} onClick={() => setKind('fight')}>
          Fights <span>{fightRuns.length}</span>
        </button>
        <button type="button" role="tab" aria-selected={kind === 'practice'} className={kind === 'practice' ? 'is-active' : ''} onClick={() => setKind('practice')}>
          Practice <span>{practiceRuns.length}</span>
        </button>
      </div>

      {runs.length === 0 ? (
        <div className="empty-history">
          <FileClock size={22} strokeWidth={1.4} />
          <strong>No {kind} runs yet</strong>
          <span>Completed simulations will appear here.</span>
        </div>
      ) : (
        <div className="history-list">
          {runs.map((run) => {
            const isSelected = selected?.kind === kind && selected.number === run.number;
            return (
              <button
                type="button"
                key={`${kind}-${run.number}`}
                className={`history-item ${isSelected ? 'is-selected' : ''}`}
                onClick={() => onSelect(kind, run.number)}
                disabled={busy}
              >
                <span className="history-item__number">{String(run.number).padStart(3, '0')}</span>
                <span className="history-item__copy">
                  <strong>{kind === 'fight' ? 'Fight' : 'Practice'} #{run.number}</strong>
                  <small><Clock3 size={11} /> {formatCreated(run.createdAt)}</small>
                </span>
                <span className={`result-label ${run.result ? 'result-label--done' : ''}`}>
                  {run.result ? String(run.result).toUpperCase() : '—'}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
