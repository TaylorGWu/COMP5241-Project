"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Button, Card, Field, SectionLabel, inputCls } from "@/components/ui";
import { api, type TeacherCourse } from "@/lib/api";

/** Teacher course catalogue: create and choose a course before touching chapters. */
export default function CoursesPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<TeacherCourse[]>([]);
  const [title, setTitle] = useState("");
  const [audience, setAudience] = useState("University beginners");
  const [duration, setDuration] = useState(45);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => setCourses((await api.courses()).courses);
  useEffect(() => { void refresh().catch((e) => setError(String(e))); }, []);

  const create = async () => {
    if (!title.trim()) return;
    setBusy(true); setError("");
    try {
      const course = await api.createCourse({ title: title.trim(), description: "", audience, durationMin: duration, language: "zh-HK" });
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
      <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_180px_130px]">
        <Field label="Course title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Git collaboration" /></Field>
        <Field label="Learners"><input className={inputCls} value={audience} onChange={(e) => setAudience(e.target.value)} /></Field>
        <Field label="Minutes"><input className={inputCls} type="number" value={duration} onChange={(e) => setDuration(Number(e.target.value))} /></Field>
      </div>
      <Button variant="primary" className="mt-4" disabled={busy || !title.trim()} onClick={create}>{busy ? "Creating…" : "Create course"}</Button>
    </Card>
    <section className="mt-8">
      <SectionLabel>Your courses</SectionLabel>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {courses.map((course) => <button key={course.id} type="button" onClick={() => router.push(`/courses/${course.id}`)} className="text-left">
          <Card className="h-full p-5 transition hover:border-blue">
            <p className="text-[18px] font-bold text-ink">{course.title}</p>
            <p className="mt-2 text-[13px] text-body">{course.audience} · {course.durationMin} min</p>
            <p className="mt-3 text-[12px] font-semibold text-muted">{course.chapterIds.length} chapters · {course.status}</p>
          </Card>
        </button>)}
        {!courses.length ? <p className="text-sm text-muted">No course yet. Create one to start building its chapters.</p> : null}
      </div>
    </section>
  </main>;
}
