import { useEffect, useMemo, useState } from 'react';
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Copy,
  Flame,
  History,
  MessageSquare,
  Play,
  RefreshCw,
  Swords,
} from 'lucide-react';
import type { SimulationJob, ThinkingItem } from '../../core/commands';
import { api } from '../../io/client';

interface Props {
  jobs: SimulationJob[];
  onOpenLauncher?: () => void;
}

export default function LiveThinkingPanel({ jobs, onOpenLauncher }: Props) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyFighterFilter, setHistoryFighterFilter] = useState<'all' | 'A' | 'B'>('all');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showRawMap, setShowRawMap] = useState<Record<string, boolean>>({});
  
  // Historical memory state
  const [memoryA, setMemoryA] = useState<import('../../io/contracts').MemoryWireResponse | null>(null);
  const [memoryB, setMemoryB] = useState<import('../../io/contracts').MemoryWireResponse | null>(null);
  const [loadingMemory, setLoadingMemory] = useState(false);

  // Focus on currently running job; if none, show the most recent completed job or empty state
  const activeJob = useMemo(() => {
    return jobs.find((j) => j.state === 'running') || (jobs.length > 0 ? jobs[0] : null);
  }, [jobs]);

  const isLive = activeJob?.state === 'running';

  // Load historical memory if no job is active or upon manual request
  const loadHistoricalMemory = async () => {
    setLoadingMemory(true);
    try {
      const [resA, resB] = await Promise.all([
        api.getMemory('A'),
        api.getMemory('B')
      ]);
      setMemoryA(resA);
      setMemoryB(resB);
    } catch (err) {
      console.error('Failed to load historical memory', err);
    } finally {
      setLoadingMemory(false);
    }
  };

  useEffect(() => {
    if (!isLive) {
      void loadHistoricalMemory();
    }
  }, [isLive]);

  const handleCopy = (key: string, text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 2000);
    }).catch(() => undefined);
  };

  const toggleRaw = (id: string) => {
    setShowRawMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const thinkingHistory = useMemo(() => {
    return activeJob?.thinkingHistory || [];
  }, [activeJob?.thinkingHistory]);

  const filteredHistory = useMemo(() => {
    if (historyFighterFilter === 'all') return thinkingHistory;
    return thinkingHistory.filter((t) => t.fighter === historyFighterFilter);
  }, [thinkingHistory, historyFighterFilter]);

  // Fighters to render in stacked cards
  const isFight = activeJob?.kind === 'fight';

  const fighterAThinking = useMemo(() => {
    if (activeJob?.latestThinkingA) return activeJob.latestThinkingA;
    if (isFight) {
      // Find latest in history for fighter A
      return [...thinkingHistory].reverse().find((t) => t.fighter === 'A') || activeJob?.latestThinking;
    }
    return activeJob?.latestThinking;
  }, [activeJob?.latestThinkingA, activeJob?.latestThinking, isFight, thinkingHistory]);

  const fighterBThinking = useMemo(() => {
    if (activeJob?.latestThinkingB) return activeJob.latestThinkingB;
    if (isFight) {
      // Find latest in history for fighter B
      return [...thinkingHistory].reverse().find((t) => t.fighter === 'B');
    }
    return undefined;
  }, [activeJob?.latestThinkingB, isFight, thinkingHistory]);

  // Extract preset/model labels from params if available
  const metaParams = useMemo(() => {
    const p = (activeJob?.params || {}) as Record<string, unknown>;
    const presets = Array.isArray(p.presets) ? p.presets : [];
    const efforts = Array.isArray(p.efforts) ? p.efforts : [];
    return {
      presetA: (p.presetA as string) || (presets[0] as string) || (p.preset as string) || 'meta_contrib',
      presetB: (p.presetB as string) || (presets[1] as string) || 'baseten',
      effortA: (p.effortA as string) || (efforts[0] as string) || (p.effort as string) || 'minimal',
      effortB: (p.effortB as string) || (efforts[1] as string) || 'minimal',
      interval: Number(p.interval || 3),
      durationMinutes: Number(p.duration_minutes || p.duration || 1),
    };
  }, [activeJob?.params]);

  if (!activeJob && !loadingMemory && !memoryA && !memoryB) {
    return (
      <div className="control-room" aria-label="AI Thinking Stream">
        <div className="empty-state" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 20px',
            }}
          >
            <Brain size={28} style={{ color: '#888' }} />
          </div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: '#f0f0f0', marginBottom: 8 }}>
            No Simulation Data Available
          </h2>
          <p style={{ maxWidth: 440, margin: '0 auto 24px', color: '#888', fontSize: 13, lineHeight: 1.6 }}>
            Follow target-pose decisions and factual descriptions of the physical changes measured after each simulation interval.
          </p>
          {onOpenLauncher && (
            <button
              type="button"
              className="action-btn"
              onClick={onOpenLauncher}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 18px',
                background: '#ff4d4d',
                color: '#fff',
                borderRadius: 6,
                fontWeight: 600,
                fontSize: 13,
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <Play size={14} />
              <span>Launch a Live Round</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="control-room" aria-label="AI Thinking Stream">
      {/* Top Banner Status */}
      <div className="monitoring-header">
        <div className="monitoring-header__info">
          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Session Context</span>
            <span className="monitoring-stat__val" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {activeJob ? (
                <>
                  {isFight ? <Swords size={14} style={{ color: '#e04b38' }} /> : <Flame size={14} style={{ color: '#4da6ff' }} />}
                  {isFight ? 'Dual Robot Match' : 'Kinematic Practice Drill'}
                </>
              ) : (
                'Historical Archive'
              )}
            </span>
          </div>

          <div className="monitoring-stat">
            <span className="monitoring-stat__label">Live Status</span>
            <span
              className={`monitoring-stat__val ${isLive ? 'text-good' : ''}`}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              {isLive ? (
                <>
                  <span className="live-indicator-dot live-indicator-dot--pulse" />
                  Live Interval Processing
                </>
              ) : activeJob ? (
                'Round Finished (Last Session)'
              ) : (
                'Archive Browsing'
              )}
            </span>
          </div>

          <div className="monitoring-stat">
            <span className="monitoring-stat__label">{activeJob ? 'Decision Pace' : 'Archive Depth'}</span>
            <span className="monitoring-stat__val">
              {activeJob ? (
                <>
                  {activeJob.decision ? `#${activeJob.decision}` : '#0'}
                  {activeJob.targetDecisions ? ` / ${activeJob.targetDecisions}` : ''}
                  <span style={{ fontSize: 11, color: '#888', marginLeft: 4 }}>
                    ({metaParams.interval}s interval)
                  </span>
                </>
              ) : (
                `${(memoryA?.task_memory.length || 0) + (memoryB?.task_memory.length || 0)} Intervals`
              )}
            </span>
          </div>

          <div className="monitoring-stat">
            <span className="monitoring-stat__label">{activeJob ? 'Sim Progress' : 'Summary Feed'}</span>
            <span className="monitoring-stat__val">
              {activeJob ? (
                <>
                  {activeJob.percent !== undefined ? `${activeJob.percent}%` : isLive ? 'Running' : '100%'}
                  {activeJob.frame !== undefined && (
                    <span style={{ fontSize: 11, color: '#888', marginLeft: 4 }}>
                      (f: {activeJob.frame}/{activeJob.maxFrame || '?'})
                    </span>
                  )}
                </>
              ) : (
                `${(memoryA?.practice_summaries.length || 0) + (memoryB?.practice_summaries.length || 0)} Summaries`
              )}
            </span>
          </div>
        </div>

        <div className="monitoring-controls">
          {!isLive && (
            <button
              type="button"
              className="action-btn"
              onClick={() => void loadHistoricalMemory()}
              disabled={loadingMemory}
              style={{
                 marginRight: 8,
                 background: 'rgba(255, 255, 255, 0.05)',
                 border: '1px solid rgba(255, 255, 255, 0.1)',
                 padding: '6px 12px',
                 fontSize: 12,
                 color: '#ddd',
                 borderRadius: 4,
                 cursor: 'pointer'
              }}
            >
              <RefreshCw size={13} className={loadingMemory ? 'animate-spin' : ''} />
              <span style={{ marginLeft: 6 }}>Sync DB Memory</span>
            </button>
          )}
          <button
            type="button"
            className={`action-btn ${historyOpen ? 'is-active' : ''}`}
            onClick={() => setHistoryOpen((v) => !v)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 12px',
              background: historyOpen ? 'rgba(255, 255, 255, 0.12)' : 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 4,
              color: '#ddd',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            <History size={13} />
            <span>{isLive ? `History Drawer (${thinkingHistory.length})` : 'Fighter Memory Archive'}</span>
            {historyOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {!isLive && (
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <HistoricalMemoryCard ai="A" themeColor="#4da6ff" memory={memoryA} onCopy={handleCopy} copiedKey={copiedKey} />
          <HistoricalMemoryCard ai="B" themeColor="#ff9933" memory={memoryB} onCopy={handleCopy} copiedKey={copiedKey} />
        </div>
      )}

      {/* Main Stacked Cards Container (Only show if live or recent job active) */}
      {(isLive || activeJob) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          {/* Robot Alpha Stacked Card */}
          <ThinkingHeroCard
            fighter="A"
            roleTitle={isFight ? 'Robot Alpha (Primary)' : 'Practice Robot Alpha'}
            themeColor="#4da6ff"
            preset={metaParams.presetA}
            effort={metaParams.effortA}
            item={fighterAThinking}
            isLive={isLive}
            targetDecisions={activeJob?.targetDecisions}
            showRaw={showRawMap['A'] || false}
            onToggleRaw={() => toggleRaw('A')}
            onCopy={(text) => handleCopy('hero-A', text)}
            isCopied={copiedKey === 'hero-A'}
          />

          {/* Robot Beta Stacked Card (in Fight mode) */}
          {isFight && (
            <ThinkingHeroCard
              fighter="B"
              roleTitle="Robot Beta (Secondary)"
              themeColor="#ff9933"
              preset={metaParams.presetB}
              effort={metaParams.effortB}
              item={fighterBThinking}
              isLive={isLive}
              targetDecisions={activeJob?.targetDecisions}
              showRaw={showRawMap['B'] || false}
              onToggleRaw={() => toggleRaw('B')}
              onCopy={(text) => handleCopy('hero-B', text)}
              isCopied={copiedKey === 'hero-B'}
            />
          )}
        </div>
      )}

      {/* History Drawer Section */}
      {historyOpen && (
        <div
          style={{
            background: 'rgba(15, 17, 23, 0.95)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 8,
            padding: 16,
            marginTop: 16,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 14,
              paddingBottom: 10,
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <History size={15} style={{ color: '#aaa' }} />
              <h4 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: '#f0f0f0' }}>
                Interval Decision Archive ({filteredHistory.length} entries)
              </h4>
            </div>

            {isFight && (
              <div style={{ display: 'flex', gap: 4 }}>
                {(['all', 'A', 'B'] as const).map((filter) => (
                  <button
                    key={filter}
                    type="button"
                    onClick={() => setHistoryFighterFilter(filter)}
                    style={{
                      padding: '3px 8px',
                      fontSize: 11,
                      borderRadius: 4,
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      background:
                        historyFighterFilter === filter ? 'rgba(255, 255, 255, 0.2)' : 'transparent',
                      color: historyFighterFilter === filter ? '#fff' : '#888',
                      cursor: 'pointer',
                    }}
                  >
                    {filter === 'all' ? 'All Fighters' : `Fighter ${filter}`}
                  </button>
                ))}
              </div>
            )}
          </div>

          {filteredHistory.length === 0 ? (
            <p style={{ color: '#777', fontSize: 12, margin: '20px 0', textAlign: 'center' }}>
              No prior intervals logged yet for this match.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxHeight: 420, overflowY: 'auto' }}>
              {filteredHistory
                .slice()
                .reverse()
                .map((item, idx) => {
                  const itemKey = `hist-${item.fighter}-${item.frame || idx}`;
                  const isFighterA = item.fighter === 'A';
                  const badgeColor = isFighterA ? '#4da6ff' : '#ff9933';
                  const isCopied = copiedKey === itemKey;

                  return (
                    <div
                      key={itemKey}
                      style={{
                        background: 'rgba(255, 255, 255, 0.02)',
                        border: '1px solid rgba(255, 255, 255, 0.06)',
                        borderRadius: 6,
                        padding: '10px 14px',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: 6,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            style={{
                              fontSize: 10,
                              fontWeight: 700,
                              color: badgeColor,
                              background: `${badgeColor}18`,
                              padding: '2px 6px',
                              borderRadius: 3,
                            }}
                          >
                            Fighter {item.fighter}
                          </span>
                          {item.decision !== undefined && (
                            <span style={{ fontSize: 11, color: '#aaa' }}>
                              Decision #{item.decision}
                            </span>
                          )}
                          {item.frame !== undefined && (
                            <span style={{ fontSize: 10, color: '#777' }}>
                              Frame {item.frame}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {item.wordCount !== undefined && (
                            <span style={{ fontSize: 10, color: '#888' }}>
                              {item.wordCount} words
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={() => handleCopy(itemKey, item.text)}
                            title="Copy interval thought"
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: isCopied ? '#4ade80' : '#888',
                              cursor: 'pointer',
                              padding: 2,
                            }}
                          >
                            <Copy size={12} />
                          </button>
                        </div>
                      </div>

                      <p
                        style={{
                          margin: '0 0 10px 0',
                          fontSize: 12,
                          color: '#e4e4e7',
                          lineHeight: 1.5,
                          fontFamily: 'ui-monospace, monospace',
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {item.text || 'AI is selecting a target pose; the physical interval summary appears after the seven-interval batch.'}
                      </p>

                      {(item.pre_tree || item.post_tree) && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 10, borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: 10 }}>
                          <div>
                            <span style={{ fontSize: 9, fontWeight: 700, color: '#888', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Pre-Interval Pose</span>
                            <pre style={{ margin: 0, fontSize: 10, color: '#aaa', background: 'rgba(0,0,0,0.2)', padding: 6, borderRadius: 4, maxHeight: 120, overflowY: 'auto' }}>
                              {item.pre_tree || 'N/A'}
                            </pre>
                          </div>
                          <div>
                            <span style={{ fontSize: 9, fontWeight: 700, color: '#888', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Post-Interval Pose</span>
                            <pre style={{ margin: 0, fontSize: 10, color: '#aaa', background: 'rgba(0,0,0,0.2)', padding: 6, borderRadius: 4, maxHeight: 120, overflowY: 'auto' }}>
                              {item.post_tree || 'N/A'}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function HistoricalMemoryCard({
  ai,
  themeColor,
  memory,
  onCopy,
  copiedKey,
}: {
  ai: 'A' | 'B';
  themeColor: string;
  memory: import('../../io/contracts').MemoryWireResponse | null;
  onCopy: (key: string, text: string) => void;
  copiedKey: string | null;
}) {
  return (
    <div
      className="monitoring-card"
      style={{
        borderLeft: `4px solid ${themeColor}`,
        background: 'rgba(18, 20, 28, 0.85)',
        padding: '16px 20px',
        borderRadius: 8,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 6,
            background: `${themeColor}22`,
            border: `1px solid ${themeColor}44`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: themeColor,
            fontWeight: 800,
            fontSize: 12,
          }}
        >
          {ai}
        </div>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700, color: '#f5f5f5' }}>Fighter {ai} Memory</h3>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <h4 style={{ fontSize: 10, fontWeight: 700, color: '#666', textTransform: 'uppercase', marginBottom: 6 }}>Recent Summaries</h4>
          {memory?.practice_summaries.length === 0 && memory?.fight_summaries.length === 0 ? (
             <p style={{ fontSize: 11, color: '#555', fontStyle: 'italic' }}>No summaries stored.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[...(memory?.fight_summaries || []), ...(memory?.practice_summaries || [])].slice(0, 3).map((s, i) => (
                <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: 8, borderRadius: 4, fontSize: 11, color: '#aaa', lineHeight: 1.4 }}>
                  "{s}"
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h4 style={{ fontSize: 10, fontWeight: 700, color: '#666', textTransform: 'uppercase', marginBottom: 6 }}>Latest Intervals</h4>
          {memory?.task_memory.length === 0 && memory?.fight_memory.length === 0 ? (
            <p style={{ fontSize: 11, color: '#555', fontStyle: 'italic' }}>No intervals stored.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[...(memory?.fight_memory || []), ...(memory?.task_memory || [])].slice(0, 5).map((m, i) => {
                const key = `hist-${ai}-${i}`;
                const isCopied = copiedKey === key;
                return (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.03)', padding: 8, borderRadius: 4, fontSize: 11, color: '#ccc', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 9, fontWeight: 700, color: themeColor }}>INTERVAL {i+1}</span>
                      <button 
                        type="button" 
                        onClick={() => onCopy(key, m.description)} 
                        style={{ background: 'none', border: 'none', color: isCopied ? '#4ade80' : '#888', cursor: 'pointer' }}
                      >
                        <Copy size={10} />
                      </button>
                    </div>
                    <p style={{ margin: 0, lineHeight: 1.4 }}>{m.description}</p>
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

/** Individual Stacked Hero Card for Fighter A or B */
function ThinkingHeroCard({
  fighter,
  roleTitle,
  themeColor,
  preset,
  effort,
  item,
  isLive,
  targetDecisions,
  showRaw,
  onToggleRaw,
  onCopy,
  isCopied,
}: {
  fighter: 'A' | 'B';
  roleTitle: string;
  themeColor: string;
  preset: string;
  effort: string;
  item?: ThinkingItem;
  isLive: boolean;
  targetDecisions?: number;
  showRaw: boolean;
  onToggleRaw: () => void;
  onCopy: (text: string) => void;
  isCopied: boolean;
}) {
  const hasText = Boolean(item?.text);
  const isFallback = Boolean(item?.isFallback);
  const isDescription = item?.status === 'described';
  const wordCount = isDescription
    ? (item?.wordCount ?? (item?.text ? item.text.split(/\s+/).filter(Boolean).length : 0))
    : 0;
  const isValidWordCount = isDescription && wordCount >= 15 && wordCount <= 30;
  const statusLabel = item?.status === 'thinking'
    ? 'CHOOSING TARGET POSE'
    : item?.status === 'target_ready'
    ? 'TARGET ACCEPTED'
    : item?.status === 'target_rejected'
    ? 'TARGET REJECTED'
    : item?.status === 'description_pending'
    ? 'PHYSICS COMPLETE · SUMMARY PENDING'
    : item?.status === 'described'
    ? 'PHYSICAL INTERVAL SUMMARY'
    : 'INTERVAL STATUS';

  return (
    <section
      className="monitoring-card"
      style={{
        borderLeft: `4px solid ${themeColor}`,
        background: 'rgba(18, 20, 28, 0.85)',
        padding: '16px 20px',
        borderRadius: 8,
      }}
    >
      {/* Card Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 6,
              background: `${themeColor}22`,
              border: `1px solid ${themeColor}44`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: themeColor,
              fontWeight: 800,
              fontSize: 14,
            }}
          >
            {fighter}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#f5f5f5' }}>{roleTitle}</h3>
              {isLive && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#4ade80',
                    background: 'rgba(74, 222, 128, 0.1)',
                    padding: '1px 6px',
                    borderRadius: 3,
                  }}
                >
                  <span className="live-indicator-dot live-indicator-dot--pulse" style={{ width: 6, height: 6 }} />
                  SIMULATION ACTIVE
                </span>
              )}
              {isFallback && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 10,
                    fontWeight: 700,
                    color: '#f59e0b',
                    background: 'rgba(245, 158, 11, 0.1)',
                    padding: '1px 6px',
                    borderRadius: 3,
                  }}
                >
                  FALLBACK
                </span>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
              <span style={{ fontSize: 11, color: '#888' }}>
                Provider: <strong style={{ color: '#bbb' }}>{preset}</strong>
              </span>
              <span style={{ fontSize: 11, color: '#666' }}>•</span>
              <span style={{ fontSize: 11, color: '#888' }}>
                Reasoning Effort: <strong style={{ color: '#bbb' }}>{effort}</strong>
              </span>
            </div>
          </div>
        </div>

        {/* Status badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {item?.decision !== undefined && (
            <span
              style={{
                fontSize: 11,
                color: '#ddd',
                background: 'rgba(255, 255, 255, 0.06)',
                padding: '4px 8px',
                borderRadius: 4,
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              Interval #{item.decision}
              {targetDecisions ? ` of ${targetDecisions}` : ''}
            </span>
          )}

          {item && (
            <span
              style={{
                fontSize: 10,
                color: isDescription ? (isValidWordCount ? '#4ade80' : '#ffb347') : '#93c5fd',
                background: isDescription ? 'rgba(74, 222, 128, 0.08)' : 'rgba(59, 130, 246, 0.08)',
                padding: '4px 8px',
                borderRadius: 4,
                border: '1px solid rgba(255, 255, 255, 0.08)',
              }}
            >
              {isDescription ? `${wordCount} words ${isValidWordCount ? '· 15-30 valid' : '· check length'}` : statusLabel}
            </span>
          )}

          {hasText && item && (
            <button
              type="button"
              onClick={() => onCopy(item.text)}
              style={{
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: isCopied ? '#4ade80' : '#ddd',
                padding: '4px 8px',
                borderRadius: 4,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: 11,
              }}
              title="Copy interval status or physical summary"
            >
              <Copy size={12} />
              <span>{isCopied ? 'Copied' : 'Copy'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Content Box */}
      <div
        style={{
          background: 'rgba(10, 11, 15, 0.9)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 6,
          padding: 16,
          minHeight: 88,
          position: 'relative',
        }}
      >
        {!hasText ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#666', fontStyle: 'italic', fontSize: 13, padding: '12px 0' }}>
            <Brain size={18} style={{ opacity: 0.5 }} />
            <span>Preparing the initial physical observation for Robot {fighter}…</span>
          </div>
        ) : (
          <>
            <div
              style={{
                fontSize: 14,
                lineHeight: 1.6,
                color: '#e4e4e7',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                whiteSpace: 'pre-wrap',
                letterSpacing: '0.01em',
              }}
            >
              {item!.text}
            </div>

            {item?.targetTree && (
              <details style={{ marginTop: 12, borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: 10 }}>
                <summary style={{ cursor: 'pointer', color: '#93c5fd', fontSize: 11, fontWeight: 700 }}>
                  REQUESTED TARGET POSE (NOT THE MEASURED RESULT)
                </summary>
                <pre style={{ margin: '8px 0 0', color: '#cbd5e1', fontSize: 11, lineHeight: 1.5, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                  {item.targetTree}
                </pre>
              </details>
            )}

            {/* Raw answer toggle if fallback was triggered or raw answer is present */}
            {item?.rawText && item.rawText !== item.text && (
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <button
                  type="button"
                  onClick={onToggleRaw}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#888',
                    fontSize: 11,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: 0,
                  }}
                >
                  <MessageSquare size={12} />
                  <span>{showRaw ? 'Hide raw answer' : 'Show full unparsed AI answer'}</span>
                  {showRaw ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>

                {showRaw && (
                  <pre
                    style={{
                      marginTop: 8,
                      padding: 10,
                      background: 'rgba(0, 0, 0, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.06)',
                      borderRadius: 4,
                      fontSize: 11,
                      color: '#999',
                      whiteSpace: 'pre-wrap',
                      maxHeight: 160,
                      overflowY: 'auto',
                    }}
                  >
                    {item.rawText}
                  </pre>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
