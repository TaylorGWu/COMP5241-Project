"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { PortalIcon } from "./PortalIcon";
import {
  portalApi,
  studentCourseHref,
  studentChapterHref,
  type StudentHome,
  type Course,
  type NextStepReason,
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
  const [minutes, setMinutes] = useState(
    data.profile.weeklyMinutes ? String(data.profile.weeklyMinutes) : "",
  );
  const [code, setCode] = useState("");
  const profile = usePortalWrite();
  const invite = usePortalWrite();
  const enrolled = data.courses.filter((course) => course.enrolled);
  const recommendation = data.courses.find(
    (course) => course.id === data.recommendation?.courseId,
  );
  // One next step, one entry point: a resume is shown in the resume card only.
  const resume =
    (data.recommendation?.reasonCode === "resume" ? recommendation : undefined) ??
    enrolled.find((course) => course.completionPercent < 100) ??
    enrolled[0];
  const reasons: Record<NextStepReason, string> = {
    resume: c.reasonResume,
    goal: c.reasonGoal,
    time: c.reasonTime,
    start: c.reasonStart,
  };
  const reason = data.recommendation
    ? reasons[data.recommendation.reasonCode]
    : "";
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
          {
            background: background.trim(),
            goal: goal.trim(),
            weeklyMinutes: minutes.trim() === "" ? 0 : Number(minutes),
          },
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
            <div className="portal-resume-course">
              <span className="portal-course-mark">
                <PortalIcon name="book" />
              </span>
              <div className="portal-resume-copy">
                <h3>{resume.title}</h3>
                <p className="portal-meta">
                  {[resume.courseCode, resume.subject]
                    .filter(Boolean)
                    .join(" · ")}{" "}
                  · {resume.chapterCount} {c.chapters}
                </p>
              </div>
              <Link
                className="portal-button"
                href={
                  resume.lastChapterId
                    ? studentChapterHref(resume.id, resume.lastChapterId)
                    : studentCourseHref(resume.id)
                }
              >
                {c.continue} <PortalIcon name="arrow" />
              </Link>
              <ProgressBar value={resume.completionPercent} />
            </div>
          ) : (
            <p>{c.noResume}</p>
          )}
        </section>
        {recommendation &&
        data.recommendation &&
        data.recommendation.reasonCode !== "resume" ? (
          <section className="portal-recommendation">
            <h2>{c.recommendation}</h2>
            <h3>
              <Link href={studentCourseHref(recommendation.id)}>
                {recommendation.title}
              </Link>
            </h3>
            <p>
              <strong>{c.why}: </strong>
              {reason}
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
            <div
              className={`portal-course-grid${visible.length === 1 ? " portal-course-grid--single" : ""}`}
            >
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
          {data.profile.background ||
          data.profile.goal ||
          data.profile.weeklyMinutes ? (
            <dl className="portal-goal-summary">
              <div>
                <dt>{c.background}</dt>
                <dd>{data.profile.background || c.notProvided}</dd>
              </div>
              <div>
                <dt>{c.goal}</dt>
                <dd>{data.profile.goal || c.notProvided}</dd>
              </div>
              {data.profile.weeklyMinutes ? (
                <div>
                  <dt>{c.weeklyMinutes}</dt>
                  <dd>
                    {data.profile.weeklyMinutes} {c.minutes}
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : (
            <p>{c.profileHint}</p>
          )}
          <details
            className="portal-goals-editor"
            open={!data.profile.background && !data.profile.goal}
          >
            <summary>{c.editGoals}</summary>
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
              <label>
                {c.weeklyMinutes}
                <input
                  type="number"
                  min={0}
                  max={6000}
                  step={15}
                  inputMode="numeric"
                  value={minutes}
                  onChange={(event) => setMinutes(event.target.value)}
                />
              </label>
              <p className="portal-meta">{c.weeklyMinutesHint}</p>
              <button className="portal-button" disabled={profile.busy}>
                {profile.busy ? c.saving : c.save}
              </button>
            </form>
          </details>
          <PortalError error={profile.error} />
          {profile.saved ? (
            <p role="status" className="portal-save-feedback">
              {c.saved}
            </p>
          ) : null}
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
      <p className="portal-course-description">{course.description}</p>
      <p className="portal-meta">
        {course.chapterCount} {c.chapters} · {course.durationMin} {c.minutes}
      </p>
      {course.enrolled ? (
        <p className="portal-meta">
          {course.visitedSlides}/{course.totalSlides} {c.pagesRead} ·{" "}
          {course.answeredQuestions}/{course.totalQuestions}{" "}
          {c.questionsAnswered}
        </p>
      ) : null}
      {course.enrolled ? (
        <ProgressBar value={course.completionPercent} />
      ) : null}
      <Link className="portal-text-link" href={studentCourseHref(course.id)}>
        {course.enrolled ? c.continue : c.choose} <PortalIcon name="arrow" />
      </Link>
    </article>
  );
}
