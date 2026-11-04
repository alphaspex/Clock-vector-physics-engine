import { useMemo, useRef, useState } from 'react';
import {
  Activity,
  Brain,
  Database,
  Expand,
  Film,
  Focus,
  Github,
  Monitor,
  Radio,
  RadioTower,
  RotateCcw,
  Terminal,
  Wifi,
  WifiOff,
} from 'lucide-react';
import LauncherPanel from '../features/launcher/LauncherPanel';
import RunHistory from '../features/history/RunHistory';
import PlaybackBar from '../features/playback/PlaybackBar';
import ControlRoomPanel from '../features/monitoring/ControlRoomPanel';
import DatabaseManager from '../features/database/DatabaseManager';
import LiveLogsPanel from '../features/logs/LiveLogsPanel';
import LiveThinkingPanel from '../features/thinking/LiveThinkingPanel';
import { usePlayback } from '../features/playback/usePlayback';
import ThreeSketchViewer from '../viewer/ThreeSketchViewer';
import StatusDot from '../components/StatusDot';
import { getConfiguredApiUrl } from '../io/client';
import { useSimulation } from './useSimulation';

type AppTab = 'tv' | 'thinking' | 'control_room' | 'database' | 'live_logs';

export default function App() {
  const simulation = useSimulation();
  const playback = usePlayback(simulation.replay);
  const [activeTab, setActiveTab] = useState<AppTab>('tv');
  const [cameraResetKey, setCameraResetKey] = useState(0);
  const stageRef = useRef<HTMLElement>(null);
  const apiUrl = getConfiguredApiUrl();

  const apiHost = useMemo(() => {
    if (!apiUrl) return 'API URL not set';
    try {
      return new URL(apiUrl).host;
    } catch {
      return apiUrl;
    }
  }, [apiUrl]);

  const activeTitle = useMemo(() => {
    if (!simulation.selectedRun) return 'No replay loaded';
    return `${simulation.selectedRun.kind === 'fight' ? 'Fight' : 'Practice'} #${simulation.selectedRun.number}`;
  }, [simulation.selectedRun]);

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await stageRef.current?.requestFullscreen();
    } catch {
      // Fullscreen is optional; browser policy may refuse it.
    }
  };

  const statusTone =
    simulation.connection === 'online'
      ? 'good'
      : simulation.connection === 'offline'
        ? 'bad'
        : 'pending';

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <span />
            <span />
            <span />
          </div>
          <div>
            <p className="brand-kicker">ROBOTICS KINEMATICS / CONTROL ROOM</p>
            <h1>Cvector Physics Engine</h1>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <nav className="topbar-nav" aria-label="Main sections">
          <button
            type="button"
            className={`topbar-nav__item ${activeTab === 'tv' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('tv')}
          >
            <Monitor size={14} />
            <span>3D TV Replay</span>
          </button>
          <button
            type="button"
            className={`topbar-nav__item ${activeTab === 'thinking' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('thinking')}
          >
            <Brain size={14} />
            <span>AI Thinking</span>
            {simulation.jobs.some((j) => j.state === 'running') && (
              <span className="live-indicator-dot live-indicator-dot--pulse" />
            )}
          </button>

          <button
            type="button"
            className={`topbar-nav__item ${activeTab === 'control_room' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('control_room')}
          >
            <Radio size={14} />
            <span>Live Control Room</span>
            {simulation.jobs.some((j) => j.state === 'running') && (
              <span className="live-indicator-dot" />
            )}
          </button>
          <button
            type="button"
            className={`topbar-nav__item ${activeTab === 'database' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('database')}
          >
            <Database size={14} />
            <span>Database Manager</span>
          </button>
          <button
            type="button"
            className={`topbar-nav__item ${activeTab === 'live_logs' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('live_logs')}
          >
            <Terminal size={14} />
            <span>Live Logs</span>
            <span className="live-indicator-dot live-indicator-dot--pulse" />
          </button>
        </nav>

        <div className="topbar-right">
          <div className="connection-block">
            {simulation.connection === 'online' ? (
              <Wifi size={14} />
            ) : simulation.connection === 'offline' ? (
              <WifiOff size={14} />
            ) : (
              <RadioTower size={14} />
            )}
            <StatusDot tone={statusTone}>
              {simulation.connection === 'online'
                ? 'Backend connected'
                : simulation.connection === 'offline'
                  ? 'Backend offline'
                  : 'Connecting'}
            </StatusDot>
          </div>
          <button
            className="topbar-refresh"
            type="button"
            onClick={() => void simulation.checkBackend()}
            disabled={simulation.connection === 'checking'}
          >
            <Activity size={14} /> <span>Check service</span>
          </button>
        </div>
      </header>

      {/* Main Tab Content */}
      {activeTab === 'tv' && (
        <div className="workspace">
          <aside className="sidebar">
            <LauncherPanel
              backendOnline={simulation.connection === 'online'}
              busy={simulation.busy}
              activityMessage={simulation.activityMessage}
              adminToken={simulation.adminToken}
              onAdminTokenChange={simulation.setAdminToken}
              onStartPractice={simulation.startPractice}
              onStartFight={simulation.startFight}
              activeThinking={simulation.jobs.find((j) => j.state === 'running')?.latestThinking ?? simulation.jobs[0]?.latestThinking}
            />
            <RunHistory
              practiceRuns={simulation.practiceRuns}
              fightRuns={simulation.fightRuns}
              activeJobs={simulation.jobs}
              selected={simulation.selectedRun}
              busy={simulation.busy}
              onSelect={simulation.selectRun}
              onCompile={simulation.compileReplay}
              onRefresh={() => {
                void simulation.refreshRuns();
                if (simulation.adminToken.trim()) {
                  void simulation.refreshMonitoring();
                }
              }}
            />
            <div className="sidebar-footnote">
              <span>RENDER / CLIENT</span>
              <span>{apiHost}</span>
            </div>
          </aside>

          <section className="stage-column" ref={stageRef} aria-label="3D replay stage">
            <div className="stage-heading">
              <div>
                <p className="eyebrow">REPLAY OUTPUT / 03</p>
                <h2>{activeTitle}</h2>
              </div>
              <div className="stage-tools">
                <span className="stage-meta">
                  {simulation.replay
                    ? `${simulation.replay.blueprint.pointCount} points · ${simulation.replay.blueprint.primitives.length} primitives`
                    : 'Server-defined geometry'}
                </span>
                <button
                  className="icon-button"
                  type="button"
                  onClick={() => setCameraResetKey((value) => value + 1)}
                  title="Reset camera"
                  aria-label="Reset camera"
                >
                  <RotateCcw size={15} />
                </button>
                <button
                  className="icon-button"
                  type="button"
                  onClick={() => void toggleFullscreen()}
                  title="Toggle fullscreen"
                  aria-label="Toggle fullscreen"
                >
                  <Expand size={15} />
                </button>
              </div>
            </div>

            <div className="viewer-card">
              <div className="viewer-label viewer-label--top">
                <span>XYZ / PERSPECTIVE</span>
                <span>NO MATERIAL · NO SHADOW</span>
              </div>
              <ThreeSketchViewer
                blueprint={simulation.replay?.blueprint ?? null}
                frame={playback.frame}
                cameraResetKey={cameraResetKey}
              />
              {!simulation.replay && (
                <div className="viewer-placeholder">
                  <div className="placeholder-symbol">
                    <Focus size={31} strokeWidth={1.1} />
                  </div>
                  <p className="eyebrow">WAITING FOR REPLAY DATA</p>
                  <h3>
                    {simulation.activity === 'loading-replay'
                      ? 'Preparing the scene'
                      : simulation.selectedRun
                        ? `${simulation.selectedRun.kind === 'fight' ? 'Fight' : 'Practice'} #${simulation.selectedRun.number} Selected`
                        : 'The stage is clear'}
                  </h3>
                  <p>
                    {simulation.activity === 'loading-replay'
                      ? simulation.activityMessage
                      : simulation.selectedRun
                        ? 'This round has not been compiled into 30 FPS replay snapshots yet. Click below to start background compilation.'
                        : 'Select a saved replay or start a new simulation. The viewer draws only the geometry described by the server.'}
                  </p>
                  {simulation.selectedRun && (
                    <button
                      type="button"
                      className="button button--primary"
                      style={{ marginTop: '0.8rem', padding: '0.4rem 0.9rem', fontSize: '0.82rem' }}
                      onClick={() => {
                        if (simulation.selectedRun) {
                          void simulation.compileReplay(simulation.selectedRun.kind, simulation.selectedRun.number);
                        }
                      }}
                      disabled={simulation.busy}
                    >
                      <Film size={14} style={{ marginRight: '0.4rem' }} />
                      <span>Compile Replay (30 FPS) for #{simulation.selectedRun.number}</span>
                    </button>
                  )}
                  {simulation.connection === 'offline' && (
                    <span className="placeholder-alert">
                      <WifiOff size={13} /> Backend connection unavailable
                    </span>
                  )}
                </div>
              )}
              <div className="viewer-label viewer-label--bottom">
                <span>SERVER-DRIVEN WIREFRAME</span>
                <span>{simulation.loadedAt ? `LOADED ${simulation.loadedAt}` : 'AWAITING DATA'}</span>
              </div>
            </div>

            {simulation.error && (
              <div className="error-banner" role="alert">
                <span>{simulation.error}</span>
                <button type="button" onClick={() => void simulation.checkBackend()}>
                  Retry connection
                </button>
              </div>
            )}

            <PlaybackBar
              currentTime={playback.currentTime}
              duration={playback.duration}
              playing={playback.playing}
              speed={playback.speed}
              disabled={!simulation.replay || playback.duration <= 0}
              onToggle={playback.togglePlayback}
              onSeek={playback.seek}
              onJump={playback.jump}
              onSpeedChange={playback.setSpeed}
            />

            <footer className="stage-footer">
              <span>
                <span className="footer-dot" /> GENERIC GEOMETRY PIPELINE
              </span>
              <span>CAMERA: ORBIT / PLAYBACK: {playback.playing ? 'RUNNING' : 'PAUSED'}</span>
            </footer>
          </section>
        </div>
      )}

      {activeTab === 'thinking' && (
        <div className="section-container">
          <LiveThinkingPanel
            jobs={simulation.jobs}
            onOpenLauncher={() => setActiveTab('tv')}
          />
        </div>
      )}



      {activeTab === 'control_room' && (
        <div className="section-container">
          <ControlRoomPanel
            jobs={simulation.jobs}
            events={simulation.events}
            backendOnline={simulation.connection === 'online'}
            lastHealthCheck={simulation.lastHealthCheck}
            adminToken={simulation.adminToken}
            onRefresh={() => void simulation.refreshMonitoring()}
          />
        </div>
      )}

      {activeTab === 'database' && (
        <div className="section-container">
          <DatabaseManager
            adminToken={simulation.adminToken}
            onRefreshHistory={() => {
              void simulation.refreshRuns();
              void simulation.refreshMonitoring();
            }}
          />
        </div>
      )}

      {activeTab === 'live_logs' && (
        <div className="section-container">
          <LiveLogsPanel
            backendOnline={simulation.connection === 'online'}
            adminToken={simulation.adminToken}
          />
        </div>
      )}


      <footer className="global-footer">
        <span>CVECTOR PHYSICS ENGINE / 2.0.0</span>
        <span>
          <Github size={12} /> Static Client · Python API · Three.js
        </span>
      </footer>
    </main>
  );
}
