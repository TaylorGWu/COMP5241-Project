"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { PortalIcon } from "./PortalIcon";
import {
  portalApi,
  courseMatchesQuery,
  type StudentHome,
  type Course,
} from "@/lib/portal";
import { PortalShell, PortalError, PortalLoading, ProgressBar, usePortalResource, usePortalWrite } from "./PortalShell";
import { CourseCard } from "./CourseCard";
import { SuggestionDialog, SUGGESTION_SEEN_KEY } from "./SuggestionDialog";

export function StudentPortal() {
  const resource = usePortalResource(portalApi.home);
  const { locale } = useI18n();
  const c = portalCopy(locale);
  return (
    <PortalShell
      // The menu is navigation: one line that jumps to the goals panel on the page.
      menuExtra={undefined}
    >
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
  const [level, setLevel] = useState("all");
  const [subject, setSubject] = useState("all");
  const [tab, setTab] = useState<"learning" | "courses">(() =>
    data.courses.some((course) => course.enrolled) ? "learning" : "courses",
  );
  const [code, setCode] = useState("");
  const enrolled = data.courses.filter((course) => course.enrolled);
  const recommendation = data.courses.find(
    (course) => course.id === data.recommendation?.courseId,
  );
  const [showSuggestion, setShowSuggestion] = useState(false);
  // The bell rings until the learner opens the suggestion it stands for; a
  // changed recommendation rings again. The seen key is browser-local on
  // purpose - whether a learner noticed a hint is not server data.
  const [suggestionSeen, setSuggestionSeen] = useState(true);
  const suggestionKey = data.recommendation
    ? `${data.recommendation.courseId}|${data.recommendation.reasonCode}`
    : "";
  useEffect(() => {
    let stored = "";
    try {
      stored = window.localStorage.getItem(SUGGESTION_SEEN_KEY) ?? "";
    } catch {
      stored = "";
    }
    setSuggestionSeen(suggestionKey === stored);
  }, [suggestionKey]);
  const levels = [...new Set(data.courses.map((course) => course.level))].sort();
  const subjects = [
    ...new Set(data.courses.map((course) => course.subject)),
  ].sort();
  const learning = data.courses.filter(
    (course) =>
      course.enrolled &&
      courseMatchesQuery(course, search) &&
      (level === "all" || course.level === level) &&
      (subject === "all" || course.subject === subject),
  );
  const visible = data.courses.filter(
    (course) =>
      courseMatchesQuery(course, search) &&
      (level === "all" || course.level === level) &&
      (subject === "all" || course.subject === subject),
  );
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
        {/* The suggestion is a notification the learner can carry in their
            eye's corner: bell, label and a dot while a recommendation stands.
            The tooltip names the course; clicking opens it as its own card. */}
        <button
          type="button"
          className="portal-tabs-notification"
          data-attention={
            data.recommendation && !suggestionSeen ? "" : undefined
          }
          title={
            (recommendation && recommendation.title) || c.recommendation
          }
          onClick={() => {
            setShowSuggestion(true);
            setSuggestionSeen(true);
          }}
        >
          <PortalIcon name="bell" />
          <span className="portal-tabs-notification__label">
            {c.recommendation}
          </span>
          {data.recommendation ? (
            <span className="portal-tabs-notification__dot" aria-hidden="true" />
          ) : null}
        </button>
        {/* The count rides with the tabs, as the teacher library's line does. */}
        <p className="portal-tabs-count">
          {tab === "learning"
            ? `${learning.length} ${learning.length === 1 ? c.course : c.courses}`
            : `${visible.length} ${visible.length === 1 ? c.course : c.courses}`}
        </p>
      </div>
      <div className="portal-student-home">
        <div className="portal-main-column">
              <div className="course-catalogue-toolbar">
                <label className="course-catalogue-search">
                  <PortalIcon name="search" />
                  <span className="sr-only">{c.search}</span>
                  <input
                    type="search"
                    placeholder={c.searchCatalogue}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </label>
                <div className="course-catalogue-filters">
                  <label className="course-catalogue-filter">
                    <span>{c.level}</span>
                    <select
                      value={level}
                      onChange={(event) => setLevel(event.target.value)}
                    >
                      <option value="all">{c.allLevels}</option>
                      {levels.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="course-catalogue-filter">
                    <span>{c.subject}</span>
                    <select
                      value={subject}
                      onChange={(event) => setSubject(event.target.value)}
                    >
                      <option value="all">{c.allSubjects}</option>
                      {subjects.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
          {tab === "learning" ? (
            <>
              {enrolled.length ? (
                <section>
                  {/* One list: the course the learner should open next is marked
                      on its card instead of being lifted out of the list. */}
                  <div
                    className={`portal-course-grid${learning.length === 1 ? " portal-course-grid--single" : ""}`}
                  >
                    {learning.map((course) => (
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
            </>
          ) : (
            <section>
              {/* Same shape as the teacher library: a bordered toolbar with the
                  search on the left and the two attributes on the right. */}
              {/* Same markup as the teacher library - one toolbar, one set of
                  styles, no second catalogue implementation. */}
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
        <SuggestionDialog
          course={recommendation}
          recommendation={data.recommendation}
          open={showSuggestion}
          onClose={() => setShowSuggestion(false)}
        />
      </div>
    </>
  );
}
