"use client";
import { useCallback } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
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
    <PortalShell>
      <Link className="portal-text-link" href="/student">
        {c.back}
      </Link>
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <PortalLoading />
      ) : data ? (
        <>
          <header className="portal-title">
            <h1>{data.course.title}</h1>
            <p>{data.course.description}</p>
            <p className="portal-meta">
              {[data.course.courseCode, data.course.subject, data.course.level]
                .filter(Boolean)
                .join(" · ")}{" "}
              · {data.course.durationMin} {c.minutes}
            </p>
            {data.enrolled ? (
              <p className="portal-meta">
                {data.course.visitedSlides}/{data.course.totalSlides}{" "}
                {c.pagesRead} · {data.course.answeredQuestions}/
                {data.course.totalQuestions} {c.questionsAnswered}
              </p>
            ) : null}
            {data.enrolled &&
            data.course.studyDays > 0 &&
            data.course.lastStudiedAt ? (
              <p className="portal-meta">
                {data.course.studyDays} {c.studyDays} · {c.lastStudied}{" "}
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
                          {chapter.slideCount} {c.outline} ·{" "}
                          {chapter.questionCount} {c.practice}
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
                            : `${chapter.completionPercent}%`}
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
              <h2>{c.progress}</h2>
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
