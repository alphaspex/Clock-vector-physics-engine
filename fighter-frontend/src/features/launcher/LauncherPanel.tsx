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

type ProviderFamily = 'meta' | 'baseten';

interface ModelChoice {
  value: ModelProvider;
  label: string;
  identifier: string;
}

const META_MODELS: ModelChoice[] = [
  { value: 'meta_contrib', label: 'Muse Spark 1.3 Contributor', identifier: 'muse-spark-1.3-contributor' },
  { value: 'meta', label: 'Muse Spark 1.3', identifier: 'muse-spark-1.3' },
];

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
 * Provider and Model selector ensuring Meta offers its two exact models,
 * and Baseten displays only its fixed model (meta-models/muse-spark-open-1026) as read-only.
 */
function ProviderModelSelector({
  label,
  currentPreset,
  onChangePreset,
}: {
  label: string;
  currentPreset: ModelProvider;
  onChangePreset: (preset: ModelProvider) => void;
}) {
  const family: ProviderFamily = currentPreset === 'baseten' ? 'baseten' : 'meta';

  const handleFamilyChange = (nextFamily: ProviderFamily) => {
    if (nextFamily === 'baseten') {
      onChangePreset('baseten');
    } else {
      onChangePreset('meta_contrib');
    }
  };

  return (
    <div className="provider-block">
      <div className="field-grid field-grid--two">
        <label className="field">
          <span className="field__label">{label} Provider</span>
          <span className="select-wrap">
            <select
              value={family}
              onChange={(e) => handleFamilyChange(e.target.value as ProviderFamily)}
            >
              <option value="meta">Meta</option>
              <option value="baseten">Baseten</option>
            </select>
            <ChevronDown size={15} aria-hidden="true" />
          </span>
        </label>

        {family === 'meta' ? (
          <label className="field">
            <span className="field__label">Meta Model</span>
            <span className="select-wrap">
              <select
                value={currentPreset}
                onChange={(e) => onChangePreset(e.target.value as ModelProvider)}
              >
                {META_MODELS.map((m) => (
                  <option value={m.value} key={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={15} aria-hidden="true" />
            </span>
          </label>
        ) : (
          <div className="field">
            <span className="field__label">Baseten Model (Fixed)</span>
            <div className="readonly-badge" title="Baseten uses fixed open model">
              <Cpu size={12} />
              <span>{BASETEN_FIXED_IDENTIFIER}</span>
            </div>
          </div>
        )}
      </div>
      <p className="micro-note">
        {family === 'meta'
          ? currentPreset === 'meta_contrib'
            ? 'Model identifier: muse-spark-1.3-contributor (system role, reasoning supported)'
            : 'Model identifier: muse-spark-1.3 (system role, reasoning supported)'
          : 'Fixed model: meta-models/muse-spark-open-1026 (developer role, fixed model)'}
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
  const [practicePreset, setPracticePreset] = useState<ModelProvider>('meta_contrib');
  const [practiceEffort, setPracticeEffort] = useState<ReasoningMode>('high');
  const [practiceInterval, setPracticeInterval] = useState(3);
  const [practiceDuration, setPracticeDuration] = useState(3.0);

  const [presetA, setPresetA] = useState<ModelProvider>('meta_contrib');
  const [presetB, setPresetB] = useState<ModelProvider>('baseten');
  const [effortA, setEffortA] = useState<ReasoningMode>('minimal');
  const [effortB, setEffortB] = useState<ReasoningMode>('minimal');
  const [fightInterval, setFightInterval] = useState(3);
  const [fightDuration, setFightDuration] = useState(1.0);

  const canLaunch = backendOnline && !busy && adminToken.trim().length > 0;

  const submitPractice = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onStartPractice(
      {
        memorySlot: practiceAI,
        provider: practicePreset,
        thinkingIntervalSeconds: practiceInterval,
        reasoning: practiceEffort,
        durationMinutes: practiceDuration,
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
          <p className="eyebrow">CONTROL ROOM / 01</p>
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
          Practice
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'fight'}
          className={mode === 'fight' ? 'is-active' : ''}
          onClick={() => setMode('fight')}
        >
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

          <ProviderModelSelector
            label="Practice"
            currentPreset={practicePreset}
            onChangePreset={setPracticePreset}
          />

          <button className="button button--primary button--wide" type="submit" disabled={!canLaunch}>
            <Play size={15} fill="currentColor" /> Start practice
          </button>
        </form>
      ) : (
        <form className="launcher-form" onSubmit={submitFight}>
          <div className="fighter-config">
            <div className="fighter-config__heading">
              <span className="fighter-mark">A</span>
              <strong>Fighter A</strong>
            </div>
            <ProviderModelSelector
              label="Fighter A"
              currentPreset={presetA}
              onChangePreset={setPresetA}
            />
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
              <strong>Fighter B</strong>
            </div>
            <ProviderModelSelector
              label="Fighter B"
              currentPreset={presetB}
              onChangePreset={setPresetB}
            />
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
              LIVE THINKING ({activeThinking.fighter}) · INTERVAL {activeThinking.interval_index ?? activeThinking.frame ?? 1}
            </span>
            <span style={{ fontSize: '0.65rem', padding: '1px 6px', borderRadius: '4px', background: activeThinking.valid_20_words ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: activeThinking.valid_20_words ? '#4ade80' : '#f87171' }}>
              {activeThinking.wordCount ?? 20} words {activeThinking.valid_20_words ? '(exact 20)' : ''}
            </span>
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
