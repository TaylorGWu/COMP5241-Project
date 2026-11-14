"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useAccount } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { authJson, safeDestination, type SessionResponse } from "@/lib/auth";
import styles from "./AuthScreen.module.css";

export function AuthFrame({ children }: { children: ReactNode }) {
  return <main className={`public-page auth-page ${styles.page}`}>
    <PublicHeader simple />
    <div className={styles.shell}>
      <section className={styles.content}>{children}</section>
      <aside className={`auth-visual ${styles.visual}`} aria-hidden="true">
        <Image src="/images/learning-studio.png" alt="" fill sizes="(max-width: 820px) 0px, 50vw" priority />
      </aside>
    </div>
  </main>;
}

export function RoleChooser() {
  const { locale } = useI18n(); const c = publicCopy(locale);
  return <AuthFrame><div className="auth-form-heading"><h1>{c.join}</h1><p>{c.joinBody}</p></div><div className="role-options">{(["student", "instructor"] as const).map((role) => <Link key={role} href={`/register/${role}`} className="role-option"><div><span>{c[role]}</span><p>{role === "student" ? c.studentBlurb : c.instructorBlurb}</p></div></Link>)}</div><p className="auth-switch">{c.hasAccount} <Link href="/login">{c.login}</Link></p><p className="auth-small-note">{c.roleNotice}</p></AuthFrame>;
}

export function AuthScreen({ mode }: { mode: "login" | "student" | "instructor" }) {
  const { locale } = useI18n(); const c = publicCopy(locale);
  const { accept } = useAccount(); const router = useRouter();
  const [show, setShow] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const registration = mode !== "login";
  const fail = (message: string) => { setError(message); requestAnimationFrame(() => errorRef.current?.focus()); };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    if (registration && form.get("password") !== form.get("confirm")) { fail(c.mismatch); return; }
    setBusy(true); setError("");
    try {
      let response: SessionResponse;
      if (registration) {
        form.set("role", mode); form.delete("confirm");
        response = await authJson<SessionResponse>("/api/auth/register", { method: "POST", body: form });
      } else {
        response = await authJson<SessionResponse>("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: form.get("email"), password: form.get("password") }) });
      }
      accept(response.user);
      const next = new URLSearchParams(window.location.search).get("next");
      router.replace(safeDestination(next, response.user)); router.refresh();
    } catch (cause) { fail(cause instanceof Error ? cause.message : c.connection); }
    finally { setBusy(false); }
  };
  return <AuthFrame><div className="auth-form-heading">{registration ? <Link href="/register" className="auth-back">{c.switchRole}</Link> : null}<h1>{mode === "login" ? c.welcome : mode === "student" ? c.studentRegister : c.teacherRegister}</h1><p>{mode === "login" ? c.loginBody : mode === "student" ? c.studentRegisterBody : c.teacherRegisterBody}</p></div>
    <form className="auth-form" onSubmit={submit} aria-busy={busy}>
      {error ? <div className="auth-error" role="alert" tabIndex={-1} ref={errorRef}>{error}</div> : null}
      {registration ? <label>{c.name}<input name="name" autoComplete="name" required minLength={2} maxLength={100} /></label> : null}
      <label>{c.email}<input name="email" type="email" autoComplete="email" inputMode="email" required maxLength={254} /></label>
      <div className="auth-password-field"><label htmlFor="account-password">{c.password}</label><span className="auth-password"><input id="account-password" name="password" type={show ? "text" : "password"} autoComplete={registration ? "new-password" : "current-password"} required minLength={registration ? 15 : 1} maxLength={128} aria-describedby={registration ? "password-help" : undefined} /><button type="button" onClick={() => setShow(!show)} aria-label={show ? c.hide : c.show} aria-pressed={show}>{show ? c.hideShort : c.showShort}</button></span>{registration ? <small id="password-help">{c.passwordHint}</small> : null}</div>
      {registration ? <label>{c.confirm}<input name="confirm" type={show ? "text" : "password"} autoComplete="new-password" required minLength={15} maxLength={128} /></label> : null}
      <button className="public-button auth-submit" type="submit" disabled={busy}>{busy ? c.waiting : mode === "login" ? c.login : c.create}</button>
    </form>
    <p className="auth-switch">{registration ? c.hasAccount : c.noAccount} <Link href={registration ? "/login" : "/register"}>{registration ? c.login : c.create}</Link></p>
    <p className="auth-small-note">{c.localNote}</p>
  </AuthFrame>;
}
