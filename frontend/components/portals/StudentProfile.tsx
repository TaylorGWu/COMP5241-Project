"use client";

import Link from "next/link";
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

/** The learner's own page: what they bring to a course and what they want out of it.
 *  It is a page rather than a card on the home screen because it is set once. */
export function StudentProfile() {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const resource = usePortalResource(portalApi.home);
  const data = resource.data;

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
        <section className="portal-profile">
          <h1>{c.profile}</h1>
          <p className="portal-profile__intro">{c.profileHint}</p>
          <div className="portal-profile__card">
            <GoalsPanel profile={data.profile} reload={resource.reload} alwaysOpen />
          </div>
        </section>
      ) : (
        <PortalLoading />
      )}
    </PortalShell>
  );
}
