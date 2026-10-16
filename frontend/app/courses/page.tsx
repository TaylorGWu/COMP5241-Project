"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge, Card, ErrorBar, Field, SectionLabel, inputCls } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api, type TeacherCourse } from "@/lib/api";

/** Course home: browse and resume work. Creation deliberately lives at /courses/new. */
export default function CoursesPage() {
  const [courses, setCourses] = useState<TeacherCourse[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "draft" | "published">("all");
  const [error, setError] = useState("");

  useEffect(() => { void api.courses().then((result) => setCourses(result.courses)).catch((e) => setError(e instanceof Error ? e.message : String(e))); }, []);
  const visibleCourses = useMemo(() => courses.filter((course) => {
    const matchesQuery = `${course.title} ${course.courseCode} ${course.subject}`.toLowerCase().includes(query.trim().toLowerCase());
    return matchesQuery && (status === "all" || course.status === status);
  }), [courses, query, status]);

  return <main className="mx-auto min-h-screen w-full max-w-[1120px] px-6 py-8">
    <TeacherNavigation active="courses" />
    <header className="flex flex-wrap items-end justify-between gap-5">
      <div className="max-w-[64ch]"><SectionLabel>Teacher workspace</SectionLabel><h1 className="mt-3 text-[44px] font-bold tracking-[-0.05em] text-ink">Your courses</h1><p className="mt-3 text-[17px] leading-[1.6] text-body">Open a course to shape its chapters, review AI drafts and publish only what you have checked.</p></div>
      <Link href="/courses/new" className="inline-flex min-h-[42px] items-center justify-center rounded-sm bg-blue px-5 text-[15px] font-semibold text-white transition-colors hover:bg-blue-deep">Create course</Link>
    </header>
    {error ? <div className="mt-6"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
    <section className="mt-9">
      <div className="flex flex-wrap items-end justify-between gap-3"><div><SectionLabel>Your course library</SectionLabel><p className="mt-2 text-sm text-muted">{courses.length} course{courses.length === 1 ? "" : "s"} · drafts stay private until publication.</p></div><div className="grid w-full gap-3 sm:w-auto sm:grid-cols-[260px_160px]"><Field label="Search"><input className={inputCls} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or code" /></Field><Field label="Status"><select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}><option value="all">All courses</option><option value="draft">Drafts</option><option value="published">Published</option></select></Field></div></div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        {visibleCourses.map((course) => <Link key={course.id} href={`/courses/${course.id}`} className="text-left"><Card className="h-full p-5 transition hover:border-blue"><div className="flex flex-wrap items-center gap-2"><p className="text-[19px] font-bold text-ink">{course.title}</p><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status}</Badge></div><p className="mt-2 text-[13px] text-body">{course.courseCode || "No course code"} · {course.subject}</p><p className="mt-1 text-[13px] text-body">{course.audience} · {course.durationMin} min · {course.chapterIds.length} chapters</p><p className="mt-3 line-clamp-2 text-sm leading-6 text-muted">{course.description || "No course purpose added yet."}</p><p className="mt-4 text-[12px] font-semibold text-blue">Open course →</p></Card></Link>)}
        {!visibleCourses.length ? <Card className="p-7 sm:col-span-2"><p className="font-semibold text-ink">{courses.length ? "No courses match these filters." : "Your course library is empty."}</p><p className="mt-2 text-sm text-muted">{courses.length ? "Clear the search or choose another status." : "Create a course first, then add its chapters inside the course workspace."}</p>{!courses.length ? <Link href="/courses/new" className="mt-4 inline-flex text-sm font-semibold text-blue">Create your first course →</Link> : null}</Card> : null}
      </div>
    </section>
  </main>;
}
