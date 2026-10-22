"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Badge, ErrorBar } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api, type TeacherCourse } from "@/lib/api";

/** The library is for finding and resuming courses. Creation has its own route. */
export default function CoursesPage() {
  const [courses, setCourses] = useState<TeacherCourse[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | "draft" | "published">("all");
  const [level, setLevel] = useState("all");
  const [subject, setSubject] = useState("all");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.courses().then((result) => setCourses(result.courses))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);
  const levels = useMemo(
    () => [...new Set(courses.map((course) => course.audience).filter(Boolean))],
    [courses],
  );
  const subjects = useMemo(
    () => [...new Set(courses.map((course) => course.subject).filter(Boolean))],
    [courses],
  );
  const visibleCourses = useMemo(() => courses.filter((course) => {
    const searchable = `${course.title} ${course.courseCode} ${course.subject} ${course.audience}`.toLowerCase();
    const matchesQuery = searchable.includes(query.trim().toLowerCase());
    const matchesLevel = level === "all" || course.audience === level;
    const matchesSubject = subject === "all" || course.subject === subject;
    return matchesQuery && matchesLevel && matchesSubject && (status === "all" || course.status === status);
  }), [courses, level, query, status, subject]);

  return (
    <main className="course-library-page min-h-screen bg-canvas">
      <div className="course-library-shell mx-auto w-full max-w-[1160px] px-5 pb-16 pt-4 sm:px-8">
        <TeacherNavigation active="courses" />
        <header className="course-library-header">
          <div className="course-library-intro">
            <div className="course-library-title-row"><h1>Your courses</h1></div>
            <p>Manage your teaching materials and continue where you left off.</p>
          </div>
          <Link href="/courses/new" className="course-library-create">New course</Link>
        </header>

        {error ? <div className="mt-7"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
        <section className="course-library-workspace" aria-label="Course library">
          <div className="course-catalogue-toolbar">
          <label className="course-catalogue-search">
            <span className="sr-only">Search courses</span>
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search courses, topics, or codes" />
          </label>

          <div className="course-catalogue-filters" aria-label="Catalogue filters">
            <label className="course-catalogue-filter" data-catalogue-filter="level">
              <span>Level</span>
              <select aria-label="Level" value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="all">All levels</option>
                {levels.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="course-catalogue-filter" data-catalogue-filter="subject">
              <span>Subject</span>
              <select aria-label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)}>
                <option value="all">All subjects</option>
                {subjects.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="course-catalogue-filter">
              <span>Status</span>
              <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
                <option value="all">All courses</option><option value="draft">Drafts</option><option value="published">Published</option>
              </select>
            </label>
          </div>
          </div>

          <div className="course-catalogue-results">
            <p role="status"><strong>{visibleCourses.length}</strong> {visibleCourses.length === 1 ? "course" : "courses"}{query.trim() || status !== "all" || level !== "all" || subject !== "all" ? " matching your filters" : " in your library"}</p>
            {query.trim() || status !== "all" || level !== "all" || subject !== "all" ? <button type="button" className="course-catalogue-clear" onClick={() => { setQuery(""); setStatus("all"); setLevel("all"); setSubject("all"); }}>Clear filters</button> : null}
          </div>
          <div className="course-library-grid">
            {visibleCourses.map((course) => (
              <Link key={course.id} href={`/courses/${course.id}`} className="course-library-card group">
                <div className="course-library-card__topline">
                  <p>{course.courseCode || course.subject}</p>
                  <Badge tone={course.status === "published" ? "green" : "amber"}>{course.status === "published" ? "Published" : "Draft"}</Badge>
                </div>
                <div className="course-library-card__body">
                  <h2>{course.title}</h2>
                  <div className="course-library-card__tags"><span>{course.audience}</span>{course.description?.trim().toLowerCase() === "short course" ? <span>{course.description.trim()}</span> : null}</div>
                  {course.description && course.description.trim().toLowerCase() !== "short course" ? <p className="course-library-card__description">{course.description}</p> : !course.description ? <p className="course-library-card__description">Add a description to orient learners before they begin.</p> : null}
                </div>
                <footer className="course-library-card__footer">
                  <div className="course-library-card__facts"><span>{course.chapterIds.length} chapter{course.chapterIds.length === 1 ? "" : "s"}</span><span>{course.durationMin} min</span></div>
                  <span className="course-library-card__continue">Continue building</span>
                </footer>
              </Link>
            ))}
            {!visibleCourses.length ? <div className="course-library-empty"><p>{loading ? "Loading courses…" : courses.length ? "No courses match your filters" : "Start with a course"}</p><span>{loading ? "Your teaching materials will appear here." : courses.length ? "Try a different search or clear your filters." : "Create a course first, then add and build chapters inside it."}</span>{!courses.length && !loading ? <Link href="/courses/new">Create your first course</Link> : null}</div> : null}
          </div>
        </section>
      </div>
    </main>
  );
}
