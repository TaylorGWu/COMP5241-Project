"use client";

import { useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { portalApi, type StudentHome } from "@/lib/portal";
import { PortalError, usePortalWrite } from "./PortalShell";
import { PortalIcon } from "./PortalIcon";

/** The learner's background, goal and weekly budget.
 *
 *  It is the whole profile page, split into the two questions the recommendation
 *  actually reads, so the form explains itself instead of being one anonymous
 *  card. The write endpoint is unchanged. */
export function GoalsPanel({
  profile,
  reload,
  onSaved,
}: {
  profile: StudentHome["profile"];
  reload: () => void;
  onSaved?: () => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [background, setBackground] = useState(profile.background);
  const [goal, setGoal] = useState(profile.goal);
  const [minutes, setMinutes] = useState(
    profile.weeklyMinutes ? String(profile.weeklyMinutes) : "",
  );
  const write = usePortalWrite();

  const save = (event: FormEvent) => {
    event.preventDefault();
    void write.run(
      (signal) =>
        portalApi.profile(
          {
            background: background.trim(),
            goal: goal.trim(),
            weeklyMinutes: minutes.trim() === "" ? 0 : Number(minutes),
          },
          signal,
        ),
      // The suggestion dialog compares the recommendation from before the
      // save, so the callback runs ahead of the refetch.
      () => {
        onSaved?.();
        reload();
      },
    );
  };

  return (
    <form className="teacher-profile-form" onSubmit={save}>
      <section id="student-profile-about" className="profile-section">
        <h2>{c.aboutYou}</h2>
        <p className="profile-optional">{c.profileHint}</p>
        <div className="profile-fields-grid">
          <div className="profile-field">
            <label htmlFor="student-background">{c.background}</label>
            <textarea
              id="student-background"
              maxLength={500}
              rows={4}
              value={background}
              disabled={write.busy}
              onChange={(event) => setBackground(event.target.value)}
            />
            <span className="profile-count">{background.length} / 500</span>
          </div>
          <div className="profile-field">
            <label htmlFor="student-goal">{c.goal}</label>
            <textarea
              id="student-goal"
              maxLength={500}
              rows={4}
              value={goal}
              disabled={write.busy}
              onChange={(event) => setGoal(event.target.value)}
            />
            <span className="profile-count">{goal.length} / 500</span>
          </div>
        </div>
      </section>
      <section id="student-profile-plan" className="profile-section">
        <h2>{c.studyPlan}</h2>
        <p className="profile-optional" id="student-weekly-hint">
          {c.weeklyMinutesHint}
        </p>
        <div className="profile-fields-grid">
          <div className="profile-field">
            <label htmlFor="student-weekly-minutes">{c.weeklyMinutes}</label>
            <input
              id="student-weekly-minutes"
              inputMode="numeric"
              maxLength={4}
              value={minutes}
              disabled={write.busy}
              aria-describedby="student-weekly-hint"
              onChange={(event) =>
                setMinutes(event.target.value.replace(/\D/g, ""))
              }
            />
            <span className="profile-count">{c.minutesPerWeek}</span>
          </div>
        </div>
      </section>
      <footer className="profile-save-bar">
        <div>
          <PortalError error={write.error} />
          {write.saved ? (
            <p className="portal-save-feedback" role="status">
              <PortalIcon name="check" /> {c.saved}
            </p>
          ) : write.error ? null : (
            <p>{c.saveHint}</p>
          )}
        </div>
        <button type="submit" className="portal-button" disabled={write.busy}>
          {write.busy ? c.saving : c.save}
        </button>
      </footer>
    </form>
  );
}
