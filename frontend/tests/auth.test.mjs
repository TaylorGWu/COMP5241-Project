import assert from "node:assert/strict";
import { test } from "node:test";
import { roleDestination, safeDestination, validateQualification } from "../lib/auth.ts";
import { authFetch, setCsrfToken, signOut } from "../lib/auth.ts";

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
