> 中文译本:[PROJECT_PLAN.zh.md](PROJECT_PLAN.zh.md)。英文原版为准,两份需保持同步。

# COMP5241 Project Plan

## 0. Working project direction

**Working concept:** an AI-assisted mini-course platform for learning software engineering.

The platform should let instructors create and refine interactive mini-courses with AI, while students receive learning content, activities, feedback, and suggested next steps suited to their background and goals.

This is a working direction, not a final product name or scope decision. The group should validate it during requirements elicitation before committing to implementation.

### Primary user roles

| Role | Main goal | Core capabilities |
| --- | --- | --- |
| Student | Learn software engineering topics at an appropriate level | Onboarding, course learning, activities, feedback, progress, recommendations |
| Instructor | Create and manage interactive mini-courses efficiently | AI course draft generation, editing, publishing, student management, analytics |
| Admin | Maintain basic platform operations | User and course overview; basic moderation/management |

### Recommended MVP user journey

```text
Instructor creates and publishes a Git Basics mini-course
  -> Student joins the course and completes a lesson plus MCQ activity
  -> System stores the attempt, score, and progress
  -> Instructor sees completion rate and common incorrect answers
```

Build this end-to-end flow before adding advanced AI features.

---

## 1. Project kickoff and team setup

### Objectives

- Establish one shared workspace and a reliable collaboration process for five members.
- Make every member's contribution visible in GitHub and the final presentation.

### Tasks

- [ ] Create a public GitHub repository in the course organisation.
- [ ] Create a GitHub Project board with `Backlog`, `Ready`, `In progress`, `Review`, and `Done` columns.
- [ ] Add every member as a collaborator and agree on a communication channel and weekly meeting time.
- [ ] Agree on branch naming, pull-request review, commit-message, and issue-assignment conventions.
- [ ] Create a project README with the project goal, team members, setup instructions, and link to the deployed app when available.
- [ ] Create an initial issue for every deliverable in this plan.

### Evidence to retain

- Repository activity, Issues, Project board, pull requests, meeting notes, and meaningful commits from each member.

### Exit criteria

- Every member has repository access and owns at least one Issue.
- The team has agreed on how changes are reviewed and merged.

---

## 2. Requirements elicitation and analysis

### Objectives

- Find the real learning and teaching problems before deciding which features to build.
- Collect evidence from students and, if possible, an instructor, teaching assistant, or tutor.

### Stakeholders

| Stakeholder | What to learn |
| --- | --- |
| Non-CS student | Where technical learning becomes confusing or discouraging |
| CS student / job seeker | Which software-engineering or AI-era career skills need more practice |
| Instructor / teaching assistant | How interactive materials and learning progress are currently created and monitored |

### Interview prompts

- How do you currently learn an unfamiliar software-engineering topic?
- What part of that process is difficult, slow, or easy to give up on?
- What information would help you decide what to learn next?
- How do you currently create or find exercises and interactive learning content?
- If AI assisted you, which work would you delegate to it and which work would you still want to review yourself?
- What happens when a student has very different background knowledge from the rest of the class?

### Tasks

- [ ] Interview 3-5 students and, where possible, one instructor/TA.
- [ ] Record consent-appropriate notes, anonymous quotes, and observed pain points.
- [ ] Create 2-3 personas from the findings.
- [ ] Map each persona's current workflow, pain points, needs, and constraints.
- [ ] Convert findings into candidate functional and non-functional requirements.

### Outputs

- Interview guide and interview notes.
- Stakeholder map and personas.
- Pain-point list.
- Requirements list with source evidence.
- Initial desk research and internal assumption workshop: [REQUIREMENTS_DESK_RESEARCH.md](REQUIREMENTS_DESK_RESEARCH.md).
- Standalone competitor analysis with public visual evidence: [competitor_analysis/README.md](competitor_analysis/README.md).

### Exit criteria

- The team can state who has a problem, in what context, and why current approaches are insufficient.

---

## 3. Define the problem, MVP scope, and priorities

### Draft problem statement

> Students with different software-engineering backgrounds need suitable, interactive learning paths, while instructors need a faster way to create, refine, and monitor such learning activities.

### Example user stories

- As a student, I want to select my experience level and learning goal so that I receive an appropriate starting course.
- As a student, I want immediate explanations after an activity so that I understand why an answer is correct or incorrect.
- As an instructor, I want AI to produce an editable course draft so that I can prepare interactive material faster while retaining control of quality.
- As an instructor, I want to view completion and performance data so that I can identify learners and topics needing support.

### MoSCoW priority proposal

| Priority | Scope |
| --- | --- |
| **Must** | Role-based login, course catalogue, course player, MCQ, progress tracking, instructor course creation/editing/publishing, basic analytics, one AI course-draft feature |
| **Should** | Student onboarding and recommendations, CSV student import, scenario-based activity |
| **Could** | AI requirements-elicitation role-play, badges, learner-generated private study path |
| **Won't for this release** | Payments, live classes, social feed/forum, unrestricted AI tutor, complex recommendation algorithm |

### Tasks

- [ ] Review interview findings and revise the problem statement.
- [ ] Agree on the primary user and a single MVP journey.
- [ ] Finalise user stories and acceptance criteria.
- [ ] Confirm Must/Should/Could/Won't scope as a group.
- [ ] Turn every Must feature into a GitHub Issue.

### Exit criteria

- The group agrees on what will and will not be built for the final prototype.

---

## 4. Wireframes and prototypes

### Objectives

- Validate the main flows before investing in implementation.

### Required prototype flows

1. **Student flow:** onboarding -> recommended path -> lesson -> activity -> feedback -> updated progress.
2. **Instructor flow:** enter course requirements -> receive AI draft -> edit -> publish -> inspect learner data.

### Tasks

- [ ] Draw low-fidelity wireframes for all key pages.
- [ ] Create a clickable high-fidelity Figma prototype for the two flows.
- [ ] Define the page hierarchy, navigation, empty states, error states, and mobile layout.
- [ ] Write down the design rationale for important choices.

### Suggested key screens

- Landing/login page
- Student onboarding
- Student dashboard and course catalogue
- Course player and activity screen
- Feedback/progress screen
- Instructor dashboard
- AI course builder and course editor
- Instructor analytics dashboard
- Basic admin overview

### Exit criteria

- A test participant can complete each prototype flow without being guided by the team.

---

## 5. User feedback and iteration

### Objectives

- Use observed feedback to improve the design rather than relying only on the team's opinions.

### Tasks

- [ ] Prepare two short usability-test scripts, one for a student and one for an instructor.
- [ ] Ask participants to complete tasks without hints; observe where they hesitate or fail.
- [ ] Record feedback, completion result, observed issue, severity, and proposed change.
- [ ] Revise the prototype and keep before/after evidence.

### Feedback log template

| Feedback or observation | Underlying issue | Decision / change | Evidence |
| --- | --- | --- | --- |
| User cannot find the recommended course | Dashboard hierarchy is unclear | Move the next recommended lesson to the top of the dashboard | Prototype version A/B |

### Exit criteria

- The final design includes at least 2-3 traceable improvements from user feedback.

---

## 6. System design

### Recommended architecture

```text
Next.js frontend
    -> REST API
FastAPI backend
    -> PostgreSQL database
    -> JWT authentication and role-based access control
    -> AI generation / feedback service
    -> File storage service
```

### Recommended technology stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL |
| ORM / migrations | SQLAlchemy + Alembic, or SQLModel |
| Authentication | JWT + password hashing, or a managed auth provider with clear FastAPI integration |
| AI integration | Backend-only LLM API calls; validated structured JSON responses |
| Charts | Recharts or equivalent frontend chart library |
| Deployment | Vercel for frontend; Render/Railway or equivalent for FastAPI; managed PostgreSQL |

### Core data model

```text
profiles: user identity, role, background, learning goals
courses: course metadata, author, status
modules / lessons: course structure and learning content
activities / questions / options: learning interactions
enrollments: student-course membership and completion state
activity_attempts: submitted answers, score, feedback, timestamps
course_generations: AI request, generated draft, review/publication state
```

### Design tasks

- [ ] Create an architecture diagram.
- [ ] Create an ERD and database migration plan.
- [ ] Define API contracts and error responses.
- [ ] Create a role-permission matrix.
- [ ] Define AI input, output JSON schema, validation, retry, and human-review steps.
- [ ] Record environment variables and secret-management rules.

### Exit criteria

- Every screen and user action has an identified API, business owner, and database effect.

---

## 7. Development and integration

### Development rule

Build one working vertical slice before expanding the scope:

```text
Instructor creates and publishes a course
-> student joins it
-> student completes a lesson and MCQ
-> backend records progress
-> instructor sees analytics
```

### Five-person module ownership

| Member | Primary ownership | Supporting contribution |
| --- | --- | --- |
| Member A | Student portal: onboarding, dashboard, catalogue, path recommendation UI | Requirements research and UI/UX validation |
| Member B | Course player: lessons, MCQ, scenario activity, feedback, progress UI | Student-flow testing |
| Member C | Instructor portal: AI course builder UI, editor, publishing, CSV import | Instructor usability testing |
| Member D | FastAPI and data: Auth, RBAC, course/enrolment/attempt APIs, PostgreSQL | ERD, API documentation, analytics queries |
| Member E | AI and quality: generation endpoints, role-play/rubric feedback, JSON validation | Deployment, integration tests, release readiness |

### Shared responsibilities

- [ ] Each member implements a separately demonstrable feature and submits it through a pull request.
- [ ] Each member reviews at least one other member’s pull request.
- [ ] Each member documents tests for their feature.
- [ ] Each member contributes to user testing, the final report, and the presentation.
- [ ] Merge frequently; do not leave integration to the final week.

### Cross-cutting engineering requirements

These are not priority candidates — they have to be done for the system to work at all,
so they are tracked here rather than voted on.

- [ ] Database persistence and migrations.
- [ ] Login and role-based authorisation, enforced server-side (403 on cross-role access).
- [ ] Do not block the request for long-running generation (background job queue).
- [ ] Responsive layout: usable down to 320px wide, no horizontal scrolling.
- [ ] Keyboard operation and accessibility: every action reachable by keyboard, every image has alt text.
- [x] One failed asset or section must not fail the whole package.
- [x] API keys live only in backend environment variables.
- [x] Model usage (tokens, estimated cost) is observable.
- [x] Three-language interface (English, Traditional Chinese, Simplified Chinese).

### Exit criteria

- The full Must-feature user journey works in a shared deployed environment.

---

## 8. Testing and deployment

### Test checklist

- [ ] Authentication and role protection: students cannot access instructor/admin functions.
- [ ] Authorisation: instructors cannot edit another instructor's course.
- [ ] Course publishing, enrolment, activity attempts, scores, and progress persist correctly.
- [ ] Invalid AI output, timeout, and API failure show helpful user-facing errors.
- [ ] CSV import validates malformed data before saving.
- [ ] Main flows work on desktop and mobile sizes.
- [ ] A user can complete the agreed acceptance-test tasks.

### Deployment tasks

- [ ] Create separate development and production environment variables.
- [ ] Deploy frontend, backend, and database.
- [ ] Verify production APIs, authentication redirects, and CORS configuration.
- [ ] Add the public URL and setup steps to the README.
- [ ] Retest the complete vertical slice on the public deployment.

### Evidence to retain

- Test cases/results, bug reports, fixes, deployment URL, screenshots or recordings, and CI output if used.

---

## 9. Final video, report, slides, and reflection

### 5-8 minute system overview video

```text
Problem and target users
-> student demo
-> instructor demo
-> AI feature demo
-> analytics / architecture overview
```

### Presentation structure

1. User problem, stakeholder evidence, and product value.
2. Main features and a concise demo.
3. System architecture, database, APIs, and AI flow.
4. Prototype feedback and iteration evidence.
5. Development process, GitHub collaboration, team contribution, testing, and deployment.
6. Reflection and lessons learned.

### AI Fluency reflection: use concrete examples

| Competency | Project example |
| --- | --- |
| Delegation | Use AI to draft course structure, question ideas, test cases, or UI alternatives |
| Description | Specify learner type, learning objectives, duration, format, and constraints in generation prompts |
| Discernment | Require instructors to review AI drafts; validate output schema; identify inaccurate or unsuitable AI content |
| Diligence | Test AI failure cases, document prompts/decisions, preserve version history, and take accountability for published content |

### Final deliverables checklist

- [ ] Public deployment link.
- [ ] 5-8 minute overview video.
- [ ] Presentation slides.
- [ ] Final report: requirements, design, development, testing, deployment, collaboration, and reflection.
- [ ] User manual for Admin, Instructor, and Student.
- [ ] Demo-video links for major features.
- [ ] Supporting evidence: interviews, prototype iterations, tests, GitHub activity, and individual contributions.

---

## Milestone before the Week 8/9 project discussion

The group should aim to have the following ready before the project-progress meeting:

- A 1-2 page progress summary.
- Clear team division of work.
- Requirements evidence and the agreed MVP.
- Wireframes/clickable prototype and user-feedback findings.
- Architecture diagram, ERD, and initial API design.
- At least one working end-to-end vertical slice.

---

## Reference

Project requirements: [project_overivew.pdf](project_overivew.pdf)
