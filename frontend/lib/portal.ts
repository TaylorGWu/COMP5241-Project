import { authJson, type AccountRole } from "./auth.ts";
import type { Slide } from "./api.ts";

export type Course = {
  id: string;
  title: string;
  description: string;
  courseCode: string;
  subject: string;
  level: string;
  durationMin: number;
  chapterCount: number;
  enrolled: boolean;
  completionPercent: number;
  lastChapterId: string | null;
  lastSlideId: string | null;
  totalSlides: number;
  visitedSlides: number;
  totalQuestions: number;
  answeredQuestions: number;
  correctAnswers: number;
  studyDays: number;
  lastStudiedAt: number | null;
  chapterTitles: string[];
};
export type ChapterSummary = {
  id: string;
  title: string;
  slideCount: number;
  questionCount: number;
  completionPercent: number;
  completed: boolean;
};
export type CourseDetail = {
  course: Course;
  chapters: ChapterSummary[];
  enrolled: boolean;
};
export type NextStepReason = "resume" | "goal" | "time" | "start";
export type StudentHome = {
  courses: Course[];
  profile: { background: string; goal: string; weeklyMinutes: number };
  recommendation: {
    courseId: string;
    reason: string;
    reasonCode: NextStepReason;
  } | null;
};
export type Progress = {
  visitedSlideIds: string[];
  lastSlideId: string | null;
  completionPercent: number;
  completed: boolean;
};
export type StudentSlide = Pick<
  Slide,
  "id" | "order" | "layout" | "title" | "quizInstruction" | "statusGroups"
> & {
  bullets?: string[];
  visuals: { id: string; kind: string; altText: string; url: string | null }[];
};
export type Question = {
  id: string;
  stem: string;
  revision: string;
  options: { id: string; text: string }[];
};
export type Result = {
  questionId: string;
  selectedOptionId: string;
  correct: boolean;
  correctOptionId: string;
  explanation: string;
  attemptId: string;
  reviewSlideId: string | null;
};
export type ChapterDetail = {
  chapter: {
    id: string;
    title: string;
    slides: StudentSlide[];
    questions: Question[];
    glossary: { term: string; plain: string }[];
  };
  progress: Progress;
  results: Record<string, Result>;
  previousChapter: { id: string; title: string } | null;
  nextChapter: { id: string; title: string } | null;
  courseTitle?: string;
};
export type AdminUser = {
  id: string;
  name: string;
  email: string;
  role: AccountRole;
  status: string;
  active: boolean;
  createdAt: number;
};
export type AdminCourse = {
  id: string;
  title: string;
  courseCode: string;
  ownerName: string | null;
  status: string;
  archived: boolean;
  moderationReason: string | null;
  chapterCount: number;
  enrollmentCount: number;
};
/**
 * Turn a past timestamp into "2 hours ago" in the reader's language.
 *
 * Derived facts only: the API reports the last activity time and how many days
 * carried activity, never a duration, because sparse timestamps cannot measure
 * time spent without inventing a number.
 */
type SearchableCourse = Pick<
  Course,
  "title" | "description" | "subject" | "courseCode" | "chapterTitles"
>;

function queryTerms(query: string): string[] {
  return query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
}

/**
 * Course search over the fields a learner can actually type: course metadata
 * plus chapter titles, so "neural" finds a course whose chapter names it.
 * Every term must appear somewhere, so extra words narrow rather than widen.
 */
export function courseMatchesQuery(
  course: SearchableCourse,
  query: string,
): boolean {
  const terms = queryTerms(query);
  if (!terms.length) return true;
  const haystack = [
    course.title,
    course.description,
    course.subject,
    course.courseCode,
    ...(course.chapterTitles ?? []),
  ]
    .join(" ")
    .toLocaleLowerCase();
  return terms.every((term) => haystack.includes(term));
}

/** Chapter titles that explain a match, so a hit is never unexplained. */
export function matchingChapterTitles(
  course: SearchableCourse,
  query: string,
): string[] {
  const terms = queryTerms(query);
  if (!terms.length) return [];
  return (course.chapterTitles ?? []).filter((title) => {
    const value = title.toLocaleLowerCase();
    return terms.some((term) => value.includes(term));
  });
}

export function relativeTime(
  pastSeconds: number,
  nowSeconds: number,
  locale: string,
): string {
  const diff = Math.max(0, Math.round(nowSeconds - pastSeconds));
  const format = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (diff < 60) return format.format(-diff, "second");
  if (diff < 3600) return format.format(-Math.floor(diff / 60), "minute");
  if (diff < 86400) return format.format(-Math.floor(diff / 3600), "hour");
  if (diff < 604800) return format.format(-Math.floor(diff / 86400), "day");
  if (diff < 2629800) return format.format(-Math.floor(diff / 604800), "week");
  if (diff < 31557600) return format.format(-Math.floor(diff / 2629800), "month");
  return format.format(-Math.floor(diff / 31557600), "year");
}
export function replacePortalRecord<T extends { id: string }>(
  records: T[],
  updated: T,
): T[] {
  return records.map((record) => (record.id === updated.id ? updated : record));
}
export type AiChange = {
  id: string;
  courseId: string;
  courseTitle: string;
  chapterId: string | null;
  chapterTitle: string;
  kind: string;
  target: string;
  status: "proposed" | "applied" | "rejected";
  author: "ai" | "teacher";
  reason: string;
  diff: string;
};

export type AuditEvent = {
  id: string;
  kind: string;
  actor: string | null;
  title: string;
  status: string;
  at: number | null;
  courseId?: string;
  reason?: string | null;
  model?: string | null;
};
export type Overview = {
  users: number;
  courses: number;
  publishedCourses: number;
  pendingApplications: number;
  enrollments: number;
  userRoles: { role: AccountRole; count: number }[];
  courseStates: {
    state: "published" | "unpublished" | "suspended";
    count: number;
  }[];
  courseEnrollments: {
    courseId: string;
    title: string;
    courseCode: string;
    count: number;
  }[];
};
export type AdminCourseFilter =
  "all" | "published" | "unpublished" | "suspended" | "enrolled";
export type AdminSection =
  | "overview"
  | "applications"
  | "users"
  | "courses"
  | "aiChanges"
  | "activity";
export type AdminDestination = {
  section: AdminSection;
  role?: AccountRole;
  courseFilter?: AdminCourseFilter;
  courseId?: string;
};
export function matchesAdminCourse(
  course: Pick<AdminCourse, "id" | "status" | "archived" | "enrollmentCount">,
  filter: AdminCourseFilter,
  courseId?: string,
) {
  if (courseId && course.id !== courseId) return false;
  if (filter === "published")
    return course.status === "published" && !course.archived;
  if (filter === "unpublished")
    return course.status !== "published" && !course.archived;
  if (filter === "suspended") return course.archived;
  if (filter === "enrolled") return course.enrollmentCount > 0;
  return true;
}
export function matchesAdminUser(
  user: Pick<AdminUser, "role">,
  role: AccountRole | "all",
) {
  return role === "all" || user.role === role;
}
const coursePath = (id: string) =>
  `/api/student/courses/${encodeURIComponent(id)}`;
const chapterPath = (id: string, chapter: string) =>
  `${coursePath(id)}/chapters/${encodeURIComponent(chapter)}`;
const json = <T>(
  path: string,
  method: string,
  body: unknown,
  signal?: AbortSignal,
) =>
  authJson<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
export const portalApi = {
  home: (signal?: AbortSignal) =>
    authJson<StudentHome>("/api/student/home", { signal }),
  profile: (profile: StudentHome["profile"], signal?: AbortSignal) =>
    json<{ profile: StudentHome["profile"] }>(
      "/api/student/profile",
      "PUT",
      profile,
      signal,
    ),
  course: (id: string, signal?: AbortSignal) =>
    authJson<CourseDetail>(coursePath(id), { signal }),
  enroll: (id: string, signal?: AbortSignal) =>
    json<CourseDetail>(`${coursePath(id)}/enroll`, "POST", {}, signal),
  join: (code: string, signal?: AbortSignal) =>
    json<{ courseId: string }>("/api/student/join", "POST", { code }, signal),
  chapter: (id: string, chapter: string, signal?: AbortSignal) =>
    authJson<ChapterDetail>(chapterPath(id, chapter), { signal }),
  /** Ask about the slide in front of the learner; the server grounds the answer. */
  tutor: (
    id: string,
    chapter: string,
    slideId: string,
    question: string,
    signal?: AbortSignal,
  ) =>
    json<{ answer: string }>(
      `${chapterPath(id, chapter)}/tutor`,
      "POST",
      { slideId, question },
      signal,
    ),
  progress: (
    id: string,
    chapter: string,
    slideId: string,
    signal?: AbortSignal,
  ) =>
    json<{ progress: Progress }>(
      `${chapterPath(id, chapter)}/progress`,
      "POST",
      { slideId },
      signal,
    ),
  attempt: (
    id: string,
    chapter: string,
    body: AttemptSubmission,
    signal?: AbortSignal,
  ) =>
    json<{ result: Result; progress: Progress }>(
      `${chapterPath(id, chapter)}/attempts`,
      "POST",
      body,
      signal,
    ),
  overview: (signal?: AbortSignal) =>
    authJson<Overview>("/api/admin/overview", { signal }),
  users: (signal?: AbortSignal) =>
    authJson<{ users: AdminUser[] }>("/api/admin/users", { signal }),
  courses: (signal?: AbortSignal) =>
    authJson<{ courses: AdminCourse[] }>("/api/admin/courses", { signal }),
  audit: (signal?: AbortSignal) =>
    authJson<{ events: AuditEvent[] }>("/api/admin/audit", { signal }),
  aiChanges: (signal?: AbortSignal) =>
    authJson<{ changes: AiChange[] }>("/api/admin/ai-changes", { signal }),
  user: (
    id: string,
    body: { role?: AccountRole; active?: boolean },
    signal?: AbortSignal,
  ) =>
    json<{ user: AdminUser }>(
      `/api/admin/users/${encodeURIComponent(id)}`,
      "PATCH",
      body,
      signal,
    ),
  moderate: (
    id: string,
    restore: boolean,
    reason: string,
    signal?: AbortSignal,
  ) =>
    json<{ course: AdminCourse }>(
      `/api/admin/courses/${encodeURIComponent(id)}/${restore ? "restore" : "archive"}`,
      "POST",
      restore ? {} : { reason },
      signal,
    ),
};
export function studentCourseHref(id: string) {
  return `/student/courses/${encodeURIComponent(id)}`;
}
export function studentChapterHref(id: string, chapter: string) {
  return `${studentCourseHref(id)}/chapters/${encodeURIComponent(chapter)}`;
}
export function progressPercent(value: {
  completionPercent?: number;
  visitedSlideIds?: string[];
  totalSlides?: number;
}) {
  const percent =
    value.completionPercent ??
    (value.totalSlides
      ? (new Set(value.visitedSlideIds ?? []).size / value.totalSlides) * 100
      : 0);
  return Number.isFinite(percent)
    ? Math.round(Math.max(0, Math.min(100, percent)))
    : 0;
}
export function resumeChapter(
  chapters: { id: string; completed: boolean }[],
  last?: string | null,
) {
  return (
    chapters.find((c) => c.id === last)?.id ??
    chapters.find((c) => !c.completed)?.id ??
    chapters[0]?.id ??
    null
  );
}
export function optionText(
  options: { id: string; text: string }[],
  id: string,
) {
  return options.find((o) => o.id === id)?.text ?? id;
}
/** Assets render separately so unavailable images never become invented fallback diagrams. */
export function studentRenderSlide(
  slide: StudentSlide,
  quizGuide: string,
): Slide {
  return {
    id: slide.id,
    order: slide.order,
    // A figure belongs inside the slide, where the teacher reviewed it. Flattening
    // diagram pages to bullets is what made the learner view a second design.
    layout: slide.layout === "quiz" ? "bullets" : slide.layout,
    title: slide.title,
    bullets: slide.layout === "quiz" ? [quizGuide] : (slide.bullets ?? []),
    quizInstruction: slide.quizInstruction,
    statusGroups: slide.statusGroups,
    // Only the kind is kept so the renderer knows a figure exists; the asset
    // itself is addressed by URL, and specs stay teacher-side.
    visuals: slide.visuals.map((visual) => ({
      id: visual.id,
      kind: visual.kind,
    })),
    speakerNotes: "",
    objectiveIds: [],
    sourceRefs: [],
    origin: "teacher",
  };
}

/** The learner-facing quiz page as IR: the slide's own title stays the prompt,
    the paired question's stem becomes the instruction line, and its options
    replace the raw bullets - which may themselves contain answers. Used where
    the learner sees the exercise (main page, thumbnails, tutor preview); the
    correct option is never marked. */
export function studentRenderQuizPage(
  slide: StudentSlide,
  question: Question,
): Slide {
  return {
    id: slide.id,
    order: slide.order,
    layout: "quiz",
    title: slide.title,
    bullets: question.options.map((option) => option.text),
    quizInstruction: question.stem,
    statusGroups: slide.statusGroups,
    visuals: slide.visuals.map((visual) => ({
      id: visual.id,
      kind: visual.kind,
    })),
    speakerNotes: "",
    objectiveIds: [],
    sourceRefs: [],
    origin: "teacher",
  };
}

/** The figure a slide should show, already resolved to a learner-readable URL. */
export function studentSlideFigure(slide: StudentSlide): string | undefined {
  const visual = slide.visuals.find(
    (entry) =>
      entry.url && ["diagram", "illustration", "screenshot"].includes(entry.kind),
  );
  return visual?.url ?? undefined;
}
export type AttemptSubmission = {
  questionId: string;
  optionId: string;
  questionRevision: string;
  submissionId: string;
};
export function prepareAttempt(
  previous: AttemptSubmission | null,
  questionId: string,
  optionId: string,
  questionRevision: string,
  createId: () => string,
): AttemptSubmission {
  return previous?.questionId === questionId &&
    previous.optionId === optionId &&
    previous.questionRevision === questionRevision
    ? previous
    : { questionId, optionId, questionRevision, submissionId: createId() };
}
/** A response from an earlier visit may arrive after a saved attempt. Both are from this snapshot. */
export function mergeProgress(current: Progress, next: Progress): Progress {
  if (next.completionPercent < current.completionPercent)
    return {
      ...current,
      visitedSlideIds: [
        ...new Set([...current.visitedSlideIds, ...next.visitedSlideIds]),
      ],
    };
  return next;
}
