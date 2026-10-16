"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Badge, Button, Card, ErrorBar, Field, SectionLabel, inputCls } from "@/components/ui";
import { TeacherNavigation } from "@/components/TeacherNavigation";
import { api, type CourseActivity, type CourseAnalytics, type CourseCoverage, type TeacherChapter, type TeacherCourse } from "@/lib/api";

type Tab = "curriculum" | "students" | "insights" | "activity" | "settings";

const chapterTone = (status: TeacherChapter["status"]) =>
  status === "ready" ? "green" : status === "failed" ? "amber" : status === "generating" ? "blue" : "neutral";
const coverageTone = (status: CourseCoverage["outcomes"][number]["status"]) =>
  status === "covered" ? "green" : status === "missing" ? "amber" : "blue";

export default function CourseDetailPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();
  const [course, setCourse] = useState<TeacherCourse | null>(null);
  const [chapters, setChapters] = useState<TeacherChapter[]>([]);
  const [tab, setTab] = useState<Tab>("curriculum");
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
    setChapterTitle(""); await load(); setNotice("Chapter created. It is a draft until you generate and review it.");
  });
  const saveChapterTitle = (chapter: TeacherChapter) => withBusy(async () => {
    if (!draftTitle.trim()) return;
    await api.updateChapter(courseId, chapter.id, { title: draftTitle.trim() });
    setEditingChapter(null); await load();
  });
  const removeChapter = (chapter: TeacherChapter) => withBusy(async () => {
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
  const openStudio = (chapter: TeacherChapter) => {
    window.localStorage.setItem("pathpilot.activeCourse", courseId);
    window.localStorage.setItem("pathpilot.activeChapter", chapter.id);
    router.push("/");
  };
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
  const publishDisabled = busy || (course?.status !== "published" && ready === 0);
  const tabs: { value: Tab; label: string }[] = [
    { value: "curriculum", label: "Curriculum" },
    { value: "students", label: "Students" },
    { value: "insights", label: "Insights" },
    { value: "activity", label: "Review trail" },
    { value: "settings", label: "Settings" },
  ];

  if (!course) return <main className="min-h-screen bg-canvas"><div className="mx-auto max-w-[1180px] px-5 pt-5 sm:px-8"><TeacherNavigation active="courses" />{error ? <ErrorBar message={error} onDismiss={() => setError("")} /> : <p className="py-12 text-sm text-muted">Opening course…</p>}</div></main>;
  return <main className="min-h-screen bg-canvas">
    <div className="mx-auto w-full max-w-[1180px] px-5 pb-20 pt-5 sm:px-8">
      <TeacherNavigation active="courses" />
      <header className="border-b border-line pb-8">
        <Link href="/courses" className="text-sm font-semibold text-blue hover:text-blue-deep">← Your courses</Link>
        <div className="mt-6 flex flex-wrap items-end justify-between gap-5">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue">Course workspace</p>
            <div className="mt-3 flex flex-wrap items-center gap-3"><h1 className="break-words text-[clamp(2.15rem,5vw,3.5rem)] font-semibold leading-[1.08] tracking-[-0.06em] text-ink">{course.title}</h1><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status === "published" ? "Published" : "Draft"}</Badge></div>
            <p className="mt-3 text-sm text-body">{course.courseCode || course.subject}<span className="mx-2 text-line">/</span>{course.audience}<span className="mx-2 text-line">/</span>{course.durationMin} min</p>
          </div>
          <div className="flex flex-col items-start gap-1 sm:items-end"><Button variant="primary" onClick={togglePublish} disabled={publishDisabled}>{course.status === "published" ? "Unpublish course" : "Publish course"}</Button>{publishDisabled && !busy ? <span className="text-xs text-muted">Prepare at least one chapter first.</span> : null}</div>
        </div>
      </header>
      {error ? <div className="mt-5"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
      {notice ? <p role="status" className="mt-5 rounded-sm border border-green/30 bg-green-soft px-4 py-3 text-sm text-green">{notice}</p> : null}

      <div className="grid grid-cols-2 border-b border-line py-6 sm:grid-cols-3">
        <div className="border-r border-line pr-4"><p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Chapters</p><p className="mt-1 text-2xl font-semibold text-ink">{chapters.length}</p></div>
        <div className="pl-5 sm:border-r sm:border-line"><p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Ready</p><p className="mt-1 text-2xl font-semibold text-ink">{ready}<span className="ml-1 text-sm font-normal text-muted">/ {chapters.length}</span></p></div>
        <div className="col-span-2 mt-5 border-t border-line pt-5 sm:col-span-1 sm:mt-0 sm:border-0 sm:pl-5 sm:pt-0"><p className="text-xs font-semibold uppercase tracking-[0.1em] text-muted">Learners</p><p className="mt-1 text-2xl font-semibold text-ink">{analytics?.enrolledCount ?? "—"}</p></div>
      </div>
      <nav className="mt-5 flex flex-wrap gap-x-7 gap-y-1 border-b border-line" aria-label="Course sections">
        {tabs.map((item) => <button key={item.value} type="button" onClick={() => setTab(item.value)} aria-current={tab === item.value ? "page" : undefined} className={tab === item.value ? "min-h-11 border-b-2 border-blue text-sm font-semibold text-ink" : "min-h-11 border-b-2 border-transparent text-sm font-medium text-body transition-colors hover:text-ink"}>{item.label}</button>)}
      </nav>

      {tab === "curriculum" ? <div className="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="min-w-0 space-y-9">
          <section>
            <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.15em] text-blue">Teaching sequence</p><h2 className="mt-2 text-[25px] font-semibold tracking-[-0.045em] text-ink">Chapters</h2></div><span className="text-sm text-muted">{chapters.length} in this course</span></div>
            <p className="mt-2 text-sm leading-6 text-body">Open a chapter to generate, edit and review its slides, questions and teaching materials.</p>
            <div className="mt-5 overflow-hidden rounded-md border border-line bg-surface">
              {chapters.map((chapter, index) => <div key={chapter.id} className="grid gap-4 border-b border-line p-5 last:border-b-0 sm:grid-cols-[36px_minmax(0,1fr)] sm:gap-5 sm:p-6">
                <span className="font-mono text-sm font-semibold text-blue">{String(index + 1).padStart(2, "0")}</span>
                <div className="min-w-0">
                  {editingChapter === chapter.id ? <div className="flex flex-wrap gap-2"><input autoFocus aria-label="Chapter name" className={inputCls + " min-w-[180px] flex-1"} value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} /><Button onClick={() => saveChapterTitle(chapter)} disabled={busy || !draftTitle.trim()}>Save</Button><Button variant="quiet" onClick={() => setEditingChapter(null)}>Cancel</Button></div> : <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="break-words text-lg font-semibold tracking-[-0.025em] text-ink">{chapter.title}</h3><p className="mt-1 line-clamp-2 text-sm text-body">{chapter.summary || "No material generated yet"}</p></div><Badge tone={chapterTone(chapter.status)}>{chapter.status}</Badge></div>}
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"><span className="text-xs text-muted">{chapter.package?.slideDeck?.slides?.length ?? 0} slides</span><div className="flex flex-wrap items-center gap-1"><Button variant="quiet" aria-label={"Move " + chapter.title + " up"} disabled={busy || index === 0} onClick={() => moveChapter(index, -1)}>↑</Button><Button variant="quiet" aria-label={"Move " + chapter.title + " down"} disabled={busy || index === chapters.length - 1} onClick={() => moveChapter(index, 1)}>↓</Button><Button variant="quiet" onClick={() => { setEditingChapter(chapter.id); setDraftTitle(chapter.title); }}>Rename</Button><Button variant="quiet" disabled={busy || chapters.length === 1} onClick={() => removeChapter(chapter)}>Delete</Button><Button onClick={() => openStudio(chapter)}>{chapter.package ? "Open studio →" : "Build chapter →"}</Button></div></div>
                </div>
              </div>)}
            </div>
          </section>
          <section className="border-t border-line pt-8">
            <h2 className="text-xl font-semibold tracking-[-0.035em] text-ink">Learning outcomes</h2>
            <p className="mt-2 text-sm leading-6 text-body">{course.description || "Add a course purpose in Settings to explain what this course promises learners."}</p>
            {coverage?.outcomes.length ? <div className="mt-5 overflow-hidden rounded-md border border-line bg-surface">{coverage.outcomes.map((outcome) => <div key={outcome.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4 last:border-b-0"><div className="flex min-w-0 gap-3"><span className="font-mono text-xs font-semibold text-blue">{outcome.id}</span><p className="text-sm font-medium text-ink">{outcome.text}</p></div><div className="flex items-center gap-2"><span className="text-xs text-muted">{outcome.slideCount} slides · {outcome.questionCount} questions</span><Badge tone={coverageTone(outcome.status)}>{outcome.status.replace("-", " ")}</Badge></div></div>)}</div> : <p className="mt-5 rounded-sm bg-soft px-5 py-4 text-sm text-body">No outcomes yet. Add them in Settings to check coverage across slides and questions.</p>}
          </section>
        </div>
        <aside className="space-y-7 lg:sticky lg:top-7">
          <section className="rounded-md border border-line bg-surface p-5"><p className="text-xs font-bold uppercase tracking-[0.15em] text-blue">Next chapter</p><h2 className="mt-2 text-lg font-semibold text-ink">Add to this course</h2><p className="mt-2 text-sm leading-6 text-body">Create a chapter now. You can rename and reorder it later.</p><div className="mt-5"><Field label="Chapter title"><input className={inputCls} value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)} placeholder="e.g. Pull request review" /></Field></div><Button variant="primary" className="mt-4 w-full" onClick={addChapter} disabled={busy || !chapterTitle.trim()}>Add chapter</Button></section>
          <section className="border-l-2 border-blue pl-5"><p className="text-xs font-bold uppercase tracking-[0.15em] text-blue">Publication check</p><p className="mt-3 text-sm leading-6 text-body">{ready ? ready + " chapter" + (ready === 1 ? " is" : "s are") + " ready. Review generated material before publishing." : "Build and review at least one chapter before publishing."}</p></section>
          {course.syllabusFilename ? <section className="border-t border-line pt-5"><p className="text-xs font-bold uppercase tracking-[0.15em] text-muted">Course reference</p><p className="mt-2 break-words text-sm font-semibold text-ink">{course.syllabusFilename}</p><p className="mt-1 text-xs leading-5 text-muted">{course.syllabusChars ?? 0} characters extracted for chapter generation.</p></section> : null}
        </aside>
      </div> : null}

      {tab === "students" ? <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course roster</SectionLabel><p className="mt-2 text-sm text-muted">Imported learners appear here before they begin. Progress is shown once student attempts are recorded.</p><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="border-b border-line text-xs text-muted"><tr><th className="pb-3">Learner</th><th className="pb-3">Email</th><th className="pb-3">Progress</th><th className="pb-3">Score</th></tr></thead><tbody>{analytics?.students.map((student) => <tr className="border-b border-line" key={student.id}><td className="py-3 font-semibold text-ink">{student.studentName}</td><td className="py-3 text-body">{student.email}</td><td className="py-3 text-body">{student.completionPercent}%</td><td className="py-3 text-body">{student.score}%</td></tr>)}{!analytics?.students.length ? <tr><td colSpan={4} className="py-8 text-center text-muted">No learners yet. Import a small roster or create an invite code.</td></tr> : null}</tbody></table></div></Card><aside className="space-y-5"><Card className="p-5"><SectionLabel>Import learners</SectionLabel><p className="mt-2 text-sm text-muted">One learner per line: <code>Name, email@example.com</code></p><textarea className={`${inputCls} mt-4 min-h-[130px]`} value={rosterText} onChange={(e) => setRosterText(e.target.value)} placeholder={"Ada Lovelace, ada@example.com\nGrace Hopper, grace@example.com"} /><Button variant="primary" className="mt-3 w-full" disabled={busy} onClick={importRoster}>Import roster</Button></Card><Card className="p-5"><SectionLabel>Invite learners</SectionLabel><p className="mt-2 text-sm text-muted">Create a compact course invite code for this local demo.</p><Button className="mt-4 w-full" disabled={busy} onClick={createInvite}>Create invite code</Button>{invite ? <p className="mt-3 break-all rounded-sm bg-soft px-3 py-2 font-mono text-sm text-ink">{invite}</p> : null}</Card></aside></div> : null}

      {tab === "insights" ? <div className="mt-7 grid gap-5 lg:grid-cols-[1fr_1fr]"><Card className="p-6"><SectionLabel>Learning snapshot</SectionLabel><div className="mt-5 grid grid-cols-2 gap-4"><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">AVERAGE SCORE</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.averageScore ?? 0}%</p></div><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">LEARNERS</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.enrolledCount ?? 0}</p></div></div><p className="mt-5 text-sm leading-6 text-muted">This view stays intentionally small: use it to decide which chapter or question needs your attention, rather than collecting vanity metrics.</p></Card><Card className="p-6"><SectionLabel>Most-missed questions</SectionLabel>{analytics?.mostMissed.length ? <ol className="mt-5 space-y-3">{analytics.mostMissed.map((item) => <li key={item.questionId} className="flex items-center justify-between border-b border-line pb-3 text-sm"><span className="font-medium text-ink">{item.questionId}</span><Badge tone="amber">{item.wrongCount} wrong</Badge></li>)}</ol> : <p className="mt-5 text-sm leading-6 text-muted">No submitted attempts yet. Once learners answer generated questions, common misconceptions appear here.</p>}</Card></div> : null}

      {tab === "activity" ? <div className="mt-7 grid gap-5 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Review trail</SectionLabel><p className="mt-2 text-sm leading-6 text-muted">A compact evidence trail of AI generation, instructor changes and publication decisions. It supports review; it does not silently publish AI output.</p><ol className="mt-5 space-y-3">{activity.map((item) => <li key={item.id} className="rounded-sm border border-line p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold text-ink">{item.reason}</p><Badge tone={item.kind === "publish" ? "green" : item.kind === "generation" ? "blue" : "neutral"}>{item.kind.replace("-", " ")}</Badge></div><p className="mt-2 text-sm text-muted">Changed: {item.changedFields.map((field) => field.replaceAll("_", " ")).join(", ") || "recorded event"}{item.chapterId ? " · chapter-owned" : " · course-level"}</p></li>)}{!activity.length ? <li className="rounded-sm bg-soft p-5 text-sm leading-6 text-muted">No review events yet. Generate a chapter, save the blueprint or publish a reviewed course to begin this record.</li> : null}</ol></Card><Card className="p-5"><SectionLabel>Demo evidence</SectionLabel><p className="mt-3 text-sm leading-6 text-muted">Use this screen during usability sessions to distinguish what the model drafted from what the teacher reviewed and published. Record real sessions separately; this prototype must not invent user evidence.</p></Card></div> : null}

      {tab === "settings" ? <div className="mt-7 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course details</SectionLabel><div className="mt-5 grid gap-4"><Field label="Course title"><input className={inputCls} value={courseTitle} onChange={(e) => setCourseTitle(e.target.value)} /></Field><div className="grid gap-4 sm:grid-cols-[150px_1fr]"><Field label="Course code"><input className={inputCls} value={courseCode} onChange={(e) => setCourseCode(e.target.value)} placeholder="e.g. SE-101" /></Field><Field label="Subject"><select className={inputCls} value={subject} onChange={(e) => setSubject(e.target.value)}><option>Software Engineering</option><option>Computing Foundations</option><option>AI &amp; Data</option><option>Professional Development</option></select></Field></div><Field label="Course description"><textarea className={`${inputCls} min-h-[110px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What will learners be able to do?" /></Field><Field label="Learning outcomes" hint="One outcome per line"><textarea className={`${inputCls} min-h-[130px]`} value={objectivesText} onChange={(e) => setObjectivesText(e.target.value)} placeholder={"Explain branch isolation\nReview a pull request before merging"} /></Field></div><Button variant="primary" className="mt-5" disabled={busy || !courseTitle.trim()} onClick={saveCourse}>Save blueprint</Button></Card><Card className="p-5"><SectionLabel>Publication check</SectionLabel><p className="mt-3 text-sm leading-6 text-muted">A course can publish only after at least one chapter is ready. Generated material remains a draft until you explicitly publish it.</p><p className="mt-4 text-sm font-semibold text-ink">{ready} of {chapters.length} chapters ready</p><Button variant={course?.status === "published" ? "ghost" : "primary"} className="mt-4 w-full" disabled={publishDisabled} onClick={togglePublish}>{course?.status === "published" ? "Unpublish course" : "Publish reviewed course"}</Button></Card></div> : null}
    </div>
  </main>;
}
