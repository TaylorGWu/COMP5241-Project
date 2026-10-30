import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const screen = readFileSync(new URL("../components/AuthScreen.tsx", import.meta.url), "utf8");

test("account registration is separate from qualification submission", () => {
  assert.doesNotMatch(screen, /name="qualification"/);
  assert.doesNotMatch(screen, /validateQualification/);
  assert.match(screen, /authJson<SessionResponse>\("\/api\/auth\/register"/);
});

test("authentication uses a quiet image rather than a fabricated course preview", () => {
  assert.doesNotMatch(screen, /auth-paper|Git, explained|Human judgment/);
  assert.match(screen, /auth-visual/);
  assert.match(screen, /learning-studio/);
});
