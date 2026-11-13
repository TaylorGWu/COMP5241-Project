"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useAccount } from "@/components/AccountProvider";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import {
  portalApi,
  studentCourseHref,
  type NextStepReason,
  type StudentHome,
} from "@/lib/portal";
import {
  PortalError,
  PortalLoading,
  PortalShell,
  usePortalResource,
} from "./PortalShell";
import { GoalsPanel } from "./GoalsPanel";
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

/** The learner's own page: who they are, what they bring to a course and what
 *  they want out of it. It uses the teacher profile's shell so both roles edit
 *  their account in the same recognisable place. */
export function StudentProfile() {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const { user } = useAccount();
  const resource = usePortalResource(portalApi.home);
  const data = resource.data;
  const initial = user?.name.trim().slice(0, 1).toLocaleUpperCase() ?? "";
  const dialogRef = useRef<HTMLDialogElement>(null);
  const previousSuggestion = useRef<StudentHome["recommendation"]>(null);
  const dataAtSave = useRef<StudentHome | null>(null);
  const [awaitingSuggestion, setAwaitingSuggestion] = useState(false);

  // A goal save can point the recommendation somewhere new. Compare the
  // suggestion captured at save time with the refetched one and announce the
  // change in a dialog; the standing card on My learning stays as the quiet
  // default for visits that did not change anything. The refetch has landed
  // once `data` is no longer the object the save started from - the loading
  // flag alone cannot tell, because it is raised a tick after the save.
  useEffect(() => {
    if (!awaitingSuggestion || data === dataAtSave.current) return;
    setAwaitingSuggestion(false);
    const current = data?.recommendation ?? null;
    const previous = previousSuggestion.current;
    previousSuggestion.current = null;
    const moved =
      current !== null &&
      previous !== null &&
      (previous.courseId !== current.courseId ||
        previous.reasonCode !== current.reasonCode);
    if (moved) dialogRef.current?.showModal();
  }, [awaitingSuggestion, data]);

  const suggestion = data?.recommendation ?? null;
  const suggestedCourse = suggestion
    ? data?.courses.find((course) => course.id === suggestion.courseId)
    : undefined;
  const reason = suggestion ? c[REASONS[suggestion.reasonCode]] : "";

  return (
    <PortalShell
      title={c.profile}
      action={
        <Link
          href="/student"
          className="portal-button portal-button--quiet portal-button--back"
        >
          <PortalIcon name="chevron" /> {c.back}
        </Link>
      }
    >
      <PortalError error={resource.error} retry={resource.reload} />
      {/* Keep the panel mounted across a save: reloading the resource must not
          replace it with the loading state, or the save confirmation never shows. */}
      {data ? (
        <section className="portal-profile profile-page">
          <h1 className="sr-only">{c.profile}</h1>
          <div className="teacher-profile-layout">
            <aside className="teacher-profile-aside">
              <div className="profile-identity">
                <span
                  className="teacher-photo teacher-photo--initial"
                  aria-hidden="true"
                >
                  {initial}
                </span>
                <div>
                  <strong>{user?.name}</strong>
                  <span>{c.studentAccount}</span>
                  <span
                    className="profile-identity-email"
                    title={user?.email}
                  >
                    {user?.email}
                  </span>
                </div>
              </div>
              <div className="profile-review-note">
                <h2>{c.recommendationNoteTitle}</h2>
                <p>{c.recommendationNote}</p>
                <Link href="/student">
                  {c.seeNextStep}
                  <svg aria-hidden="true" viewBox="0 0 24 24">
                    <path d="M5 12h14m-6-6 6 6-6 6" />
                  </svg>
                </Link>
              </div>
            </aside>
            <GoalsPanel
              profile={data.profile}
              reload={resource.reload}
              onSaved={() => {
                previousSuggestion.current = data.recommendation ?? null;
                dataAtSave.current = data;
                setAwaitingSuggestion(true);
              }}
            />
          </div>
          <dialog
            ref={dialogRef}
            className="portal-suggestion-dialog"
            aria-labelledby="portal-suggestion-title"
          >
            <h2 id="portal-suggestion-title">{c.recommendation}</h2>
            <p className="portal-suggestion-dialog__lead">{c.suggestionLead}</p>
            {suggestedCourse ? (
              <>
                <h3 className="portal-suggestion-dialog__course">
                  <Link href={studentCourseHref(suggestedCourse.id)}>
                    {suggestedCourse.title}
                  </Link>
                </h3>
                <p className="portal-suggestion-dialog__why">
                  <strong>{c.why}: </strong>
                  {reason}
                </p>
              </>
            ) : null}
            <div className="portal-suggestion-dialog__buttons">
              <button
                type="button"
                className="portal-button portal-button--secondary"
                onClick={() => dialogRef.current?.close()}
              >
                {c.suggestionDismiss}
              </button>
              {suggestedCourse ? (
                <Link
                  className="portal-button"
                  href={studentCourseHref(suggestedCourse.id)}
                  onClick={() => dialogRef.current?.close()}
                >
                  {c.viewCourse}
                </Link>
              ) : null}
            </div>
          </dialog>
        </section>
      ) : (
        <PortalLoading />
      )}
    </PortalShell>
  );
}
