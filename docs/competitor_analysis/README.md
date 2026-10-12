> 中文译本:[README.zh.md](README.zh.md)。英文原版为准,两份需保持同步。

# Competitor Analysis: AI-Enabled Learning Platforms

**Research date:** 12 September 2026  
**Research method:** public product pages and public documentation; no account was created and no private course/student data was accessed.  
**Purpose:** identify established product patterns, avoid building a generic copy of an existing platform, and justify a focused MVP for the COMP5241 project.

> Evidence boundary: this is desk research, not a user study. It identifies design hypotheses and competitor capabilities; it does not prove that our target users have the same needs.

## 1. Executive conclusion

The market already contains broad platforms for AI tutoring, course creation, quizzes, simulations, gamification, and personalised recommendations. Rebuilding all of those features would make our project generic and unmanageable.

The proposed product should therefore focus on a narrower space:

> **A guided software-engineering learning platform where instructors create reviewed AI-assisted mini-courses and students practise real professional skills through adaptive activities - especially requirements elicitation and effective use of AI coding agents.**

Our differentiation is not "we also use AI." It is the combination of:

1. a transparent next-step recommendation for software-engineering learners;
2. instructor-controlled AI course creation, rather than automatic publishing; and
3. a structured requirements-elicitation role-play that assesses the quality of a learner's questions.

---

## 2. Research scope

| Platform | Why it was selected | Evidence inspected |
| --- | --- | --- |
| GPTutor | PolyU-associated AI learning platform named in the project brief; comparable student and instructor workflows. | Public homepage and official user/instructor documentation. |
| Coursera | Established example of goal-based content discovery and personalised recommendations. | Official product announcement describing the recommendation workflow. |
| Teachnow AI | Example of AI-supported paths, practice, progress, and teacher course creation. | Public documentation for learner and teacher journeys. |
| EvoClass | Example of structured AI-literacy learning content. | Public website content. |

### Research limitations

- We did not create accounts, upload materials, enrol in courses, or access private interfaces.
- A public product page describes intended capabilities; it is not independent proof of usability or learning effectiveness.
- Teachnow's public home page was region-limited when checked; its public documentation remained accessible. We use its documentation only for the published workflow, not for claims about live product behaviour in Hong Kong.
- Any stated product opportunity below must still be tested with a prototype.

---

## 3. Competitor evidence

### 3.1 GPTutor - broad AI course and activity toolkit

GPTutor publicly presents document chat, scenario simulation, AI question generation, quizzes, flashcards, course management, and student-progress review. Its instructor documentation describes a workflow in which an AI-generated tutorial draft can be edited, previewed, versioned, published, and reviewed through student sessions.

![GPTutor scenario-simulation product image](assets/gptutor-simulation.png)

*Figure 1. GPTutor's public scenario-simulation visual, captured from the platform's public feature page on 12 September 2026. Source: [GPTutor](https://gptutor.comp.polyu.edu.hk/).* 

![GPTutor question-generation product image](assets/gptutor-question-generation.png)

*Figure 2. GPTutor's public question-generation visual. Source: [GPTutor](https://gptutor.comp.polyu.edu.hk/).* 

![GPTutor flashcards product image](assets/gptutor-flashcards.png)

*Figure 3. GPTutor's public quizzes/flashcards visual. Source: [GPTutor](https://gptutor.comp.polyu.edu.hk/).* 

#### What we learn

- Interactive activities, not static content alone, are a normal expectation for an AI learning platform.
- AI-created learning material should remain editable before publication.
- Learning sessions and activity attempts can support instructors' follow-up decisions.

#### What we will not copy

GPTutor is deliberately broad. Our project will not attempt document chat, many unrelated activity types, a general asset library, or a full platform-scale course-management system.

#### Design decision for our MVP

Implement **one** carefully designed scenario activity: an AI stakeholder role-play for practising requirements elicitation. Pair it with an instructor review-and-publish flow and basic activity analytics.

Sources: [GPTutor user manual](https://gptutor.comp.polyu.edu.hk/user-guide), [GPTutor tutorial workflow](https://gptutor.comp.polyu.edu.hk/user-guide/tutorials/instructors).

---

### 3.2 Coursera - goal-led, explainable recommendation

Coursera's 2025 product announcement describes a flow in which learners complete a short career quiz, receive content recommendations and a top recommendation, and can inspect why a recommendation was made. The stated goal is to reduce uncertainty about which skills to learn next.

![Coursera career-based recommendation visual](assets/coursera-career-recommendation.png)

*Figure 4. Coursera's public career-based discovery visual, reproduced from its product announcement. Source: [Coursera Blog](https://blog.coursera.org/from-catalog-to-compass/).* 

#### What we learn

- An onboarding questionnaire can turn a large catalogue into a manageable first step.
- Recommendations should be explainable: a learner should know why a course or activity appears next.
- "Resume learning" and "top recommendation" are more actionable than showing many equally weighted choices.

#### What we will not copy

We will not create career-market data, support dozens of roles, or claim to use advanced recommendation machine learning.

#### Design decision for our MVP

Use three transparent inputs - **background**, **learning goal**, and **recent activity result** - to recommend the next mini-course or activity. Display a brief explanation such as: "Recommended because you selected beginner Git and missed the branching activity."

Source: [Coursera: From Catalog to Compass](https://blog.coursera.org/from-catalog-to-compass/).

---

### 3.3 Teachnow AI - organised learner and teacher journeys

Teachnow's public documentation separates learner journeys (starting a course, learning with its AI tutor, practice/quizzes, progress review, and interactive lessons) from teacher journeys (building a course with AI, preparing activities, assigning work, grading, and reporting). Its teacher documentation explicitly describes an AI-written course plan that is read before publication.

#### What we learn

- Student and instructor experience should be treated as separate, focused flows rather than one overloaded dashboard.
- A usable course lifecycle has meaningful stages: draft, review/edit, publish, learner activity, and progress review.
- Gamification and live teaching are possible extensions, not MVP necessities.

#### What we will not copy

No live classes, payments, parent accounts, learning-world game, certificates, or voice tutoring in the MVP.

#### Design decision for our MVP

Create only these lifecycle states:

```text
AI draft -> Instructor edit -> Preview -> Publish -> Student attempt -> Instructor analytics
```

Sources: [Teachnow documentation](https://www.teachnow.ai/docs), [Teachnow course-creation guide](https://www.teachnow.ai/docs/teach/create-a-course).

---

### 3.4 EvoClass - AI literacy as a learning outcome

EvoClass publicly presents a structured AI-literacy course covering AI fundamentals, GenAI/LLMs, agents, human-AI co-creation, and ethics.

#### What we learn

An AI-related learning platform should teach judgment and responsible human-AI collaboration, not only promote AI automation.

#### Design decision for our MVP

One sample course should be **Effective Use of AI Coding Agents**. It should require students to evaluate AI output and explain what they would verify, linking naturally to the course's AI Fluency framework.

Source: [EvoClass](https://evoclass.ai/).

---

## 4. Capability matrix and deliberate scope

Legend: `✓` = include in MVP; `△` = narrowed version or later iteration; `—` = out of scope.

| Capability | GPTutor | Coursera | Teachnow | Our project decision | Rationale |
| --- | --- | --- | --- | --- | --- |
| Course catalogue | ✓ | ✓ | ✓ | ✓ | Needed to enrol and learn mini-courses. |
| Goal/background onboarding | △ | ✓ | ✓ | ✓ | Needed for a clear starting point. |
| AI tutor / general chat | ✓ | ✓ | ✓ | — | Too broad, hard to validate, and not differentiated. |
| AI course generation | ✓ | △ | ✓ | ✓ | Keep instructor review before publishing. |
| AI question generation | ✓ | △ | △ | ✓ | Generate an editable question draft only. |
| Quizzes and instant feedback | ✓ | ✓ | ✓ | ✓ | Core interactive learning activity. |
| Scenario simulation / role-play | ✓ | △ | △ | ✓ | Make this the distinctive software-engineering activity. |
| Progress analytics | ✓ | ✓ | ✓ | ✓ | Keep metrics actionable and basic. |
| ML recommendation system | △ | ✓ | △ | — | Replace with transparent rules for MVP. |
| Voice/live classes/gamified world | △ | △ | ✓ | — | High implementation cost; weak fit with the focused problem. |

---

## 5. Derived product hypotheses

These are hypotheses for prototype testing, not verified findings.

| ID | Hypothesis | Prototype feature | Validation task |
| --- | --- | --- | --- |
| H-01 | Beginners need a clear first step more than a large list of courses. | Onboarding + one recommended mini-course. | Ask a participant to find a suitable first course unaided. |
| H-02 | Learners need explanation and next-action guidance after an incorrect answer. | Feedback card with explanation + next recommendation. | Ask the participant what they would do next after a wrong answer. |
| H-03 | Instructors will only trust AI-generated course content if they can edit and preview it first. | AI draft -> edit -> preview -> publish flow. | Ask an instructor/TA to create a course and state trust concerns. |
| H-04 | Completion rate, common mistakes, and inactivity are more actionable than many chart types. | Instructor analytics summary. | Ask which data point would change the instructor's next action. |
| H-05 | Simulated stakeholder conversations can practise requirements elicitation more meaningfully than MCQs alone. | Controlled AI role-play + question-quality rubric. | Compare a learner's first and revised questioning attempt. |

---

## 6. MVP decision traceability

| Research insight | Requirement / feature decision |
| --- | --- |
| Broad tools already offer generic chat, many activities, and document Q&A. | Do not build a general chatbot; specialise in software-engineering learning activities. |
| Instructor-oriented products rely on an AI draft that is reviewed before publication. | Implement Draft, Preview, and Published states; do not permit automatic AI publication. |
| Personalised platforms ask learners about goals and show a clear next action. | Add a short onboarding flow and an explainable next recommendation. |
| Simulations can make learning interactive. | Implement one requirements-elicitation role-play with a narrow rubric. |
| Teachers need to act on progress data. | Show completion rate, common wrong answer, and inactive learner list - not a complex analytics suite. |

---

## 7. Recommended next step

Use this research to create two clickable Figma flows:

1. **Student:** onboarding -> recommended Git/AI-coding-agent mini-course -> lesson -> MCQ or role-play -> feedback -> next step.
2. **Instructor:** describe course -> AI draft -> edit -> preview -> publish -> view completion/common mistakes.

After the team has an initial prototype, run short task-based sessions with 2-3 people outside the group. Update the hypothesis table with actual observations and design changes. Do not describe desk research or group role-play as external user feedback.
