"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { Badge, Button, Card, ErrorBar, Field, SectionLabel, inputCls } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api, type CourseActivity, type CourseAnalytics, type CourseCoverage, type TeacherChapter, type TeacherCourse } from "@/lib/api";
import { chapterHref } from "@/lib/routes";

type Tab = "curriculum" | "students" | "insights" | "activity" | "settings";

const chapterTone = (status: TeacherChapter["status"]) =>
  status === "ready" ? "green" : status === "failed" ? "amber" : status === "generating" ? "blue" : "neutral";
const coverageTone = (status: CourseCoverage["outcomes"][number]["status"]) =>
  status === "covered" ? "green" : status === "missing" ? "amber" : "blue";

export default function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [course, setCourse] = useState<TeacherCourse | null>(null);
  const [chapters, setChapters] = useState<TeacherChapter[]>([]);
  const [tab, setTab] = useState<Tab>("curriculum");
  const [showAddChapter, setShowAddChapter] = useState(false);
  const [chapterTitle, setChapterTitle] = useState("");
  const [editingChapter, setEditingChapter] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [rosterText, setRosterText] = useState("");
  const [invite, setInvite] = useState("");
  const [analytics, setAnalytics] = useState<CourseAnalytics | null>(null);
  const [courseTitle, setCourseTitle] = useState("");
  const [description, setDescription] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [subject, setSubject] = useState("Software Engineering");
  const [objectivesText, setObjectivesText] = useState("");
  const [activity, setActivity] = useState<CourseActivity[]>([]);
  const [coverage, setCoverage] = useState<CourseCoverage | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const nextCourse = await api.course(courseId);
    const nextChapters = await Promise.all(nextCourse.chapterIds.map((id) => api.chapter(courseId, id)));
    setCourse(nextCourse);
    setChapters(nextChapters);
    setCourseTitle(nextCourse.title);
    setDescription(nextCourse.description);
    setCourseCode(nextCourse.courseCode);
    setSubject(nextCourse.subject);
    setObjectivesText(nextCourse.learningObjectives.map((objective) => objective.text).join("\n"));
    setCoverage(await api.coverage(courseId));
  }, [courseId]);
  const loadAnalytics = useCallback(async () => setAnalytics(await api.analytics(courseId)), [courseId]);
  const loadActivity = useCallback(async () => setActivity((await api.activity(courseId)).activity), [courseId]);

  useEffect(() => { void Promise.resolve().then(load).catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [load]);
  useEffect(() => { if (tab === "students" || tab === "insights") void Promise.resolve().then(loadAnalytics).catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [tab, loadAnalytics]);
  useEffect(() => { if (tab === "activity") void Promise.resolve().then(loadActivity).catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [tab, loadActivity]);

  const withBusy = async (action: () => Promise<void>) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };

  const addChapter = () => withBusy(async () => {
    if (!chapterTitle.trim()) return;
    await api.createChapter(courseId, { title: chapterTitle.trim() });
    setChapterTitle(""); setShowAddChapter(false); await load(); setNotice("Chapter created. It is a draft until you generate and review it.");
  });
  const saveChapterTitle = (chapter: TeacherChapter) => withBusy(async () => {
    if (!draftTitle.trim()) return;
    await api.updateChapter(courseId, chapter.id, { title: draftTitle.trim() });
    setEditingChapter(null); await load();
  });
  const removeChapter = (chapter: TeacherChapter) => withBusy(async () => {
    if (!window.confirm(`Delete "${chapter.title}"? This cannot be undone.`)) return;
    await api.deleteChapter(courseId, chapter.id); await load(); setNotice("Chapter deleted.");
  });
  const moveChapter = (index: number, direction: -1 | 1) => withBusy(async () => {
    const next = [...chapters];
    const target = index + direction;
    if (!next[target]) return;
    [next[index], next[target]] = [next[target], next[index]];
    await api.reorderChapters(courseId, next.map((chapter) => chapter.id));
    await load();
  });
  const importRoster = () => withBusy(async () => {
    const rows = rosterText.split("\n").map((line, index) => {
      const [name = "", email = ""] = line.split(",");
      return { row: index + 1, name: name.trim(), email: email.trim() };
    }).filter((row) => row.name || row.email);
    if (!rows.length) { setError("Add one learner per line as Name, email@example.com."); return; }
    const result = await api.importStudents(courseId, rows);
    setRosterText(""); await loadAnalytics();
    setNotice(result.errors.length ? `${result.imported} learners imported; ${result.errors.length} row(s) need attention.` : `${result.imported} learners imported.`);
  });
  const createInvite = () => withBusy(async () => {
    const result = await api.createInvite(courseId);
    setInvite(result.code); setNotice("Invite code created. Share it with learners for this local prototype.");
  });
  const saveCourse = () => withBusy(async () => {
    const updated = await api.updateCourse(courseId, {
      title: courseTitle.trim(), description, courseCode, subject,
      learningObjectives: objectivesText.split("\n").map((text, index) => ({ id: `LO${index + 1}`, text: text.trim() })).filter((objective) => objective.text),
    });
    setCourse(updated); setNotice("Course details saved.");
  });
  const togglePublish = () => withBusy(async () => {
    if (!course) return;
    const updated = course.status === "published" ? await api.unpublishCourse(courseId) : await api.publishCourse(courseId);
    setCourse(updated); setNotice(updated.status === "published" ? "Course published. Learners can now access reviewed content." : "Course returned to draft.");
  });

  const ready = chapters.filter((chapter) => chapter.status === "ready").length;
  const preparationSummary = ready > 0 && ready === chapters.length
    ? `All ${chapters.length} ${chapters.length === 1 ? "chapter is" : "chapters are"} ready. Review the course before publishing.`
    : ready > 0
      ? `${ready} of ${chapters.length} chapters are ready. Build the remaining chapters before publishing.`
      : "Build and review a chapter first. AI drafts stay private until you publish.";
  const publishDisabled = busy || (course?.status !== "published" && ready === 0);
  const tabs: { value: Tab; label: string }[] = [
    { value: "curriculum", label: "Curriculum" },
    { value: "students", label: "Students" },
    { value: "insights", label: "Insights" },
    { value: "activity", label: "Review trail" },
    { value: "settings", label: "Settings" },
  ];

  if (!course) return <main className="min-h-screen bg-canvas"><div className="mx-auto max-w-[1280px] px-5 pt-5 sm:px-8"><TeacherNavigation active={null} />{error ? <ErrorBar message={error} onDismiss={() => setError("")} /> : <p className="py-12 text-sm text-muted">Opening course…</p>}</div></main>;
  return <main className="course-detail min-h-screen bg-canvas">
    <div className="mx-auto w-full max-w-[1440px] px-5 pb-20 pt-4 sm:px-8">
      <TeacherNavigation active={null} />
      <header className="course-header">
        <div className="course-header__main">
          <div className="course-heading"><h1>{course.title}</h1><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status === "published" ? "Published" : "Draft"}</Badge></div>
          {course.description && course.description.trim().toLowerCase() !== "short course" ? <p className="course-summary">{course.description}</p> : null}
          <div className="course-meta"><span>{course.courseCode || course.subject}</span><span>{course.audience}</span><span>{course.durationMin} min</span>{course.description?.trim().toLowerCase() === "short course" ? <span>{course.description.trim()}</span> : null}</div>
        </div>
      </header>
      {error ? <div className="mt-5"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
      {notice ? <p role="status" className="mt-5 rounded-sm border border-green/30 bg-green-soft px-4 py-3 text-sm text-green">{notice}</p> : null}
      <div className="course-workspace">
        <nav className="course-menu" aria-label="Course sections">
          {tabs.map((item) => <button key={item.value} type="button" onClick={() => setTab(item.value)} aria-current={tab === item.value ? "page" : undefined} className={tab === item.value ? "course-menu__item is-active" : "course-menu__item"}>{item.label}</button>)}
          <div className="course-menu__progress"><strong>{ready} / {chapters.length}</strong><span>chapters ready</span></div>
        </nav>
        <div className="course-content">
      {tab !== "curriculum" ? <div className="course-section-head course-secondary-head"><div><h2>{tabs.find((item) => item.value === tab)?.label}</h2><p>{tab === "students" ? "Manage enrollment and invite learners to this course." : tab === "insights" ? "See where learners need more support." : tab === "activity" ? "Trace what the model proposed and what you approved." : "Update the course brief and learning outcomes."}</p></div></div> : null}
      {tab === "curriculum" ? <div className="course-curriculum">
        <section className="course-outline">
          <div className="course-section-head"><div><div className="course-outline__heading"><h2>Course outline</h2><span className="course-outline__count">{chapters.length} {chapters.length === 1 ? "chapter" : "chapters"}</span></div><p>Arrange your chapters. Open one to build or refine its materials.</p></div><Button variant="primary" onClick={() => setShowAddChapter((value) => !value)} aria-expanded={showAddChapter}>{showAddChapter ? "Close" : "Add chapter"}</Button></div>
          {showAddChapter ? <div className="course-add"><Field label="New chapter title"><input autoFocus className={inputCls} value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void addChapter(); }} placeholder="e.g. Reviewing pull requests" /></Field><Button variant="primary" disabled={busy || !chapterTitle.trim()} onClick={addChapter}>Create chapter</Button></div> : null}
          <ol className="chapter-sequence">
            {chapters.map((chapter, index) => {
              const slides = chapter.package?.slideDeck?.slides ?? [];
              const summary = chapter.summary || slides[0]?.title || (chapter.package
                ? "Teaching materials available to review and edit."
                : "Add a teaching brief to build this chapter.");
              const status = chapter.status === "empty" ? "Not started"
                : chapter.status.charAt(0).toUpperCase() + chapter.status.slice(1);
              return <li key={chapter.id} className="chapter-entry">
                <span className="chapter-entry__index" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <div className="chapter-entry__body">
                  <div className="chapter-entry__top">
                    <div className="min-w-0">
                      {editingChapter === chapter.id ? <div className="chapter-entry__rename">
                        <input autoFocus aria-label="Chapter name" className={inputCls} value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void saveChapterTitle(chapter); }} />
                        <Button onClick={() => saveChapterTitle(chapter)} disabled={busy || !draftTitle.trim()}>Save</Button>
                        <Button variant="quiet" onClick={() => setEditingChapter(null)}>Cancel</Button>
                      </div> : <><h3>{chapter.title}</h3><p>{summary}</p></>}
                    </div>
                  </div>
                  <div className="chapter-entry__foot">
                    <div className="chapter-entry__facts"><Badge tone={chapterTone(chapter.status)}>{status}</Badge><span>{slides.length ? `${slides.length} ${slides.length === 1 ? "slide" : "slides"}` : chapter.package ? "Materials available" : "No materials yet"}</span></div>
                    <div className="chapter-entry__actions">
                      <details className="chapter-actions">
                        <summary aria-label={`Manage ${chapter.title}`}>Manage</summary>
                        <div className="chapter-actions__menu">
                          <button type="button" onClick={() => { setEditingChapter(chapter.id); setDraftTitle(chapter.title); }}>Rename</button>
                          <button type="button" disabled={busy || index === 0} onClick={() => moveChapter(index, -1)}>Move up</button>
                          <button type="button" disabled={busy || index === chapters.length - 1} onClick={() => moveChapter(index, 1)}>Move down</button>
                          <button type="button" disabled={busy || chapters.length === 1} onClick={() => removeChapter(chapter)}>Delete</button>
                        </div>
                      </details>
                      <Link href={chapterHref(courseId, chapter.id)} className="chapter-entry__open" aria-label={`${chapter.package ? "Open" : "Build"} ${chapter.title}`}>{chapter.package ? "Open chapter" : "Build chapter"}</Link>
                    </div>
                  </div>
                </div>
              </li>;
            })}
          </ol>
          {!chapters.length ? <div className="course-outline__empty"><h3>Start with your first chapter</h3><p>Add a chapter, then create its teaching materials in the editor.</p></div> : null}
        </section>
        <aside className="course-context" aria-label="Course information">
          <details className="course-info">
            <summary><span>Publication</span><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status === "published" ? "Published" : "Draft"}</Badge></summary>
            <div className="course-info__body"><p>{preparationSummary}</p><button type="button" onClick={() => setTab("settings")}>Publication settings</button></div>
          </details>
          <details className="course-info">
            <summary><span>Learning outcomes</span><span className="course-info__value">{coverage?.outcomes.length || "Not set"}</span></summary>
            <div className="course-info__body">{coverage?.outcomes.length ? <ul>{coverage.outcomes.map((outcome) => <li key={outcome.id}><span>{outcome.text}</span><Badge tone={coverageTone(outcome.status)}>{outcome.status.replace("-", " ")}</Badge></li>)}</ul> : <><p>Add outcomes to check slide and question coverage.</p><button type="button" onClick={() => setTab("settings")}>Add learning outcomes</button></>}</div>
          </details>
          {course.syllabusFilename ? <details className="course-info">
            <summary><span>Syllabus</span><span className="course-info__value" title={course.syllabusFilename}>{course.syllabusFilename}</span></summary>
            <div className="course-info__body"><p className="break-words">{course.syllabusFilename}</p><p>Available as source material when generating chapters.</p></div>
          </details> : null}
        </aside>
      </div> : null}

      {tab === "students" ? <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course roster</SectionLabel><p className="mt-2 text-sm text-muted">Imported learners appear here before they begin. Progress is shown once student attempts are recorded.</p><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="border-b border-line text-xs text-muted"><tr><th className="pb-3">Learner</th><th className="pb-3">Email</th><th className="pb-3">Progress</th><th className="pb-3">Score</th></tr></thead><tbody>{analytics?.students.map((student) => <tr className="border-b border-line" key={student.id}><td className="py-3 font-semibold text-ink">{student.studentName}</td><td className="py-3 text-body">{student.email}</td><td className="py-3 text-body">{student.completionPercent}%</td><td className="py-3 text-body">{student.score}%</td></tr>)}{!analytics?.students.length ? <tr><td colSpan={4} className="py-8 text-center text-muted">No learners yet. Import a small roster or create an invite code.</td></tr> : null}</tbody></table></div></Card><aside className="space-y-5"><Card className="p-5"><SectionLabel>Import learners</SectionLabel><p className="mt-2 text-sm text-muted">One learner per line: <code>Name, email@example.com</code></p><textarea className={`${inputCls} mt-4 min-h-[130px]`} value={rosterText} onChange={(e) => setRosterText(e.target.value)} placeholder={"Ada Lovelace, ada@example.com\nGrace Hopper, grace@example.com"} /><Button variant="primary" className="mt-3 w-full" disabled={busy} onClick={importRoster}>Import roster</Button></Card><Card className="p-5"><SectionLabel>Invite learners</SectionLabel><p className="mt-2 text-sm text-muted">Create a compact course invite code for this local demo.</p><Button className="mt-4 w-full" disabled={busy} onClick={createInvite}>Create invite code</Button>{invite ? <p className="mt-3 break-all rounded-sm bg-soft px-3 py-2 font-mono text-sm text-ink">{invite}</p> : null}</Card></aside></div> : null}

      {tab === "insights" ? <div className="mt-7 grid gap-5 lg:grid-cols-[1fr_1fr]"><Card className="p-6"><SectionLabel>Learning snapshot</SectionLabel><div className="mt-5 grid grid-cols-2 gap-4"><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">AVERAGE SCORE</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.averageScore ?? 0}%</p></div><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">LEARNERS</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.enrolledCount ?? 0}</p></div></div><p className="mt-5 text-sm leading-6 text-muted">This view stays intentionally small: use it to decide which chapter or question needs your attention, rather than collecting vanity metrics.</p></Card><Card className="p-6"><SectionLabel>Most-missed questions</SectionLabel>{analytics?.mostMissed.length ? <ol className="mt-5 space-y-3">{analytics.mostMissed.map((item) => <li key={item.questionId} className="flex items-center justify-between border-b border-line pb-3 text-sm"><span className="font-medium text-ink">{item.questionId}</span><Badge tone="amber">{item.wrongCount} wrong</Badge></li>)}</ol> : <p className="mt-5 text-sm leading-6 text-muted">No submitted attempts yet. Once learners answer generated questions, common misconceptions appear here.</p>}</Card></div> : null}

      {tab === "activity" ? <div className="mt-7 grid gap-5 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Review trail</SectionLabel><p className="mt-2 text-sm leading-6 text-muted">A compact evidence trail of AI generation, instructor changes and publication decisions. It supports review; it does not silently publish AI output.</p><ol className="mt-5 space-y-3">{activity.map((item) => <li key={item.id} className="rounded-sm border border-line p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold text-ink">{item.reason}</p><Badge tone={item.kind === "publish" ? "green" : item.kind === "generation" ? "blue" : "neutral"}>{item.kind.replace("-", " ")}</Badge></div><p className="mt-2 text-sm text-muted">Changed: {item.changedFields.map((field) => field.replaceAll("_", " ")).join(", ") || "recorded event"}{item.chapterId ? " · chapter-owned" : " · course-level"}</p></li>)}{!activity.length ? <li className="rounded-sm bg-soft p-5 text-sm leading-6 text-muted">No review events yet. Generate a chapter, save the blueprint or publish a reviewed course to begin this record.</li> : null}</ol></Card><Card className="p-5"><SectionLabel>Demo evidence</SectionLabel><p className="mt-3 text-sm leading-6 text-muted">Use this screen during usability sessions to distinguish what the model drafted from what the teacher reviewed and published. Record real sessions separately; this prototype must not invent user evidence.</p></Card></div> : null}

      {tab === "settings" ? <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course details</SectionLabel><div className="mt-5 grid gap-4"><Field label="Course title"><input className={inputCls} value={courseTitle} onChange={(e) => setCourseTitle(e.target.value)} /></Field><div className="grid gap-4 sm:grid-cols-[150px_1fr]"><Field label="Course code"><input className={inputCls} value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="e.g. SE-101" /></Field><Field label="Subject"><select className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)}><option>Software Engineering</option><option>Computing Foundations</option><option>AI &amp; Data</option><option>Professional Development</option></select></Field></div><Field label="Course description"><textarea className={`${inputCls} min-h-[110px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What will learners be able to do?" /></Field><Field label="Learning outcomes" hint="One outcome per line"><textarea className={`${inputCls} min-h-[130px]`} value={objectivesText} onChange={(e) => setObjectivesText(e.target.value)} placeholder={"Explain branch isolation\nReview a pull request before merging"} /></Field></div><Button variant="primary" className="mt-5" disabled={busy || !courseTitle.trim()} onClick={saveCourse}>Save blueprint</Button></Card><Card className="p-5"><SectionLabel>Publication check</SectionLabel><p className="mt-3 text-sm leading-6 text-muted">A course can publish only after at least one chapter is ready. Generated material remains a draft until you explicitly publish it.</p><p className="mt-4 text-sm font-semibold text-ink">{ready} of {chapters.length} chapters ready</p><Button variant={course?.status === "published" ? "ghost" : "primary"} className="mt-4 w-full" disabled={publishDisabled} onClick={togglePublish}>{course?.status === "published" ? "Unpublish course" : "Publish reviewed course"}</Button></Card></div> : null}
        </div>
      </div>
    </div>
  </main>;
}
