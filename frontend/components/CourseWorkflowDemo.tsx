"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import { workflowDemoCopy } from "@/lib/workflow-demo-copy";

const SCENE_MS = 4200;

/** Deterministic product walkthrough: no API clients, account writes or publishing. */
export function CourseWorkflowDemo({ hero = false }: { hero?: boolean }) {
  const { locale } = useI18n();
  const c = workflowDemoCopy(locale);
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const moveFocus = useRef(false);
  const [phase, setPhase] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [visible, setVisible] = useState(false);
  const [foreground, setForeground] = useState(true);
  const [reduced, setReduced] = useState(true);
  const act = Math.floor(phase / 2);
  const running = playing && visible && foreground && phase < 5;

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => { setReduced(preference.matches); setPlaying(!preference.matches); };
    sync();
    preference.addEventListener("change", sync);
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.15 });
    if (host.current) observer.observe(host.current);
    const visibility = () => setForeground(!document.hidden);
    visibility();
    document.addEventListener("visibilitychange", visibility);
    return () => { preference.removeEventListener("change", sync); observer.disconnect(); document.removeEventListener("visibilitychange", visibility); };
  }, []);

  useEffect(() => {
    if (!running) return;
    const timer = window.setTimeout(() => setPhase(current => Math.min(current + 1, 5)), SCENE_MS);
    return () => window.clearTimeout(timer);
  }, [phase, running]);

  useEffect(() => {
    if (moveFocus.current) {
      canvas.current?.focus({ preventScroll: true });
      moveFocus.current = false;
    }
  }, [phase]);

  const jump = (next: number) => { setPlaying(false); setPhase(next); };
  const replay = () => { setPhase(0); setPlaying(!reduced); };
  const nextButton = (label: string, next: number) => <button type="button" className="public-button public-button--small" data-demo-next onClick={() => { moveFocus.current = true; jump(next); }}>{label}<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6" /></svg></button>;
  const sampleField = (label: string, value: string) => <div className="workflow-field"><dt>{label}</dt><dd>{value}</dd></div>;

  return <section className={`teaching-example workflow-section${hero ? " workflow-section--hero" : ""}`} id="how-it-works" aria-labelledby="example-title">
    <div className="example-heading"><h2 id="example-title">{c.title}</h2><span>{c.note}</span></div>
    <div ref={host} className="workflow-demo" data-phase={phase} data-playing={playing && phase < 5} data-running={running}>
      <div className="workflow-chrome"><span><span className="workflow-mark" aria-hidden="true">CW</span>Coursework <span className="workflow-breadcrumb">/ {phase === 0 ? c.courses : c.course}</span></span><span className="workflow-draft">{c.draft}</span></div>
      <div className="workflow-stage">
        <aside className="workflow-index" aria-label={c.controls}>
          {c.steps.map((label, index) => <button key={label} type="button" data-demo-step={index} aria-pressed={act === index} onClick={() => jump(index * 2)} className={act === index ? "is-current" : act > index ? "is-done" : ""}><span className="workflow-step-number">{act > index ? <Tick /> : `0${index + 1}`}</span><span>{label}</span></button>)}
          <p>{c.publishNote}</p>
        </aside>
        <div ref={canvas} className="workflow-canvas" tabIndex={-1} role="group" aria-label={c.steps[act]}>
          <div key={phase} className="workflow-scene">
            {phase <= 1 ? <div className="workflow-course">
              {phase === 0 ? <><h3>{c.steps[0]}</h3><dl className="workflow-fields">{sampleField(c.courseName, c.course)}<div className="workflow-inline">{sampleField(c.audience, c.beginners)}{sampleField(c.objective, c.objectiveText)}</div></dl>{nextButton(c.create, 1)}</> :
                <><div className="workflow-result-label"><Tick />{c.created}</div><article className="workflow-course-card"><span className="workflow-course-subject">{c.beginners}</span><h3>{c.course}</h3><p>{c.objectiveText}</p><div><span>{c.noChapters}</span>{nextButton(c.add, 2)}</div></article></>}
            </div> : phase === 2 ? <div className="workflow-course"><h3>{c.steps[1]}</h3><dl className="workflow-fields">{sampleField(c.chapterName, c.chapter)}{sampleField(c.brief, c.briefText)}</dl><p className="workflow-materials">{c.materials}</p>{nextButton(c.generate, 3)}</div> :
              <div className={phase >= 4 ? "workflow-editor has-review" : "workflow-editor"}>
                <div className="workflow-preview-column">
                  <div className="workflow-preview-meta"><span>{c.preview} · {c.chapter}</span><span>{phase === 5 ? c.updated : phase === 4 ? c.unchanged : c.generated}</span></div>
                  <article className="workflow-slide"><h3>{c.slideTitle}</h3><ol>{c.bullets.map((bullet, index) => <li key={bullet}><span>{index + 1}</span>{bullet}</li>)}</ol><p data-demo-preview className={phase === 5 ? "is-updated" : ""}>{phase === 5 ? c.after : c.before}</p></article>
                  {phase === 3 ? <div className="workflow-preview-action"><span>{c.materials}</span>{nextButton(c.edit, 4)}</div> : <p className="workflow-publish-note">{c.publishNote}</p>}
                </div>
                {phase >= 4 ? <aside className="workflow-review"><span className="workflow-request-label">{c.requestLabel}</span><p className="workflow-request">{c.request}</p><div className="workflow-review-title"><span>AI</span><h4>{c.proposal}</h4></div><del>{c.before}</del><ins>{c.after}</ins><span className={phase === 5 ? "workflow-result-label" : "workflow-pending"}>{phase === 5 ? <Tick /> : null}{phase === 5 ? c.accepted : c.pending}</span><button data-demo-accept type="button" className="public-button public-button--small" disabled={phase === 5} onClick={() => jump(5)}>{phase === 5 ? c.accepted : c.accept}</button></aside> : null}
              </div>}
          </div>
        </div>
      </div>
      <div className="workflow-caption" aria-live={playing ? "off" : "polite"}><span>{c.captions[phase]}</span><span className="workflow-scene-count" aria-hidden="true">{String(phase + 1).padStart(2, "0")} / 06</span></div>
      <div className="workflow-timeline" aria-hidden="true">{c.captions.map((_, index) => <span key={index} className={index < phase || phase === 5 ? "is-complete" : index === phase ? "is-playing" : ""}><i key={`${phase}-${playing}-${visible}-${foreground}`} /></span>)}</div>
    </div>
    <div className="workflow-controls"><p className="example-disclaimer">{c.disclaimer}</p><div><button type="button" className="workflow-control" data-demo-play aria-pressed={playing && phase < 5} onClick={() => { if (phase === 5) setPhase(0); setPlaying(current => phase === 5 || !current); }}>{playing && phase < 5 ? <Pause /> : <Play />}{playing && phase < 5 ? c.pause : c.play}</button><button type="button" className="workflow-control" data-demo-replay onClick={replay}><Replay />{c.replay}</button></div></div>
  </section>;
}

function Tick() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>; }
function Pause() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M8 5v14M16 5v14" /></svg>; }
function Play() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m8 5 11 7-11 7V5Z" /></svg>; }
function Replay() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 10a8 8 0 1 1 1 7M4 4v6h6" /></svg>; }
