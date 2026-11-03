import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { getReplayDuration, sampleAtTime } from '../../core/playback';
import type { ReplayScene } from '../../core/scene';

/** Playback state is separate from the viewer. The viewer only receives a sampled frame. */
export function usePlayback(replay: ReplayScene | null) {
  const frames = replay?.frames ?? [];
  const duration = useMemo(() => getReplayDuration(frames), [frames]);
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const timeRef = useRef(0);

  // Reset playback whenever another replay is loaded.
  useEffect(() => {
    timeRef.current = 0;
    setCurrentTime(0);
    setPlaying(false);
  }, [replay]);

  const seek = useCallback((time: number) => {
    const safeTime = Math.min(duration, Math.max(0, Number.isFinite(time) ? time : 0));
    timeRef.current = safeTime;
    setCurrentTime(safeTime);
  }, [duration]);

  const togglePlayback = useCallback(() => {
    if (duration <= 0) return;
    if (playing) {
      // Flush the most recent RAF time before pausing so the image and clock agree.
      setCurrentTime(timeRef.current);
      setPlaying(false);
      return;
    }
    if (timeRef.current >= duration) seek(0);
    setPlaying(true);
  }, [duration, playing, seek]);

  const jump = useCallback((offset: number) => seek(timeRef.current + offset), [seek]);

  useEffect(() => {
    if (!playing || duration <= 0) return undefined;

    let requestId = 0;
    let previousTimestamp = performance.now();
    let lastPublishedTimestamp = previousTimestamp;
    const frameIntervalMs = 1000 / Math.max(1, replay?.blueprint.framesPerSecond ?? 30);
    const tick = (timestamp: number) => {
      const elapsedSeconds = Math.max(0, (timestamp - previousTimestamp) / 1000);
      previousTimestamp = timestamp;
      const nextTime = timeRef.current + elapsedSeconds * speed;

      if (nextTime >= duration) {
        timeRef.current = duration;
        setCurrentTime(duration);
        setPlaying(false);
        return;
      }

      timeRef.current = nextTime;
      // The backend currently emits 30 snapshots per second. Publish at that
      // cadence instead of forcing React to re-render at the monitor's 60 Hz.
      if (timestamp - lastPublishedTimestamp >= frameIntervalMs) {
        setCurrentTime(nextTime);
        lastPublishedTimestamp = timestamp;
      }
      requestId = window.requestAnimationFrame(tick);
    };

    requestId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(requestId);
  }, [playing, speed, duration, replay]);

  const frame = useMemo(() => sampleAtTime(frames, currentTime), [frames, currentTime]);

  return {
    currentTime,
    duration,
    playing,
    speed,
    frame,
    seek,
    jump,
    setSpeed,
    togglePlayback,
    stop: () => setPlaying(false),
  };
}
