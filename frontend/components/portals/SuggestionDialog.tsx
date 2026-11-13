"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import type { Course, NextStepReason, StudentHome } from "@/lib/portal";
import { CourseCard } from "./CourseCard";

const REASONS: Record<
  NextStepReason,
  "reasonResume" | "reasonGoal" | "reasonTime" | "reasonStart"
> = {
  resume: "reasonResume",
  goal: "reasonGoal",
  time: "reasonTime",
  start: "reasonStart",
};

/** The bell's seen state is a browser fact, not a server fact: the key of the
 *  last suggestion the learner opened lives in localStorage, so the shake
 *  restarts only when the recommendation itself changes. */
export const SUGGESTION_SEEN_KEY = "portal.suggestion.seen";

/** The one suggestion, opened where it is asked for: from the My learning bell
 *  or after a goal save. The recommended course appears as the very card the
 *  catalogue shows - same anatomy, same way in - and with nothing left to
 *  suggest, the dialog says so instead of showing an empty shell. */
export function SuggestionDialog({
  course,
  recommendation,
  open,
  onClose,
}: {
  course?: Course;
  recommendation: StudentHome["recommendation"];
  open: boolean;
  onClose: () => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) {
      ref.current?.showModal();
      // showModal focuses the first focusable, which would light up the whole
      // course card; the dismiss button is the safe landing spot, as in the
      // slide editor's confirm dialog.
      const dismiss = ref.current?.querySelector<HTMLButtonElement>(
        ".portal-suggestion-dialog__buttons button",
      );
      dismiss?.focus();
    } else {
      ref.current?.close();
    }
  }, [open]);

  useEffect(() => {
    if (open && recommendation) {
      try {
        window.localStorage.setItem(
          SUGGESTION_SEEN_KEY,
          `${recommendation.courseId}|${recommendation.reasonCode}`,
        );
      } catch {
        // Private browsing may refuse storage; the bell then simply shakes
        // again next visit instead of breaking the dialog.
      }
    }
  }, [open, recommendation]);

  const reason = recommendation ? c[REASONS[recommendation.reasonCode]] : "";

  return (
    <dialog
      ref={ref}
      className="portal-suggestion-dialog"
      aria-labelledby="portal-suggestion-title"
      onClose={onClose}
    >
      <h2 id="portal-suggestion-title">{c.recommendation}</h2>
      {course ? (
        <>
          <p className="portal-suggestion-dialog__lead">{c.suggestionLead}</p>
          <CourseCard course={course} query="" reason={reason} />
        </>
      ) : (
        <p className="portal-suggestion-dialog__empty">{c.suggestionEmpty}</p>
      )}
      <div className="portal-suggestion-dialog__buttons">
        <button
          type="button"
          className="portal-button portal-button--secondary"
          onClick={() => ref.current?.close()}
        >
          {c.suggestionDismiss}
        </button>
        {!course ? (
          <Link
            className="portal-button"
            href="/student"
            onClick={() => ref.current?.close()}
          >
            {c.browseCourses}
          </Link>
        ) : null}
      </div>
    </dialog>
  );
}
