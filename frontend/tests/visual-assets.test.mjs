import assert from "node:assert/strict";
import { test } from "node:test";
import { chapterVisualPath } from "../lib/routes.ts";

test("illustrations use authenticated PNG while diagrams keep deterministic SVG", () => {
  assert.equal(chapterVisualPath("course-2", "chapter-3", "il-123", "illustration"), "/api/demo/courses/course-2/chapters/chapter-3/assets/il-123.png");
  assert.equal(chapterVisualPath("course-2", "chapter-3", "as-2", "diagram"), "/api/demo/courses/course-2/chapters/chapter-3/assets/as-2.svg");
  assert.equal(chapterVisualPath("course/2", "chapter/3", "image/1", "illustration"), "/api/demo/courses/course%2F2/chapters/chapter%2F3/assets/image%2F1.png");
});
