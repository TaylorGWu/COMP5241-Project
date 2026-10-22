"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, ErrorBar, Field, inputCls } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api } from "@/lib/api";

/** Focused creation screen, kept separate from the teacher's course library. */
export default function CreateCoursePage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [audience, setAudience] = useState("University beginners");
  const [duration, setDuration] = useState(45);
  const [objectives, setObjectives] = useState("");
  const [syllabus, setSyllabus] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const create = async () => {
    if (!title.trim()) return;
    setBusy(true); setError("");
    try {
      const course = await api.createCourse({
        title: title.trim(), description: description.trim(), audience, durationMin: duration, language: "zh-HK",
        courseCode: courseCode.trim(), subject: "Software Engineering",
        learningObjectives: objectives.split("\n").map((item) => item.trim()).filter(Boolean),
      });
      if (syllabus) await api.uploadSyllabus(course.id, syllabus);
      router.push(`/courses/${course.id}`);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  return <main className="course-create-page min-h-screen bg-canvas">
    <div className="course-create-shell mx-auto w-full max-w-[1280px] px-5 pb-20 pt-4 sm:px-8">
      <TeacherNavigation active="create" />
      <header className="course-create-header border-b border-line pb-7">
        <Link href="/courses" className="course-create-back text-sm font-semibold text-blue hover:text-blue-deep">Your courses</Link>
        <h1 className="mt-5 text-[clamp(2rem,4vw,3rem)] font-semibold leading-[1.1] tracking-[-0.055em] text-ink">Create a course</h1>
        <p className="mt-2 max-w-[58ch] text-[15px] leading-6 text-body">Define the course now. Add chapters in its workspace afterwards.</p>
      </header>
      {error ? <div className="mt-6"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
      <div className="course-create-content mt-7 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="overflow-hidden rounded-md border border-line bg-surface">
          <section className="p-6 sm:p-8">
            <div className="border-b border-line pb-5"><h2 className="text-lg font-semibold tracking-[-0.03em] text-ink">Course details</h2></div>
            <div className="mt-6 grid gap-5">
              <Field label="Course title"><input autoFocus className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Git collaboration" /></Field>
              <div className="grid gap-5 sm:grid-cols-[1fr_1.4fr_110px]"><Field label="Course code" hint="Optional"><input className={inputCls} value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="SE-101" /></Field><Field label="Learners"><select className={inputCls} value={audience} onChange={(e) => setAudience(e.target.value)}><option>University beginners</option><option>Computer science undergraduates</option><option>Mixed-level cohort</option><option>Working professionals</option></select></Field><Field label="Minutes"><input className={inputCls} type="number" min={10} max={180} value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></Field></div>
              <Field label="Course purpose" hint="A one-sentence promise to learners"><textarea className={`${inputCls} min-h-[105px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What practical capability will this course build?" /></Field>
              <Field label="Learning outcomes" hint="One outcome per line"><textarea className={`${inputCls} min-h-[130px]`} value={objectives} onChange={(e) => setObjectives(e.target.value)} placeholder={"Explain branch isolation\nReview a pull request before merging"} /></Field>
            </div>
          </section>
          <section className="border-t border-line bg-soft/40 p-6 sm:p-8">
            <div className="flex items-baseline gap-3"><h2 className="text-lg font-semibold tracking-[-0.03em] text-ink">Syllabus</h2><span className="text-xs text-muted">Optional</span></div>
            <p className="mt-2 text-sm leading-6 text-body">Attach a syllabus to give chapter generation the right context.</p>
            <div className="mt-5"><Field label="Syllabus or course outline" hint="PDF, DOCX, PPTX, Markdown or TXT · up to 10 MB"><input className={inputCls} type="file" accept=".pdf,.docx,.pptx,.md,.markdown,.txt" onChange={(e) => setSyllabus(e.target.files?.[0] ?? null)} />{syllabus ? <p className="mt-2 text-xs text-muted">Attached: {syllabus.name}</p> : null}</Field></div>
          </section>
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line px-6 py-5 sm:px-8"><Link href="/courses" className="text-sm font-semibold text-body hover:text-ink">Cancel</Link><Button variant="primary" disabled={busy || !title.trim()} onClick={create}>{busy ? "Creating…" : "Create course"}</Button></div>
        </div>
        <aside className="course-create-preview lg:sticky lg:top-7">
          <p className="text-xs font-bold uppercase tracking-[0.1em] text-blue">Draft preview</p>
          <h2 className="mt-4 break-words text-xl font-semibold tracking-[-0.04em] text-ink">{title.trim() || "Untitled course"}</h2>
          <p className="mt-2 text-sm leading-6 text-body">{description.trim() || "Add a purpose to tell learners what they will achieve."}</p>
          <dl className="mt-6 space-y-4 border-t border-line pt-5 text-sm"><div><dt className="text-muted">Audience</dt><dd className="mt-1 font-semibold text-ink">{audience}</dd></div><div><dt className="text-muted">Duration</dt><dd className="mt-1 font-semibold text-ink">{duration} minutes</dd></div><div><dt className="text-muted">Outcomes</dt><dd className="mt-1 font-semibold text-ink">{objectives.split("\n").filter((item) => item.trim()).length} defined</dd></div><div><dt className="text-muted">Syllabus</dt><dd className="mt-1 break-words font-semibold text-ink">{syllabus?.name || "None attached"}</dd></div></dl>
          <p className="mt-6 border-t border-line pt-5 text-xs leading-5 text-body">This course remains private until you review and publish its chapters.</p>
        </aside>
      </div>
    </div>
  </main>;
}
