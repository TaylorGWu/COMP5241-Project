"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { publicCopy } from "@/lib/public-copy";
import { AccountGate, useAccount } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";
import { authJson } from "@/lib/auth";
import { profilePayload, teacherProfileCopy, type TeacherProfile } from "@/lib/teacher-profile";

import { PrivateTeacherPhoto } from "@/components/PrivateTeacherPhoto";
export { PrivateTeacherPhoto } from "@/components/PrivateTeacherPhoto";

export function TeacherProfilePage() {
  return <AccountGate destination="/profile"><ProfileEditor /></AccountGate>;
}

function ProfileEditor() {
  const { user, refresh } = useAccount(); const { locale } = useI18n(); const c = teacherProfileCopy(locale);
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [saved, setSaved] = useState<TeacherProfile | null>(null);
  const [loading, setLoading] = useState(true); const [error, setError] = useState(""); const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false); const locked = useRef(false);
  const [file, setFile] = useState<File | null>(null); const [preview, setPreview] = useState("");
  const [photoError, setPhotoError] = useState(""); const [photoMessage, setPhotoMessage] = useState("");
  const [photoBusy, setPhotoBusy] = useState(false); const photoLocked = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [subjectsOpen, setSubjectsOpen] = useState(false); const [search, setSearch] = useState("");
  const subjectTrigger = useRef<HTMLButtonElement>(null);
  const [section, setSection] = useState("profile-personal");
  const reviewState = user?.status === "approved" ? "approved" : user?.status === "rejected" ? "rejected" : user?.qualificationSubmitted ? "pending" : "unsubmitted";
  const accountCopy = publicCopy(locale);
  const dirty = !!profile && !!saved && JSON.stringify(profilePayload(profile)) !== JSON.stringify(profilePayload(saved));
  const load = async () => {
    setLoading(true); setError("");
    try { const data = await authJson<{ profile: TeacherProfile }>("/api/auth/profile"); setProfile(data.profile); setSaved(data.profile); }
    catch { setError(c.loadError); } finally { setLoading(false); }
  };
  useEffect(() => {
    const controller = new AbortController();
    void authJson<{ profile: TeacherProfile }>("/api/auth/profile", { signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) { setProfile(data.profile); setSaved(data.profile); setLoading(false); }
    }).catch(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [user?.id]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => {
    if (!dirty && !file) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, file]);
  function change<K extends keyof TeacherProfile>(key: K, value: TeacherProfile[K]) {
    setProfile(p => p ? { ...p, [key]: value } : p); setMessage("");
  }
  const save = async (event: FormEvent) => {
    event.preventDefault(); if (!profile || locked.current) return;
    locked.current = true; setBusy(true); setError(""); setMessage("");
    try {
      const data = await authJson<{ profile: TeacherProfile }>("/api/auth/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profilePayload(profile)) });
      setProfile(data.profile); setSaved(data.profile); setMessage(c.saved);
      void refresh({ preserveOnError: true }).catch(() => {});
    } catch (cause) { setError(cause instanceof Error ? cause.message : c.error); }
    finally { locked.current = false; setBusy(false); }
  };
  const photo = async (remove = false) => {
    if (photoLocked.current || (!remove && !file)) return;
    photoLocked.current = true; setPhotoBusy(true); setPhotoError(""); setPhotoMessage("");
    try {
      const body = new FormData(); if (file) body.set("avatar", file);
      const data = await authJson<{ profile: TeacherProfile }>("/api/auth/avatar", { method: remove ? "DELETE" : "PUT", ...(remove ? {} : { body }) });
      // Only update photo fields; never overwrite unsaved form edits.
      const photoFields = { hasAvatar: data.profile.hasAvatar, avatarVersion: data.profile.avatarVersion };
      setProfile(p => p ? { ...p, ...photoFields } : p); setSaved(p => p ? { ...p, ...photoFields } : p);
      window.dispatchEvent(new Event("coursework-profile-photo-changed"));
      setFile(null); setPreview(""); if (fileInput.current) fileInput.current.value = "";
      setPhotoMessage(remove ? c.photoRemoved : c.photoSaved);
    } catch (cause) { setPhotoError(cause instanceof Error ? cause.message : c.error); }
    finally { photoLocked.current = false; setPhotoBusy(false); }
  };
  const selectFile = (next?: File) => {
    setPhotoError(""); setPhotoMessage("");
    if (!next) return;
    if (!next.size || next.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png"].includes(next.type)) {
      setPhotoError(c.photoError); if (fileInput.current) fileInput.current.value = ""; return;
    }
    setFile(next); setPreview(URL.createObjectURL(next));
  };
  const labels = c.subjectNames as Record<string, string>;
  return <main className="public-page teacher-profile-page" onClickCapture={event => {
    const target = event.target instanceof Element ? event.target.closest("a, [data-account-logout]") : null;
    if (!target || (target instanceof HTMLAnchorElement && target.hash && target.pathname === location.pathname)) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (busy || photoBusy || ((dirty || file) && !window.confirm(c.leave))) { event.preventDefault(); event.stopPropagation(); }
  }}><PublicHeader simple /><div className="teacher-profile-shell">
    <h1 className="sr-only">{c.title}</h1>
    {loading ? <p role="status" className="profile-loading">{c.loading}</p> : !profile ? <div role="alert" className="profile-error">{c.loadError}<button type="button" onClick={() => void load()}>{c.retry}</button></div> :
    <div className="teacher-profile-layout"><aside className="teacher-profile-aside">
      <div className="profile-identity"><div><strong>{saved?.name || profile.name}</strong><span>{c.teacherAccount}</span><span className="profile-identity-email" title={user?.email}>{user?.email}</span></div></div>
      <nav aria-label={c.title}>{[["profile-personal",c.personal],["profile-education",c.education],["profile-teaching",c.teaching]].map(([id,label],index)=><a key={id} href={`#${id}`} aria-current={section===id ? "location" : undefined} onClick={()=>setSection(id)}><ProfileSectionIcon index={index} /><span>{label}</span></a>)}</nav>
      <div className="profile-review-note"><h2>{c.qualification}</h2><span className="profile-review-status" data-review-state={reviewState}><i aria-hidden="true" />{reviewState === "approved" ? accountCopy.approved : reviewState === "rejected" ? accountCopy.rejected : reviewState === "pending" ? accountCopy.pending : accountCopy.unsubmitted}</span><p>{c.qualificationHint}</p><Link href={user?.status === "approved" ? "/courses" : "/application"}>{user?.status === "approved" ? accountCopy.workspace : c.viewStatus}<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6" /></svg></Link></div></aside>
      <form className="teacher-profile-form" onSubmit={save}>
        <section id="profile-personal" className="profile-section"><h2>{c.personal}</h2><p className="profile-optional">{c.optional}</p>
          <div className="profile-photo-editor"><div>{preview ? <Image unoptimized width={88} height={88} className="teacher-photo" src={preview} alt={c.photo} /> : <PrivateTeacherPhoto version={profile.avatarVersion} name={profile.name} />}</div><div className="profile-photo-controls"><div className="profile-photo-actions"><label className={`profile-secondary ${photoBusy ? "is-disabled" : ""}`} htmlFor="teacher-photo">{c.choosePhoto}<input ref={fileInput} id="teacher-photo" type="file" accept="image/jpeg,image/png" disabled={photoBusy || busy} aria-describedby="photo-help" onChange={event => selectFile(event.target.files?.[0])} /></label>{file ? <><button type="button" className="profile-secondary" disabled={photoBusy || busy} onClick={() => void photo()}>{photoBusy ? c.saving : c.savePhoto}</button><button type="button" className="profile-text-button" disabled={photoBusy} onClick={() => { setFile(null); setPreview(""); if (fileInput.current) fileInput.current.value = ""; }}>{c.cancelPhoto}</button></> : profile.hasAvatar ? <button type="button" className="profile-text-button" disabled={photoBusy || busy} onClick={() => void photo(true)}>{c.removePhoto}</button> : null}</div><p id="photo-help">{c.photoHint}</p>{photoError ? <p role="alert" className="profile-error">{photoError}</p> : null}<p className="profile-photo-message" role="status">{photoBusy ? c.saving : photoMessage}</p></div></div>
          <div className="profile-field"><label htmlFor="teacher-name">{c.name} <span aria-hidden="true">*</span></label><input id="teacher-name" autoComplete="name" required maxLength={100} value={profile.name} disabled={busy} onChange={e => change("name", e.target.value)} /></div>
          <div className="profile-field"><label htmlFor="teacher-bio">{c.bio}</label><textarea id="teacher-bio" maxLength={1000} rows={4} value={profile.bio} disabled={busy} onChange={e => change("bio", e.target.value)} /><span className="profile-count">{profile.bio.length} / 1000</span></div>
        </section>
        <section id="profile-education" className="profile-section"><h2>{c.education}</h2><div className="profile-fields-grid"><div className="profile-field"><label htmlFor="teacher-university">{c.university}</label><input id="teacher-university" maxLength={160} value={profile.university} disabled={busy} onChange={e => change("university", e.target.value)} /></div><div className="profile-field"><label htmlFor="teacher-degree">{c.degree}</label><select id="teacher-degree" value={profile.degree} disabled={busy} onChange={e => change("degree", e.target.value)}><option value="">{c.select}</option>{Object.entries(c.degrees).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div></section>
        <section id="profile-teaching" className="profile-section"><h2>{c.teaching}</h2><label className="profile-checkbox"><input type="checkbox" checked={profile.independent} disabled={busy} onChange={e => change("independent", e.target.checked)} />{c.independent}</label><div className="profile-fields-grid">{!profile.independent ? <div className="profile-field"><label htmlFor="teacher-institution">{c.institution}</label><input id="teacher-institution" maxLength={160} value={profile.institution} disabled={busy} onChange={e => change("institution", e.target.value)} /></div> : null}<div className="profile-field"><label htmlFor="teacher-position">{c.position}</label><input id="teacher-position" maxLength={100} value={profile.position} disabled={busy} onChange={e => change("position", e.target.value)} /></div></div>
          <div className="profile-teaching-extra"><div className="profile-field"><label htmlFor="teacher-experience">{c.experience}</label><select id="teacher-experience" value={profile.experience} disabled={busy} onChange={e => change("experience", e.target.value)}><option value="">{c.select}</option>{Object.entries(c.years).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          <fieldset className="profile-subjects" disabled={busy}><legend>{c.subjects}</legend><div className="profile-subject-tags">{profile.subjects.map(value => <button type="button" key={value} onClick={() => change("subjects", profile.subjects.filter(item => item !== value))} aria-label={`${locale === "en" ? "Remove" : "移除"} ${labels[value]}`}>{labels[value]} <span aria-hidden="true">×</span></button>)}</div><button type="button" ref={subjectTrigger} className="profile-secondary" aria-expanded={subjectsOpen} aria-controls="subject-options" onClick={() => { setSubjectsOpen(v => !v); setSearch(""); }}>{c.chooseSubjects}</button>
          {subjectsOpen ? <div id="subject-options" className="profile-subject-options" onKeyDown={e => { if (e.key === "Escape") { setSubjectsOpen(false); subjectTrigger.current?.focus(); } }}><label htmlFor="subject-search">{c.search}</label><input id="subject-search" type="search" value={search} onChange={e => setSearch(e.target.value)} /><div className="profile-subject-list">{Object.entries(labels).filter(([, label]) => label.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(([value, label]) => <label key={value} className="profile-checkbox"><input type="checkbox" checked={profile.subjects.includes(value)} onChange={e => change("subjects", e.target.checked ? [...profile.subjects, value] : profile.subjects.filter(item => item !== value))} />{label}</label>)}{!Object.values(labels).some(label => label.toLocaleLowerCase().includes(search.toLocaleLowerCase())) ? <p>{c.noMatch}</p> : null}</div><button type="button" className="profile-text-button" onClick={() => { setSubjectsOpen(false); subjectTrigger.current?.focus(); }}>{c.done}</button></div> : null}</fieldset>
          </div>{profile.subjects.includes("other") ? <div className="profile-field"><label htmlFor="teacher-other">{c.other}</label><input id="teacher-other" required maxLength={100} value={profile.otherSubject} disabled={busy} onChange={e => change("otherSubject", e.target.value)} /></div> : null}
        </section>
        <footer className="profile-save-bar"><div><p className={error ? "profile-error" : ""} role={error ? "alert" : "status"}>{error || message || (dirty ? c.unsaved : c.unchanged)}</p></div><button type="button" className="profile-text-button" disabled={busy || photoBusy || !dirty} onClick={() => { setProfile(saved); setError(""); setMessage(""); }}>{c.discard}</button><button type="submit" className="public-button" disabled={busy || photoBusy || !dirty}>{busy ? c.saving : c.save}</button></footer>
      </form></div>}
  </div></main>;
}

function ProfileSectionIcon({index}:{index:number}) { return <svg aria-hidden="true" viewBox="0 0 24 24">{index===0?<><circle cx="12" cy="7" r="3" /><path d="M5 21v-3a7 7 0 0 1 14 0v3H5Z" /></>:index===1?<><path d="m2 8 10-5 10 5-10 5L2 8Zm4 3v6c4 3 8 3 12 0v-6M22 8v8" /></>:<><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h3" /></>}</svg>; }

export function ApplicantProfile({ id }: { id: string }) {
  const { locale } = useI18n(); const c = teacherProfileCopy(locale);
  const [open, setOpen] = useState(false); const [data, setData] = useState<TeacherProfile | null>(null);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false);
  const load = async () => {
    setLoading(true); setError("");
    try { setData((await authJson<{ profile: TeacherProfile }>(`/api/admin/applications/${encodeURIComponent(id)}/profile`)).profile); }
    catch { setError(c.loadError); } finally { setLoading(false); }
  };
  return <div className="applicant-profile"><button type="button" className="profile-text-button" aria-expanded={open} onClick={() => { setOpen(v => !v); if (!open && !data) void load(); }}>{open ? c.hideProfile : c.viewProfile}</button>{open ? <div>{loading ? <p role="status">{c.checking}</p> : error ? <p role="alert">{error} <button type="button" onClick={() => void load()}>{c.retry}</button></p> : data ? <><PrivateTeacherPhoto name={data.name} version={data.avatarVersion} path={`/api/admin/applications/${encodeURIComponent(id)}/avatar`} /><dl>{[
    [c.university, data.university], [c.degree, (c.degrees as Record<string, string>)[data.degree]],
    [c.institution, data.independent ? c.independent : data.institution], [c.position, data.position],
    [c.experience, (c.years as Record<string, string>)[data.experience]],
    [c.subjects, data.subjects.map(value => value === "other" ? data.otherSubject : (c.subjectNames as Record<string, string>)[value]).join(", ")], [c.bio, data.bio],
  ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || c.empty}</dd></div>)}</dl></> : null}</div> : null}</div>;
}
