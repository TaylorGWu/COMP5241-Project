import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

import { chapterHref, chapterDiagramPath, chapterDeckPath, chapterToolPath } from "../lib/routes.ts";

const coursesPagePath = new URL("../app/courses/page.tsx", import.meta.url);
const createCoursePagePath = new URL("../app/courses/new/page.tsx", import.meta.url);
const chapterWorkspacePath = new URL("../app/courses/[courseId]/chapters/[chapterId]/page.tsx", import.meta.url);

test("course library starts with filters without a redundant title banner", async () => {
  const source = await readFile(coursesPagePath, "utf8");
  assert.doesNotMatch(source, /className="course-library-header"/);
  assert.doesNotMatch(source, /Manage your teaching materials and continue where you left off/);
  assert.match(source, /<h1 className="sr-only">Your courses<\/h1>/);
  assert.match(source, /className="course-catalogue-toolbar"/);
});

test("chapter title is the row link, with management outside the link", async () => {
  const source = await readFile(new URL("../app/courses/[courseId]/page.tsx", import.meta.url), "utf8");
  assert.match(source, /<h3><Link href=\{chapterHref\(courseId, chapter.id\)\} className="chapter-entry__link">/);
  assert.doesNotMatch(source, /Open chapter|Build chapter/);
  assert.match(source, /<details className="chapter-actions">/);
});

test("empty slides offer a recovery path without deleting the saved plan", async () => {
  const source = await readFile(chapterWorkspacePath, "utf8");
  assert.match(source, /data-retry-empty-slides/);
  assert.match(source, /t.slide.retrySlides/);
});

test("a chapter editor URL belongs to its course", () => {
  assert.equal(chapterHref("course-7", "chapter-2"), "/courses/course-7/chapters/chapter-2");
});

test("diagram preview and deck download keep the same course and chapter", () => {
  assert.equal(chapterDiagramPath("course-7", "chapter-2", "as-9"), "/api/demo/courses/course-7/chapters/chapter-2/assets/as-9.svg");
  assert.equal(chapterDeckPath("course-7", "chapter-2"), "/api/demo/courses/course-7/chapters/chapter-2/export/deck.pptx");
});

test("teacher tools are scoped to the chapter in the URL", () => {
  assert.equal(
    chapterToolPath("course-7", "chapter-2", "edit/stream"),
    "/api/demo/courses/course-7/chapters/chapter-2/edit/stream",
  );
  assert.equal(
    chapterToolPath("course-7", "chapter-2", "questions"),
    "/api/demo/courses/course-7/chapters/chapter-2/questions",
  );
});

test("course library follows a browsable catalogue flow rather than a single flat row", async () => {
  const source = await readFile(coursesPagePath, "utf8");

  assert.match(source, /course-library-shell/);
  assert.match(source, /course-catalogue-search/);
  assert.match(source, /course-catalogue-filter/);
  assert.match(source, /data-catalogue-filter="level"/);
  assert.match(source, /data-catalogue-filter="subject"/);
  assert.match(source, /course-library-card/);
  assert.match(source, /Search courses, topics, or codes/);
  assert.match(source, /course-catalogue-results/);
  assert.match(source, /Continue building/);
  assert.doesNotMatch(source, /⌘ K/);
  assert.doesNotMatch(source, /Teaching studio/);
});

test("course catalogue actions use clear labels instead of decorative arrows", async () => {
  const source = await readFile(coursesPagePath, "utf8");

  assert.doesNotMatch(source, />New course<\/Link>/);
  assert.match(source, /<TeacherNavigation active="courses"/);
  assert.match(source, />Continue building<\/span>/);
  assert.match(source, />Create your first course<\/Link>/);
  assert.doesNotMatch(source, /New course <span/);
  assert.doesNotMatch(source, /Continue building <b/);
  assert.doesNotMatch(source, /Create your first course →/);
});

test("teacher navigation gives both destinations the same visual treatment", async () => {
  const nav = await readFile(new URL("../components/TeacherNavigation.tsx", import.meta.url), "utf8");
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");
  assert.doesNotMatch(nav, /teacher-nav__link--create/);
  assert.doesNotMatch(css, /teacher-nav__link--create/);
  assert.match(nav, /aria-current=/);
});

test("course creation uses a compact heading without a redundant back link", async () => {
  const source = await readFile(createCoursePagePath, "utf8");

  assert.match(source, /course-create-page/);
  assert.doesNotMatch(source, />Your courses<\/Link>/);
  assert.match(source, /<TeacherNavigation/);
  assert.doesNotMatch(source, /← Your courses/);
});

test("generation brings the live progress console into view after the first event", async () => {
  const source = await readFile(chapterWorkspacePath, "utf8");

  assert.match(source, /generationRef/);
  assert.match(source, /scrollIntoView\(\{ behavior: "smooth", block: "start" \}\)/);
  assert.match(source, /autoScrollGenerationRef/);
});

test("publishing stays in course settings rather than the course header", async () => {
  const source = await readFile(new URL("../app/courses/[courseId]/page.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(source, /className="course-publish"/);
  assert.match(source, /Publication check/);
  assert.match(source, /Publish reviewed course/);
});
test("creation screen omits the redundant title banner but keeps an accessible heading", async () => {
  const source = await readFile(new URL("../app/courses/new/page.tsx", import.meta.url), "utf8");
  assert.match(source, /<h1 className="sr-only">Create a course<\/h1>/);
  assert.doesNotMatch(source, /Define the course now\.|<header className="course-create-header/);
});
