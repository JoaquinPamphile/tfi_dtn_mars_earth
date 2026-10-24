import { useCallback, useEffect, useRef, useState } from "react";

export type PlaybackSpeed = 1 | 2 | 4;

const BASE_MS = 1700;

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

export function useRecoveryPlayback(stepCount: number, reduced: boolean) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<PlaybackSpeed>(1);
  const indexRef = useRef(0);
  indexRef.current = index;

  useEffect(() => {
    if (reduced) {
      setPlaying(false);
    }
  }, [reduced]);

  useEffect(() => {
    setIndex(0);
    setPlaying(false);
  }, [stepCount]);

  useEffect(() => {
    if (!playing || reduced || stepCount === 0) {
      return;
    }
    const timer = window.setInterval(() => {
      const current = indexRef.current;
      if (current >= stepCount - 1) {
        setPlaying(false);
        return;
      }
      setIndex(current + 1);
    }, BASE_MS / speed);
    return () => window.clearInterval(timer);
  }, [playing, reduced, speed, stepCount]);

  const play = useCallback(() => {
    if (reduced || stepCount === 0) {
      return;
    }
    setIndex((current) => (current >= stepCount - 1 ? 0 : current));
    setPlaying(true);
  }, [reduced, stepCount]);

  const pause = useCallback(() => setPlaying(false), []);

  const toggle = useCallback(() => {
    if (playing) {
      setPlaying(false);
      return;
    }
    play();
  }, [play, playing]);

  const restart = useCallback(() => {
    setPlaying(false);
    setIndex(0);
  }, []);

  const next = useCallback(() => {
    setPlaying(false);
    setIndex((current) => Math.min(Math.max(stepCount - 1, 0), current + 1));
  }, [stepCount]);

  const previous = useCallback(() => {
    setPlaying(false);
    setIndex((current) => Math.max(0, current - 1));
  }, []);

  const select = useCallback((nextIndex: number) => {
    setPlaying(false);
    setIndex(nextIndex);
  }, []);

  return {
    index,
    playing,
    speed,
    setSpeed,
    play,
    pause,
    toggle,
    restart,
    next,
    previous,
    select,
  };
}
