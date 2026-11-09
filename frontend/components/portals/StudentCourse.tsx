"use client";
import { useCallback } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { PortalIcon } from "./PortalIcon";
import {
  portalApi,
  relativeTime,
  resumeChapter,
  studentChapterHref,
} from "@/lib/portal";
import {
  PortalShell,
  PortalError,
  PortalLoading,
  ProgressBar,
  usePortalResource,
  usePortalWrite,
} from "./PortalShell";
export function StudentCourse({ courseId }: { courseId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => portalApi.course(courseId, signal),
    [courseId],
  );
  const resource = usePortalResource(load);
  const join = usePortalWrite();
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const data = resource.data;
  const next = data
    ? resumeChapter(data.chapters, data.course.lastChapterId)
    : null;
  return (
    <PortalShell
      title={data?.course.title}
      action={
        <Link
          className="portal-button portal-button--quiet portal-button--back"
          href="/student"
        >
          <PortalIcon name="chevron" /> {c.back}
        </Link>
      }
    >
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <PortalLoading />
      ) : data ? (
        <>
          <header className="portal-title">
            <div className="portal-title-head">
              <h1>{data.course.title}</h1>
            </div>
            <p>{data.course.description}</p>
            <p className="portal-tags">
              {[data.course.courseCode, data.course.subject, data.course.level]
                .filter(Boolean)
                .map((label) => (
                  <span key={label}>{label}</span>
                ))}
            </p>
            <div className="portal-facts">
              <span>
                {data.course.chapterCount}{" "}
                {data.course.chapterCount === 1 ? c.chapter : c.chapters}
              </span>
              <span>
                {data.course.durationMin} {c.minutes}
              </span>
              {data.enrolled ? (
                <span>
                  {data.course.visitedSlides}/{data.course.totalSlides}{" "}
                  {c.pagesRead}
                </span>
              ) : null}
              {data.enrolled && data.course.totalQuestions ? (
                <span>
                  {data.course.answeredQuestions}/{data.course.totalQuestions}{" "}
                  {c.questionsAnswered}
                </span>
              ) : null}
              {data.enrolled && data.course.studyDays > 0 ? (
                <span>
                  {data.course.studyDays}{" "}
                  {data.course.studyDays === 1 ? c.studyDay : c.studyDays}
                </span>
              ) : null}
            </div>
            {data.enrolled &&
            data.course.studyDays > 0 &&
            data.course.lastStudiedAt ? (
              <p className="portal-meta">
                {c.lastStudied}{" "}
                {relativeTime(
                  data.course.lastStudiedAt,
                  Date.now() / 1000,
                  locale,
                )}
              </p>
            ) : null}
          </header>
          <div className="portal-course-overview">
            <section>
              <h2>{c.chapters}</h2>
              {data.chapters.length ? (
                <ol className="portal-chapter-list">
                  {data.chapters.map((chapter, index) => (
                    <li key={chapter.id}>
                      <span className="portal-chapter-number">{index + 1}</span>
                      <div>
                        <h3>
                          {data.enrolled ? (
                            <Link
                              href={studentChapterHref(courseId, chapter.id)}
                            >
                              {chapter.title}
                            </Link>
                          ) : (
                            chapter.title
                          )}
                        </h3>
                        <p>
                          {chapter.slideCount} {c.pages}
                          {chapter.questionCount
                            ? ` · ${chapter.questionCount} ${c.practiceQuestions}`
                            : ""}
                        </p>
                        <span
                          className={
                            chapter.completed
                              ? "portal-status portal-status--complete"
                              : "portal-meta"
                          }
                        >
                          {chapter.completed
                            ? c.complete
                            : chapter.completionPercent
                              ? `${chapter.completionPercent}%`
                              : c.notStarted}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="portal-empty">{c.empty}</p>
              )}
            </section>
            <aside className="portal-panel">
              <h2>{c.yourProgress}</h2>
              {data.enrolled ? (
                <>
                  <ProgressBar value={data.course.completionPercent} />
                  {next ? (
                    <Link
                      className="portal-button"
                      href={studentChapterHref(courseId, next)}
                    >
                      {data.course.completionPercent ? c.continue : c.start}
                    </Link>
                  ) : null}
                </>
              ) : (
                <button
                  className="portal-button"
                  disabled={join.busy}
                  onClick={() =>
                    void join.run(
                      (signal) => portalApi.enroll(courseId, signal),
                      resource.setData,
                    )
                  }
                >
                  {join.busy ? c.loading : c.join}
                </button>
              )}
              <PortalError error={join.error} />
            </aside>
          </div>
        </>
      ) : null}
    </PortalShell>
  );
}
