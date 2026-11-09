"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { PortalIcon } from "./PortalIcon";
import {
  portalApi,
  relativeTime,
  courseMatchesQuery,
  matchingChapterTitles,
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
  const [tab, setTab] = useState<"learning" | "courses">(() =>
    data.courses.some((course) => course.enrolled) ? "learning" : "courses",
  );
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
  // The hero already shows the course it resumes, so the list holds the rest.
  const others = enrolled.filter((course) => course.id !== resume?.id);
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
    courseMatchesQuery(course, search),
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
    <>
      {/* The tab names the page, so a visible title would only repeat it. The
          heading stays for document structure and screen readers. */}
      <h1 className="sr-only">{tab === "learning" ? c.learning : c.courses}</h1>
      {/* Two destinations side by side with the catalogue filter. */}
      <div className="portal-tabs-row">
        <nav className="portal-tabs" aria-label={c.learning}>
          <button
            type="button"
            aria-current={tab === "learning" ? "page" : undefined}
            onClick={() => setTab("learning")}
          >
            {c.learning}
          </button>
          <button
            type="button"
            aria-current={tab === "courses" ? "page" : undefined}
            onClick={() => setTab("courses")}
          >
            {c.courses}
          </button>
        </nav>
        {tab === "courses" && data.courses.length ? (
          <label className="portal-search portal-search--compact">
            <span className="sr-only">{c.search}</span>
            <input
              type="search"
              placeholder={c.search}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        ) : null}
      </div>
      <div className="portal-student-home">
        <div className="portal-main-column">
          {tab === "learning" ? (
            <>
              {enrolled.length ? (
                <section>
                  <div className="portal-section-heading">
                    <h2>{c.myCourses}</h2>
                    <span>{enrolled.length}</span>
                  </div>
                  {/* One list: the course the learner should open next is marked
                      on its card instead of being lifted out of the list. */}
                  <div
                    className={`portal-course-grid${enrolled.length === 1 ? " portal-course-grid--single" : ""}`}
                  >
                    {enrolled.map((course) => (
                      <CourseCard
                        key={course.id}
                        course={course}
                        query=""
                        reason={
                          data.recommendation?.reasonCode === "resume" &&
                          data.recommendation.courseId === course.id
                            ? c.reasonResume
                            : undefined
                        }
                      />
                    ))}
                  </div>
                </section>
              ) : (
                <section className="portal-resume">
                  <h2>{c.continue}</h2>
                  <p>{c.noResume}</p>
                  <button
                    type="button"
                    className="portal-button portal-button--secondary"
                    onClick={() => setTab("courses")}
                  >
                    {c.browseCourses} <PortalIcon name="arrow" />
                  </button>
                </section>
              )}
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
            </>
          ) : (
            <section>
              {visible.length ? (
                <div
                  className={`portal-course-grid${visible.length === 1 ? " portal-course-grid--single" : ""}`}
                >
                  {visible.map((course) => (
                    <CourseCard
                      key={course.id}
                      course={course}
                      query={search}
                    />
                  ))}
                </div>
              ) : (
                <div className="portal-empty">
                  <h3>{c.noCourses}</h3>
                  <p>{c.noCoursesHint}</p>
                </div>
              )}
            </section>
          )}
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
              <div>
                <dt>{c.weeklyMinutes}</dt>
                <dd>
                  {data.profile.weeklyMinutes
                    ? `${data.profile.weeklyMinutes} ${c.minutes}`
                    : c.notProvided}
                </dd>
              </div>
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
              <div className="portal-form-actions">
                <button className="portal-button" disabled={profile.busy}>
                  {profile.busy ? c.saving : c.save}
                </button>
                {profile.saved ? (
                  <span role="status" className="portal-save-feedback">
                    <PortalIcon name="check" />
                    {c.saved}
                  </span>
                ) : null}
              </div>
            </form>
          </details>
          <PortalError error={profile.error} />
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
    </>
  );
}
function CourseCard({
  course,
  query,
  reason,
}: {
  course: Course;
  query: string;
  /** Why this course is the next step, shown only for the recommended one. */
  reason?: string;
}) {
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
      {matchingChapterTitles(course, query).length ? (
        <p className="portal-meta">
          {c.matchedChapters}{" "}
          {matchingChapterTitles(course, query).join(" · ")}
        </p>
      ) : null}
      <p className="portal-meta">
        {course.chapterCount} {c.chapters} · {course.durationMin} {c.minutes}
      </p>
      {course.enrolled ? (
        <p className="portal-meta">
          {course.visitedSlides}/{course.totalSlides} {c.pagesRead}
          {course.totalQuestions
            ? ` · ${course.answeredQuestions}/${course.totalQuestions} ${c.questionsAnswered}`
            : ""}
        </p>
      ) : null}
      {course.enrolled && course.studyDays > 0 && course.lastStudiedAt ? (
        <p className="portal-meta">
          {course.studyDays} {c.studyDays} · {c.lastStudied}{" "}
          {relativeTime(course.lastStudiedAt, Date.now() / 1000, locale)}
        </p>
      ) : null}
      {course.enrolled ? (
        <ProgressBar value={course.completionPercent} />
      ) : null}
      {reason ? (
        <p className="portal-course-reason">
          <strong>{c.why}: </strong>
          {reason}
        </p>
      ) : null}
      <Link className="portal-text-link" href={studentCourseHref(course.id)}>
        {course.enrolled ? c.continue : c.choose} <PortalIcon name="arrow" />
      </Link>
    </article>
  );
}
