import { useState } from 'react';
import type { FormEvent } from 'react';
import { ChevronDown, KeyRound, Play, ShieldCheck } from 'lucide-react';
import type { FightCommand, MemorySlot, ModelProvider, PracticeCommand, ReasoningMode } from '../../core/commands';

interface Props {
  backendOnline: boolean;
  busy: boolean;
  activityMessage: string;
  onStartPractice: (input: PracticeCommand, token: string) => void;
  onStartFight: (input: FightCommand, token: string) => void;
}

const PROVIDERS: { value: ModelProvider; label: string; note: string }[] = [
  { value: 'meta_contrib', label: 'Meta · Contributor', note: 'muse-spark-1.3-contributor' },
  { value: 'meta', label: 'Meta · Muse Spark', note: 'muse-spark-1.3' },
  { value: 'baseten', label: 'Baseten · Open', note: 'meta-models/muse-spark-open' },
];

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

const providerLabels = Object.fromEntries(PROVIDERS.map((provider) => [provider.value, provider.label])) as Record<ModelProvider, string>;

/**
 * UI-only launcher. Change a select to a text box, add a button, or rearrange
 * this panel without touching the API client or 3D viewer. Its callbacks emit
 * the same typed command objects consumed by the app controller.
 */
export default function LauncherPanel({ backendOnline, busy, activityMessage, onStartPractice, onStartFight }: Props) {
  const [mode, setMode] = useState<Mode>('practice');
  const [adminToken, setAdminToken] = useState('');
  const [practiceAI, setPracticeAI] = useState<MemorySlot>('A');
  const [practicePreset, setPracticePreset] = useState<ModelProvider>('meta_contrib');
  const [practiceEffort, setPracticeEffort] = useState<ReasoningMode>('high');
  const [practiceInterval, setPracticeInterval] = useState(3);
  const [presetA, setPresetA] = useState<ModelProvider>('meta_contrib');
  const [presetB, setPresetB] = useState<ModelProvider>('meta_contrib');
  const [effortA, setEffortA] = useState<ReasoningMode>('minimal');
  const [effortB, setEffortB] = useState<ReasoningMode>('minimal');
  const [fightInterval, setFightInterval] = useState(3);

  const canLaunch = backendOnline && !busy && adminToken.trim().length > 0;
  const providerOptions = PROVIDERS.map((provider) => provider.value);

  const submitPractice = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onStartPractice({ memorySlot: practiceAI, provider: practicePreset, thinkingIntervalSeconds: practiceInterval, reasoning: practiceEffort }, adminToken.trim());
  };

  const submitFight = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onStartFight({
      fighterA: { provider: presetA, reasoning: effortA },
      fighterB: { provider: presetB, reasoning: effortB },
      thinkingIntervalSeconds: fightInterval,
    }, adminToken.trim());
  };

  return (
    <section className="panel launcher-panel" aria-label="Simulation launcher">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">CONTROL ROOM / 01</p>
          <h2>New simulation</h2>
        </div>
        <span className="panel-icon"><Play size={16} /></span>
      </div>

      <div className="mode-switch" role="tablist" aria-label="Simulation type">
        <button type="button" role="tab" aria-selected={mode === 'practice'} className={mode === 'practice' ? 'is-active' : ''} onClick={() => setMode('practice')}>
          Practice
        </button>
        <button type="button" role="tab" aria-selected={mode === 'fight'} className={mode === 'fight' ? 'is-active' : ''} onClick={() => setMode('fight')}>
          Fight
        </button>
      </div>

      {mode === 'practice' ? (
        <form className="launcher-form" onSubmit={submitPractice}>
          <div className="field-grid field-grid--two">
            <label className="field">
              <span className="field__label">AI memory</span>
              <span className="select-wrap">
                <select value={practiceAI} onChange={(event) => setPracticeAI(event.target.value as MemorySlot)}>
                  <option value="A">Fighter A</option>
                  <option value="B">Fighter B</option>
                </select>
                <ChevronDown size={15} aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span className="field__label">Think interval</span>
              <span className="number-wrap">
                <input type="number" min={1} max={10} step={1} value={practiceInterval} onChange={(event) => setPracticeInterval(Math.min(10, Math.max(1, Number(event.target.value) || 1)))} />
                <span>sec</span>
              </span>
            </label>
          </div>
          <SelectField label="AI provider" value={practicePreset} values={providerOptions} onChange={setPracticePreset} descriptions={providerLabels} />
          <SelectField label="Reasoning effort" value={practiceEffort} values={EFFORTS} onChange={setPracticeEffort} />
          <button className="button button--primary button--wide" type="submit" disabled={!canLaunch}>
            <Play size={15} fill="currentColor" /> Start practice
          </button>
        </form>
      ) : (
        <form className="launcher-form" onSubmit={submitFight}>
          <div className="fighter-config">
            <div className="fighter-config__heading"><span className="fighter-mark">A</span><strong>Fighter A</strong></div>
            <SelectField label="AI provider" value={presetA} values={providerOptions} onChange={setPresetA} descriptions={providerLabels} />
            <SelectField label="Reasoning effort" value={effortA} values={EFFORTS} onChange={setEffortA} />
          </div>
          <div className="fighter-config">
            <div className="fighter-config__heading"><span className="fighter-mark fighter-mark--b">B</span><strong>Fighter B</strong></div>
            <SelectField label="AI provider" value={presetB} values={providerOptions} onChange={setPresetB} descriptions={providerLabels} />
            <SelectField label="Reasoning effort" value={effortB} values={EFFORTS} onChange={setEffortB} />
          </div>
          <label className="field">
            <span className="field__label">Think interval</span>
            <span className="number-wrap">
              <input type="number" min={1} max={10} step={1} value={fightInterval} onChange={(event) => setFightInterval(Math.min(10, Math.max(1, Number(event.target.value) || 1)))} />
              <span>sec</span>
            </span>
          </label>
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
            onChange={(event) => setAdminToken(event.target.value)}
            placeholder="Enter server ADMIN_TOKEN"
            autoComplete="off"
            spellCheck={false}
          />
        </label>
        <p className="micro-note"><ShieldCheck size={12} /> Kept in this tab's memory only. Never saved to the project or browser storage.</p>
      </div>

      {busy && <div className="activity-inline"><span className="spinner" /> <span>{activityMessage}</span></div>}
      {!backendOnline && <p className="form-hint">Connect the backend before launching a simulation. Saved replays become available when the service is online.</p>}
      {backendOnline && !adminToken.trim() && <p className="form-hint">Read-only mode. Enter the admin token to enable new simulations.</p>}
    </section>
  );
}
