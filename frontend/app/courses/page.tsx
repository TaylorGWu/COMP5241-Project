"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Badge, Button, Card, Field, SectionLabel, inputCls } from "@/components/ui";
import { api, type TeacherCourse } from "@/lib/api";

/** Teacher course catalogue: create and choose a course before touching chapters. */
export default function CoursesPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<TeacherCourse[]>([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [subject, setSubject] = useState("Software Engineering");
  const [level, setLevel] = useState("Undergraduate");
  const [objectives, setObjectives] = useState("");
  const [audience, setAudience] = useState("University beginners");
  const [duration, setDuration] = useState(45);
  const [syllabus, setSyllabus] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => setCourses((await api.courses()).courses);
  useEffect(() => { void refresh().catch((e) => setError(String(e))); }, []);

  const create = async () => {
    if (!title.trim()) return;
    setBusy(true); setError("");
    try {
      const course = await api.createCourse({
        title: title.trim(), description: description.trim(), audience, durationMin: duration, language: "zh-HK",
        courseCode: courseCode.trim(), subject, level,
        learningObjectives: objectives.split("\n").map((item) => item.trim()).filter(Boolean),
      });
      if (syllabus) await api.uploadSyllabus(course.id, syllabus);
      router.push(`/courses/${course.id}`);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  return <main className="mx-auto min-h-screen w-full max-w-[1120px] px-6 py-12">
    <header className="mb-9 max-w-[70ch]">
      <SectionLabel>Teacher courses</SectionLabel>
      <h1 className="mt-3 text-[44px] font-bold tracking-[-0.05em] text-ink">Courses, then chapters.</h1>
      <p className="mt-3 text-[17px] leading-[1.6] text-body">Create the course first. Its chapters, generated slides, question bank and assessments stay inside that course.</p>
    </header>
    {error ? <p className="mb-5 rounded-sm border border-amber/30 bg-amber-soft p-3 text-sm text-amber">{error}</p> : null}
    <Card className="p-6">
      <SectionLabel>Create a course</SectionLabel>
      <p className="mt-2 max-w-[72ch] text-sm leading-6 text-muted">Start with the teaching brief, then decide the chapter sequence. These details become the course’s reviewable blueprint instead of disappearing into a first chapter.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_220px_130px]">
        <Field label="Course title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Git collaboration" /></Field>
        <Field label="Learners"><select className={inputCls} value={audience} onChange={(e) => setAudience(e.target.value)}><option>University beginners</option><option>Computer science undergraduates</option><option>Mixed-level cohort</option><option>Working professionals</option></select></Field>
        <Field label="Minutes"><input className={inputCls} type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></Field>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-[150px_1fr_180px]"><Field label="Course code"><input className={inputCls} value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="e.g. SE-101" /></Field><Field label="Subject"><select className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)}><option>Software Engineering</option><option>Computing Foundations</option><option>AI &amp; Data</option><option>Professional Development</option></select></Field><Field label="Level"><select className={inputCls} value={level} onChange={(e) => setLevel(e.target.value)}><option>Undergraduate</option><option>Postgraduate</option><option>Professional</option></select></Field></div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"><Field label="Course purpose" hint="Optional · a one-sentence promise to learners"><textarea className={`${inputCls} min-h-[108px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What practical capability will this course build?" /></Field><Field label="Learning outcomes" hint="Optional · one outcome per line"><textarea className={`${inputCls} min-h-[108px]`} value={objectives} onChange={(e) => setObjectives(e.target.value)} placeholder={"Explain branch isolation\nReview a pull request before merging"} /></Field></div>
      <div className="mt-4 max-w-[640px]"><Field label="Syllabus or course outline" hint="Optional · PDF, DOCX, PPTX, Markdown or TXT · up to 10 MB"><input className={inputCls} type="file" accept=".pdf,.docx,.pptx,.md,.markdown,.txt" onChange={(e) => setSyllabus(e.target.files?.[0] ?? null)} />{syllabus ? <p className="mt-2 text-xs text-muted">Attached: {syllabus.name}</p> : null}</Field></div>
      <Button variant="primary" className="mt-4" disabled={busy || !title.trim()} onClick={create}>{busy ? "Creating…" : "Create course"}</Button>
    </Card>
    <section className="mt-8">
      <SectionLabel>Your courses</SectionLabel>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {courses.map((course) => <button key={course.id} type="button" onClick={() => router.push(`/courses/${course.id}`)} className="text-left">
          <Card className="h-full p-5 transition hover:border-blue">
            <div className="flex flex-wrap items-center gap-2"><p className="text-[18px] font-bold text-ink">{course.title}</p><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status}</Badge></div>
            <p className="mt-2 text-[13px] text-body">{course.courseCode || "Uncoded"} · {course.subject} · {course.level}</p>
            <p className="mt-1 text-[13px] text-body">{course.audience} · {course.durationMin} min · {course.chapterIds.length} chapters</p>
            <p className="mt-3 text-[12px] font-semibold text-muted">{course.learningObjectives.length} learning outcomes</p>
          </Card>
        </button>)}
        {!courses.length ? <p className="text-sm text-muted">No course yet. Create one to start building its chapters.</p> : null}
      </div>
    </section>
  </main>;
}
