"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAccount } from "@/components/AccountProvider";
import { PrivateTeacherPhoto } from "@/components/PrivateTeacherPhoto";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { teacherProfileCopy, type TeacherProfile } from "@/lib/teacher-profile";
import { authJson, roleDestination, type Account } from "@/lib/auth";

/** One account disclosure shared by signed-in public and teacher navigation. */
export function AccountActions({ menuExtra }: { menuExtra?: ReactNode }) {
  const { user } = useAccount();
  return user ? <AccountMenu key={user.id} user={user} menuExtra={menuExtra} /> : null;
}

function AccountMenu({ user, menuExtra }: { user: Account; menuExtra?: ReactNode }) {
  const { logout } = useAccount();
  const router = useRouter(); const pathname = usePathname();
  const { locale } = useI18n(); const c = publicCopy(locale);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState<string | null>(null);
  const host = useRef<HTMLDivElement>(null); const trigger = useRef<HTMLButtonElement>(null);
  const panelId = useId(); const triggerId = useId();
  const destination = roleDestination(user);

  useEffect(() => {
    if (user.role !== "instructor") return;
    let pending: AbortController | null = null;
    const load = () => {
      pending?.abort();
      const request = new AbortController(); pending = request;
      void authJson<{ profile: TeacherProfile }>("/api/auth/profile", { signal: request.signal })
        .then(data => { if (!request.signal.aborted) setVersion(data.profile.hasAvatar ? data.profile.avatarVersion : null); })
        .catch(() => {});
    };
    load();
    window.addEventListener("coursework-profile-photo-changed", load);
    return () => { pending?.abort(); window.removeEventListener("coursework-profile-photo-changed", load); };
  }, [user.role]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!host.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);

  const close = () => setOpen(false);
  return <div ref={host} className="account-actions account-menu" onBlur={event => {
    // Disabling a focused sign-out button blurs it to BODY (relatedTarget=null).
    // Keep the disclosure mounted so a failed request can show its retry/error.
    if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false);
  }}>
    <button ref={trigger} id={triggerId} type="button" className="account-menu-trigger" data-account-menu-trigger
      aria-label={`${c.accountLabel} · ${user.name}`} aria-expanded={open} aria-controls={open ? panelId : undefined}
      onClick={() => setOpen(value => !value)} onKeyDown={event => {
        if (event.key === "ArrowDown") {
          event.preventDefault(); setOpen(true);
          requestAnimationFrame(() => host.current?.querySelector<HTMLAnchorElement>(".account-menu-panel a")?.focus());
        }
      }}>
      <PrivateTeacherPhoto name={user.name} version={version} />
    </button>
    {open ? <div id={panelId} role="group" aria-labelledby={triggerId} className="account-menu-panel" data-account-menu-panel>
      <div className="account-menu-summary"><strong className="account-menu-name">{user.name}</strong><span>{user.email}</span></div>
      {menuExtra}
      {user.role === "student" ? (
        <Link className="account-menu-goals" href="/student/profile" onClick={close}>
          Your learning goals
        </Link>
      ) : null}
      <div className="account-menu-links">
        <Link href={destination} onClick={close} aria-current={pathname === destination ? "page" : undefined}>{user.role === "instructor" && user.status !== "approved" ? teacherProfileCopy(locale).qualification : c.workspace}</Link>
        {user.role === "instructor" ? <Link href="/profile" onClick={close} aria-current={pathname === "/profile" ? "page" : undefined}>{teacherProfileCopy(locale).title}</Link> : null}
        {pathname !== "/" ? <Link href="/" onClick={close}>{c.home}</Link> : null}
      </div>
      <button type="button" className="account-menu-logout" data-account-logout disabled={busy} onClick={async () => {
        setBusy(true); setError("");
        try { await logout(); router.replace("/login"); router.refresh(); }
        catch (cause) { setError(cause instanceof Error ? cause.message : c.connection); }
        finally { setBusy(false); }
      }}>{busy ? c.waiting : c.logout}</button>
      {error ? <p className="account-menu-error" role="alert">{error}</p> : null}
    </div> : null}
  </div>;
}
