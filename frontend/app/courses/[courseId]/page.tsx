"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Badge, Button, Card, ErrorBar, Field, SectionLabel, Segmented, inputCls } from "@/components/ui";
import { api, type CourseAnalytics, type TeacherChapter, type TeacherCourse } from "@/lib/api";

type Tab = "curriculum" | "students" | "insights" | "settings";

const chapterTone = (status: TeacherChapter["status"]) =>
  status === "ready" ? "green" : status === "failed" ? "amber" : status === "generating" ? "blue" : "neutral";

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
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const load = async () => {
    const nextCourse = await api.course(courseId);
    const nextChapters = await Promise.all(nextCourse.chapterIds.map((id) => api.chapter(courseId, id)));
    setCourse(nextCourse);
    setChapters(nextChapters);
    setCourseTitle(nextCourse.title);
    setDescription(nextCourse.description);
  };
  const loadAnalytics = async () => setAnalytics(await api.analytics(courseId));

  useEffect(() => { void load().catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [courseId]);
  useEffect(() => { if (tab === "students" || tab === "insights") void loadAnalytics().catch((e) => setError(e instanceof Error ? e.message : String(e))); }, [tab]);

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
    const updated = await api.updateCourse(courseId, { title: courseTitle.trim(), description });
    setCourse(updated); setNotice("Course details saved.");
  });
  const togglePublish = () => withBusy(async () => {
    if (!course) return;
    const updated = course.status === "published" ? await api.unpublishCourse(courseId) : await api.publishCourse(courseId);
    setCourse(updated); setNotice(updated.status === "published" ? "Course published. Learners can now access reviewed content." : "Course returned to draft.");
  });

  const ready = chapters.filter((chapter) => chapter.status === "ready").length;
  return <main className="min-h-screen bg-soft/40">
    <div className="mx-auto w-full max-w-[1280px] px-6 py-8">
      <button type="button" onClick={() => router.push("/courses")} className="text-sm font-semibold text-blue">← Course catalogue</button>
      {course ? <header className="mt-5 rounded-md bg-ink px-7 py-8 text-white">
        <SectionLabel className="text-[#a9c2ff]">Teacher course studio</SectionLabel>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-5"><div><div className="flex items-center gap-3"><h1 className="text-[38px] font-bold tracking-[-0.05em]">{course.title}</h1><Badge tone={course.status === "published" ? "green" : "amber"}>{course.status}</Badge></div><p className="mt-2 text-[15px] text-[#c4d0e5]">{course.audience} · {course.durationMin} min · {chapters.length} chapters</p></div><Button variant="primary" onClick={togglePublish} disabled={busy}>{course.status === "published" ? "Unpublish course" : "Publish reviewed course"}</Button></div>
      </header> : null}
      {error ? <div className="mt-5"><ErrorBar message={error} onDismiss={() => setError("")} /></div> : null}
      {notice ? <p className="mt-5 rounded-sm border border-green/30 bg-green-soft p-3 text-sm text-green">{notice}</p> : null}

      <div className="mt-6 grid gap-4 sm:grid-cols-3"><Card className="p-4"><p className="text-xs font-semibold text-muted">CHAPTERS</p><p className="mt-1 text-2xl font-bold text-ink">{chapters.length}</p></Card><Card className="p-4"><p className="text-xs font-semibold text-muted">READY TO REVIEW</p><p className="mt-1 text-2xl font-bold text-ink">{ready}</p></Card><Card className="p-4"><p className="text-xs font-semibold text-muted">ENROLLED LEARNERS</p><p className="mt-1 text-2xl font-bold text-ink">{analytics?.enrolledCount ?? "—"}</p></Card></div>
      <Segmented className="mt-6 max-w-[620px]" label="Course workspace" value={tab} onChange={setTab} options={[{ value: "curriculum", label: "Curriculum" }, { value: "students", label: "Students" }, { value: "insights", label: "Insights" }, { value: "settings", label: "Settings" }]} />

      {tab === "curriculum" ? <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><section><Card className="p-6"><SectionLabel>Course chapters</SectionLabel><p className="mt-2 text-sm text-muted">Arrange your teaching sequence, then open one chapter to generate, edit, preview and review its materials.</p><div className="mt-5 space-y-3">
        {chapters.map((chapter, index) => <Card key={chapter.id} className="flex flex-wrap items-center gap-4 border-line p-5"><span className="grid h-9 w-9 place-items-center rounded-full bg-blue-soft font-mono text-sm font-bold text-blue">{String(index + 1).padStart(2, "0")}</span><div className="min-w-[190px] flex-1">{editingChapter === chapter.id ? <div className="flex gap-2"><input autoFocus className={inputCls} value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} /><Button onClick={() => saveChapterTitle(chapter)} disabled={busy}>Save</Button><Button variant="quiet" onClick={() => setEditingChapter(null)}>Cancel</Button></div> : <><p className="font-bold text-ink">{chapter.title}</p><p className="mt-1 text-sm text-muted">{chapter.package?.slideDeck?.slides?.length ?? 0} slides · {chapter.summary || "No chapter summary yet"}</p></>}</div><Badge tone={chapterTone(chapter.status)}>{chapter.status}</Badge><div className="flex gap-1"><Button variant="quiet" aria-label="Move chapter up" disabled={busy || index === 0} onClick={() => moveChapter(index, -1)}>↑</Button><Button variant="quiet" aria-label="Move chapter down" disabled={busy || index === chapters.length - 1} onClick={() => moveChapter(index, 1)}>↓</Button></div><Button variant="quiet" onClick={() => { setEditingChapter(chapter.id); setDraftTitle(chapter.title); }}>Rename</Button><Button onClick={() => openStudio(chapter)}>{chapter.package ? "Open studio" : "Build chapter"}</Button><Button variant="quiet" disabled={busy || chapters.length === 1} onClick={() => removeChapter(chapter)}>Delete</Button></Card>)}
      </div></Card></section><aside className="space-y-5"><Card className="p-5"><SectionLabel>Create a chapter</SectionLabel><p className="mt-2 text-sm leading-6 text-muted">Chapter 0 is a normal editable starting draft. Add, rename, reorder or remove chapters as you shape the course.</p><div className="mt-4"><Field label="Chapter title"><input className={inputCls} value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)} placeholder="e.g. Pull request review" /></Field></div><Button variant="primary" className="mt-4 w-full" onClick={addChapter} disabled={busy || !chapterTitle.trim()}>Create chapter</Button></Card>{course?.syllabusFilename ? <Card className="p-5"><SectionLabel>Course reference</SectionLabel><p className="mt-3 font-semibold text-ink">{course.syllabusFilename}</p><p className="mt-1 text-sm leading-6 text-muted">{course.syllabusChars ?? 0} characters extracted · used as reference when generating every chapter.</p></Card> : null}</aside></div> : null}

      {tab === "students" ? <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course roster</SectionLabel><p className="mt-2 text-sm text-muted">Imported learners appear here before they begin. Progress is shown once student attempts are recorded.</p><div className="mt-5 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="border-b border-line text-xs text-muted"><tr><th className="pb-3">Learner</th><th className="pb-3">Email</th><th className="pb-3">Progress</th><th className="pb-3">Score</th></tr></thead><tbody>{analytics?.students.map((student) => <tr className="border-b border-line" key={student.id}><td className="py-3 font-semibold text-ink">{student.studentName}</td><td className="py-3 text-body">{student.email}</td><td className="py-3 text-body">{student.completionPercent}%</td><td className="py-3 text-body">{student.score}%</td></tr>)}{!analytics?.students.length ? <tr><td colSpan={4} className="py-8 text-center text-muted">No learners yet. Import a small roster or create an invite code.</td></tr> : null}</tbody></table></div></Card><aside className="space-y-5"><Card className="p-5"><SectionLabel>Import learners</SectionLabel><p className="mt-2 text-sm text-muted">One learner per line: <code>Name, email@example.com</code></p><textarea className={`${inputCls} mt-4 min-h-[130px]`} value={rosterText} onChange={(e) => setRosterText(e.target.value)} placeholder={"Ada Lovelace, ada@example.com\nGrace Hopper, grace@example.com"} /><Button variant="primary" className="mt-3 w-full" disabled={busy} onClick={importRoster}>Import roster</Button></Card><Card className="p-5"><SectionLabel>Invite learners</SectionLabel><p className="mt-2 text-sm text-muted">Create a compact course invite code for this local demo.</p><Button className="mt-4 w-full" disabled={busy} onClick={createInvite}>Create invite code</Button>{invite ? <p className="mt-3 break-all rounded-sm bg-soft px-3 py-2 font-mono text-sm text-ink">{invite}</p> : null}</Card></aside></div> : null}

      {tab === "insights" ? <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1fr]"><Card className="p-6"><SectionLabel>Learning snapshot</SectionLabel><div className="mt-5 grid grid-cols-2 gap-4"><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">AVERAGE SCORE</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.averageScore ?? 0}%</p></div><div className="rounded-sm bg-soft p-4"><p className="text-xs font-semibold text-muted">LEARNERS</p><p className="mt-1 text-3xl font-bold text-ink">{analytics?.enrolledCount ?? 0}</p></div></div><p className="mt-5 text-sm leading-6 text-muted">This view stays intentionally small: use it to decide which chapter or question needs your attention, rather than collecting vanity metrics.</p></Card><Card className="p-6"><SectionLabel>Most-missed questions</SectionLabel>{analytics?.mostMissed.length ? <ol className="mt-5 space-y-3">{analytics.mostMissed.map((item) => <li key={item.questionId} className="flex items-center justify-between border-b border-line pb-3 text-sm"><span className="font-medium text-ink">{item.questionId}</span><Badge tone="amber">{item.wrongCount} wrong</Badge></li>)}</ol> : <p className="mt-5 text-sm leading-6 text-muted">No submitted attempts yet. Once learners answer generated questions, common misconceptions appear here.</p>}</Card></div> : null}

      {tab === "settings" ? <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_330px]"><Card className="p-6"><SectionLabel>Course details</SectionLabel><div className="mt-5 grid gap-4"><Field label="Course title"><input className={inputCls} value={courseTitle} onChange={(e) => setCourseTitle(e.target.value)} /></Field><Field label="Course description"><textarea className={`${inputCls} min-h-[110px]`} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What will learners be able to do?" /></Field></div><Button variant="primary" className="mt-5" disabled={busy || !courseTitle.trim()} onClick={saveCourse}>Save details</Button></Card><Card className="p-5"><SectionLabel>Publication check</SectionLabel><p className="mt-3 text-sm leading-6 text-muted">A course can publish only after at least one chapter is ready. Generated material remains a draft until you explicitly publish it.</p><p className="mt-4 text-sm font-semibold text-ink">{ready} of {chapters.length} chapters ready</p><Button variant={course?.status === "published" ? "ghost" : "primary"} className="mt-4 w-full" disabled={busy} onClick={togglePublish}>{course?.status === "published" ? "Unpublish course" : "Publish reviewed course"}</Button></Card></div> : null}
    </div>
  </main>;
}
