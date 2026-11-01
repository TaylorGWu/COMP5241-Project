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
export type StudentHome = {
  courses: Course[];
  profile: { background: string; goal: string };
  recommendation: { courseId: string; reason: string } | null;
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
export function replacePortalRecord<T extends { id: string }>(
  records: T[],
  updated: T,
): T[] {
  return records.map((record) => (record.id === updated.id ? updated : record));
}
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
  "overview" | "applications" | "users" | "courses" | "activity";
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
    layout: ["diagram", "quiz"].includes(slide.layout)
      ? "bullets"
      : slide.layout,
    title: slide.title,
    bullets: slide.layout === "quiz" ? [quizGuide] : (slide.bullets ?? []),
    quizInstruction: slide.quizInstruction,
    statusGroups: slide.statusGroups,
    visuals: [],
    speakerNotes: "",
    objectiveIds: [],
    sourceRefs: [],
    origin: "teacher",
  };
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
