import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("slide canvas has semantic visual treatments instead of a universal flow fallback", async () => {
  const source = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.match(source, /function ComparisonFrame/);
  assert.match(source, /function ScenarioFrame/);
  assert.match(source, /function EvidenceFrame/);
  assert.match(source, /visualPurpose === "comparison"/);
});

test("diagram reading notes use the available slide height instead of clustering at the top", async () => {
  const source = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.match(source, /function Bullets\(\{ items, twoCol, spread/);
  assert.match(source, /flex-1 flex-col justify-evenly/);
  assert.match(source, /<Bullets items=\{bullets\.slice\(0, 4\)\} spread/);
});

test("engineering case points are split into balanced, full-height reading columns", async () => {
  const source = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.match(source, /function ScenarioFrame[\s\S]*const columns = \[/);
  assert.match(source, /grid min-h-0 flex-1 grid-cols-2 gap-8/);
  assert.match(source, /<Bullets items=\{column\} spread presentation=\{presentation\} targetIndices=/);
});

test("content-heavy slide layouts use their available height instead of leaving empty lower halves", async () => {
  const source = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.match(source, /function BalancedBulletColumns/);
  assert.match(source, /<BalancedBulletColumns items=\{bullets\} presentation=\{presentation\} \/>/);
  assert.match(source, /function EvidenceFrame[\s\S]*<Bullets items=\{items\} spread presentation=\{presentation\} \/>/);
  assert.match(source, /<ol className="flex min-h-0 flex-1 flex-col justify-evenly">/);
});
