import assert from "node:assert/strict";
import { test } from "node:test";
import {
  studentChapterHref,
  progressPercent,
  resumeChapter,
  optionText,
  portalApi,
  studentRenderSlide,
  prepareAttempt,
  mergeProgress,
} from "../lib/portal.ts";
import { setCsrfToken } from "../lib/auth.ts";
import { portalCopy } from "../lib/portal-copy.ts";

test("portal paths encode both identifiers independently", () => {
  assert.equal(
    studentChapterHref("c/1", "ch 2"),
    "/student/courses/c%2F1/chapters/ch%202",
  );
});
test("progress is finite, clamped and based on unique visits", () => {
  assert.equal(
    progressPercent({ visitedSlideIds: ["s1", "s1"], totalSlides: 2 }),
    50,
  );
  assert.equal(progressPercent({ completionPercent: 125 }), 100);
  assert.equal(progressPercent({ completionPercent: -1 }), 0);
  assert.equal(progressPercent({ totalSlides: 0 }), 0);
  assert.equal(progressPercent({ completionPercent: NaN }), 0);
});
test("resume keeps a current last chapter and recovers removed chapters", () => {
  const chapters = [
    { id: "one", completed: true },
    { id: "two", completed: false },
  ];
  assert.equal(resumeChapter(chapters, "one"), "one");
  assert.equal(resumeChapter(chapters, "removed"), "two");
  assert.equal(resumeChapter([], null), null);
});
test("answer labels map IDs to current option text", () => {
  assert.equal(
    optionText([{ id: "B", text: "Use a branch" }], "B"),
    "Use a branch",
  );
  assert.equal(optionText([], "removed"), "removed");
});
test("student rendering supplies only safe content and useful quiz guidance", () => {
  const slide = studentRenderSlide(
    {
      id: "s",
      order: 1,
      layout: "quiz",
      title: "Practice",
      bullets: ["private answer"],
      speakerNotes: "private notes",
      visuals: [],
    },
    "Answer the questions below",
  );
  assert.deepEqual(slide.bullets, ["Answer the questions below"]);
  assert.equal(slide.speakerNotes, "");
  assert.deepEqual(slide.sourceRefs, []);
  assert.deepEqual(slide.objectiveIds, []);
});
test("ambiguous failed submissions reuse an ID until choice or explicit retry changes", () => {
  let generated = 0;
  const id = () => `submission-${++generated}`;
  const first = prepareAttempt(null, "q", "B", id);
  assert.deepEqual(first, {
    questionId: "q",
    optionId: "B",
    submissionId: "submission-1",
  });
  assert.equal(prepareAttempt(first, "q", "B", id), first);
  assert.deepEqual(prepareAttempt(first, "q", "A", id), {
    questionId: "q",
    optionId: "A",
    submissionId: "submission-2",
  });
  assert.deepEqual(prepareAttempt(null, "q", "B", id), {
    questionId: "q",
    optionId: "B",
    submissionId: "submission-3",
  });
});
test("late saved progress cannot erase a newer saved question result", () => {
  const latest = {
    visitedSlideIds: ["s1", "s2"],
    lastSlideId: "s2",
    completionPercent: 100,
    completed: true,
  };
  assert.deepEqual(
    mergeProgress(latest, {
      visitedSlideIds: ["s1"],
      lastSlideId: "s1",
      completionPercent: 33,
      completed: false,
    }),
    latest,
  );
});
test("each supported locale supplies the complete portal vocabulary", () => {
  const english = portalCopy("en");
  for (const locale of ["zh-HK", "zh-CN"]) {
    const copy = portalCopy(locale);
    assert.deepEqual(Object.keys(copy).sort(), Object.keys(english).sort());
    assert.equal(copy.continue, locale === "zh-HK" ? "繼續學習" : "继续学习");
    assert.equal(copy.restore, locale === "zh-HK" ? "恢復存取" : "恢复访问");
  }
});
test("portal requests use student contracts and authenticated JSON mutations", async () => {
  const original = globalThis.fetch;
  const calls = [];
  setCsrfToken("portal-test");
  globalThis.fetch = async (url, init) => {
    calls.push({ path: new URL(url).pathname, init });
    return Response.json({});
  };
  try {
    const signal = new AbortController().signal;
    await portalApi.home(signal);
    await portalApi.chapter("c/1", "ch 2", signal);
    await portalApi.progress("c/1", "ch 2", "s1", signal);
    await portalApi.attempt(
      "c/1",
      "ch 2",
      { questionId: "q", optionId: "B", submissionId: "unique" },
      signal,
    );
    await portalApi.user("u/1", { active: false }, signal);
    await portalApi.moderate("c/1", false, "Review needed", signal);
    assert.deepEqual(
      calls.map((c) => c.path),
      [
        "/api/student/home",
        "/api/student/courses/c%2F1/chapters/ch%202",
        "/api/student/courses/c%2F1/chapters/ch%202/progress",
        "/api/student/courses/c%2F1/chapters/ch%202/attempts",
        "/api/admin/users/u%2F1",
        "/api/admin/courses/c%2F1/archive",
      ],
    );
    assert.deepEqual(JSON.parse(calls[2].init.body), { slideId: "s1" });
    assert.deepEqual(JSON.parse(calls[3].init.body), {
      questionId: "q",
      optionId: "B",
      submissionId: "unique",
    });
    assert.equal(calls[4].init.method, "PATCH");
    assert.deepEqual(JSON.parse(calls[5].init.body), {
      reason: "Review needed",
    });
    assert.ok(
      calls.every(
        (c) => c.init.signal === signal && c.init.credentials === "include",
      ),
    );
    assert.equal(calls[2].init.headers.get("X-CSRF-Token"), "portal-test");
  } finally {
    globalThis.fetch = original;
    setCsrfToken(null);
  }
});
