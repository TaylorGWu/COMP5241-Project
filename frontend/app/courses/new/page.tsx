"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, ErrorBar, Field, SectionLabel, inputCls } from "@/components/ui";
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

  return <main className="mx-auto min-h-screen w-full max-w-[920px] px-6 py-8">
    <TeacherNavigation active="create" />
    <header className="max-w-[62ch]"><SectionLabel>New course</SectionLabel><h1 className="mt-3 text-[42px] font-bold tracking-[-0.05em] text-ink">Create a course</h1><p className="mt-3 text-[17px] leading-[1.6] text-body">Set the teaching brief now. You will add and build chapters after the course exists.</p></header>
    {error ? <div className="mt-6"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
    <Card className="mt-8 p-6 sm:p-8"><div className="flex items-center justify-between gap-3"><SectionLabel>Course brief</SectionLabel><span className="text-xs font-semibold text-muted">Step 1 of 2</span></div><div className="mt-5 grid gap-5"><Field label="Course title"><input autoFocus className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Git collaboration" /></Field><div className="grid gap-4 sm:grid-cols-[1fr_220px_130px]"><Field label="Course code" hint="Optional"><input className={inputCls} value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="e.g. SE-101" /></Field><Field label="Learners"><select className={inputCls} value={audience} onChange={(e) => setAudience(e.target.value)}><option>University beginners</option><option>Computer science undergraduates</option><option>Mixed-level cohort</option><option>Working professionals</option></select></Field><Field label="Minutes"><input className={inputCls} type="number" min={10} max={180} value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></Field></div><Field label="Course purpose" hint="Optional · a one-sentence promise to learners"><textarea className={`${inputCls} min-h-[105px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What practical capability will this course build?" /></Field><Field label="Learning outcomes" hint="Optional · one outcome per line"><textarea className={`${inputCls} min-h-[130px]`} value={objectives} onChange={(e) => setObjectives(e.target.value)} placeholder={"Explain branch isolation\nReview a pull request before merging"} /></Field></div></Card>
    <Card className="mt-5 p-6 sm:p-8"><div className="flex items-center justify-between gap-3"><SectionLabel>Source material</SectionLabel><span className="text-xs font-semibold text-muted">Optional</span></div><div className="mt-4"><Field label="Syllabus or course outline" hint="PDF, DOCX, PPTX, Markdown or TXT · up to 10 MB"><input className={inputCls} type="file" accept=".pdf,.docx,.pptx,.md,.markdown,.txt" onChange={(e) => setSyllabus(e.target.files?.[0] ?? null)} />{syllabus ? <p className="mt-2 text-xs text-muted">Attached: {syllabus.name}</p> : null}</Field></div></Card>
    <div className="mt-6 flex flex-wrap items-center justify-between gap-4"><Link href="/courses" className="text-sm font-semibold text-body hover:text-ink">Cancel</Link><Button variant="primary" disabled={busy || !title.trim()} onClick={create}>{busy ? "Creating…" : "Create course and add chapters"}</Button></div>
  </main>;
}
