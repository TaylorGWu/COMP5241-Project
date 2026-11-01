"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import {
  portalApi,
  studentCourseHref,
  studentChapterHref,
  type StudentHome,
  type Course,
} from "@/lib/portal";
import {
  PortalShell,
  PortalError,
  PortalLoading,
  ProgressBar,
  usePortalResource,
  usePortalWrite,
} from "./PortalShell";

export function StudentPortal() {
  const resource = usePortalResource(portalApi.home);
  const { locale } = useI18n();
  const c = portalCopy(locale);
  return (
    <PortalShell>
      <header className="portal-title">
        <h1>{c.learning}</h1>
      </header>
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading && !resource.data ? (
        <PortalLoading />
      ) : resource.data ? (
        <StudentHomeContent data={resource.data} reload={resource.reload} />
      ) : null}
    </PortalShell>
  );
}
function StudentHomeContent({
  data,
  reload,
}: {
  data: StudentHome;
  reload: () => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [background, setBackground] = useState(data.profile.background);
  const [goal, setGoal] = useState(data.profile.goal);
  const [code, setCode] = useState("");
  const profile = usePortalWrite();
  const invite = usePortalWrite();
  const enrolled = data.courses.filter((course) => course.enrolled);
  const resume =
    enrolled.find((course) => course.completionPercent < 100) ?? enrolled[0];
  const recommendation = data.courses.find(
    (course) => course.id === data.recommendation?.courseId,
  );
  const visible = data.courses.filter((course) =>
    `${course.title} ${course.description} ${course.subject} ${course.courseCode}`
      .toLocaleLowerCase()
      .includes(search.toLocaleLowerCase()),
  );
  const save = (e: FormEvent) => {
    e.preventDefault();
    void profile.run(
      (signal) =>
        portalApi.profile(
          { background: background.trim(), goal: goal.trim() },
          signal,
        ),
      reload,
    );
  };
  const join = (e: FormEvent) => {
    e.preventDefault();
    void invite.run(
      (signal) => portalApi.join(code.trim(), signal),
      (result) => router.push(studentCourseHref(result.courseId)),
    );
  };
  return (
    <div className="portal-student-home">
      <div className="portal-main-column">
        <section className="portal-resume">
          <h2>{c.continue}</h2>
          {resume ? (
            <>
              <h3>{resume.title}</h3>
              <ProgressBar value={resume.completionPercent} />
              <Link
                className="portal-button"
                href={
                  resume.lastChapterId
                    ? studentChapterHref(resume.id, resume.lastChapterId)
                    : studentCourseHref(resume.id)
                }
              >
                {c.continue}
              </Link>
            </>
          ) : (
            <p>{c.noResume}</p>
          )}
        </section>
        {recommendation && data.recommendation ? (
          <section className="portal-recommendation">
            <h2>{c.recommendation}</h2>
            <h3>
              <Link href={studentCourseHref(recommendation.id)}>
                {recommendation.title}
              </Link>
            </h3>
            <p>
              <strong>{c.why}: </strong>
              {data.recommendation.reason}
            </p>
          </section>
        ) : null}
        <section>
          <div className="portal-section-heading">
            <h2>{c.discover}</h2>
            <span>{visible.length}</span>
          </div>
          <label className="portal-search">
            {c.search}
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          {visible.length ? (
            <div className="portal-course-grid">
              {visible.map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </div>
          ) : (
            <div className="portal-empty">
              <h3>{c.noCourses}</h3>
              <p>{c.noCoursesHint}</p>
            </div>
          )}
        </section>
      </div>
      <aside className="portal-sidebar">
        <section className="portal-panel">
          <h2>{c.profile}</h2>
          <p>{c.profileHint}</p>
          <form onSubmit={save}>
            <label>
              {c.background}
              <textarea
                maxLength={500}
                value={background}
                onChange={(event) => setBackground(event.target.value)}
              />
            </label>
            <label>
              {c.goal}
              <textarea
                maxLength={500}
                value={goal}
                onChange={(event) => setGoal(event.target.value)}
              />
            </label>
            <button className="portal-button" disabled={profile.busy}>
              {profile.busy ? c.saving : c.save}
            </button>
            <PortalError error={profile.error} />
            {profile.saved ? <p role="status">{c.saved}</p> : null}
          </form>
        </section>
        <section className="portal-panel">
          <h2>{c.invite}</h2>
          <form onSubmit={join}>
            <label>
              {c.code}
              <input
                required
                maxLength={100}
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </label>
            <button
              className="portal-button portal-button--secondary"
              disabled={invite.busy || !code.trim()}
            >
              {invite.busy ? c.loading : c.join}
            </button>
            <PortalError error={invite.error} />
          </form>
        </section>
      </aside>
    </div>
  );
}
function CourseCard({ course }: { course: Course }) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  return (
    <article className="portal-course">
      <p className="portal-meta">
        {[course.courseCode, course.subject, course.level]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <h3>
        <Link href={studentCourseHref(course.id)}>{course.title}</Link>
      </h3>
      <p>{course.description}</p>
      <p className="portal-meta">
        {course.chapterCount} {c.chapters} · {course.durationMin} {c.minutes}
      </p>
      {course.enrolled ? (
        <ProgressBar value={course.completionPercent} />
      ) : null}
      <Link className="portal-text-link" href={studentCourseHref(course.id)}>
        {course.enrolled ? c.continue : c.choose}
      </Link>
    </article>
  );
}
