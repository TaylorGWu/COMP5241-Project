import assert from "node:assert/strict";
import { test } from "node:test";
import { workspaceCopy } from "../lib/workspace-copy.ts";

for (const [locale, copy] of Object.entries(workspaceCopy)) {
  test(`${locale}: selection labels use visible order and handle an empty deck`, () => {
    assert.match(copy.slide(3), /3/);
    assert.match(copy.count(3, 17), /3.*17/);
    assert.match(copy.count(0, 0), /0.*0/);
    assert.ok(copy.target && copy.hint && copy.proposals && copy.empty);
  });
}
