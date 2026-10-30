import assert from "node:assert/strict";
import { test } from "node:test";
import { publicCopy } from "../lib/public-copy.ts";

for (const locale of ["en", "zh-HK", "zh-CN"]) {
  test(`${locale}: homepage teaches an everyday process without Git knowledge`, () => {
    const copy = publicCopy(locale);
    const example = [copy.exampleTitle, copy.exampleTopic, copy.exampleSlideLabel,
      copy.briefText, copy.objective, copy.slideTitle, copy.before, copy.after, copy.reason];
    assert.ok(example.every(value => typeof value === "string" && value.length > 0));
    assert.doesNotMatch(example.join(" "), /\bgit\b|app\.js|\bcommit\b/i);
    assert.equal(copy.phaseCues.length, 3);
    assert.equal(new Set(copy.phaseCues).size, 3);
    assert.equal(new Set([copy.phaseUnderstand, copy.phaseTry, copy.phaseCheck]).size, 3);
    assert.notEqual(copy.before, copy.after);
  });
}
