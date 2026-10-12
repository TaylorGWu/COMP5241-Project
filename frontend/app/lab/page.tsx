"use client";

/**
 * L1 / L2 测试台。
 *
 * 这个页面的唯一目的是**让你在浏览器里点着验证产品流程**:
 *   ① 填表单 → 生成(看六阶段进度、材料报告、产出的课件与教案)
 *   ② 说一句话 → 看 agent 提议的改动(diff + 理由)
 *   ③ 确认或驳回 → 看产物到底变没变
 *
 * 它连的是 `/api/demo/*`(内存版,无认证、无数据库)。
 */

import { useState } from "react";

import {
  api,
  type CoursePackage,
  type GenerateResponse,
  type MaterialReport,
  type Outline,
  type Patch,
  type ProgressEvent,
  type Slide,
  type TimelineEntry,
} from "@/lib/api";

// ── 小工具组件 ────────────────────────────────────────────────

function Card({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <header className="mb-4">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {hint && <p className="mt-1 text-sm text-zinc-500">{hint}</p>}
      </header>
      {children}
    </section>
  );
}

function Badge({ children, tone = "zinc" }: { children: React.ReactNode; tone?: string }) {
  const tones: Record<string, string> = {
    zinc: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
    amber: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    red: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
    blue: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone] ?? tones.zinc}`}>
      {children}
    </span>
  );
}

function ProgressBar({ events }: { events: ProgressEvent[] }) {
  const percent = events.length ? events[events.length - 1].percent : 0;
  return (
    <div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      <ol className="mt-3 max-h-56 space-y-1 overflow-auto font-mono text-xs">
        {events.map((e, i) => (
          <li key={i} className="flex gap-2">
            <span className="w-12 shrink-0 text-right text-zinc-400">{e.percent}%</span>
            <span className="w-24 shrink-0 font-semibold">{e.phase}</span>
            <span className="text-zinc-600 dark:text-zinc-400">{e.detail}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

const MATERIAL_TONE: Record<MaterialReport["status"], string> = {
  ok: "green",
  degraded: "amber",
  failed: "red",
};

function MaterialTable({ materials }: { materials: MaterialReport[] }) {
  if (!materials.length) return <p className="text-sm text-zinc-500">没上传材料。</p>;
  return (
    <ul className="space-y-2">
      {materials.map((m) => (
        <li key={m.filename} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={MATERIAL_TONE[m.status]}>{m.status}</Badge>
            <span className="font-medium">{m.filename}</span>
            <span className="text-xs text-zinc-500">
              {m.detected_form} · {m.pages} 页 · 抽到 {m.extracted_chars} 字
              {m.ocr_used ? " · 已 OCR" : ""}
            </span>
          </div>
          {m.message && <p className="mt-1 text-xs text-zinc-500">{m.message}</p>}
        </li>
      ))}
    </ul>
  );
}

function OutlineView({ outline }: { outline: Outline }) {
  return (
    <div className="space-y-2">
      {outline.usedFallback && <Badge tone="amber">退回了兜底骨架</Badge>}
      <ul className="space-y-1 text-sm">
        {outline.sections.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span className="w-6 text-zinc-400">{i + 1}.</span>
            <span className="font-medium">{s.title}</span>
            <span className="text-zinc-500">{s.minutes} 分钟</span>
            <span className="text-xs text-zinc-400">{s.objectiveIds.join(", ")}</span>
          </li>
        ))}
      </ul>
      {outline.rationale && (
        <p className="text-xs text-zinc-500">理由:{outline.rationale}</p>
      )}
    </div>
  );
}

function SlideList({
  pkg,
  editingId,
  busy,
  onStartEdit,
  onSave,
  onCancel,
}: {
  pkg: CoursePackage;
  editingId: string | null;
  busy: boolean;
  onStartEdit: (id: string) => void;
  onSave: (id: string, payload: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const slides = pkg.slideDeck?.slides ?? [];
  if (!slides.length) return <p className="text-sm text-zinc-500">还没有课件。</p>;

  return (
    <ul className="space-y-3">
      {slides.map((s) =>
        editingId === s.id ? (
          <li key={s.id}>
            <SlideEditor
              slide={s}
              busy={busy}
              onCancel={onCancel}
              onSave={(payload) => onSave(s.id, payload)}
            />
          </li>
        ) : (
          <li
            key={s.id}
            className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-zinc-400">{s.id}</span>
              <span className="font-medium">{s.title}</span>
              <Badge>{s.layout}</Badge>
              <Badge tone={s.origin === "sourced" ? "blue" : "amber"}>
                {s.origin === "sourced" ? "有来源" : "AI 补充"}
              </Badge>
              <button
                onClick={() => onStartEdit(s.id)}
                className="ml-auto rounded border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                编辑
              </button>
            </div>
            <ul className="mt-2 list-disc pl-5 text-sm text-zinc-600 dark:text-zinc-400">
              {s.bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            {s.speakerNotes && (
              <p className="mt-2 text-xs italic text-zinc-500">讲稿:{s.speakerNotes}</p>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-zinc-500">
              {s.sourceRefs.map((r, i) => (
                <span key={i} className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">
                  来源 {r.materialId} p.{r.page}
                </span>
              ))}
              {s.visuals.map((v) => (
                <span key={v.id} className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">
                  {v.kind} → {v.assetId ?? "未生成"}
                </span>
              ))}
            </div>
          </li>
        ),
      )}
    </ul>
  );
}


function TimelineEditor({
  entry,
  busy,
  onSave,
  onCancel,
}: {
  entry: TimelineEntry;
  busy: boolean;
  onSave: (payload: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [phase, setPhase] = useState(entry.phase);
  const [minutes, setMinutes] = useState(String(entry.minutes));
  const [teacherAction, setTeacherAction] = useState(entry.teacherAction);
  const [studentAction, setStudentAction] = useState(entry.studentAction);
  const [check, setCheck] = useState(entry.checkUnderstanding);

  return (
    <div className="rounded-lg border border-blue-300 bg-blue-50/40 p-3 dark:border-blue-800 dark:bg-blue-950/20">
      <div className="grid gap-2 sm:grid-cols-2">
        <Field label="环节名称" value={phase} onChange={setPhase} />
        <Field label="时长(分钟)" value={minutes} onChange={setMinutes} />
        <Field label="教师做什么" value={teacherAction} onChange={setTeacherAction} multiline />
        <Field label="学生做什么" value={studentAction} onChange={setStudentAction} multiline />
      </div>
      <div className="mt-2">
        <Field
          label="怎么确认学生听懂了"
          value={check}
          onChange={setCheck}
          multiline
        />
      </div>
      <EditActions
        busy={busy}
        onCancel={onCancel}
        onSave={() =>
          onSave({
            phase,
            minutes: Number(minutes),
            teacherAction,
            studentAction,
            checkUnderstanding: check,
          })
        }
      />
    </div>
  );
}


function LessonPlanView({
  pkg,
  editingId,
  busy,
  onStartEdit,
  onSave,
  onCancel,
}: {
  pkg: CoursePackage;
  editingId: string | null;
  busy: boolean;
  onStartEdit: (id: string) => void;
  onSave: (id: string, payload: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const timeline = pkg.lessonPlan?.timeline ?? [];
  if (!timeline.length) return <p className="text-sm text-zinc-500">还没有教案。</p>;

  return (
    <div className="space-y-2">
      <table className="w-full text-left text-sm">
        <thead className="text-xs uppercase text-zinc-500">
          <tr>
            <th className="py-2 pr-3">环节</th>
            <th className="py-2 pr-3">时长</th>
            <th className="py-2 pr-3">教师做什么</th>
            <th className="py-2 pr-3">对应页</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {timeline.map((t) => (
            <tr key={t.id} className="border-t border-zinc-100 dark:border-zinc-800">
              <td className="py-2 pr-3 font-medium">{t.phase}</td>
              <td className="py-2 pr-3 text-zinc-500">{t.minutes} 分</td>
              <td className="py-2 pr-3 text-zinc-600 dark:text-zinc-400">
                {t.teacherAction}
              </td>
              <td className="py-2 pr-3 font-mono text-xs text-zinc-500">
                {t.slideIds.join(", ")}
              </td>
              <td className="py-2">
                <button
                  onClick={() => onStartEdit(t.id)}
                  className="rounded border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
                >
                  编辑
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {editingId &&
        (() => {
          const entry = timeline.find((t) => t.id === editingId);
          return entry ? (
            <TimelineEditor
              entry={entry}
              busy={busy}
              onCancel={onCancel}
              onSave={(payload) => onSave(entry.id, payload)}
            />
          ) : null;
        })()}
    </div>
  );
}


/** 一个字段的编辑控件。select 用下拉,列表用多行文本。 */
function Field({
  label,
  value,
  onChange,
  options,
  multiline,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options?: string[];
  multiline?: boolean;
}) {
  const cls =
    "mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-950";
  return (
    <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400">
      {label}
      {options ? (
        <select value={value} onChange={(e) => onChange(e.target.value)} className={cls}>
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : multiline ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          className={cls}
        />
      ) : (
        <input value={value} onChange={(e) => onChange(e.target.value)} className={cls} />
      )}
    </label>
  );
}

/** 保存 / 取消 两个按钮。 */
function EditActions({
  busy,
  onSave,
  onCancel,
}: {
  busy: boolean;
  onSave: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mt-3 flex gap-2">
      <button
        onClick={onSave}
        disabled={busy}
        className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
      >
        保存
      </button>
      <button
        onClick={onCancel}
        disabled={busy}
        className="rounded border border-zinc-300 px-3 py-1 text-xs hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
      >
        取消
      </button>
      <span className="self-center text-xs text-zinc-400">
        保存后仍会留下一条改动记录,可回退
      </span>
    </div>
  );
}

const LAYOUTS = ["title", "bullets", "diagram", "twoCol", "code", "quiz"];

const linesToArray = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);
const arrayToLines = (a: string[]) => a.join("\n");

function SlideEditor({
  slide,
  busy,
  onSave,
  onCancel,
}: {
  slide: Slide;
  busy: boolean;
  onSave: (payload: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(slide.title);
  const [layout, setLayout] = useState(slide.layout);
  const [bullets, setBullets] = useState(arrayToLines(slide.bullets));
  const [notes, setNotes] = useState(slide.speakerNotes);

  return (
    <div className="rounded-lg border border-blue-300 bg-blue-50/40 p-3 dark:border-blue-800 dark:bg-blue-950/20">
      <div className="space-y-2">
        <Field label="标题" value={title} onChange={setTitle} />
        <Field label="版面" value={layout} onChange={setLayout} options={LAYOUTS} />
        <Field
          label="要点(一行一条)"
          value={bullets}
          onChange={setBullets}
          multiline
        />
        <Field label="讲稿" value={notes} onChange={setNotes} multiline />
      </div>
      <EditActions
        busy={busy}
        onCancel={onCancel}
        onSave={() =>
          onSave({
            title,
            layout,
            bullets: linesToArray(bullets),
            speakerNotes: notes,
          })
        }
      />
    </div>
  );
}


function PatchCard({
  patch,
  busy,
  onApply,
  onReject,
}: {
  patch: Patch;
  busy: boolean;
  onApply: () => void;
  onReject: () => void;
}) {
  const statusTone =
    patch.status === "applied" ? "green" : patch.status === "rejected" ? "red" : "amber";
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-zinc-400">{patch.id}</span>
        <Badge tone={statusTone}>{patch.status}</Badge>
        <Badge tone={patch.author === "teacher" ? "blue" : "zinc"}>
          {patch.author === "teacher" ? "教师手改" : "AI 提议"}
        </Badge>
        <span className="text-sm">
          {patch.kind} → <span className="font-mono">{patch.target_id}</span>
        </span>
      </div>
      <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">理由:{patch.reason}</p>
      <pre className="mt-2 overflow-x-auto rounded bg-zinc-50 p-2 font-mono text-xs dark:bg-zinc-950">
        {patch.diff}
      </pre>
      {patch.status === "proposed" && (
        <div className="mt-2 flex gap-2">
          <button
            onClick={onApply}
            disabled={busy}
            className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            确认应用
          </button>
          <button
            onClick={onReject}
            disabled={busy}
            className="rounded border border-zinc-300 px-3 py-1 text-xs font-medium hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            驳回
          </button>
        </div>
      )}
    </div>
  );
}

// ── 主页面 ────────────────────────────────────────────────────

export default function Home() {
  const [topic, setTopic] = useState("Git 分支管理");
  const [audience, setAudience] = useState("非计算机专业初学者");
  const [duration, setDuration] = useState(45);
  const [objectives, setObjectives] = useState("解释分支与主干的关系\n完成一次安全的合并");
  const [materialText, setMaterialText] = useState(
    "# Git 讲义\n\n分支让不同人的改动互相隔离,主干始终保持可用。\n合并之前先确认改动可审查。\n",
  );
  const [useReal, setUseReal] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [gen, setGen] = useState<GenerateResponse | null>(null);
  const [pkg, setPkg] = useState<CoursePackage | null>(null);
  const [patches, setPatches] = useState<Patch[]>([]);
  const [editMessage, setEditMessage] = useState("第 2 页太难了,给非 CS 背景的学生降一档。");
  const [reply, setReply] = useState("");
  const [lastCallNames, setLastCallNames] = useState<string[]>([]);
  /** 提议阶段的产物快照 —— 用来在页面上证明「产物没变」。 */
  const [snapshotAtProposal, setSnapshotAtProposal] = useState("");
  const [unchangedAfterProposal, setUnchangedAfterProposal] = useState<boolean | null>(null);
  /** 正在手动编辑的目标。格式 `${kind}:${id}`,null 表示没在编辑。 */
  const [editing, setEditing] = useState<string | null>(null);

  const payload = () => ({
    topic,
    audience,
    duration_min: duration,
    objectives: objectives.split("\n").map((s) => s.trim()).filter(Boolean),
    material_text: materialText,
    use_real_model: useReal,
    // 归档页固定用 zh-HK —— 它只做行为级验证,不参与语言切换。
    language: "zh-HK",
  });

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError("");
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  const onOutline = () =>
    run(async () => {
      const r = await api.outline(payload());
      setGen((g) => (g ? { ...g, outline: r.outline, model_mode: r.model_mode } : g));
      setEvents([
        {
          phase: "规划大纲",
          percent: 100,
          detail: r.outline.rationale,
          kind: "phase",
          sectionIndex: null,
          sectionTitle: null,
          slideCount: 0,
          tool: null,
          status: "",
        },
      ]);
    });

  const onGenerate = () =>
    run(async () => {
      const r = await api.generate(payload());
      setGen(r);
      setPkg(r.package);
      setEvents(r.events);
      setPatches([]);
      setReply("");
      setLastCallNames([]);
      setUnchangedAfterProposal(null);
    });

  const onEdit = () =>
    run(async () => {
      const before = JSON.stringify(pkg);
      const r = await api.edit(editMessage, useReal);
      setReply(r.reply);
      setLastCallNames(r.call_names);
      setPatches((old) => [...r.patches, ...old]);
      setSnapshotAtProposal(before);
      // ★ 关键:后端说「产物没变」,但这里自己再比对一次,不信口头承诺
      setUnchangedAfterProposal(before === JSON.stringify(r.package));
      setPkg(r.package);
    });

  const onApply = (id: string) =>
    run(async () => {
      const r = await api.apply(id);
      setPkg(r.package);
      setPatches((old) => old.map((p) => (p.id === id ? { ...p, status: "applied" } : p)));
      setUnchangedAfterProposal(null);
    });

  const onReject = (id: string) =>
    run(async () => {
      const r = await api.reject(id);
      setPkg(r.package);
      setPatches((old) => old.map((p) => (p.id === id ? { ...p, status: "rejected" } : p)));
    });

  /** 教师手动保存 —— 不走 AI。后端会生成一条 author="teacher" 的 patch 并立刻生效。 */
  const onManualSave = (kind: "slide" | "timeline", id: string, payload: Record<string, unknown>) =>
    run(async () => {
      const r = await api.manualEdit(kind, id, payload);
      setPkg(r.package);
      setPatches((old) => [r.patch, ...old]);   // 记录进历史,可审计
      setEditing(null);
    });

  const onReset = () =>
    run(async () => {
      await api.reset();
      setGen(null);
      setPkg(null);
      setPatches([]);
      setEvents([]);
      setReply("");
      setError("");
      setUnchangedAfterProposal(null);
      setEditing(null);
    });

  return (
    <main className="mx-auto max-w-5xl space-y-5 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">PathPilot · L1 / L2 测试台</h1>
          <p className="mt-1 text-sm text-zinc-500">
            连的是 <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-800">/api/demo/*</code>
            内存接口 —— 无认证、重启即丢,只用来验证流程。
          </p>
        </div>
        <div className="flex items-center gap-2">
          {gen?.model_mode && (
            <Badge tone={gen.model_mode === "deepseek" ? "green" : "zinc"}>
              模型:{gen.model_mode}
            </Badge>
          )}
          <button
            onClick={onReset}
            disabled={busy}
            className="rounded border border-zinc-300 px-3 py-1 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            重置
          </button>
        </div>
      </header>

      {error && (
        <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      {/* ── ① 生成表单 ─────────────────────────────────── */}
      <Card title="① 生成课程(L1)" hint="阶段 1 读材料 → 阶段 2 出大纲 → 阶段 3 分节生成 → 装配校验">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            课程主题
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="text-sm">
            学习者
            <input
              value={audience}
              onChange={(e) => setAudience(e.target.value)}
              className="mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="text-sm">
            课时(分钟)
            <input
              type="number"
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="text-sm">
            学习目标(一行一个)
            <textarea
              value={objectives}
              onChange={(e) => setObjectives(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
        </div>
        <label className="mt-3 block text-sm">
          讲义材料(直接贴文本;留空则不摄取)
          <textarea
            value={materialText}
            onChange={(e) => setMaterialText(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-zinc-300 px-2 py-1.5 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950"
          />
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={useReal} onChange={(e) => setUseReal(e.target.checked)} />
            用真实 DeepSeek(需先在 backend/env.yaml 配 key)
          </label>
          <div className="ml-auto flex gap-2">
            <button
              onClick={onOutline}
              disabled={busy}
              className="rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              只看大纲(快)
            </button>
            <button
              onClick={onGenerate}
              disabled={busy}
              className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busy ? "运行中…" : "生成"}
            </button>
          </div>
        </div>
      </Card>

      {/* ── 进度 ──────────────────────────────────────── */}
      {events.length > 0 && (
        <Card title="运行进度">
          <ProgressBar events={events} />
        </Card>
      )}

      {/* ── ② 材料报告 ────────────────────────────────── */}
      {gen && (
        <Card title="② 材料摄取报告" hint="阶段 1。抽到 0 字会被标为失败,不会静默成功。">
          <MaterialTable materials={gen.materials} />
        </Card>
      )}

      {/* ── 大纲 ──────────────────────────────────────── */}
      {gen?.outline && (
        <Card title="③ 章节大纲" hint="阶段 2。模型产出;失败会自动退回兜底骨架。">
          <OutlineView outline={gen.outline} />
        </Card>
      )}

      {/* ── ③ 产物 ────────────────────────────────────── */}
      {pkg && (
        <Card
          title="④ 产物"
          hint="同一份 IR 派生出课件与教案。想改哪一页/哪个环节直接点「编辑」—— 不用通过 AI。"
        >
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-3 text-zinc-500">
              <span>项目:{pkg.project.meta.title}</span>
              <span>受众:{pkg.project.meta.audience}</span>
              <span>课时:{pkg.project.meta.durationMin} 分钟</span>
              <span>资产:{pkg.assets.length} 个</span>
            </div>
            {gen && (
              <div>
                {gen.integrity_issues.length === 0 ? (
                  <Badge tone="green">§6.4 交叉引用校验通过</Badge>
                ) : (
                  <div className="space-y-1">
                    {gen.integrity_issues.map((issue, i) => (
                      <div key={i}>
                        <Badge tone="red">{issue}</Badge>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {gen?.agents?.length ? (
              <details className="text-xs">
                <summary className="cursor-pointer text-zinc-500">
                  每个 SectionAgent 的工具调用序列
                </summary>
                <ul className="mt-2 space-y-1 font-mono">
                  {gen.agents.map((a, i) => (
                    <li key={i}>
                      第 {i + 1} 节:{JSON.stringify(a.call_names)} · {a.turns} 轮 · {a.stopped_by}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold">课件</h3>
              <SlideList
                pkg={pkg}
                editingId={editing?.startsWith("slide:") ? editing.slice(6) : null}
                busy={busy}
                onStartEdit={(id) => setEditing(`slide:${id}`)}
                onSave={(id, payload) => onManualSave("slide", id, payload)}
                onCancel={() => setEditing(null)}
              />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold">教案</h3>
              <LessonPlanView
                pkg={pkg}
                editingId={editing?.startsWith("timeline:") ? editing.slice(9) : null}
                busy={busy}
                onStartEdit={(id) => setEditing(`timeline:${id}`)}
                onSave={(id, payload) => onManualSave("timeline", id, payload)}
                onCancel={() => setEditing(null)}
              />
            </div>
          </div>
        </Card>
      )}

      {/* ── ④ 编辑 ────────────────────────────────────── */}
      {pkg && (
        <Card
          title="⑤ 对话式修改(L2)"
          hint="agent 只提议,不直接改。产物必须经你确认才会变 —— 这是 NFR-04 的落点。"
        >
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={editMessage}
              onChange={(e) => setEditMessage(e.target.value)}
              placeholder="例如:第 2 页太难了,给非 CS 背景的学生降一档"
              className="flex-1 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
            <button
              onClick={onEdit}
              disabled={busy || !editMessage.trim()}
              className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              发送
            </button>
          </div>

          {lastCallNames.length > 0 && (
            <p className="mt-2 font-mono text-xs text-zinc-500">
              工具调用序列:{JSON.stringify(lastCallNames)}
            </p>
          )}
          {reply && <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">agent:{reply}</p>}

          {unchangedAfterProposal !== null && (
            <div className="mt-3">
              {unchangedAfterProposal ? (
                <Badge tone="green">
                  ✓ 提议阶段产物一字未变(前端自己比对过,不是听后端说的)
                </Badge>
              ) : (
                <Badge tone="red">✗ 提议阶段产物就被改了 —— 设计被破坏</Badge>
              )}
            </div>
          )}

          {patches.length > 0 && (
            <div className="mt-4 space-y-3">
              <h3 className="text-sm font-semibold">待确认的改动</h3>
              {patches.map((p) => (
                <PatchCard
                  key={p.id}
                  patch={p}
                  busy={busy}
                  onApply={() => onApply(p.id)}
                  onReject={() => onReject(p.id)}
                />
              ))}
            </div>
          )}
        </Card>
      )}

      <footer className="pb-6 pt-2 text-center text-xs text-zinc-400">
        正式接口(§13)需要认证、数据库与异步作业 —— 这套 demo 路由届时整份删掉。
      </footer>
    </main>
  );
}
