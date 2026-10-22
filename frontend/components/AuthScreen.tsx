"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useAccount } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { Arrow, Document } from "@/components/PublicHome";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { authJson, safeDestination, validateQualification, type SessionResponse } from "@/lib/auth";

export function AuthFrame({ children }: { children: ReactNode }) {
  const { locale } = useI18n(); const c = publicCopy(locale);
  return <main className="public-page auth-page"><PublicHeader simple /><div className="auth-layout"><aside className="auth-story"><h2>{c.authSideTitle}</h2><p>{c.authSideBody}</p><div className="auth-story-art" aria-hidden="true"><span className="auth-paper auth-paper--back" /><div className="auth-paper"><div><i /><i /><i /></div><strong>Git, explained.</strong><span>app.js</span><div className="auth-paper-track"><b /><b /><b /></div><p>Draft. Review. Teach.</p></div><span className="auth-annotation">Human judgment.<br />Always.</span></div><p className="auth-story-signature">{c.authSideQuote}</p></aside><section className="auth-content">{children}</section></div></main>;
}

export function RoleChooser() {
  const { locale } = useI18n(); const c = publicCopy(locale);
  return <AuthFrame><div className="auth-form-heading"><h1>{c.join}</h1><p>{c.joinBody}</p></div><div className="role-options">{(["student", "instructor"] as const).map((role) => <Link key={role} href={`/register/${role}`} className="role-option"><div><span>{c[role]}</span><p>{role === "student" ? c.studentBlurb : c.instructorBlurb}</p></div><Arrow /></Link>)}</div><p className="auth-switch">{c.hasAccount} <Link href="/login">{c.login}</Link></p><p className="auth-small-note">{c.roleNotice}</p></AuthFrame>;
}

export function AuthScreen({ mode }: { mode: "login" | "student" | "instructor" }) {
  const { locale } = useI18n(); const c = publicCopy(locale);
  const { accept } = useAccount(); const router = useRouter();
  const [show, setShow] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const [filename, setFilename] = useState("");
  const registration = mode !== "login";
  const fail = (message: string) => { setError(message); requestAnimationFrame(() => errorRef.current?.focus()); };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy) return;
    const form = new FormData(event.currentTarget);
    if (registration && form.get("password") !== form.get("confirm")) { fail(c.mismatch); return; }
    if (mode === "instructor") {
      const file = form.get("qualification");
      if (!(file instanceof File) || !file.name) { fail(c.fileRequired); return; }
      const issue = validateQualification(file);
      if (issue) { fail(issue === "size" ? c.fileSize : issue === "type" ? c.fileType : c.fileEmpty); return; }
    }
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
      <div className="auth-password-field"><label htmlFor="account-password">{c.password}</label><span className="auth-password"><input id="account-password" name="password" type={show ? "text" : "password"} autoComplete={registration ? "new-password" : "current-password"} required minLength={registration ? 15 : 1} maxLength={128} aria-describedby={registration ? "password-help" : undefined} /><button type="button" onClick={() => setShow(!show)} aria-label={show ? c.hide : c.show} aria-pressed={show}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{show ? <path d="m3 3 18 18" /> : null}</svg></button></span>{registration ? <small id="password-help">{c.passwordHint}</small> : null}</div>
      {registration ? <label>{c.confirm}<input name="confirm" type={show ? "text" : "password"} autoComplete="new-password" required minLength={15} maxLength={128} /></label> : null}
      {mode === "instructor" ? <div className="qualification-field"><label htmlFor="qualification">{c.qualification}</label><p id="qualification-help">{c.qualificationHint}</p><label className="qualification-upload" htmlFor="qualification"><Document /><span>{filename || c.chooseFile}</span><input id="qualification" name="qualification" type="file" accept="application/pdf,image/png,image/jpeg" required aria-describedby="qualification-help" onChange={(event) => setFilename(event.target.files?.[0]?.name ?? "")} /></label></div> : null}
      <button className="public-button auth-submit" type="submit" disabled={busy}>{busy ? c.waiting : mode === "login" ? c.login : mode === "instructor" ? c.submitApplication : c.create}{!busy ? <Arrow /> : null}</button>
    </form>
    <p className="auth-switch">{registration ? c.hasAccount : c.noAccount} <Link href={registration ? "/login" : "/register"}>{registration ? c.login : c.create}</Link></p>
    <p className="auth-small-note">{c.localNote}</p>
  </AuthFrame>;
}
