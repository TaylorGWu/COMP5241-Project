import assert from "node:assert/strict";
import { test } from "node:test";
import { roleDestination, safeDestination, validateQualification } from "../lib/auth.ts";
import { authFetch, authJson, setCsrfToken, signOut } from "../lib/auth.ts";

test("instructors cannot navigate into teaching before approval", () => {
  assert.equal(roleDestination({ role: "instructor", status: "pending" }), "/application");
  assert.equal(roleDestination({ role: "instructor", status: "rejected" }), "/application");
  assert.equal(roleDestination({ role: "instructor", status: "approved" }), "/courses");
  assert.equal(roleDestination({ role: "student", status: "active" }), "/student");
  assert.equal(roleDestination({ role: "admin", status: "active" }), "/admin");
});

test("next redirects reject external hosts and cross-role destinations", () => {
  const student = { role: "student", status: "active" };
  const teacher = { role: "instructor", status: "approved" };
  for (const path of ["//evil.test", "https://evil.test", "/\\evil.test", "/courses", "/studentish", "/student/%2f%2fevil", "/student/../admin"]) {
    assert.equal(safeDestination(path, student), "/student");
  }
  assert.equal(safeDestination("/courses/course-1", teacher), "/courses/course-1");
  assert.equal(safeDestination("/courses/new", { role: "instructor", status: "pending" }), "/application");
});

test("qualification feedback rejects unsupported and oversize uploads", () => {
  assert.equal(validateQualification({ size: 5 * 1024 * 1024 + 1, type: "application/pdf" }), "size");
  assert.equal(validateQualification({ size: 50, type: "image/svg+xml" }), "type");
  assert.equal(validateQualification({ size: 0, type: "application/pdf" }), "empty");
  assert.equal(validateQualification({ size: 120, type: "application/pdf" }), null);
});

test("unsafe requests obtain a CSRF challenge and send cookie credentials", async () => {
  const original = globalThis.fetch;
  const calls = [];
  setCsrfToken(null);
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return calls.length === 1 ? Response.json({ csrfToken: "challenge-from-server" }) : Response.json({ ok: true });
  };
  try {
    await authFetch("/api/auth/register", { method: "POST", body: new FormData() });
    assert.match(calls[0].url, /\/api\/auth\/csrf$/);
    assert.equal(calls[0].init.credentials, "include");
    assert.equal(calls[1].init.credentials, "include");
    assert.equal(calls[1].init.headers.get("X-CSRF-Token"), "challenge-from-server");
    assert.equal(calls[1].init.headers.has("Content-Type"), false);
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});

test("signing out an expired session still clears local credentials", async () => {
  const original = globalThis.fetch;
  setCsrfToken("expired-session-token");
  globalThis.fetch = async () => Response.json({ detail: "Sign in to continue" }, { status: 401 });
  try { await assert.doesNotReject(signOut()); }
  finally { globalThis.fetch = original; setCsrfToken(null); }
});

test("an expired identity check discards session CSRF before the next login", async () => {
  const original = globalThis.fetch;
  const calls = [];
  setCsrfToken("expired-session-token");
  globalThis.fetch = async (url, init) => {
    calls.push({ path: new URL(url).pathname, token: init.headers?.get?.("X-CSRF-Token") });
    if (url.endsWith("/me")) return Response.json({ detail: "Sign in to continue" }, { status: 401 });
    if (url.endsWith("/csrf")) return Response.json({ csrfToken: "fresh-challenge" });
    return Response.json({ ok: true });
  };
  try {
    assert.equal((await authFetch("/api/auth/me")).status, 401);
    await authFetch("/api/auth/login", { method: "POST", body: "{}" });
    assert.deepEqual(calls.map(call => call.path), ["/api/auth/me", "/api/auth/csrf", "/api/auth/login"]);
    assert.equal(calls.at(-1).token, "fresh-challenge");
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});

for (const path of ["/api/auth/profile", "/api/auth/avatar", "/api/auth/qualification"]) {
  test(`expired private account response clears credentials for ${path}`, async () => {
    const original = globalThis.fetch; const originalWindow = globalThis.window;
    const events = new EventTarget(); let expired = 0; const calls = [];
    events.addEventListener("coursework-session-expired", () => expired++);
    globalThis.window = events;
    setCsrfToken("old-session");
    globalThis.fetch = async url => {
      calls.push(new URL(url).pathname);
      if (url.endsWith(path)) return Response.json({ detail: "Sign in to continue" }, { status: 401 });
      return Response.json({ csrfToken: "new-token" });
    };
    try {
      assert.equal((await authFetch(path)).status, 401);
      assert.equal(expired, 1);
      await authFetch("/api/auth/login", { method: "POST", body: "{}" });
      assert.deepEqual(calls, [path, "/api/auth/csrf", "/api/auth/login"]);
    } finally { globalThis.fetch = original; globalThis.window = originalWindow; setCsrfToken(null); }
  });
}

for (const path of ["/api/auth/login", "/api/auth/register"]) {
  test(`an expired pre-auth form refreshes its challenge once for ${path}`, async () => {
    const original = globalThis.fetch;
    const calls = [];
    const body = path.endsWith("register") ? new FormData() : "{}";
    setCsrfToken("expired-challenge");
    globalThis.fetch = async (url, init) => {
      calls.push({ path: new URL(url).pathname, init });
      if (url.endsWith("/csrf")) return Response.json({ csrfToken: "fresh-challenge" });
      if (init.headers.get("X-CSRF-Token") === "expired-challenge") return Response.json({ detail: "The form expired. Reload and try again." }, { status: 403 });
      return Response.json({ ok: true });
    };
    try {
      assert.equal((await authFetch(path, { method: "POST", body })).status, 200);
      assert.deepEqual(calls.map(call => call.path), [path, "/api/auth/csrf", path]);
      assert.equal(calls.at(-1).init.headers.get("X-CSRF-Token"), "fresh-challenge");
      assert.equal(calls.at(-1).init.body, body);
    } finally { globalThis.fetch = original; setCsrfToken(null); }
  });
}

test("CSRF rejection never replays a private mutation or an unrelated auth failure", async () => {
  const original = globalThis.fetch;
  try {
    for (const [path, detail] of [["/api/demo/courses", "The form expired. Reload and try again."], ["/api/auth/login", "Request origin is not allowed"], ["/api/auth/register", "An approved instructor account is required"]]) {
      let calls = 0;
      setCsrfToken("stale-token");
      globalThis.fetch = async () => { calls++; return Response.json({ detail }, { status: 403 }); };
      assert.equal((await authFetch(path, { method: "POST", body: "{}" })).status, 403);
      assert.equal(calls, 1, `must not replay ${path}: ${detail}`);
    }
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});

test("an expired login challenge is recovered at most once", async () => {
  const original = globalThis.fetch;
  const calls = [];
  setCsrfToken("expired-challenge");
  globalThis.fetch = async url => {
    calls.push(new URL(url).pathname);
    return url.endsWith("/csrf") ? Response.json({ csrfToken: "replacement-challenge" }) : Response.json({ detail: "The form expired. Reload and try again." }, { status: 403 });
  };
  try {
    assert.equal((await authFetch("/api/auth/login", { method: "POST", body: "{}" })).status, 403);
    assert.deepEqual(calls, ["/api/auth/login", "/api/auth/csrf", "/api/auth/login"]);
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});

test("an aborted identity response cannot replace a newer session CSRF token", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  setCsrfToken("new-session-token");
  globalThis.fetch = async (url, init) => {
    if (url.endsWith("/me")) {
      controller.abort();
      return Response.json({ csrfToken: "old-session-token" });
    }
    assert.equal(init.headers.get("X-CSRF-Token"), "new-session-token");
    return Response.json({ ok: true });
  };
  try {
    await authJson("/api/auth/me", { signal: controller.signal });
    await authFetch("/api/demo/courses", { method: "POST" });
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});

test("an aborted identity 401 cannot clear a newer session CSRF token", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  setCsrfToken("new-session-token");
  globalThis.fetch = async (url, init) => {
    if (url.endsWith("/me")) {
      controller.abort();
      return Response.json({ detail: "Sign in to continue" }, { status: 401 });
    }
    assert.equal(init.headers.get("X-CSRF-Token"), "new-session-token");
    return Response.json({ ok: true });
  };
  try {
    await assert.rejects(authJson("/api/auth/me", { signal: controller.signal }), { status: 401 });
    await authFetch("/api/demo/courses", { method: "POST" });
  } finally { globalThis.fetch = original; setCsrfToken(null); }
});
