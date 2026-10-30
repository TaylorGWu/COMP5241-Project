# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Coursework is a COMP5241 team project for software-engineering mini-courses. Its intended learners include non-CS beginners and CS students preparing for software-development work with AI. Instructors prepare, review and publish learning materials. Administrators handle platform access; the current account increment gives them a teacher-application review queue.

The runnable interface in this worktree centres on instructor preparation and the public account journey. A student account landing is present; the student learning portal is a separate integration module. Full administration, moderation and generation-audit operations are separate future modules.

## Product Purpose

Help instructors turn a teaching brief and existing materials into editable mini-course content while retaining responsibility for what students receive. The wider project aims to give learners an understandable next step, short lessons and interactive activities suited to their background and goal.

Success for this student project includes a demonstrable working slice, design decisions the team can explain, attributable contributions, test results and real stakeholder evidence. Feature count alone is not the quality target.

## Positioning

The confirmed design mechanism is a shared structured content source: AI drafts JSON intermediate representations; deterministic renderers and exporters derive the web and file outputs from that source. Proposed AI edits are reviewed before application, and publication remains a teacher decision. This is a design commitment, not a claim of market exclusivity or measured learning improvement.

## Operating Context

The instructor workflow is teaching brief/materials → structured draft → preview and edit → teacher confirmation → publication/export. The design covers lesson plans, slide decks, questions, assembled exam papers and narrated slide videos; individual implementation availability must be checked against the running application.

Public entry provides a shared login and separate student/teacher registration. Both registration forms create an account from identity and credentials; teacher registration does not require a qualification upload. Students register without approval. New teacher accounts remain pending and can later submit their first qualification from the application page. The interface distinguishes an account that has not submitted a qualification from an application already in review. Only administrator approval opens teacher tools. Rejection includes a reason; the applicant can replace the file and resubmit. The public interactive problem-solving example is illustrative, makes no model request and changes no real course.

The approved local account increment uses SQLite-backed accounts and opaque server sessions alongside the existing teacher workspace. It is a local, single-application-worker prototype; this record makes no production deployment or independent security-audit claim.

Teachers can optionally maintain a private `/profile` after registration, including
a sanitized photo, biography, education, current institution or independent status,
experience and subject specialisms. Teachers and administrators can see these
details; they are not published to students or treated as verified credentials.
Only administrator qualification approval grants access to teacher course tools.

## Capabilities and Constraints

- AI produces structured IR, not HTML or PowerPoint files. Renderers and exporters contain no model calls. Model calls go through `ModelRouter` and its configuration.
- AI output remains draft until a teacher publishes it. Agent write tools propose patches; explicit application is the boundary that changes the artifact. Preserve the reason and diff as review evidence.
- Authorization is enforced by the backend. A teacher sees their own courses; teachers who have not submitted a qualification and pending/rejected applicants cannot use teacher endpoints. Administrator identity does not grant permission to edit another teacher's content.
- Public registration offers only student and teacher roles. Administrator accounts are provisioned locally. Qualification downloads are private to authorized applicants/reviewers; approval is a human review decision, not automated identity verification.
- The account interface accepts PDF/JPEG/PNG qualifications up to 5 MiB. The local prototype does not verify email addresses. Do not add social login, password reset or verification controls without working supporting services.
- Formal generation is designed as asynchronous ARQ jobs. The documented demo generation path is a limited deviation; the account increment does not replace it with a multi-worker generation system.
- Prefer deterministic diagrams, charts and icons before generated imagery. Diagrams with text labels use Mermaid. Isolate failed assets/sections and preserve recoverable work.
- Fixed-layout exports aim for content equivalence, not pixel-for-pixel reproduction of the web preview.
- No general student chatbot, text-to-video generation, automatic publishing, real-time collaborative editing or arbitrary PowerPoint layout in the agreed scope.

Open decisions: production host/domain and operational readiness, final product name, legal/privacy terms and retention policy, and the timing/details of student-portal and full-admin integration. Do not invent these facts in UI copy.

## Brand Commitments

`Coursework` is the existing temporary descriptive name (`frontend/lib/brand.ts`). The approved public/auth work extends the established product identity. Keep the voice concrete about teaching, editing and human judgment. Claims must describe actual capabilities and availability; do not fabricate adoption figures, institutional endorsements, testimonials, verification or learning outcomes.

## Evidence on Hand

- `AGENTS.md` records project constraints and the requirement to retain real interviews, usability tests, individual contributions and test evidence.
- `docs/design/course-generation-design.md` is the generation design source; it distinguishes the intended formal architecture from limited demonstration paths.
- `docs/PROJECT_PLAN.md` records the wider team scope and proposed end-to-end learner/teacher journey, not a blanket implementation-completion claim.
- `docs/REQUIREMENTS_DESK_RESEARCH.md` and `docs/competitor_analysis/README.md` contain desk research and explicitly bounded hypotheses. Their internal workshop is not an external interview; they do not establish measured product effectiveness.
- `docs/project_overivew.pdf` supplies the coursework objectives, deliverables and assessment context.
- `docs/superpowers/specs/2026-10-22-public-entry-auth-design.md` records the approved public/account scope and teacher-qualification amendment. `docs/design/public-entry-interface.md` records its surface direction.
- `frontend/components/PublicHome.tsx`, `AuthScreen.tsx` and `AccountPages.tsx` supply the implemented public example and account UI. Their existence does not establish a complete student LMS or full administrative console.
- `frontend/components/AuthScreen.module.css` records the revised form-first account interface. `frontend/public/images/learning-studio.provenance.md` records the generated decorative image and its prompt. The scene is illustrative; it does not document a named campus or establish an institutional affiliation.

External interview/test outcomes, deployment status and commercial proof must be supported by their own evidence before being presented as facts.

## Product Principles

1. Keep teachers accountable for AI-assisted content through visible review and explicit publication.
2. Keep one structured content source so previews and exports remain explainably related.
3. Make role, approval state, next action and module availability clear.
4. Preserve partial work and provide a useful recovery path when a step fails.
5. Retain honest process evidence; distinguish hypotheses, examples and planned features from observed results.

## Accessibility & Inclusion

The project plan requires keyboard operation, text alternatives and layouts usable down to 320px without horizontal page scrolling. Support English, Traditional Chinese and Simplified Chinese through the existing dictionaries. Honor reduced motion, retain visible form labels/focus, and allow password managers and paste. The intended non-CS audience needs explanations that do not assume technical vocabulary.
