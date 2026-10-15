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
  const togglePublish = async () => {
    if (!course) return;
    try {
      setCourse(course.status === "published" ? await api.unpublishCourse(courseId) : await api.publishCourse(courseId));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const ready = chapters.filter((chapter) => chapter.status === "ready").length;
  return <main className="min-h-screen bg-soft/40">
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
    <button type="button" onClick={() => router.push("/courses")} className="text-sm font-semibold text-blue">← Course catalogue</button>
    {course ? <header className="mt-5 rounded-md bg-ink px-7 py-8 text-white">
      <SectionLabel className="text-[#a9c2ff]">Teacher course studio</SectionLabel>
      <div className="mt-4 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-[42px] font-bold tracking-[-0.05em]">{course.title}</h1><p className="mt-2 text-[15px] text-[#c4d0e5]">{course.audience} · {course.durationMin} min · {course.status}</p></div><Button onClick={togglePublish}>{course.status === "published" ? "Unpublish course" : "Publish course"}</Button></div>
    </header> : null}
    {error ? <p className="mt-5 rounded-sm border border-amber/30 bg-amber-soft p-3 text-sm text-amber">{error}</p> : null}
    <div className="mt-6 grid gap-4 sm:grid-cols-3"><Card className="p-4"><p className="text-xs font-semibold text-muted">CHAPTERS</p><p className="mt-1 text-2xl font-bold text-ink">{chapters.length}</p></Card><Card className="p-4"><p className="text-xs font-semibold text-muted">READY TO REVIEW</p><p className="mt-1 text-2xl font-bold text-ink">{ready}</p></Card><Card className="p-4"><p className="text-xs font-semibold text-muted">COURSE STATUS</p><p className="mt-1 text-2xl font-bold text-ink capitalize">{course?.status ?? "draft"}</p></Card></div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><section><Card className="p-6"><SectionLabel>Course chapters</SectionLabel><p className="mt-2 text-sm text-muted">Build the teaching sequence first; open a chapter only when you are ready to draft its material.</p><div className="mt-5 space-y-3">
      {chapters.map((chapter) => <Card key={chapter.id} className="flex flex-wrap items-center gap-4 border-line p-5"><span className="grid h-9 w-9 place-items-center rounded-full bg-blue-soft font-mono text-sm font-bold text-blue">{String(chapter.order).padStart(2, "0")}</span><div className="min-w-[220px] flex-1"><p className="font-bold text-ink">{chapter.title}</p><p className="mt-1 text-sm text-muted">{chapter.status} · {chapter.package?.slideDeck?.slides?.length ?? 0} slides</p></div><Button onClick={() => open(chapter)}>{chapter.package ? "Open studio" : "Build chapter"}</Button></Card>)}
    </div></Card></section><aside><Card className="p-5"><SectionLabel>Create a chapter</SectionLabel><p className="mt-2 text-sm leading-6 text-muted">Add the next teaching unit to this course. You can draft its slides later.</p><div className="mt-4"><Field label="Chapter title"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Pull request review" /></Field></div><Button variant="primary" className="mt-4 w-full" onClick={addChapter} disabled={!title.trim()}>Create chapter</Button></Card></aside></div>
    </div></main>;
}
