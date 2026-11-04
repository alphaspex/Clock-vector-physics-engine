import { useState } from 'react';
import type { FormEvent } from 'react';
import { ChevronDown, Cpu, KeyRound, Play, ShieldCheck } from 'lucide-react';
import type { FightCommand, MemorySlot, ModelProvider, PracticeCommand, ReasoningMode } from '../../core/commands';
import NumericInput from './NumericInput';

interface Props {
  backendOnline: boolean;
  busy: boolean;
  activityMessage: string;
  adminToken: string;
  onAdminTokenChange: (token: string) => void;
  onStartPractice: (input: PracticeCommand, token: string) => void;
  onStartFight: (input: FightCommand, token: string) => void;
  activeThinking?: import('../../core/commands').ThinkingItem;
}

const BASETEN_FIXED_IDENTIFIER = 'meta-models/muse-spark-open-1026';

const EFFORTS: ReasoningMode[] = ['minimal', 'low', 'medium', 'high', 'xhigh', 'max'];

type Mode = 'practice' | 'fight';

function SelectField<T extends string>({
  label,
  value,
  values,
  onChange,
  descriptions,
}: {
  label: string;
  value: T;
  values: readonly T[];
  onChange: (value: T) => void;
  descriptions?: Record<T, string>;
}) {
  return (
    <label className="field">
      <span className="field__label">{label}</span>
      <span className="select-wrap">
        <select value={value} onChange={(event) => onChange(event.target.value as T)}>
          {values.map((option) => (
            <option value={option} key={option}>{descriptions?.[option] ?? option}</option>
          ))}
        </select>
        <ChevronDown size={15} aria-hidden="true" />
      </span>
    </label>
  );
}

/**
 * Provider and Model display showing Baseten as the exclusive fixed provider
 * (meta-models/muse-spark-open-1026) for simulations.
 */
function ProviderModelSelector({
  label,
}: {
  label: string;
}) {
  return (
    <div className="provider-block">
      <div className="field-grid field-grid--two">
        <div className="field">
          <span className="field__label">{label} Provider</span>
          <div className="readonly-badge" title="Baseten is the active simulation provider">
            <Cpu size={12} />
            <span>Baseten</span>
          </div>
        </div>

        <div className="field">
          <span className="field__label">Baseten Model (Fixed)</span>
          <div className="readonly-badge" title="Baseten uses fixed open model">
            <Cpu size={12} />
            <span>{BASETEN_FIXED_IDENTIFIER}</span>
          </div>
        </div>
      </div>
      <p className="micro-note">
        Fixed model: meta-models/muse-spark-open-1026 (developer role, fixed model)
      </p>
    </div>
  );
}

export default function LauncherPanel({
  backendOnline,
  busy,
  activityMessage,
  adminToken,
  onAdminTokenChange,
  onStartPractice,
  onStartFight,
  activeThinking,
}: Props) {
  const [mode, setMode] = useState<Mode>('practice');
  const [practiceAI, setPracticeAI] = useState<MemorySlot>('A');
  const [practicePreset] = useState<ModelProvider>('baseten');
  const [practiceEffort, setPracticeEffort] = useState<ReasoningMode>('medium');
  const [practiceInterval, setPracticeInterval] = useState(3);
  const [practiceDuration, setPracticeDuration] = useState(3.0);

  const [practiceTask, setPracticeTask] = useState('Stand and keep standing');
  const [customTask, setCustomTask] = useState('');

  const PRACTICE_TASKS = [
    'Stand and keep standing',
    'Recover from the ground',
    'Keep the head protected',
    'Plant both fists',
    'Maintain the current posture',
    'Move forward',
    'Move backward',
    'Turn left',
    'Turn right',
    'Custom task',
  ];

  const [presetA] = useState<ModelProvider>('baseten');
  const [presetB] = useState<ModelProvider>('baseten');
  const [effortA, setEffortA] = useState<ReasoningMode>('minimal');
  const [effortB, setEffortB] = useState<ReasoningMode>('minimal');
  const [fightInterval, setFightInterval] = useState(3);
  const [fightDuration, setFightDuration] = useState(1.0);

  const canLaunch = backendOnline && !busy && adminToken.trim().length > 0 && (practiceTask !== 'Custom task' || customTask.trim().length > 0);

  const submitPractice = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onStartPractice(
      {
        memorySlot: practiceAI,
        provider: practicePreset,
        thinkingIntervalSeconds: practiceInterval,
        reasoning: practiceEffort,
        durationMinutes: practiceDuration,
        taskText: practiceTask === 'Custom task' ? customTask : practiceTask,
      },
      adminToken.trim(),
    );
  };

  const submitFight = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onStartFight(
      {
        fighterA: { provider: presetA, reasoning: effortA },
        fighterB: { provider: presetB, reasoning: effortB },
        thinkingIntervalSeconds: fightInterval,
        durationMinutes: fightDuration,
      },
      adminToken.trim(),
    );
  };

  return (
    <section className="panel launcher-panel" aria-label="Simulation launcher">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">ROBOTICS CONTROL ROOM / 01</p>
          <h2>New simulation</h2>
        </div>
        <span className="panel-icon"><Play size={16} /></span>
      </div>

      <div className="mode-switch" role="tablist" aria-label="Simulation type">
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'practice'}
          className={mode === 'practice' ? 'is-active' : ''}
          onClick={() => setMode('practice')}
        >
          Practice Drill
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'fight'}
          className={mode === 'fight' ? 'is-active' : ''}
          onClick={() => setMode('fight')}
        >
          Dual Robot Test
        </button>
      </div>

      {mode === 'practice' ? (
        <form className="launcher-form" onSubmit={submitPractice}>
          <div className="field-grid field-grid--two">
            <label className="field">
              <span className="field__label">Robot Entity Memory</span>
              <span className="select-wrap">
                <select value={practiceAI} onChange={(event) => setPracticeAI(event.target.value as MemorySlot)}>
                  <option value="A">Robot Alpha</option>
                  <option value="B">Robot Beta</option>
                </select>
                <ChevronDown size={15} aria-hidden="true" />
              </span>
            </label>
            <NumericInput
              label="Duration"
              value={practiceDuration}
              onChange={setPracticeDuration}
              min={0.2}
              max={30.0}
              step={0.5}
              unit="min"
              isDecimal={true}
            />
          </div>

          <div className="field-grid field-grid--two">
            <NumericInput
              label="Think interval"
              value={practiceInterval}
              onChange={setPracticeInterval}
              min={1}
              max={10}
              step={1}
              unit="sec"
            />
            <SelectField
              label="Reasoning effort"
              value={practiceEffort}
              values={EFFORTS}
              onChange={setPracticeEffort}
            />
          </div>

          <div className="field">
            <span className="field__label">Practice Task</span>
            <span className="select-wrap">
              <select value={practiceTask} onChange={(event) => setPracticeTask(event.target.value)}>
                {PRACTICE_TASKS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <ChevronDown size={15} aria-hidden="true" />
            </span>
          </div>

          {practiceTask === 'Custom task' && (
            <div className="field">
              <span className="field__label">Custom Task Description</span>
              <input
                className="text-input"
                value={customTask}
                onChange={(e) => setCustomTask(e.target.value)}
                placeholder="Enter your own objective..."
                required
              />
            </div>
          )}

          <ProviderModelSelector label="Practice" />

          <button className="button button--primary button--wide" type="submit" disabled={!canLaunch}>
            <Play size={15} fill="currentColor" /> Start practice
          </button>
        </form>
      ) : (
        <form className="launcher-form" onSubmit={submitFight}>
          <div className="fighter-config">
            <div className="fighter-config__heading">
              <span className="fighter-mark">A</span>
              <strong>Robot Alpha</strong>
            </div>
            <ProviderModelSelector label="Robot Alpha" />
            <SelectField
              label="Reasoning effort"
              value={effortA}
              values={EFFORTS}
              onChange={setEffortA}
            />
          </div>

          <div className="fighter-config">
            <div className="fighter-config__heading">
              <span className="fighter-mark fighter-mark--b">B</span>
              <strong>Robot Beta</strong>
            </div>
            <ProviderModelSelector label="Robot Beta" />
            <SelectField
              label="Reasoning effort"
              value={effortB}
              values={EFFORTS}
              onChange={setEffortB}
            />
          </div>

          <div className="field-grid field-grid--two">
            <NumericInput
              label="Fight duration"
              value={fightDuration}
              onChange={setFightDuration}
              min={0.2}
              max={30.0}
              step={0.5}
              unit="min"
              isDecimal={true}
            />
            <NumericInput
              label="Think interval"
              value={fightInterval}
              onChange={setFightInterval}
              min={1}
              max={10}
              step={1}
              unit="sec"
            />
          </div>

          <button className="button button--primary button--wide" type="submit" disabled={!canLaunch}>
            <Play size={15} fill="currentColor" /> Start fight
          </button>
        </form>
      )}

      <div className="token-area">
        <label className="field">
          <span className="field__label"><KeyRound size={12} /> Admin token</span>
          <input
            className="text-input"
            type="password"
            value={adminToken}
            onChange={(event) => onAdminTokenChange(event.target.value)}
            placeholder="Enter server ADMIN_TOKEN"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <p className="micro-note">
          <ShieldCheck size={12} /> Kept in this tab's memory only. Never saved to the project or browser storage.
        </p>
      </div>

      {busy && (
        <div className="activity-inline">
          <span className="spinner" /> <span>{activityMessage}</span>
        </div>
      )}
      {activeThinking && (
        <div className="card" style={{ marginTop: '0.75rem', borderColor: '#3b82f6', background: 'rgba(59, 130, 246, 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.05em', color: '#60a5fa' }}>
              {activeThinking.status === 'described' ? 'PHYSICAL INTERVAL SUMMARY' : 'LIVE INTERVAL STATUS'} ({activeThinking.fighter}) · INTERVAL {activeThinking.interval_index ?? activeThinking.frame ?? 1}
            </span>
            {activeThinking.status === 'described' && activeThinking.wordCount !== undefined && (
              <span style={{ fontSize: '0.65rem', padding: '1px 6px', borderRadius: '4px', background: (activeThinking.wordCount >= 15 && activeThinking.wordCount <= 30) ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: (activeThinking.wordCount >= 15 && activeThinking.wordCount <= 30) ? '#4ade80' : '#f87171' }}>
                {activeThinking.wordCount} words (Target: 15-30)
              </span>
            )}
          </div>
          <p style={{ margin: 0, fontStyle: 'italic', fontSize: '0.8rem', lineHeight: '1.4', color: '#e2e8f0' }}>
            "{activeThinking.text}"
          </p>
        </div>
      )}
      {!backendOnline && (
        <p className="form-hint">Connect the backend before launching a simulation. Saved replays become available when the service is online.</p>
      )}
      {backendOnline && !adminToken.trim() && (
        <p className="form-hint">Read-only mode. Enter the admin token to enable new simulations, live monitoring, and database management.</p>
      )}
    </section>
  );
}
