import { FastForward, Pause, Play, Rewind, RotateCcw } from 'lucide-react';
import type { CSSProperties } from 'react';
import { formatTime } from '../../core/playback';

interface Props {
  currentTime: number;
  duration: number;
  playing: boolean;
  speed: number;
  disabled: boolean;
  onToggle: () => void;
  onSeek: (time: number) => void;
  onJump: (seconds: number) => void;
  onSpeedChange: (speed: number) => void;
}

const SPEEDS = [0.25, 0.5, 1, 1.5, 2, 4];

/** UI-only playback controls. The playhead math lives in core/playback.ts. */
export default function PlaybackBar({
  currentTime, duration, playing, speed, disabled, onToggle, onSeek, onJump, onSpeedChange,
}: Props) {
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <section className="playback-bar" aria-label="Replay playback controls">
      <div className="timeline-row">
        <span className="timecode">{formatTime(currentTime)}</span>
        <input
          className="timeline-slider"
          type="range"
          min={0}
          max={Math.max(duration, 0.001)}
          step={0.01}
          value={Math.min(currentTime, duration)}
          style={{ '--timeline-progress': `${progress}%` } as CSSProperties}
          onChange={(event) => onSeek(Number(event.target.value))}
          disabled={disabled}
          aria-label="Replay position"
        />
        <span className="timecode timecode--muted">{formatTime(duration)}</span>
      </div>
      <div className="transport-row">
        <div className="transport-group">
          <button className="transport-button transport-button--small" type="button" onClick={() => onJump(-5)} disabled={disabled} aria-label="Back five seconds">
            <Rewind size={15} />
          </button>
          <button className="transport-button transport-button--play" type="button" onClick={onToggle} disabled={disabled} aria-label={playing ? 'Pause replay' : 'Play replay'}>
            {playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
          </button>
          <button className="transport-button transport-button--small" type="button" onClick={() => onJump(5)} disabled={disabled} aria-label="Forward five seconds">
            <FastForward size={15} />
          </button>
          <button className="transport-button transport-button--small" type="button" onClick={() => onSeek(0)} disabled={disabled} aria-label="Restart replay">
            <RotateCcw size={14} />
          </button>
        </div>
        <label className="speed-select">
          <span>Speed</span>
          <select value={speed} onChange={(event) => onSpeedChange(Number(event.target.value))} disabled={disabled}>
            {SPEEDS.map((item) => <option value={item} key={item}>{item}×</option>)}
          </select>
        </label>
      </div>
    </section>
  );
}
