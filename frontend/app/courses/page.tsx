"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge, ErrorBar, Field, inputCls } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api, type TeacherCourse } from "@/lib/api";

/** The library is for finding and resuming courses. Creation has its own route. */
export default function CoursesPage() {
  const [courses, setCourses] = useState<TeacherCourse[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "draft" | "published">("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.courses().then((result) => setCourses(result.courses))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);
  const visibleCourses = useMemo(() => courses.filter((course) => {
    const matchesQuery = `${course.title} ${course.courseCode} ${course.subject}`.toLowerCase().includes(query.trim().toLowerCase());
    return matchesQuery && (status === "all" || course.status === status);
  }), [courses, query, status]);

  return (
    <main className="min-h-screen bg-canvas">
      <div className="mx-auto w-full max-w-[1180px] px-5 pb-20 pt-5 sm:px-8">
        <TeacherNavigation active="courses" />
        <header className="flex flex-wrap items-end justify-between gap-5 border-b border-line pb-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue">Workspace / Courses</p>
            <h1 className="mt-3 text-[clamp(2.25rem,5vw,3.75rem)] font-semibold leading-[1.05] tracking-[-0.065em] text-ink">Your courses<span className="ml-3 align-top text-lg font-medium tracking-normal text-muted">{courses.length}</span></h1>
            <p className="mt-3 max-w-[58ch] text-[15px] leading-6 text-body">Continue a chapter, review AI drafts, or publish a course when its teaching material is ready.</p>
          </div>
          <Link href="/courses/new" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-sm bg-blue px-5 text-sm font-semibold text-white transition-colors hover:bg-blue-deep">Create course <span aria-hidden>↗</span></Link>
        </header>

        {error ? <div className="mt-6"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
        <section className="pt-8" aria-label="Course library">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold tracking-[-0.025em] text-ink">Course library</h2>
              <p className="mt-1 text-sm text-muted">Draft courses are private until you publish them.</p>
            </div>
            <div className="grid w-full gap-3 sm:w-auto sm:grid-cols-[240px_160px]">
              <Field label="Search courses"><input className={inputCls} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Title or course code" /></Field>
              <Field label="Status"><select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}><option value="all">All courses</option><option value="draft">Drafts</option><option value="published">Published</option></select></Field>
            </div>
          </div>
          <div className="mt-5 overflow-hidden rounded-md border border-line bg-surface">
            {visibleCourses.map((course, index) => (
              <Link key={course.id} href={`/courses/${course.id}`} className="group grid gap-x-6 gap-y-4 border-b border-line px-5 py-5 transition-colors last:border-b-0 hover:bg-blue-soft/40 sm:grid-cols-[52px_minmax(0,1fr)_170px_24px] sm:items-center sm:px-7">
                <span className="hidden font-mono text-[13px] text-muted sm:block">{String(index + 1).padStart(2, "0")}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3"><h3 className="truncate text-[19px] font-semibold tracking-[-0.03em] text-ink group-hover:text-blue">{course.title}</h3><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status === "published" ? "Published" : "Draft"}</Badge></div>
                  <p className="mt-1.5 text-sm text-body">{course.courseCode || course.subject} <span className="mx-1.5 text-line">/</span> {course.audience}</p>
                  {course.description ? <p className="mt-1 line-clamp-1 text-sm text-muted">{course.description}</p> : null}
                </div>
                <div className="text-sm text-body"><span className="font-semibold text-ink">{course.chapterIds.length}</span> chapter{course.chapterIds.length === 1 ? "" : "s"}<span className="mx-2 text-line">·</span>{course.durationMin} min</div>
                <span className="hidden text-lg text-blue transition-transform group-hover:translate-x-1 sm:block" aria-hidden>→</span>
              </Link>
            ))}
            {!visibleCourses.length ? <div className="px-7 py-12"><p className="text-lg font-semibold text-ink">{loading ? "Loading courses…" : courses.length ? "No courses match your filters" : "Start with a course"}</p><p className="mt-2 max-w-[48ch] text-sm leading-6 text-body">{courses.length ? "Try another title or status." : "Create a course first. You can add, rename and build chapters inside it."}</p>{!courses.length && !loading ? <Link href="/courses/new" className="mt-5 inline-flex text-sm font-semibold text-blue">Create your first course →</Link> : null}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
