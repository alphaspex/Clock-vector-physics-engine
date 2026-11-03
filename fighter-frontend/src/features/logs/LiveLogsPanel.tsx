import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowDown,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  Download,
  Layers,
  Pause,
  Play,
  Search,
  Send,
  Terminal,
  Trash2,
  Wifi,
  WifiOff,
} from 'lucide-react';
import type { LiveLogsWireResponse, ServerLogEntryWire, ServerStatusWire } from '../../io/contracts';
import { api } from '../../io/client';

interface Props {
  backendOnline: boolean;
  adminToken: string;
}

const SUBSYSTEMS = [
  'ALL',
  'SIMULATION',
  'AI_ENGINE',
  'PHYSICS',
  'HTTP',
  'DATABASE',
  'CACHE',
  'SYSTEM',
] as const;

const LEVELS = ['ALL', 'DEBUG', 'INFO', 'WARN', 'ERROR'] as const;

export default function LiveLogsPanel({ backendOnline, adminToken }: Props) {
  const [logs, setLogs] = useState<ServerLogEntryWire[]>([]);
  const [serverStatus, setServerStatus] = useState<ServerStatusWire | null>(null);
  const [pollingActive, setPollingActive] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedLevel, setSelectedLevel] = useState<string>('ALL');
  const [selectedSubsystem, setSelectedSubsystem] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [isEmittingPing, setIsEmittingPing] = useState(false);
  const [pingSuccess, setPingSuccess] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const terminalRef = useRef<HTMLDivElement>(null);
  const maxSeenIdRef = useRef<number>(0);
  const isFetchingRef = useRef(false);

  // Fetch live logs periodically
  const fetchLogs = useCallback(
    async (isInitial = false) => {
      if (isFetchingRef.current || !backendOnline) return;
      isFetchingRef.current = true;
      try {
        const sinceId = isInitial ? undefined : maxSeenIdRef.current;
        const res: LiveLogsWireResponse = await api.getLiveLogs(adminToken, {
          sinceId: sinceId && sinceId > 0 ? sinceId : undefined,
          limit: isInitial ? 250 : 150,
        });

        if (res.status) {
          setServerStatus(res.status);
        }

        if (res.logs && res.logs.length > 0) {
          setLogs((prev) => {
            const existingIds = new Set(prev.map((l) => l.id));
            const newEntries = res.logs.filter((l) => !existingIds.has(l.id));
            if (newEntries.length === 0) return prev;
            const merged = [...prev, ...newEntries];
            // keep up to 1,500 logs in frontend view
            return merged.slice(-1500);
          });

          const highest = Math.max(...res.logs.map((l) => l.id));
          if (highest > maxSeenIdRef.current) {
            maxSeenIdRef.current = highest;
          }
        } else if (res.max_id && res.max_id > maxSeenIdRef.current) {
          maxSeenIdRef.current = res.max_id;
        }

        setLastError(null);
      } catch (err) {
        if (err instanceof Error) {
          setLastError(err.message);
        }
      } finally {
        isFetchingRef.current = false;
      }
    },
    [adminToken, backendOnline],
  );

  // Initial load
  useEffect(() => {
    maxSeenIdRef.current = 0;
    void fetchLogs(true);
  }, [fetchLogs]);

  // Polling loop (every 750ms when active)
  useEffect(() => {
    if (!pollingActive || !backendOnline) return;
    const interval = setInterval(() => {
      void fetchLogs(false);
    }, 750);
    return () => clearInterval(interval);
  }, [pollingActive, backendOnline, fetchLogs]);

  // Auto-scroll to bottom of terminal
  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (!terminalRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = terminalRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 40;
    if (autoScroll !== isAtBottom) {
      setAutoScroll(isAtBottom);
    }
  };

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleEmitTestPing = async () => {
    setIsEmittingPing(true);
    setPingSuccess(false);
    try {
      await api.emitTestLog(adminToken, `Client diagnostic ping at ${new Date().toLocaleTimeString()}`);
      setPingSuccess(true);
      setTimeout(() => setPingSuccess(false), 2000);
      void fetchLogs(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to emit test ping');
    } finally {
      setIsEmittingPing(false);
    }
  };

  const handleClearLogs = async () => {
    if (!window.confirm('Clear all live logs on server and console?')) return;
    try {
      await api.clearLiveLogs(adminToken);
      setLogs([]);
      maxSeenIdRef.current = 0;
      void fetchLogs(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to clear logs');
    }
  };

  const handleDownloadLogs = () => {
    const textContent = filteredLogs
      .map((l) => {
        const details = l.details && Object.keys(l.details).length > 0 ? `\n  DETAILS: ${JSON.stringify(l.details)}` : '';
        return `[${l.iso || new Date(l.timestamp * 1000).toISOString()}] [${l.level.padEnd(5)}] [${l.subsystem.padEnd(10)}] #${l.id}: ${l.message}${details}`;
      })
      .join('\n');

    const blob = new Blob([textContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fighter_server_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyLogs = async () => {
    const textContent = filteredLogs
      .map((l) => `[${l.iso || new Date(l.timestamp * 1000).toISOString()}] [${l.level}] [${l.subsystem}] #${l.id}: ${l.message}`)
      .join('\n');
    try {
      await navigator.clipboard.writeText(textContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  // Filtered logs
  const filteredLogs = useMemo(() => {
    let result = logs;

    if (selectedLevel !== 'ALL') {
      result = result.filter((l) => l.level.toUpperCase() === selectedLevel);
    }

    if (selectedSubsystem !== 'ALL') {
      result = result.filter((l) => l.subsystem.toUpperCase() === selectedSubsystem);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter(
        (l) =>
          l.message.toLowerCase().includes(q) ||
          l.subsystem.toLowerCase().includes(q) ||
          (l.details && JSON.stringify(l.details).toLowerCase().includes(q)),
      );
    }

    return result;
  }, [logs, selectedLevel, selectedSubsystem, searchQuery]);

  // Level counts for badge
  const levelCounts = useMemo(() => {
    const counts = { DEBUG: 0, INFO: 0, WARN: 0, ERROR: 0 };
    for (const l of logs) {
      const lvl = l.level.toUpperCase() as keyof typeof counts;
      if (counts[lvl] !== undefined) counts[lvl]++;
    }
    return counts;
  }, [logs]);

  // Format uptime
  const formattedUptime = useMemo(() => {
    if (!serverStatus?.uptime_seconds) return '--';
    const s = Math.floor(serverStatus.uptime_seconds);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    return `${hrs}h ${mins}m ${secs}s`;
  }, [serverStatus?.uptime_seconds]);

  return (
    <div className="live-logs-container" aria-label="Live Server Logs Console">
      {/* HUD Header: What the server is doing right now */}
      <section className="live-logs-hud">
        <div className="hud-primary">
          <div className="hud-status-badge">
            <span className={`hud-pulse-dot ${backendOnline ? 'hud-pulse-dot--online' : 'hud-pulse-dot--offline'}`} />
            <span className="hud-status-text">
              {backendOnline ? (pollingActive ? 'LIVE LOG STREAM' : 'STREAM PAUSED') : 'BACKEND OFFLINE'}
            </span>
          </div>

          <div className="hud-activity-box">
            <span className="hud-activity-label">WHAT SERVER IS DOING NOW:</span>
            <div className="hud-activity-content">
              <strong className="hud-activity-title">
                {serverStatus?.activity || (backendOnline ? 'Idle - Awaiting requests' : 'Server not responding')}
              </strong>
              {serverStatus?.detail && (
                <span className="hud-activity-detail"> — {serverStatus.detail}</span>
              )}
            </div>
          </div>
        </div>

        <div className="hud-stats">
          <div className="hud-stat-item">
            <span className="hud-stat-label"><Clock size={11} /> UPTIME</span>
            <span className="hud-stat-value">{formattedUptime}</span>
          </div>
          <div className="hud-stat-item">
            <span className="hud-stat-label"><Terminal size={11} /> TOTAL LOGS</span>
            <span className="hud-stat-value">{serverStatus?.total_logs ?? logs.length}</span>
          </div>
          <div className="hud-stat-item">
            <span className="hud-stat-label"><Layers size={11} /> BUFFER</span>
            <span className="hud-stat-value">{serverStatus?.buffer_size ?? logs.length} / 5000</span>
          </div>
          <div className="hud-stat-item">
            <span className="hud-stat-label"><Activity size={11} /> DISPLAYED</span>
            <span className="hud-stat-value">{filteredLogs.length}</span>
          </div>
        </div>
      </section>

      {/* Control Bar: Filters, Search & Actions */}
      <div className="live-logs-toolbar">
        {/* Search */}
        <div className="log-search-box">
          <Search size={13} className="log-search-icon" />
          <input
            type="text"
            className="log-search-input"
            placeholder="Search log messages, parameters, coordinates, errors..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="log-search-clear" type="button" onClick={() => setSearchQuery('')}>
              ×
            </button>
          )}
        </div>

        {/* Subsystem filter chips */}
        <div className="subsystem-chips" aria-label="Filter by subsystem">
          <span className="toolbar-group-label">SUBSYSTEM:</span>
          {SUBSYSTEMS.map((sub) => (
            <button
              key={sub}
              type="button"
              className={`subsystem-chip ${selectedSubsystem === sub ? 'is-active' : ''}`}
              onClick={() => setSelectedSubsystem(sub)}
            >
              {sub}
            </button>
          ))}
        </div>

        {/* Level filter pills */}
        <div className="level-pills" aria-label="Filter by log level">
          <span className="toolbar-group-label">LEVEL:</span>
          {LEVELS.map((lvl) => {
            const count = lvl === 'ALL' ? logs.length : levelCounts[lvl as keyof typeof levelCounts] ?? 0;
            return (
              <button
                key={lvl}
                type="button"
                className={`level-pill level-pill--${lvl.toLowerCase()} ${selectedLevel === lvl ? 'is-active' : ''}`}
                onClick={() => setSelectedLevel(lvl)}
              >
                <span>{lvl}</span>
                <span className="level-pill__count">{count}</span>
              </button>
            );
          })}
        </div>

        {/* Action Controls */}
        <div className="toolbar-actions">
          <button
            type="button"
            className={`action-btn ${autoScroll ? 'action-btn--active' : ''}`}
            onClick={() => {
              setAutoScroll(!autoScroll);
              if (!autoScroll && terminalRef.current) {
                terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
              }
            }}
            title={autoScroll ? 'Auto-scroll locked to bottom' : 'Click to lock auto-scroll to bottom'}
          >
            <ArrowDown size={12} />
            <span>{autoScroll ? 'Scroll: Locked' : 'Scroll: Free'}</span>
          </button>

          <button
            type="button"
            className={`action-btn ${pollingActive ? 'action-btn--active' : ''}`}
            onClick={() => setPollingActive(!pollingActive)}
            title={pollingActive ? 'Pause live stream' : 'Resume live stream'}
          >
            {pollingActive ? <Pause size={12} /> : <Play size={12} />}
            <span>{pollingActive ? 'Streaming (750ms)' : 'Paused'}</span>
          </button>

          <button
            type="button"
            className={`action-btn ${pingSuccess ? 'action-btn--success' : ''}`}
            onClick={handleEmitTestPing}
            disabled={isEmittingPing || !backendOnline}
            title="Send diagnostic heartbeat ping to verify live server logging"
          >
            {pingSuccess ? <CheckCircle2 size={12} /> : <Send size={12} />}
            <span>{pingSuccess ? 'Ping Sent!' : 'Emit Ping'}</span>
          </button>

          <button
            type="button"
            className="action-btn"
            onClick={handleCopyLogs}
            disabled={filteredLogs.length === 0}
            title="Copy visible logs to clipboard"
          >
            <Copy size={12} />
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>

          <button
            type="button"
            className="action-btn"
            onClick={handleDownloadLogs}
            disabled={filteredLogs.length === 0}
            title="Download visible logs as .log file"
          >
            <Download size={12} />
            <span>Export</span>
          </button>

          <button
            type="button"
            className="action-btn action-btn--danger"
            onClick={handleClearLogs}
            title="Clear all server logs"
          >
            <Trash2 size={12} />
            <span>Clear</span>
          </button>
        </div>
      </div>

      {lastError && (
        <div className="live-logs-error-banner" role="alert">
          <AlertCircle size={14} />
          <span>{lastError}</span>
        </div>
      )}

      {/* Terminal Display */}
      <div className="terminal-container">
        <div className="terminal-header">
          <div className="terminal-dots">
            <span className="dot dot--red" />
            <span className="dot dot--yellow" />
            <span className="dot dot--green" />
          </div>
          <span className="terminal-title">fighter-backend: live stdout & event pipe</span>
          <div className="terminal-meta">
            {backendOnline ? (
              <span className="text-good flex items-center gap-1 font-mono">
                <Wifi size={11} /> 0.0.0.0:8000
              </span>
            ) : (
              <span className="text-bad flex items-center gap-1 font-mono">
                <WifiOff size={11} /> OFFLINE
              </span>
            )}
          </div>
        </div>

        <div className="terminal-body" ref={terminalRef} onScroll={handleScroll}>
          {filteredLogs.length === 0 ? (
            <div className="terminal-empty">
              <Terminal size={32} strokeWidth={1.2} />
              <p>No log records matching criteria.</p>
              {searchQuery || selectedLevel !== 'ALL' || selectedSubsystem !== 'ALL' ? (
                <button
                  type="button"
                  className="button button--small"
                  onClick={() => {
                    setSelectedLevel('ALL');
                    setSelectedSubsystem('ALL');
                    setSearchQuery('');
                  }}
                >
                  Reset Filters
                </button>
              ) : (
                <p className="terminal-hint">
                  Launch a practice or fight simulation, or click "Emit Ping" to observe server events in real time.
                </p>
              )}
            </div>
          ) : (
            <div className="log-rows-list">
              {filteredLogs.map((entry) => {
                const isExpanded = expandedIds.has(entry.id);
                const hasDetails = entry.details && Object.keys(entry.details).length > 0;
                const timeStr = entry.iso
                  ? entry.iso.substring(11, 23)
                  : new Date(entry.timestamp * 1000).toLocaleTimeString();

                return (
                  <div
                    key={entry.id}
                    className={`log-row log-row--${entry.level.toLowerCase()}`}
                  >
                    <div className="log-row__main">
                      <span className="log-col log-col--id">#{entry.id}</span>
                      <span className="log-col log-col--time" title={entry.iso || ''}>
                        {timeStr}
                      </span>
                      <span className={`log-badge log-badge--level log-badge--${entry.level.toLowerCase()}`}>
                        {entry.level}
                      </span>
                      <span className={`log-badge log-badge--subsystem log-badge--sub-${entry.subsystem.toLowerCase()}`}>
                        {entry.subsystem}
                      </span>
                      <span className="log-col log-col--msg">{entry.message}</span>

                      {hasDetails && (
                        <button
                          type="button"
                          className="log-expand-btn"
                          onClick={() => toggleExpand(entry.id)}
                          title="Toggle JSON details"
                        >
                          {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                          <span>{isExpanded ? 'Hide' : 'Details'}</span>
                        </button>
                      )}
                    </div>

                    {isExpanded && hasDetails && (
                      <div className="log-row__details">
                        <pre className="log-details-json">
                          {JSON.stringify(entry.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
