"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AccountGate, useAccount } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { Check, Document } from "@/components/PublicHome";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { portalCopy } from "@/lib/portal-copy";
import { AUTH_API_BASE, authJson, roleDestination, validateQualification, type Application } from "@/lib/auth";
import { teacherProfileCopy, type TeacherProfile } from "@/lib/teacher-profile";
import { ApplicantProfile, PrivateTeacherPhoto } from "@/components/TeacherProfile";

export { AccountActions } from "@/components/AccountActions";

function ApplicationIdentity({ name, email, download }: { name: string; email: string; download: string | null }) {
  const [avatarVersion, setAvatarVersion] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    // Profile/photo failure must not prevent status checks or qualification access.
    void authJson<{ profile: TeacherProfile }>("/api/auth/profile", { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setAvatarVersion(data.profile.hasAvatar ? data.profile.avatarVersion : null); })
      .catch(() => {});
    return () => controller.abort();
  }, []);
  return <div className="application-identity"><PrivateTeacherPhoto name={name} version={avatarVersion} /><div><strong>{name}</strong><span>{email}</span></div>{download ? <a href={`${AUTH_API_BASE}/api/auth/qualification`} className="public-text-link">{download}</a> : null}</div>;
}

export function ApplicationPage() {
  const { user, refresh } = useAccount(); const { locale } = useI18n(); const c = publicCopy(locale); const pc = teacherProfileCopy(locale);
  const checkLock = useRef(false); const [checkError, setCheckError] = useState("");
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [file, setFile] = useState<File | null>(null);
  const router = useRouter();
  const rejected = user?.status === "rejected";
  const unsubmitted = user?.qualificationSubmitted === false;
  const check = async () => {
    if (checkLock.current) return;
    checkLock.current = true; setBusy(true); setMessage(""); setCheckError("");
    try {
      // Preserve the page on a transient error. Global refresh deliberately clears
      // identity on failure, which is right for a gate but wrong for this retry.
      const next = await refresh({ preserveOnError: true });
      if (!next) return;
      if (next.status === "approved") router.replace(roleDestination(next));
      else setMessage(next.status === "rejected" ? pc.refreshedRejected : pc.stillPending);
    } catch (cause) { setCheckError(cause instanceof Error ? cause.message : c.connection); }
    finally { checkLock.current = false; setBusy(false); }
  };
  const resubmit = async (event: FormEvent) => {
    event.preventDefault(); if (!file) { setMessage(c.fileRequired); return; }
    const issue = validateQualification(file); if (issue) { setMessage(issue === "size" ? c.fileSize : issue === "type" ? c.fileType : c.fileEmpty); return; }
    setBusy(true); setMessage("");
    try { const data = new FormData(); data.set("qualification", file); await authJson("/api/auth/qualification", { method: "POST", body: data }); await refresh(); setFile(null); setMessage(c.submitted); }
    catch (cause) { setMessage(cause instanceof Error ? cause.message : c.connection); }
    finally { setBusy(false); }
  };
  return <AccountGate destination="/application"><main className="public-page account-page application-page"><PublicHeader simple /><div className="account-page-shell"><section className="application-panel"><span className={`account-status ${rejected ? "account-status--rejected" : ""}`}><i aria-hidden="true" />{unsubmitted ? c.unsubmitted : rejected ? c.rejected : c.pending}</span><h1>{unsubmitted ? c.unsubmittedTitle : rejected ? c.rejectedTitle : c.pendingTitle}</h1><p>{unsubmitted ? c.unsubmittedBody : rejected ? c.rejectedBody : c.pendingBody}</p><ApplicationIdentity key={user?.id} name={user?.name ?? ""} email={user?.email ?? ""} download={unsubmitted ? null : c.download} />{rejected && user?.reviewReason ? <div className="review-feedback"><strong>{c.reasonLabel}</strong><p>{user.reviewReason}</p></div> : null}
    {rejected || unsubmitted ? <form onSubmit={resubmit} className="auth-form"><div className="qualification-field"><label htmlFor="replacement-qualification">{c.qualification}</label><p id="replacement-help">{c.qualificationHint}</p><label className="qualification-upload" htmlFor="replacement-qualification"><Document /><span>{file?.name || c.chooseFile}</span><input id="replacement-qualification" type="file" required accept="application/pdf,image/png,image/jpeg" aria-describedby="replacement-help" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label></div><button className="public-button" disabled={busy}>{busy ? c.waiting : unsubmitted ? c.submitApplication : c.resubmit}</button></form> : <div className="application-status-refresh"><button type="button" className="profile-secondary" disabled={busy} aria-busy={busy} onClick={() => void check()}><span className={busy ? "status-refresh-icon is-checking" : "status-refresh-icon"} aria-hidden="true" />{busy ? pc.checking : pc.refresh}</button><p role={checkError ? "alert" : "status"} className={checkError ? "profile-error" : ""}>{checkError || (busy ? pc.checking : message)}</p></div>}
    {message && (rejected || unsubmitted) ? <p className="account-message" role="status">{message}</p> : null}</section></div></main></AccountGate>;
}

export function ApplicationQueue({ onReviewed }: { onReviewed?: () => void }) {
  const { locale } = useI18n(); const c = publicCopy(locale);
  const pc = portalCopy(locale); const [search, setSearch] = useState("");
  const { user } = useAccount();
  const [applications, setApplications] = useState<Application[]>([]); const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("pending"); const [error, setError] = useState(""); const [busy, setBusy] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null); const [reason, setReason] = useState(""); const [saved, setSaved] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);
  const pendingRead = useRef<AbortController | null>(null); const pendingWrite = useRef<AbortController | null>(null); const alive = useRef(false);
  const load = useCallback(async () => { pendingRead.current?.abort(); const request = new AbortController(); pendingRead.current = request; setLoading(true); setError(""); try { const data = await authJson<{ applications: Application[] }>("/api/admin/applications", { signal: request.signal }); if (!request.signal.aborted) setApplications(data.applications); } catch (cause) { if (!request.signal.aborted) setError(cause instanceof Error ? cause.message : c.connection); } finally { if (!request.signal.aborted) setLoading(false); } }, [c.connection]);
  useEffect(() => { if (user?.role !== "admin") return; alive.current = true; const initial = window.setTimeout(() => { void load(); }, 0); return () => { alive.current = false; window.clearTimeout(initial); pendingRead.current?.abort(); pendingWrite.current?.abort(); }; }, [user?.id, user?.role, load]);
  const review = async (id: string, decision: "approved" | "rejected") => {
    if (pendingWrite.current) return;
    if (decision === "rejected" && !reason.trim()) { setError(c.reviewRequired); requestAnimationFrame(() => errorRef.current?.focus()); return; }
    const request = new AbortController(); pendingWrite.current = request; setBusy(id); setError(""); setSaved("");
    try { await authJson(`/api/admin/applications/${encodeURIComponent(id)}/review`, { method: "POST", signal: request.signal, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, reason: decision === "rejected" ? reason.trim() : "" }) }); if (!alive.current || request.signal.aborted) return; setEditing(null); setReason(""); await load(); if (alive.current && !request.signal.aborted) { setSaved(c.reviewSaved); onReviewed?.(); } }
    catch (cause) { if (alive.current && !request.signal.aborted) setError(cause instanceof Error ? cause.message : c.connection); }
    finally { if (pendingWrite.current === request) pendingWrite.current = null; if (alive.current && !request.signal.aborted) setBusy(null); }
  };
  const visible = applications.filter((entry) => (filter === "all" || entry.status === filter) && `${entry.name} ${entry.email}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <section className="application-queue"><div className="application-queue-toolbar"><h2>{c.applications} <span>{visible.length}</span></h2><label><span className="sr-only">{c.applications}</span><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="pending">{c.pending}</option><option value="approved">{c.approved}</option><option value="rejected">{c.rejected}</option><option value="all">{c.filterAll}</option></select></label><button onClick={() => void load()} type="button" disabled={loading}>{c.refresh}</button></div>
    <label className="portal-search">{pc.search}<input type="search" value={search} onChange={event => setSearch(event.target.value)} /></label>
    {error ? <div className="auth-error" role="alert" tabIndex={-1} ref={errorRef}>{error}<button type="button" onClick={() => void load()}>{c.retry}</button></div> : null}{saved ? <p role="status" className="account-message">{saved}</p> : null}
    {loading ? <p role="status" className="queue-empty">{c.waiting}</p> : visible.length === 0 ? <div className="queue-empty"><Check /><h3>{c.noApplications}</h3><p>{c.noApplicationsBody}</p></div> : <ul>{visible.map((entry) => <li key={entry.id} className="application-entry"><div className="application-entry-main"><div className="applicant-avatar" aria-hidden="true">{entry.name.slice(0, 1).toUpperCase()}</div><div><h3>{entry.name}</h3><p>{entry.email}</p><span>{c.reviewDate} · {new Date(entry.submittedAt * 1000).toLocaleString(locale)}</span></div><span className={`account-status account-status--${entry.status}`}>{entry.status === "approved" ? c.approved : entry.status === "rejected" ? c.rejected : c.pending}</span></div><ApplicantProfile id={entry.id} /><a className="qualification-download" href={`${AUTH_API_BASE}/api/admin/applications/${encodeURIComponent(entry.id)}/qualification`}><Document /><span>{entry.qualificationFilename}</span><span>{c.download}</span></a>{entry.reviewReason ? <div className="review-feedback"><strong>{c.reasonLabel}</strong><p>{entry.reviewReason}</p></div> : null}{entry.status === "pending" ? <div className="application-review-actions">{editing === entry.id ? <label>{c.reasonLabel}<textarea value={reason} maxLength={1000} onChange={(event) => setReason(event.target.value)} placeholder={c.rejectHint} /><button type="button" disabled={busy !== null} onClick={() => void review(entry.id, "rejected")}>{busy === entry.id ? c.waiting : c.reject}</button></label> : <button type="button" onClick={() => { setEditing(entry.id); setReason(""); setError(""); }} disabled={busy !== null}>{c.reject}</button>}<button className="public-button" type="button" disabled={busy !== null} onClick={() => void review(entry.id, "approved")}>{busy === entry.id ? c.waiting : c.approve}</button></div> : null}</li>)}</ul>}
    </section>;
}
