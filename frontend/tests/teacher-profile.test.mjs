import assert from "node:assert/strict";
import { test } from "node:test";
import { profilePayload } from "../lib/teacher-profile.ts";
import { readFile } from "node:fs/promises";

test("profile omits the intro banner while retaining an accessible localized heading", async () => {
  const source = await readFile(new URL("../components/TeacherProfile.tsx", import.meta.url), "utf8");
  assert.match(source, /<h1 className="sr-only">\{c.title\}<\/h1>/);
  assert.doesNotMatch(source, /<header className="teacher-profile-heading"|\{c.intro\}/);
});

test("profile saves only editable fields, never server-owned metadata", () => {
  const result = profilePayload({ name: "Teacher", bio: "", institution: "College", independent: false, position: "", university: "University", degree: "master", experience: "3-5", subjects: ["databases"], otherSubject: "", hasAvatar: true, avatarVersion: "v1", status: "approved", id: "not-editable" });
  assert.deepEqual(result, { name: "Teacher", bio: "", institution: "College", independent: false, position: "", university: "University", degree: "master", experience: "3-5", subjects: ["databases"], otherSubject: "" });
});

test("independent teachers clear institution and deselected custom subject", () => {
  const result = profilePayload({ name: "Teacher", bio: "", institution: "Old College", independent: true, position: "", university: "", degree: "", experience: "", subjects: [], otherSubject: "Old subject", hasAvatar: false, avatarVersion: null });
  assert.equal(result.institution, "");
  assert.equal(result.otherSubject, "");
});
