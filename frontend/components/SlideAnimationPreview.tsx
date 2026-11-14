"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Button, cx } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { SlideAnimation } from "@/lib/api";

/** State consumed by the existing slide renderer; it never changes slide IR. */
export type AnimationPresentation = {
  animatedTargets: ReadonlySet<string>;
  revealedTargets: ReadonlySet<string>;
  emphasizedTarget: string | null;
};

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  return reduced;
}

/**
 * A deterministic, teacher-only preview controller. It schedules presentation
 * state over already-rendered regions; it does not generate media or mutate a
 * draft. Reduced-motion users always receive the fully readable static slide.
 */
export function SlideAnimationPreview({
  animation,
  children,
}: {
  animation: SlideAnimation;
  children: (presentation: AnimationPresentation) => React.ReactNode;
}) {
  const { t } = useI18n();
  const reducedMotion = useReducedMotion();
  const steps = useMemo(
    () => [...animation.steps].sort((left, right) => left.atMs - right.atMs),
    [animation.steps],
  );
  const animatedTargets = useMemo(() => new Set(steps.map((step) => step.target)), [steps]);
  const finishAt = steps.reduce((latest, step) => Math.max(latest, step.atMs + step.durationMs), 0);
  const [elapsed, setElapsed] = useState(() => (animation.autoplay ? -1 : finishAt));
  const [running, setRunning] = useState(animation.autoplay);
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    setElapsed(animation.autoplay ? -1 : finishAt);
    setRunning(animation.autoplay);
  }, [animation, finishAt]);

  useEffect(() => {
    if (!reducedMotion) return;
    setElapsed(finishAt);
    setRunning(false);
  }, [finishAt, reducedMotion]);

  useEffect(() => {
    if (!running || reducedMotion) return;
    const next = steps.find((step) => step.atMs > elapsed);
    if (!next) {
      setRunning(false);
      return;
    }
    startedAtRef.current = performance.now();
    const timer = window.setTimeout(() => setElapsed(next.atMs), Math.max(0, next.atMs - elapsed));
    return () => window.clearTimeout(timer);
  }, [elapsed, reducedMotion, running, steps]);

  const revealedTargets = useMemo(
    () => new Set(steps.filter((step) => step.atMs <= elapsed).map((step) => step.target)),
    [elapsed, steps],
  );
  const emphasizedTarget = useMemo(() => {
    const active = steps.filter(
      (step) => step.kind === "emphasis" && elapsed >= step.atMs && elapsed <= step.atMs + step.durationMs,
    );
    return active.at(-1)?.target ?? null;
  }, [elapsed, steps]);

  const pause = () => {
    if (startedAtRef.current != null) {
      setElapsed((current) => Math.min(finishAt, current + performance.now() - startedAtRef.current!));
    }
    setRunning(false);
  };
  const replay = () => {
    setElapsed(-1);
    setRunning(true);
  };

  return (
    <div className="slide-animation-preview" data-animation-preview="1">
      {children({ animatedTargets, revealedTargets, emphasizedTarget })}
      <div className="slide-animation-preview__controls" aria-label={t.slide.previewAnimation}>
        {reducedMotion ? (
          <span className="slide-animation-preview__reduced">{t.slide.reducedMotion}</span>
        ) : running ? (
          <Button variant="quiet" className="slide-animation-preview__button" onClick={pause}>
            {t.slide.pauseAnimation}
          </Button>
        ) : (
          <Button
            variant="quiet"
            className={cx("slide-animation-preview__button", elapsed >= finishAt && "slide-animation-preview__button--replay")}
            onClick={replay}
          >
            {elapsed >= finishAt ? t.slide.replayAnimation : t.slide.resumeAnimation}
          </Button>
        )}
      </div>
    </div>
  );
}
