# Student and administrator verification record

Branch: `codex/student-admin-portals`  
Base teacher source: `7efa5e9`  
Date: 2026-11-01

## Baseline (before feature implementation)

| Check | Command | Actual result |
| --- | --- | --- |
| Backend | Shared Python 3.12 environment, `pytest -q` from backend | 453 passed in 18.96s |
| Frontend | `node --experimental-strip-types --test tests/*.test.mjs` | 84 passed, 0 failed |
| Fresh checkout route types | `npx next typegen` | Successfully generated |
| TypeScript after typegen | `npx tsc --noEmit --incremental false` | Exit 0 |
| Dependency restore | `npm ci --offline` | 365 packages added, 0 vulnerabilities reported |

The first typecheck before Next.js type generation reported missing generated
`LayoutProps`. This was resolved by typegen, not by changing application code.
Node's experimental TypeScript stripping/module-type warnings are pre-existing
test-runner noise; they are not backend failures or new frontend diagnostics.

## Data isolation

Initial API verification used a separate anonymised SQLite backup under
`/private/tmp/coursework-portals-preview.*`. After the user explicitly requested
port3000, that dataset was copied into the new worktree's ignored
`backend/.local/student-admin-workspace.db`. Original teacher identities/profile
and session rows were restored only in this independent copy for compatibility.
Synthetic student/admin accounts and test learning/audit records remain in the
copy. Illustration files were copied, not moved. No live model request was used
in portal verification.

The original database has six draft courses and fourteen chapters. A student
catalogue with no explicit publication must therefore be empty. Any demonstration
publication will be performed only on the preview copy. Original branch, data,
teacher login and handoff archives remain outside the write scope.

## Acceptance checklist

Backend task commit `24f76d3`: independently rerun from the controller with
`pytest -q`, **461 passed in 13.10s**. This is intermediate backend evidence;
review fixes, frontend and final integrated verification are still pending.

Backend review fixes committed as `53fdaa7`; implementer reports **464 passed in
15.53s**, and independent scoped review approved both fixes (empty publication
rejection and malformed asset degradation). Final controller suite will be rerun
after frontend integration.

### Actual local HTTP walkthrough

Executed `/private/tmp/coursework_portal_api_walkthrough.py` against the isolated
running backend on port8002. It used real cookie/CSRF login and the existing AI
Concepts course copied from the teacher dataset, not a scripted model.

Actual result: all assertions passed for published catalogue, role rejection,
idempotent join, slide visit, wrong/right MCQ attempts, idempotent submission,
persisted progress/results, private diagram fetch, teacher analytics roster,
administrator suspension/restore, teacher republish guard, self-lockout guard,
student session revocation/re-enable/re-login, qualification approval and audit.

This was an **API walkthrough, not a browser interaction test**. It made no writes
to the original dataset. Copied test users and records remain in the preview DB.

### Browser permission and actual interactions

The initial port3002 startup was rejected and respected. The user's subsequent
explicit request to use port3000 superseded that restriction. Actual Chrome UI
checks then ran on frontend3000/backend8000 against the independent copy.

- Student: real login/role redirect, catalogue, learning-goal save acknowledgement,
  chapter navigation, server-graded answer feedback, authenticated diagram rendering
  and refresh restoring the last page and selected/correct answer.
- Administrator: real login rejects the student `next` destination and routes to
  `/admin`; user search filters correctly; own-account controls are protected.
  Course suspension requires an inline reason/confirmation, then displays Suspended;
  restoration displays Available. Activity shows both real actions with actor/time.
  Qualification review retains profile, private download and approve/revision actions.
  No original applicant was approved/rejected during these browser checks.
- Rendering: student/player and admin inspected at1440px,390px and320px widths.
  Ordinary course/question/admin content has document width equal to viewport width
  at390px and320px. English, Traditional Chinese, Simplified Chinese and dark theme
  were inspected; original English/system preferences were restored afterwards.
  Keyboard Tab/Enter selected the Users section; focused control computed a3px blue
  outline. This is a targeted keyboard check, not an exhaustive accessibility audit.
- Impeccable detector ran once on portal components/CSS/copy and returned `[]`.

Teacher integration was exercised through the real authenticated teacher API
(publication, fixture edits and analytics) and the existing teacher regression
suite. A final optional browser sign-in as the synthetic applicant hit the
existing six-logins-per-account/15-minute throttle after repeated fixture API
logins. It was not bypassed or disabled; that last teacher UI switch was not
completed. Student sign-in was restored normally. This is not a claim that every
teacher screen was browser-retested in this increment.

### Integrated automated results

Controller rerun after migration fix: backend `pytest -q`: **465 passed in16.22s**.
Frontend `node --experimental-strip-types --test tests/*.test.mjs`: **93 passed,
0failed**. `npx tsc --noEmit --incremental false` and changed-file ESLint exited0.
`npm run build` succeeded and included the new course/chapter routes. The first
attempt used `npm test`, which is not a configured script; the actual repository
Node test command above was then used successfully.

Independent UI code review identified stale admin state after a successful write
followed by a failed GET, and long code content clipped by the reused renderer.
Both were fixed and scoped re-reviewed as addressed. Actual browser regression:
after restoring a course, temporarily stopping only the isolated backend and
pressing Refresh displayed the network error, retained `Change saved` and kept
the correct Available state. The backend was restarted and the retry succeeded.
A clearly labelled synthetic long-code fixture was created through the real
teacher API in the copied DB. At320px, both code lines had clientWidth=scrollWidth
(214px), grew in height, and the document remained320px wide. The fixture was
withdrawn using the teacher API afterwards; no content was physically deleted.

The final whole-branch review found a stale-question version gap. The fix returns
an opaque student-specific revision with each question, requires it on submission
and rejects an unseen changed version with409. Browser regression loaded the
original synthetic question, republished a changed question with the same option
IDs through the teacher API, and submitted from the old page. The UI displayed
`This question has changed` with a reload action, no answer was graded, and
progress remained50%. The reload showed the updated question; submitting its
answer produced Correct, Answer saved and100%. That synthetic course was again
withdrawn from the student catalogue. The final scoped review approved the fix,
localized recommendation/moderation wording and malformed-question filtering.

Final controller results on commit `2d0e9bf`: **467 backend tests passed
in18.22s;94 frontend tests passed,0failed**. Production build succeeded; scoped
ESLint exited0, and the implementer's cache-free TypeScript check exited0 (the
production build also ran TypeScript successfully). There are no remaining
Critical/Important findings in the final scoped code review. The independent
Impeccable finish review returned `disposition: ship` for the supplied captures;
`student-admin-design-check.md` records the preserved design-system extension.

The initial desktop student capture had an incorrect height. It was recaptured
at1440×1000 with DOM/client dimensions verified, then independently reviewed
anew. All seven final screenshots are archived under
`docs/design/assets/student-admin/`, without browser chrome. They contain internal
test identities and fixtures, not external participant evidence.

| Boundary | Evidence |
| --- | --- |
| Publish, enrol, learn, submit, resume, teacher analytics | Real HTTP walkthrough plus `test_published_course_enrollment_learning_and_analytics`; student browser reading/submission/refresh |
| Draft snapshot isolation, foreign/private content and assets | `test_published_course_enrollment_learning_and_analytics`, `test_invite_and_private_snapshot_asset_boundaries` |
| Server grading, immutable retries and current progress reconciliation | Real HTTP walkthrough; learning/analytics and last-location regression tests |
| Admin access, session revocation, self/last-admin and suspension | Real HTTP walkthrough plus `test_admin_suspends_and_restores_course_and_protects_accounts`; browser suspension/restore |
| Registration/session and CSRF/role rejection | `test_registered_student_can_sign_in_and_open_portal`, auth/role/CSRF tests |
| Additive migration/backup and invalid legacy content | Upgrade/backup tests and `test_upgrade_skips_unlearnable_published_course_without_changing_it` |
| Empty publication and malformed asset degradation | Empty-publication and malformed-asset regression tests |
| Qualification, audit, locales, responsive and keyboard UI | Existing auth regression suite, actual API walkthrough and targeted browser checks above |

## Evidence boundary

Automated regression tests and internal browser walkthroughs are developer
verification. They are not user interviews, external usability tests or proof of
measured learning improvement. The implementation is still the documented local,
single-worker prototype unless separately deployed and tested.
