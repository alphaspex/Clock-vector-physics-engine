import { useCallback, useEffect, useState } from 'react';
import { api } from '../io/client';
import type {
  ActivityEvent,
  FightCommand,
  PracticeCommand,
  SavedRun,
  SimulationJob,
  SimulationKind,
} from '../core/commands';
import type { ReplayScene } from '../core/scene';

export type ConnectionState = 'checking' | 'online' | 'offline';
export type ActivityState = 'idle' | 'starting' | 'running' | 'loading-replay';

const WAIT_BETWEEN_POLLS_MS = 1_200;
const MAX_JOB_POLLS = 600; // Up to 12 minutes
const MAX_REPLAY_POLLS = 100; // Up to 2 minutes

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function describeJob(job: SimulationJob): string {
  if (job.state === 'done') return 'Simulation complete. Preparing replay…';
  if (job.state === 'error') return job.errorMessage || 'The simulation failed.';
  if (job.stage === 'saving') return 'Saving simulation results to database…';
  if (job.stage === 'preparing_replay') return 'Generating deterministic 3D replay frames…';
  if (job.stage === 'decision' && job.decision) {
    return `AI reasoning decision ${job.decision}/${job.targetDecisions || '?'}…`;
  }
  return 'Simulation is running on the backend…';
}

/**
 * Application controller. Coordinates UI actions with the I/O adapter.
 * Contains no rendering or form-layout decisions.
 */
export function useSimulation() {
  const [connection, setConnection] = useState<ConnectionState>('checking');
  const [lastHealthCheck, setLastHealthCheck] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityState>('idle');
  const [activityMessage, setActivityMessage] = useState('Waiting for the backend');
  const [error, setError] = useState<string | null>(null);
  const [adminToken, setAdminToken] = useState<string>('');

  const [practiceRuns, setPracticeRuns] = useState<SavedRun[]>([]);
  const [fightRuns, setFightRuns] = useState<SavedRun[]>([]);
  const [jobs, setJobs] = useState<SimulationJob[]>([]);
  const [events, setEvents] = useState<ActivityEvent[]>([]);

  const [replay, setReplay] = useState<ReplayScene | null>(null);
  const [selectedRun, setSelectedRun] = useState<{ kind: SimulationKind; number: number } | null>(null);
  const [loadedAt, setLoadedAt] = useState<string | null>(null);

  const refreshRuns = useCallback(async () => {
    try {
      const [practice, fight] = await Promise.all([api.listRuns('practice'), api.listRuns('fight')]);
      setPracticeRuns([...practice].sort((a, b) => b.number - a.number));
      setFightRuns([...fight].sort((a, b) => b.number - a.number));
    } catch {
      // Ignore if offline
    }
  }, []);

  const refreshMonitoring = useCallback(async () => {
    if (!adminToken.trim()) return;
    try {
      const [jList, evList] = await Promise.all([
        api.listJobs(adminToken.trim()),
        api.listEvents(adminToken.trim(), 100),
      ]);
      setJobs(jList);
      setEvents(evList);
    } catch {
      // Ignore background monitoring failure
    }
  }, [adminToken]);

  const checkBackend = useCallback(async () => {
    setConnection('checking');
    try {
      await api.health();
      setConnection('online');
      setLastHealthCheck(new Date().toLocaleTimeString());
      setError(null);
      await refreshRuns();
      if (adminToken.trim()) {
        await refreshMonitoring();
      }
    } catch (cause) {
      setConnection('offline');
      setError(cause instanceof Error ? cause.message : 'Could not connect to the backend.');
    }
  }, [adminToken, refreshRuns, refreshMonitoring]);

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

  const waitForJob = useCallback(
    async (jobId: string): Promise<SimulationJob> => {
      for (let attempt = 0; attempt < MAX_JOB_POLLS; attempt += 1) {
        const job = await api.getJob(jobId);
        setActivityMessage(describeJob(job));

        // Update active job in list
        setJobs((current) => {
          const idx = current.findIndex((j) => j.id === jobId);
          if (idx >= 0) {
            const next = [...current];
            next[idx] = job;
            return next;
          }
          return [job, ...current];
        });

        if (job.state === 'done') return job;
        if (job.state === 'error') throw new Error(job.errorMessage || 'The simulation job failed.');
        await delay(WAIT_BETWEEN_POLLS_MS);
      }
      throw new Error('The backend job has taken longer than expected. Check the saved run list.');
    },
    [],
  );

  const startRun = useCallback(
    async (
      kind: SimulationKind,
      input: PracticeCommand | FightCommand,
      token: string,
    ) => {
      setError(null);
      setReplay(null);
      setActivity('starting');
      setActivityMessage(`Sending ${kind} request…`);

      try {
        const jobId =
          kind === 'practice'
            ? await api.startPractice(input as PracticeCommand, token)
            : await api.startFight(input as FightCommand, token);

        setActivity('running');
        setActivityMessage('Simulation is running on the backend…');

        // Add initial running job state
        const initialJob: SimulationJob = {
          id: jobId,
          kind,
          state: 'running',
          stage: 'simulation',
          createdAt: new Date().toLocaleTimeString(),
        };
        setJobs((current) => [initialJob, ...current]);

        const job = await waitForJob(jobId);
        if (typeof job.runNumber !== 'number') {
          throw new Error('The backend finished the job but did not return a saved run number.');
        }

        await refreshRuns();
        if (token.trim()) await refreshMonitoring();
        await loadReplay(kind, job.runNumber);
      } catch (cause) {
        setActivity('idle');
        setError(cause instanceof Error ? cause.message : 'The simulation could not be started.');
      } finally {
        setActivity((current) => (current === 'loading-replay' ? current : 'idle'));
      }
    },
    [loadReplay, refreshRuns, refreshMonitoring, waitForJob],
  );

  const startPractice = useCallback(
    (input: PracticeCommand, token: string) => {
      void startRun('practice', input, token);
    },
    [startRun],
  );

  const startFight = useCallback(
    (input: FightCommand, token: string) => {
      void startRun('fight', input, token);
    },
    [startRun],
  );

  const selectRun = useCallback(
    (kind: SimulationKind, number: number) => {
      void loadReplay(kind, number).catch(() => undefined);
    },
    [loadReplay],
  );

  const busy = activity !== 'idle';

  return {
    connection,
    lastHealthCheck,
    activity,
    activityMessage,
    busy,
    error,
    adminToken,
    setAdminToken,
    practiceRuns,
    fightRuns,
    jobs,
    events,
    replay,
    selectedRun,
    loadedAt,
    checkBackend,
    selectRun,
    startPractice,
    startFight,
    refreshRuns,
    refreshMonitoring,
  };
}
