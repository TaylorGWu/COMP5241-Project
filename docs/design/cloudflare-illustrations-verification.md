# Optional teaching illustrations — verification, 2026-10-27

## Implemented boundary

The existing SectionAgent `request_illustration` tool can use Cloudflare Workers AI
in real-model generation. Model selection comes from `ModelRouter.image`.
Credentials remain in backend configuration; no secrets or local paths enter IR.
The tool records the requested and resolved prompt, provider, model and status.
Generated files are validated, re-encoded as PNG and stored privately.
The existing chapter authorization boundary also requires a slide reference before
serving a file. Preview and PPTX export read the same stored PNG; neither generates images.

Deterministic diagrams remain the first choice for labelled technical content.
Illustrations are optional, unlabelled teaching scenarios, not factual photographs.
Each generation instance allows two external attempts, serializes them, and reuses
successful duplicate prompts within that generation. There is no automatic retry.
Failed assets remain retryable; lesson text is preserved and the generation result
reports the missing image. The teacher must explicitly regenerate to try again.
Publication remains an explicit teacher action.

## Verification run

- Backend: `pytest -q -p no:cacheprovider` — **435 passed**.
- Frontend: `node --experimental-strip-types --test tests/*.test.mjs` — **79 passed**.
- TypeScript: `npx tsc --noEmit` — exit 0.
- ESLint on the changed canvas, chapter page, API client and route helper — exit 0.
- `git diff --check` — exit 0 before this documentation addition.

New tests cover provider/router selection, private PNG persistence, duplicate reuse,
the two-attempt limit, safe quota/malformed-image/timeout failures, path rejection,
redacted settings, tool-call-before-section-submission ordering, complete text
retention after image failure, chapter-scoped preview and embedded PPTX image bytes.
External HTTP is mocked; storage, IR, chapter routes and PPTX conversion are real.
The chapter route integration test attaches a controlled image to generated IR;
it does not claim a live language model chose the illustration tool.

## Not yet verified / known limits

After the user saved the credentials in the running worktree's `backend/env.yaml`,
a live provider smoke test generated one classroom/team illustration successfully:
Cloudflare `@cf/black-forest-labs/flux-1-schnell`, 4 steps, normalized PNG 469361 bytes.
The local preview is `/private/tmp/coursework-cloudflare-first-illustration.png`.
The backend was restarted with `APP_CONFIG_FILE` explicitly targeting the worktree
configuration; `/api/health` returned `{"status":"ok"}`. No credentials were logged.
This verifies one live provider request and stored output, not a full live LLM chapter
generation or the consistency of image quality across subjects. No existing course
was regenerated or overwritten.

The integration uses the pre-existing `/api/demo/*` SSE prototype exception;
formal ARQ job migration is still outstanding. Automatic icon/library retrieval is
not implemented, and the resource-choice rules are prompt guidance, not a complete
AssetResolver. The local image store has no automatic orphan cleanup or distributed
object storage. Broader quotas across concurrent jobs/accounts are not enforced by
the per-generation two-attempt guard.
