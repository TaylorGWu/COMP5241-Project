"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import {
  relativeTime,
  courseMatchesQuery,
  matchingChapterTitles,
  studentCourseHref,
  type Course,
} from "@/lib/portal";
import { PortalIcon } from "./PortalIcon";

/** The catalogue's course card, shared by the My learning grid and the
 *  suggestion dialog so the recommended course looks exactly like itself. */
export function CourseCard({
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
    <article className="course-library-card portal-course">
      {/* The teacher library's card anatomy: code and status on top, the title
          large, one tag, the description, then a footer divided by a rule. */}
      <header className="portal-course__head">
        <span className="portal-course__code">
          {course.courseCode || course.subject}
        </span>
        {course.enrolled ? (
          <span className="portal-course__value">
            {course.completionPercent}%
          </span>
        ) : null}
      </header>
      <h3>
        <Link href={studentCourseHref(course.id)}>{course.title}</Link>
      </h3>
      <p className="portal-tags">
        {[course.subject, course.level]
          .filter(Boolean)
          .map((label) => (
            <span key={label}>{label}</span>
          ))}
      </p>
      <p className="portal-course-description">{course.description}</p>
      {matchingChapterTitles(course, query).length ? (
        <p className="portal-meta">
          {c.matchedChapters}{" "}
          {matchingChapterTitles(course, query).join(" · ")}
        </p>
      ) : null}
      {reason ? (
        <p className="portal-course-reason">
          <strong>{c.why}: </strong>
          {reason}
        </p>
      ) : null}
      {course.enrolled && course.studyDays > 0 && course.lastStudiedAt ? (
        <p className="portal-meta">
          {c.lastStudied}{" "}
          {relativeTime(course.lastStudiedAt, Date.now() / 1000, locale)}
        </p>
      ) : null}
      <footer className="portal-course__foot">
        <div className="portal-facts">
          <span>
            {course.chapterCount}{" "}
            {course.chapterCount === 1 ? c.chapter : c.chapters}
          </span>
          <span>
            {course.durationMin} {c.minutes}
          </span>
          {course.enrolled ? (
            <span>
              {course.visitedSlides}/{course.totalSlides} {c.pagesRead}
            </span>
          ) : null}
          {course.enrolled && course.totalQuestions ? (
            <span>
              {course.answeredQuestions}/{course.totalQuestions}{" "}
              {c.questionsAnswered}
            </span>
          ) : null}
          {course.enrolled && course.studyDays > 0 ? (
            <span>
              {course.studyDays}{" "}
              {course.studyDays === 1 ? c.studyDay : c.studyDays}
            </span>
          ) : null}
        </div>
        <Link
          className="portal-course__action"
          href={studentCourseHref(course.id)}
        >
          {course.enrolled ? c.continue : c.choose} <PortalIcon name="arrow" />
        </Link>
      </footer>
    </article>
  );
}
