import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { api } from "../lib/api.ts";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test("generation reports the backend error frame instead of a generic missing-result error", async () => {
  const frame = 'event: error\ndata: {"error":{"code":"HTTPException","message":"未配置模型密钥。请配置 DEEPSEEK_API_KEY。"}}\n\n';
  globalThis.fetch = async () => new Response(frame, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });

  await assert.rejects(
    api.generateChapterStream("course-1", "chapter-1", {
      topic: "Git branches",
      audience: "University beginners",
      duration_min: 20,
      objectives: ["Explain branches"],
      material_text: "",
      use_real_model: true,
      language: "en",
    }, { onResult: () => assert.fail("No result should be emitted") }),
    /未配置模型密钥。请配置 DEEPSEEK_API_KEY。/,
  );
});

test("an edit validation response shows FastAPI's message instead of object object", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({
    detail: [{ msg: "String should have at most 500 characters" }],
  }), {
    status: 422,
    headers: { "Content-Type": "application/json" },
  });

  await assert.rejects(
    api.editChapterStream(
      "course-1",
      "chapter-1",
      "A long planned request",
      "slides",
      true,
      [],
      { onResult: () => assert.fail("No result should be emitted") },
    ),
    /String should have at most 500 characters/,
  );
});
