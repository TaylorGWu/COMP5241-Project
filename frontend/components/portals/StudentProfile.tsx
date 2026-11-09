"use client";

import Link from "next/link";
import { useAccount } from "@/components/AccountProvider";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { portalApi } from "@/lib/portal";
import {
  PortalError,
  PortalLoading,
  PortalShell,
  usePortalResource,
} from "./PortalShell";
import { GoalsPanel } from "./GoalsPanel";
import { PortalIcon } from "./PortalIcon";

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
            <GoalsPanel profile={data.profile} reload={resource.reload} />
          </div>
        </section>
      ) : (
        <PortalLoading />
      )}
    </PortalShell>
  );
}
