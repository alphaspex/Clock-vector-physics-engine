import { useCallback, useEffect, useState } from 'react';
import { api } from '../io/client';
import type { FightCommand, PracticeCommand, SavedRun, SimulationJob, SimulationKind } from '../core/commands';
import type { ReplayScene } from '../core/scene';

export type ConnectionState = 'checking' | 'online' | 'offline';
export type ActivityState = 'idle' | 'starting' | 'running' | 'loading-replay';

const WAIT_BETWEEN_POLLS_MS = 1_200;
const MAX_JOB_POLLS = 600; // Up to 12 minutes at the current polling interval.
const MAX_REPLAY_POLLS = 100; // Up to 2 minutes at the current polling interval.

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function describeJob(job: SimulationJob): string {
  if (job.state === 'done') return 'Simulation complete. Preparing replay…';
  if (job.state === 'error') return job.errorMessage || 'The simulation failed.';
  return 'Simulation is running on the backend…';
}

/**
 * Application controller. This is the only layer that coordinates UI actions
 * with the I/O adapter. It contains no rendering or form-layout decisions.
 */
export function useSimulation() {
  const [connection, setConnection] = useState<ConnectionState>('checking');
  const [activity, setActivity] = useState<ActivityState>('idle');
  const [activityMessage, setActivityMessage] = useState('Waiting for the backend');
  const [error, setError] = useState<string | null>(null);
  const [practiceRuns, setPracticeRuns] = useState<SavedRun[]>([]);
  const [fightRuns, setFightRuns] = useState<SavedRun[]>([]);
  const [replay, setReplay] = useState<ReplayScene | null>(null);
  const [selectedRun, setSelectedRun] = useState<{ kind: SimulationKind; number: number } | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  const refreshRuns = useCallback(async () => {
    const [practice, fight] = await Promise.all([api.listRuns('practice'), api.listRuns('fight')]);
    setPracticeRuns([...practice].sort((a, b) => b.number - a.number));
    setFightRuns([...fight].sort((a, b) => b.number - a.number));
  }, []);

  const checkBackend = useCallback(async () => {
    setConnection('checking');
    try {
      await api.health();
      setConnection('online');
      setError(null);
      await refreshRuns();
    } catch (cause) {
      setConnection('offline');
      setError(cause instanceof Error ? cause.message : 'Could not connect to the backend.');
    }
  }, [refreshRuns]);

  useEffect(() => {
    void checkBackend();
  }, [checkBackend]);

  const loadReplay = useCallback(async (kind: SimulationKind, runNumber: number) => {
    setError(null);
    setActivity('loading-replay');
    setActivityMessage(`Preparing ${kind} replay #${runNumber}…`);
    setReplay(null);
    setSelectedRun({ kind, number: runNumber });

    try {
      for (let attempt = 0; attempt < MAX_REPLAY_POLLS; attempt += 1) {
        const response = await api.getReplay(kind, runNumber);
        if (response.status === 'ready') {
          setReplay(response.scene);
          setLoadedAt(new Date().toLocaleTimeString());
          setActivity('idle');
          setActivityMessage(`${kind === 'fight' ? 'Fight' : 'Practice'} #${runNumber} loaded`);
          return;
        }
        await delay(WAIT_BETWEEN_POLLS_MS);
      }
      throw new Error('The backend is still preparing this replay. Try loading it again shortly.');
    } catch (cause) {
      setActivity('idle');
      setError(cause instanceof Error ? cause.message : 'Could not load the replay.');
      throw cause;
    }
  }, []);

  const waitForJob = useCallback(async (jobId: string): Promise<SimulationJob> => {
    for (let attempt = 0; attempt < MAX_JOB_POLLS; attempt += 1) {
      const job = await api.getJob(jobId);
      setActivityMessage(describeJob(job));
      if (job.state === 'done') return job;
      if (job.state === 'error') throw new Error(job.errorMessage || 'The simulation job failed.');
      await delay(WAIT_BETWEEN_POLLS_MS);
    }
    throw new Error('The backend job has taken longer than expected. Check the saved run list before starting another job.');
  }, []);

  const startRun = useCallback(async (
    kind: SimulationKind,
    input: PracticeCommand | FightCommand,
    adminToken: string,
  ) => {
    setError(null);
    setReplay(null);
    setActivity('starting');
    setActivityMessage(`Sending ${kind} request…`);

    try {
      const jobId = kind === 'practice'
        ? await api.startPractice(input as PracticeCommand, adminToken)
        : await api.startFight(input as FightCommand, adminToken);

      setActivity('running');
      setActivityMessage('Simulation is running on the backend…');
      const job = await waitForJob(jobId);
      if (typeof job.runNumber !== 'number') throw new Error('The backend finished the job but did not return a saved run number.');

      await refreshRuns();
      await loadReplay(kind, job.runNumber);
    } catch (cause) {
      setActivity('idle');
      setError(cause instanceof Error ? cause.message : 'The simulation could not be started.');
    } finally {
      // loadReplay sets this too; this final assignment covers early failures.
      setActivity((current) => current === 'loading-replay' ? current : 'idle');
    }
  }, [loadReplay, refreshRuns, waitForJob]);

  const startPractice = useCallback((input: PracticeCommand, token: string) => {
    void startRun('practice', input, token);
  }, [startRun]);

  const startFight = useCallback((input: FightCommand, token: string) => {
    void startRun('fight', input, token);
  }, [startRun]);

  const selectRun = useCallback((kind: SimulationKind, number: number) => {
    void loadReplay(kind, number).catch(() => undefined);
  }, [loadReplay]);

  const busy = activity !== 'idle';
  return {
    connection,
    activity,
    activityMessage,
    busy,
    error,
    practiceRuns,
    fightRuns,
    replay,
    selectedRun,
    loadedAt,
    checkBackend,
    selectRun,
    startPractice,
    startFight,
    refreshRuns,
  };
}
