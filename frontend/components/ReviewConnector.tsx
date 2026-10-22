"use client";

import { useEffect, useLayoutEffect, useState } from "react";

import type { Patch } from "@/lib/api";

type ConnectorGeometry = {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
};

/** A patch payload names the region that the teacher should inspect. */
export function patchReviewField(patch: Patch): string {
  if ("bulletEdit" in patch.payload || "bullets" in patch.payload) return "bullets";
  if ("title" in patch.payload) return "title";
  if ("speakerNotes" in patch.payload) return "speakerNotes";
  if ("visuals" in patch.payload) return "visuals";
  if ("layout" in patch.payload) return "layout";
  return "slide";
}

function selectorValue(value: string) {
  return typeof CSS !== "undefined" && CSS.escape ? CSS.escape(value) : value.replaceAll('"', '\\"');
}

/**
 * One selected review item, one visual relationship. Keeping this separate
 * from both columns prevents review controls from leaking into the material.
 */
export function ReviewConnector({ patch, isTargetActive }: { patch: Patch | null; isTargetActive: boolean }) {
  const [geometry, setGeometry] = useState<ConnectorGeometry | null>(null);

  useLayoutEffect(() => {
    if (!patch || patch.kind !== "slide" || !isTargetActive) {
      setGeometry(null);
      return;
    }

    const update = () => {
      const card = document.querySelector<HTMLElement>(`[data-review-card-id="${selectorValue(patch.id)}"]`);
      const field = patchReviewField(patch);
      const target = document.querySelector<HTMLElement>(`[data-review-target="slide:${selectorValue(patch.target_id)}:${selectorValue(field)}"]`)
        ?? document.querySelector<HTMLElement>(`[data-review-target="slide:${selectorValue(patch.target_id)}:slide"]`);
      if (!card || !target) {
        setGeometry(null);
        return;
      }
      const cardBox = card.getBoundingClientRect();
      const targetBox = target.getBoundingClientRect();
      setGeometry({
        fromX: cardBox.left,
        fromY: cardBox.top + cardBox.height / 2,
        toX: targetBox.right,
        toY: targetBox.top + targetBox.height / 2,
      });
    };

    update();
    const observer = new ResizeObserver(update);
    observer.observe(document.documentElement);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [isTargetActive, patch]);

  useEffect(() => {
    if (!patch || patch.kind !== "slide" || !isTargetActive) return;
    const frame = requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    return () => cancelAnimationFrame(frame);
  }, [isTargetActive, patch]);

  if (!geometry) return null;
  const bendX = Math.max(geometry.toX + 28, geometry.fromX - 56);
  const path = `M ${geometry.fromX} ${geometry.fromY} C ${bendX} ${geometry.fromY}, ${bendX} ${geometry.toY}, ${geometry.toX} ${geometry.toY}`;

  return (
    <svg className="review-connector" aria-hidden="true" data-review-connector="1">
      <path className="review-connector__halo" d={path} />
      <path className="review-connector__line" d={path} />
      <circle className="review-connector__point" cx={geometry.toX} cy={geometry.toY} r="4" />
    </svg>
  );
}
