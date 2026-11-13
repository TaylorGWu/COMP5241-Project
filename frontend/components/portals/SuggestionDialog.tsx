"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import {
  studentCourseHref,
  type Course,
  type NextStepReason,
  type StudentHome,
} from "@/lib/portal";
import { PortalIcon } from "./PortalIcon";

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
 *  or after a goal save. The course block borrows the catalogue card's anatomy,
 *  and the reason is copy keyed by the code the backend sends - never a rebuilt
 *  sentence. With nothing left to suggest, the dialog says so instead of
 *  showing an empty shell. */
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
    if (open) ref.current?.showModal();
    else ref.current?.close();
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
          <div className="portal-suggestion-dialog__course">
            <header className="portal-course__head">
              <span className="portal-course__code">
                {course.courseCode || course.subject}
              </span>
              <span className="portal-course__value">{course.durationMin} min</span>
            </header>
            <h3>
              <Link href={studentCourseHref(course.id)}>{course.title}</Link>
            </h3>
            <p className="portal-tags">
              {[course.subject, course.level]
                .filter(Boolean)
                .map((label) => (
                  <span key={label}>{label}</span>
                ))}
            </p>
            <p className="portal-course-description">{course.description}</p>
          </div>
          <div className="portal-suggestion-dialog__note">
            <PortalIcon name="spark" />
            <p>
              <strong>{c.why}: </strong>
              {reason}
            </p>
          </div>
        </>
      ) : (
        <p className="portal-suggestion-dialog__empty">{c.suggestionEmpty}</p>
      )}
      <div className="portal-suggestion-dialog__buttons">
        <button
          type="button"
          className="portal-button portal-button--secondary"
          autoFocus
          onClick={() => ref.current?.close()}
        >
          {c.suggestionDismiss}
        </button>
        {course ? (
          <Link
            className="portal-button"
            href={studentCourseHref(course.id)}
            onClick={() => ref.current?.close()}
          >
            {c.viewCourse}
          </Link>
        ) : (
          <Link
            className="portal-button"
            href="/student"
            onClick={() => ref.current?.close()}
          >
            {c.browseCourses}
          </Link>
        )}
      </div>
    </dialog>
  );
}
