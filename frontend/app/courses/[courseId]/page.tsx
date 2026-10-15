"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Button, Card, Field, SectionLabel, inputCls } from "@/components/ui";
import { api, type TeacherChapter, type TeacherCourse } from "@/lib/api";

export default function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();
  const [course, setCourse] = useState<TeacherCourse | null>(null);
  const [chapters, setChapters] = useState<TeacherChapter[]>([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    const nextCourse = await api.course(courseId);
    const nextChapters = await Promise.all(nextCourse.chapterIds.map((id) => api.chapter(courseId, id)));
    setCourse(nextCourse); setChapters(nextChapters);
  };
  useEffect(() => { void load().catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [courseId]);

  const addChapter = async () => {
    if (!title.trim()) return;
    try { await api.createChapter(courseId, { title: title.trim() }); setTitle(""); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };
  const open = (chapter: TeacherChapter) => {
    window.localStorage.setItem("pathpilot.activeCourse", courseId);
    window.localStorage.setItem("pathpilot.activeChapter", chapter.id);
    router.push("/");
  };

  return <main className="mx-auto min-h-screen w-full max-w-[1120px] px-6 py-12">
    <button type="button" onClick={() => router.push("/courses")} className="text-sm font-semibold text-blue">← All courses</button>
    {course ? <header className="mt-6 flex flex-wrap items-end justify-between gap-4">
      <div><SectionLabel>Course workspace</SectionLabel><h1 className="mt-3 text-[42px] font-bold tracking-[-0.05em] text-ink">{course.title}</h1><p className="mt-2 text-body">{course.audience} · {course.durationMin} min · {course.status}</p></div>
    </header> : null}
    {error ? <p className="mt-5 rounded-sm border border-amber/30 bg-amber-soft p-3 text-sm text-amber">{error}</p> : null}
    <Card className="mt-8 p-6"><SectionLabel>Create a chapter</SectionLabel><div className="mt-3 flex gap-3"><Field label="Chapter title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Pull request review" /></Field><Button variant="primary" className="mt-[26px]" onClick={addChapter} disabled={!title.trim()}>Create chapter</Button></div></Card>
    <section className="mt-8"><SectionLabel>Chapters</SectionLabel><div className="mt-3 space-y-3">
      {chapters.map((chapter) => <Card key={chapter.id} className="flex flex-wrap items-center gap-4 p-5"><span className="font-mono text-sm text-muted">{String(chapter.order).padStart(2, "0")}</span><div className="min-w-[220px] flex-1"><p className="font-bold text-ink">{chapter.title}</p><p className="mt-1 text-sm text-muted">{chapter.status} · {chapter.package?.slideDeck?.slides?.length ?? 0} slides</p></div><Button onClick={() => open(chapter)}>{chapter.package ? "Open chapter studio" : "Build chapter"}</Button></Card>)}
    </div></section>
  </main>;
}
