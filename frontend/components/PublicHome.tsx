"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PublicHeader } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";

export function PublicHome() {
  const { locale } = useI18n();
  const c = publicCopy(locale);
  const [step, setStep] = useState(0);
  const [accepted, setAccepted] = useState(false);
  const [playing, setPlaying] = useState(true);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !playing || step >= 2) return;
    const timer = window.setTimeout(() => setStep((current) => current + 1), 5000);
    return () => window.clearTimeout(timer);
  }, [step, playing]);
  const select = (next: number) => { setStep(next); setPlaying(false); };
  return <main className="public-page">
    <PublicHeader />
    <section className="public-hero" aria-labelledby="home-title">
      <h1 id="home-title">{c.heroA}<br /><span>{c.heroB}</span></h1>
      <div className="public-hero-aside"><p>{c.heroBody}</p><div className="public-actions"><Link className="public-button" href="/register/instructor">{c.teacherCta}<Arrow /></Link><Link className="public-text-link" href="/register/student">{c.studentCta}<Arrow /></Link></div></div>
    </section>
    <section className="teaching-example" id="how-it-works" aria-labelledby="example-title">
      <div className="example-heading"><h2 id="example-title">{c.exampleTitle}</h2><span>{c.example}</span></div>
      <div className="example-workspace">
        <div className="example-topline"><span><i aria-hidden="true" />Coursework / Git essentials</span><span className="example-draft">{accepted ? c.accepted : c.draft}</span></div>
        <div className="example-body">
          <aside className={`example-brief ${step === 0 ? "is-current" : ""}`}><span className="example-file"><Document />{c.material}</span><p>{c.briefText}</p><div className="example-objective"><span>LO1</span>{c.objective}</div><div className="example-source-lines" aria-hidden="true"><i /><i /><i /></div></aside>
          <div className={`example-slide ${step === 1 ? "is-current" : ""}`}><span className="example-slide-number">01 / Git</span><h3>{c.slideTitle}</h3><div className="git-demo-flow">{[c.working, c.staging, c.history].map((label, index) => <div key={label} className={`git-demo-stop ${step >= 1 ? "is-revealed" : ""}`}><span className="git-demo-index">0{index + 1}</span><strong>{label}</strong><code>{index === 0 ? c.file : index === 1 ? "git add app.js" : "git commit"}</code><p>{[c.draftText, c.stagedText, c.historyText][index]}</p></div>)}</div><p className="example-slide-foot">{accepted ? c.after : c.before}</p></div>
          <aside className={`example-review ${step === 2 ? "is-current" : ""}`}><div className="example-review-heading"><span>AI</span><strong>{c.suggestion}</strong></div><del>{c.before}</del><ins>{c.after}</ins><p>{c.reason}</p><button type="button" disabled={accepted} onClick={() => { setAccepted(true); setStep(2); setPlaying(false); }}>{accepted ? <Check /> : null}{accepted ? c.accepted : c.accept}</button></aside>
        </div>
      </div>
      <div className="example-controls"><div className="example-stepper" role="group" aria-label={c.demoLabel}>{[c.brief, c.draft, c.review].map((label, index) => <button type="button" key={label} aria-pressed={step === index} className={step === index ? "is-active" : ""} onClick={() => select(index)}><span>0{index + 1}</span>{label}</button>)}</div><button type="button" className="example-replay" onClick={() => { setStep(0); setAccepted(false); setPlaying(true); }}>{c.replay}<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 10a8 8 0 1 1 1 7M4 4v6h6" /></svg></button></div>
      <p className="example-disclaimer">{c.exampleNote}</p>
    </section>
    <section className="public-teacher-story" aria-labelledby="teacher-story"><div><h2 id="teacher-story">{c.teacherTitle}</h2><p>{c.teacherBody}</p><Link href="/register/instructor" className="public-button public-button--light">{c.teacherCta}<Arrow /></Link></div><div className="public-story-proof"><div><Document /><span>{c.source}</span></div><div><Check /><span>{c.human}</span></div><div><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m14 5 5 5M4 20l4-1L20 7a2 2 0 0 0-4-4L4 15v5Z" /></svg><span>{c.editable}</span></div></div></section>
    <section className="public-student-story" aria-labelledby="student-story"><h2 id="student-story">{c.studentTitle}</h2><div><p>{c.studentBody}</p><Link href="/register/student" className="public-text-link">{c.studentCta}<Arrow /></Link></div></section>
    <section className="public-close"><h2>{c.finalTitle}</h2><p>{c.finalBody}</p><Link href="/register" className="public-button">{c.start}<Arrow /></Link></section>
    <footer className="public-footer"><Link href="/" className="public-footer-brand">Coursework.</Link><p>{c.footer}</p><Link href="/login">{c.login}</Link></footer>
  </main>;
}

export function Arrow() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6" /></svg>; }
export function Document() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5" /></svg>; }
export function Check() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>; }
