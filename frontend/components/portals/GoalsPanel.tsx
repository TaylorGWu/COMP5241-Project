"use client";

import { useState, type FormEvent } from "react";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { portalApi, type StudentHome } from "@/lib/portal";
import { PortalError, usePortalWrite } from "./PortalShell";

/** The learner's background, goal and weekly budget.
 *
 *  It lives in the account menu rather than on the home page: it is set once and
 *  then read, so it does not deserve a card next to the courses. */
export function GoalsPanel({
  profile,
  reload,
}: {
  profile: StudentHome["profile"];
  reload: () => void;
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
      reload,
    );
  };

  const filled =
    profile.background || profile.goal || profile.weeklyMinutes > 0;

  return (
    <details className="account-menu-goals-panel">
      <summary>{c.profile}</summary>
      <div className="account-menu-goals-body">
        {filled ? (
          <dl>
            <div>
              <dt>{c.background}</dt>
              <dd>{profile.background || c.notProvided}</dd>
            </div>
            <div>
              <dt>{c.goal}</dt>
              <dd>{profile.goal || c.notProvided}</dd>
            </div>
            <div>
              <dt>{c.weeklyMinutes}</dt>
              <dd>
                {profile.weeklyMinutes
                  ? `${profile.weeklyMinutes} ${c.minutes}`
                  : c.notProvided}
              </dd>
            </div>
          </dl>
        ) : (
          <p>{c.profileHint}</p>
        )}
        <form onSubmit={save}>
          <label>
            {c.background}
            <textarea
              maxLength={500}
              value={background}
              onChange={(event) => setBackground(event.target.value)}
            />
          </label>
          <label>
            {c.goal}
            <textarea
              maxLength={500}
              value={goal}
              onChange={(event) => setGoal(event.target.value)}
            />
          </label>
          <label>
            {c.weeklyMinutes}
            <input
              inputMode="numeric"
              maxLength={4}
              value={minutes}
              onChange={(event) => setMinutes(event.target.value.replace(/\D/g, ""))}
            />
          </label>
          <button type="submit" className="portal-button" disabled={write.busy}>
            {write.busy ? c.saving : c.save}
          </button>
        </form>
        <PortalError error={write.error} />
      </div>
    </details>
  );
}
