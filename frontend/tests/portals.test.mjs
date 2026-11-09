import assert from "node:assert/strict";
import { test } from "node:test";
import {
  studentChapterHref,
  relativeTime,
  progressPercent,
  resumeChapter,
  optionText,
  portalApi,
  studentRenderSlide,
  prepareAttempt,
  mergeProgress,
  replacePortalRecord,
  matchesAdminCourse,
  matchesAdminUser,
} from "../lib/portal.ts";
test("dashboard course drilldowns exclude suspended publications and preserve identity", () => {
  const live = {
    id: "live",
    status: "published",
    archived: false,
    enrollmentCount: 2,
  };
  const suspended = { ...live, id: "held", archived: true };
  const draft = { ...live, id: "draft", status: "draft", enrollmentCount: 0 };
  assert.equal(matchesAdminCourse(live, "published"), true);
  assert.equal(matchesAdminCourse(suspended, "published"), false);
  assert.equal(matchesAdminCourse(suspended, "suspended"), true);
  assert.equal(matchesAdminCourse(draft, "unpublished"), true);
  assert.equal(matchesAdminCourse(suspended, "unpublished"), false);
  assert.equal(matchesAdminCourse(draft, "enrolled"), false);
  assert.equal(matchesAdminCourse(suspended, "enrolled"), true);
  assert.equal(matchesAdminCourse(live, "all", "held"), false);
  assert.equal(matchesAdminCourse(live, "all", "live"), true);
  assert.equal(matchesAdminCourse(draft, "all"), true);
});
test("dashboard role drilldowns retain disabled accounts and use exact roles", () => {
  assert.equal(
    matchesAdminUser({ role: "student", active: false }, "student"),
    true,
  );
  assert.equal(matchesAdminUser({ role: "instructor" }, "student"), false);
  assert.equal(matchesAdminUser({ role: "admin" }, "all"), true);
});
test("successful administrative changes replace only the matching list record", () => {
  const current = [
    { id: "a", active: true },
    { id: "b", active: true },
  ];
  assert.deepEqual(replacePortalRecord(current, { id: "a", active: false }), [
    { id: "a", active: false },
    { id: "b", active: true },
  ]);
  assert.deepEqual(current, [
    { id: "a", active: true },
    { id: "b", active: true },
  ]);
});
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
  const first = prepareAttempt(null, "q", "B", "rev1", id);
  assert.deepEqual(first, {
    questionId: "q",
    optionId: "B",
    questionRevision: "rev1",
    submissionId: "submission-1",
  });
  assert.equal(prepareAttempt(first, "q", "B", "rev1", id), first);
  assert.deepEqual(prepareAttempt(first, "q", "A", "rev1", id), {
    questionId: "q",
    optionId: "A",
    questionRevision: "rev1",
    submissionId: "submission-2",
  });
  assert.deepEqual(prepareAttempt(first, "q", "B", "rev2", id), {
    questionId: "q",
    optionId: "B",
    questionRevision: "rev2",
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
      {
        questionId: "q",
        optionId: "B",
        submissionId: "unique",
        questionRevision: "rev1",
      },
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
      questionRevision: "rev1",
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

test("every locale explains each recommendation reason and the time budget", () => {
  // The backend sends a reason code, so a missing translation would leave the
  // "why this course" line blank in one language.
  const required = [
    "reasonResume",
    "reasonGoal",
    "reasonTime",
    "reasonStart",
    "weeklyMinutes",
    "weeklyMinutesHint",
    "reviewRelated",
  ];
  for (const locale of ["en", "zh-HK", "zh-CN"]) {
    const copy = portalCopy(locale);
    for (const key of required) {
      assert.equal(
        typeof copy[key],
        "string",
        `${locale} is missing ${key}`,
      );
      assert.ok(copy[key].trim().length > 0, `${locale} has empty ${key}`);
    }
  }
  // The union in lib/portal.ts must cover exactly the codes the backend emits.
  const codes = ["resume", "goal", "time", "start"];
  const copy = portalCopy("en");
  const mapped = codes.map(
    (code) => copy[`reason${code[0].toUpperCase()}${code.slice(1)}`],
  );
  assert.equal(new Set(mapped).size, codes.length);
});

test("last-activity reads naturally in every locale and never says \"in\"", () => {
  const now = 1_760_000_000;
  const twoHoursAgo = now - 2 * 3600;
  assert.equal(relativeTime(twoHoursAgo, now, "en"), "2 hours ago");
  assert.match(relativeTime(twoHoursAgo, now, "zh-HK"), /2.*小時前/);
  assert.match(relativeTime(twoHoursAgo, now, "zh-CN"), /2.*小时前/);
  // Larger gaps use weeks and months rather than a silly day count.
  assert.equal(relativeTime(now - 10 * 86400, now, "en"), "last week");
  assert.match(relativeTime(now - 40 * 86400, now, "en"), /last month/);
  // A clock skew must not produce a future statement.
  assert.equal(relativeTime(now + 30, now, "en"), "now");
});
