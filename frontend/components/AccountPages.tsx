"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AccountGate, useAccount } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { Check, Document } from "@/components/PublicHome";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { AUTH_API_BASE, authJson, roleDestination, validateQualification, type Application } from "@/lib/auth";

export function AccountActions() {
  const { user, logout } = useAccount(); const router = useRouter();
  const { locale } = useI18n(); const c = publicCopy(locale);
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  return <div className="account-actions"><span title={user?.email}>{user?.name}</span><button type="button" disabled={busy} onClick={async () => { setBusy(true); try { await logout(); router.replace("/login"); router.refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : c.connection); } finally { setBusy(false); } }}>{busy ? c.waiting : c.logout}</button>{error ? <span className="account-action-error" role="alert">{error}</span> : null}</div>;
}

export function ApplicationPage() {
  const { user, refresh } = useAccount(); const { locale } = useI18n(); const c = publicCopy(locale);
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [file, setFile] = useState<File | null>(null);
  const router = useRouter();
  const rejected = user?.status === "rejected";
  const check = async () => { setBusy(true); setMessage(""); try { const next = await refresh(); if (next?.status === "approved") router.replace(roleDestination(next)); } finally { setBusy(false); } };
  const resubmit = async (event: FormEvent) => {
    event.preventDefault(); if (!file) { setMessage(c.fileRequired); return; }
    const issue = validateQualification(file); if (issue) { setMessage(issue === "size" ? c.fileSize : issue === "type" ? c.fileType : c.fileEmpty); return; }
    setBusy(true); setMessage("");
    try { const data = new FormData(); data.set("qualification", file); await authJson("/api/auth/qualification", { method: "POST", body: data }); await refresh(); setFile(null); setMessage(c.submitted); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : c.connection); }
    finally { setBusy(false); }
  };
  return <AccountGate destination="/application"><main className="public-page account-page"><PublicHeader simple /><div className="account-page-shell"><AccountActions /><section className="application-panel"><span className={`account-status ${rejected ? "account-status--rejected" : ""}`}><i aria-hidden="true" />{rejected ? c.rejected : c.pending}</span><h1>{rejected ? c.rejectedTitle : c.pendingTitle}</h1><p>{rejected ? c.rejectedBody : c.pendingBody}</p><div className="application-identity"><Document /><div><strong>{user?.name}</strong><span>{user?.email}</span></div><a href={`${AUTH_API_BASE}/api/auth/qualification`} className="public-text-link">{c.download}</a></div>{rejected && user?.reviewReason ? <div className="review-feedback"><strong>{c.reasonLabel}</strong><p>{user.reviewReason}</p></div> : null}
    {rejected ? <form onSubmit={resubmit} className="auth-form"><div className="qualification-field"><label htmlFor="replacement-qualification">{c.qualification}</label><p id="replacement-help">{c.qualificationHint}</p><label className="qualification-upload" htmlFor="replacement-qualification"><Document /><span>{file?.name || c.chooseFile}</span><input id="replacement-qualification" type="file" required accept="application/pdf,image/png,image/jpeg" aria-describedby="replacement-help" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label></div><button className="public-button" disabled={busy}>{busy ? c.waiting : c.resubmit}</button></form> : <button type="button" className="public-button" disabled={busy} onClick={() => void check()}>{busy ? c.waiting : c.refresh}</button>}
    {message ? <p className="account-message" role="status">{message}</p> : null}</section></div></main></AccountGate>;
}

export function StudentAccountPage() {
  const { user } = useAccount(); const { locale } = useI18n(); const c = publicCopy(locale);
  return <AccountGate destination="/student"><main className="public-page account-page"><PublicHeader simple /><div className="account-page-shell"><AccountActions /><section className="student-account-intro"><span className="account-status account-status--approved"><Check />{c.studentReady}</span><h1>{c.studentWelcome}</h1><p>{c.studentWelcomeBody}</p><div className="student-account-details"><span>{c.accountLabel}</span><strong>{user?.name}</strong><span>{user?.email}</span></div></section><section className="student-account-empty"><Document /><h2>{c.noCourses}</h2><p>{c.noCoursesBody}</p><Link className="public-text-link" href="/">{c.home}</Link></section></div></main></AccountGate>;
}

export function AdminAccountPage() {
  const { locale } = useI18n(); const c = publicCopy(locale);
  const { user } = useAccount();
  const [applications, setApplications] = useState<Application[]>([]); const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending"); const [error, setError] = useState(""); const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null); const [reason, setReason] = useState(""); const [saved, setSaved] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const load = async () => { setLoading(true); setError(""); try { const data = await authJson<{ applications: Application[] }>("/api/admin/applications"); setApplications(data.applications); } catch (cause) { setError(cause instanceof Error ? cause.message : c.connection); } finally { setLoading(false); } };
  useEffect(() => { if (user?.role === "admin") void load(); }, [user?.id, user?.role]); // The queue is fetched only after identity is established.
  const review = async (id: string, decision: "approved" | "rejected") => {
    if (decision === "rejected" && !reason.trim()) { setError(c.reviewRequired); requestAnimationFrame(() => errorRef.current?.focus()); return; }
    setBusy(id); setError(""); setSaved("");
    try { await authJson(`/api/admin/applications/${encodeURIComponent(id)}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, reason: decision === "rejected" ? reason.trim() : "" }) }); setEditing(null); setReason(""); await load(); setSaved(c.reviewSaved); }
    catch (cause) { setError(cause instanceof Error ? cause.message : c.connection); }
    finally { setBusy(null); }
  };
  const visible = applications.filter((entry) => filter === "all" || entry.status === filter);
  return <AccountGate destination="/admin"><main className="public-page account-page"><PublicHeader simple /><div className="admin-page-shell"><AccountActions /><header className="admin-intro"><h1>{c.adminTitle}</h1><p>{c.adminBody}</p></header><section className="application-queue"><div className="application-queue-toolbar"><h2>{c.applications} <span>{visible.length}</span></h2><label><span className="sr-only">{c.applications}</span><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="pending">{c.pending}</option><option value="approved">{c.approved}</option><option value="rejected">{c.rejected}</option><option value="all">{c.filterAll}</option></select></label><button onClick={() => void load()} type="button" disabled={loading}>{c.refresh}</button></div>
    {error ? <div className="auth-error" role="alert" tabIndex={-1} ref={errorRef}>{error}<button type="button" onClick={() => void load()}>{c.retry}</button></div> : null}{saved ? <p role="status" className="account-message">{saved}</p> : null}
    {loading ? <p role="status" className="queue-empty">{c.waiting}</p> : visible.length === 0 ? <div className="queue-empty"><Check /><h3>{c.noApplications}</h3><p>{c.noApplicationsBody}</p></div> : <ul>{visible.map((entry) => <li key={entry.id} className="application-entry"><div className="application-entry-main"><div className="applicant-avatar" aria-hidden="true">{entry.name.slice(0, 1).toUpperCase()}</div><div><h3>{entry.name}</h3><p>{entry.email}</p><span>{c.reviewDate} · {new Date(entry.submittedAt * 1000).toLocaleString(locale)}</span></div><span className={`account-status account-status--${entry.status}`}>{entry.status === "approved" ? c.approved : entry.status === "rejected" ? c.rejected : c.pending}</span></div><a className="qualification-download" href={`${AUTH_API_BASE}/api/admin/applications/${encodeURIComponent(entry.id)}/qualification`}><Document /><span>{entry.qualificationFilename}</span><span>{c.download}</span></a>{entry.reviewReason ? <div className="review-feedback"><strong>{c.reasonLabel}</strong><p>{entry.reviewReason}</p></div> : null}{entry.status === "pending" ? <div className="application-review-actions">{editing === entry.id ? <label>{c.reasonLabel}<textarea value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} placeholder={c.rejectHint} /><button type="button" disabled={busy !== null} onClick={() => void review(entry.id, "rejected")}>{busy === entry.id ? c.waiting : c.reject}</button></label> : <button type="button" onClick={() => { setEditing(entry.id); setReason(""); setError(""); }} disabled={busy !== null}>{c.reject}</button>}<button className="public-button" type="button" disabled={busy !== null} onClick={() => void review(entry.id, "approved")}>{busy === entry.id ? c.waiting : c.approve}</button></div> : null}</li>)}</ul>}
    </section></div></main></AccountGate>;
}
