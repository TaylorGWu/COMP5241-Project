> 中文译本:[REQUIREMENTS_DESK_RESEARCH.zh.md](REQUIREMENTS_DESK_RESEARCH.zh.md)。英文原版为准,两份需保持同步。

# Requirements Desk Research and Internal Assumption Workshop

## Purpose and evidence boundary

This document is the first, internal stage of requirements elicitation for the COMP5241 group project.

It uses publicly available product documentation and a five-member stakeholder-role workshop to identify candidate needs and product opportunities. It **does not** report these assumptions as real user-interview findings. Any conclusion marked `Hypothesis` must later be tested through a prototype usability session with people outside the project group.

## Research question

> How might an AI-assisted mini-course platform help students learn software-engineering topics at an appropriate level while allowing instructors to create, refine, and monitor interactive learning activities efficiently?

---

## 1. Desk research: existing platforms

### Comparison summary

| Platform | Evidence from its public documentation | Useful idea to learn from | Deliberate project opportunity / boundary |
| --- | --- | --- | --- |
| GPTutor | Supports document chat, practice questions, simulations, quizzes, flashcards, progress review, course management, and member management. Its instructor workflow can generate tutorial drafts from materials, allow direct editing, and publish versioned tutorials while recording student sessions. | Treat AI output as a draft that an instructor edits before publishing; combine learning content with activities and progress data. | Do not try to copy a general-purpose platform. Focus on software-engineering mini-courses and make the instructor review step, learner pathway, and requirements-elicitation activity explicit. |
| Coursera | Publicly describes personalised browsing/homepages that help learners resume courses and receive recommendations based on their learning journey and goals. | A learner should see a clear "continue" or "next step", not merely a large course catalogue. | Use transparent, simple recommendation rules based on stated goal, background, and recent activity; do not claim to implement a sophisticated recommendation algorithm. |
| Teachnow AI | Publicly describes adaptive lesson paths, progress tracking, learner-created plans, and AI-supported learning across multiple subjects. | Goal-based paths can make a broad subject feel approachable. | Do not include voice tutoring or broad, unlimited subject coverage in the first release. Support a small set of curated software-engineering courses plus one controlled self-learning-path demonstration. |
| EvoClass | Publicly presents structured AI-literacy learning content that includes prompting, specialised agents, human-AI co-creation, and ethics. | AI-assisted learning should include responsible use and practical human-AI collaboration, not only tool operation. | Include an AI-coding-agent or requirements-elicitation mini-course with a clear learning outcome and reflective activity. |

### Sources

- [GPTutor user manual](https://gptutor.comp.polyu.edu.hk/user-guide)
- [GPTutor instructor tutorial workflow](https://gptutor.comp.polyu.edu.hk/user-guide/tutorials/instructors)
- [Coursera personalised learning features](https://blog.coursera.org/introducing-new-platform-innovations-as-demand-for-online-learning-grows/)
- [Teachnow AI](https://www.teachnow.ai/)
- [EvoClass](https://evoclass.ai/)

### Design implications from desk research

1. A large course catalogue alone does not guide a beginner. The student dashboard should present a visible **recommended next action**.
2. AI-generated course content should be a private, editable **draft**, not automatically published learning material.
3. Activities should provide explanation and an actionable next step, not only a score.
4. The platform needs a limited, distinct focus. The first release should cover software-engineering learning, rather than attempting a general LMS for every subject.
5. The team should implement one distinctive interactive activity rather than many shallow activity types.

---

## 2. Internal stakeholder-role workshop

### Purpose

Use five project members to challenge the team's assumptions before building. Each member temporarily represents one stakeholder perspective. This is an **internal design workshop**, not an external user interview.

### Role cards

| Workshop role | Scenario | Assumed pain point | Candidate need | Key question to challenge the assumption |
| --- | --- | --- | --- | --- |
| Non-CS beginner | Needs Git for a group assignment and has little technical vocabulary. | A long, uniform course feels intimidating; does not know where to start. | A short starting diagnostic and a clearly explained beginner path. | Is the real barrier terminology, lack of time, fear of making mistakes, or something else? |
| CS student / job seeker | Wants to prepare for AI-era software-development work. | Knows syntax but has limited practice with requirements, validation, collaboration, and coding agents. | Scenario-based practice with feedback on reasoning, not only factual quiz questions. | Would a student actually complete role-play activities, and what feedback would be useful? |
| Instructor | Needs to turn existing slides or notes into a short interactive lesson. | Creating questions, explanations, and separate versions of materials takes time. | AI-generated editable draft, preview, and controlled publication. | Which parts may AI draft safely, and which parts always require human review? |
| Teaching assistant | Helps students who are stuck and wants to identify common misunderstandings. | Difficult to know who is inactive or which concept is causing errors. | Completion, score, and common-mistake view by course/module/activity. | Which metrics change an intervention decision instead of producing unused charts? |
| Platform administrator / AI-quality sceptic | Is responsible for user access and reputational risk. | AI may produce inaccurate, unsafe, or unsuitable content; access may be misconfigured. | Roles, audit-friendly generation records, validation, human review, and safe error messages. | What must happen when AI output is malformed, unsupported, or factually doubtful? |

### 90-minute workshop agenda

1. **10 min - Review evidence boundary:** agree that every statement below is a hypothesis, not a proven user fact.
2. **15 min - Individual role preparation:** each member reads one role card and writes the top three needs, fears, and success criteria.
3. **20 min - Current-flow mapping:** each role explains how the task is completed without the proposed platform.
4. **20 min - Prototype critique:** each role walks through the planned student or instructor flow and identifies missing information, failure cases, and confusing decisions.
5. **15 min - Prioritisation:** score candidate features using Must / Should / Could / Won't.
6. **10 min - Decision log:** record what changed, why, owner, and evidence source.

### Workshop record template

| Assumption ID | Stakeholder role | Assumption | Evidence type | Decision | Follow-up validation |
| --- | --- | --- | --- | --- | --- |
| H-01 | Non-CS beginner | A goal-and-background onboarding flow improves the choice of first lesson. | Desk research + internal workshop | Include in prototype | Test task completion with an external student later |

---

## 3. Candidate hypotheses and requirements

### Hypotheses to test

| ID | Hypothesis | Candidate feature | Validation task |
| --- | --- | --- | --- |
| H-01 | Beginners need a clear starting point more than a large catalogue. | Onboarding plus a recommended next mini-course. | Ask a participant to find an appropriate first course without help. |
| H-02 | Students benefit more from explanation and a next step than from a score alone. | Feedback card with correct-answer explanation and recommended follow-up lesson. | Compare whether participants can state what to do after an incorrect answer. |
| H-03 | Instructors will use AI-generated content only if they can inspect and edit it before students see it. | AI draft -> edit -> preview -> publish workflow. | Ask an instructor/TA to create a course and identify trust concerns. |
| H-04 | Teachers need actionable participation information, not a dashboard full of vanity metrics. | Completion rate, most-missed question, and inactive-student list. | Ask an instructor which chart would change their next action. |
| H-05 | Requirements-elicitation practice becomes more engaging when students question a simulated stakeholder. | Controlled AI role-play with a rubric covering problem, current process, and exceptions. | Observe whether students can explain the feedback and improve a second attempt. |
| H-06 | AI course generation must be constrained to predictable structured output. | Server-validated JSON course draft with retry/error state. | Test malformed and incomplete AI responses. |

### Candidate functional requirements

| ID | Requirement | Priority | Acceptance signal |
| --- | --- | --- | --- |
| FR-01 | A student can create an account and access only student functions. | Must | Student cannot open instructor/admin routes or APIs. |
| FR-02 | A student can state background and goal, then receive a recommended starting course. | Should | The dashboard shows one next course and explains why it was recommended. |
| FR-03 | A student can complete a lesson and MCQ activity, then receive explanation and progress update. | Must | Attempt, score, and completion state persist after refresh. |
| FR-04 | An instructor can create, edit, preview, and publish a mini-course. | Must | Published content is visible to enrolled students; drafts are not. |
| FR-05 | An instructor can ask AI to generate a structured, editable course draft from topic, audience, outcomes, and duration. | Must | AI output is displayed as an editable draft; invalid output produces a recoverable error. |
| FR-06 | An instructor can view course completion, average score, and common incorrect answers. | Must | Dashboard statistics match stored enrolment and attempt records. |
| FR-07 | An instructor can add students using a small validated CSV import or invite code. | Should | Valid users are enrolled; invalid rows receive a clear error. |
| FR-08 | A student can complete one scenario-based requirements-elicitation activity and receive rubric-based feedback. | Could | Feedback identifies coverage of problem, current process, and exceptions. |

### Candidate non-functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| NFR-01 | The primary student and instructor flows are usable on desktop and mobile-sized screens. | Must |
| NFR-02 | Role-based authorisation is enforced by the backend, not only hidden in the frontend. | Must |
| NFR-03 | LLM API keys are stored only in backend environment variables. | Must |
| NFR-04 | AI-generated content is visibly labelled as a draft until instructor publication. | Must |
| NFR-05 | User-facing AI errors explain what happened and offer retry/edit options without exposing secrets. | Must |

---

## 4. Recommended MVP decision

### Build first

```text
Instructor creates/publishes a Git Basics mini-course
-> Student joins it
-> Student completes a lesson and MCQ
-> System stores progress and score
-> Instructor sees completion and common-mistake data
```

Then add the AI course-draft workflow. Add the scenario-based role-play only after this end-to-end slice is stable.

### Explicitly out of scope for MVP

- Real-time video classes or voice tutor.
- Payments, certificates, social feed, forum, and chat moderation.
- Full LMS compatibility or all-subject content coverage.
- An unrestricted general chatbot.
- A complex machine-learning recommendation system.

---

## 5. Next validation step

The internal workshop should create the initial prototype and its hypotheses. Before the final presentation, run short task-based prototype tests with at least 2-3 people outside the group where practical.

Suggested tasks:

1. "You are new to Git. Find a suitable starting course and complete its first question."
2. "You are an instructor. Generate a short course, inspect the AI draft, correct something, and publish it."

Record only what is needed: task completion, hesitation points, observed issue, participant quote (if consented), design change, and before/after prototype evidence.

---

## 6. Evidence status summary

| Evidence | Status | How it may be described in report/slides |
| --- | --- | --- |
| Public documentation of existing platforms | Available | "Desk research identified established patterns and competitor capabilities." |
| Five-member stakeholder-role workshop | Planned | "Internal assumption workshop used to define and critique initial hypotheses." |
| External usability test | Not yet completed | Do not claim it has been conducted until it is actually completed. |

