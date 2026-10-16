"use client";

/**
 * 教师工作台。
 *
 * 这个页面的单一职责是:**让教师审完一份 AI 起草的课程材料**。
 * 所以版式是一张审阅桌 ——
 *   左栏 「我在看什么」  课件/教案切换 + 导航(滚动时高亮当前页)
 *   中间 「材料本身」    真实的 16:9 幻灯片,或教案时间线
 *   右栏 「要我决定什么」待确认的改动、覆盖度缺口、与 agent 的对话
 *
 * 语言有两条独立的轴:
 *   界面语言  —— 头部切换,存在 cookie 里(见 lib/i18n.tsx)
 *   教材语言  —— 生成表单里选,决定模型写哪种语言的内容
 *
 * 它连的是 `/api/demo/*`(内存版,无认证、无数据库)。旧的行为级测试台移到 `/lab`。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { LessonPlan } from "@/components/LessonPlan";
import { ReviewMargin } from "@/components/ReviewMargin";
import { TeacherTools } from "@/components/TeacherTools";
import { SlideCanvas } from "@/components/SlideCanvas";
import {
  Badge,
  Button,
  Card,
  Dot,
  ErrorBar,
  Field,
  SectionLabel,
  Segmented,
  cx,
  inputCls,
} from "@/components/ui";
import {
  api,
  type CoursePackage,
  type EditProgressEvent,
  type GenerateResponse,
  type MaterialReport,
  type Patch,
  type ProgressEvent,
  type TeacherChapter,
  type TeacherCourse,
} from "@/lib/api";
import { LOCALES, LOCALE_LABELS, normalizeLocale, type Locale } from "@/lib/i18n-config";
import { useI18n } from "@/lib/i18n";

/** 后端六阶段。用区间判断当前在哪一段,而不是解析字符串。 */
const PHASE_RANGES = [
  { key: "materials", from: 0, to: 10 },
  { key: "outline", from: 10, to: 25 },
  { key: "sections", from: 25, to: 75 },
  { key: "visuals", from: 75, to: 85 },
  { key: "assets", from: 85, to: 95 },
  { key: "assembly", from: 95, to: 101 },
] as const;

const CONTENT_LANG_KEY = "pathpilot.contentLang";

/**
 * 生成完成后,控制台在 100% 上停留多久再切到工作台(毫秒)。
 * 原因是 React 的批处理会把最后一批进度帧和结果合成一次渲染(见 onResult)。
 */
const REVEAL_DELAY_MS = 700;

const DEFAULT_TOPIC = "Git for group projects";
const DEFAULT_AUDIENCE = "Second-year students with no version-control background";
const DEFAULT_OBJECTIVES =
  "Explain how a branch keeps one person's work separate\nReview a pull request before merging";
const DEFAULT_MATERIAL = `# Working with branches

A branch keeps one person's work separate from everyone else's, so the shared main line stays usable.

Before merging, read the change the way a reviewer would: what does it do, what could it break, and who needs to know?`;

// ── 页头 ──────────────────────────────────────────────────────

function AppHeader({
  title,
  modelMode,
  busy,
  onBackToCourses,
}: {
  title?: string;
  modelMode?: string;
  busy: boolean;
  onBackToCourses: () => void;
}) {
  const { t, locale, setLocale } = useI18n();

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
      <div className="mx-auto flex min-h-[64px] w-full max-w-[1600px] flex-wrap items-center gap-3 px-5 py-2 sm:px-8">
        <span className="flex items-center gap-2.5 text-[17px] font-bold tracking-[-0.04em] text-ink">
          <span className="flex size-8 items-center justify-center rounded-[9px] bg-ink text-[17px] font-black tracking-[-0.12em] text-white">P<span className="text-[#9bb9ff]">.</span></span>
          PathPilot
        </span>

        {title ? (
          <>
            <span className="text-muted" aria-hidden>
              /
            </span>
            <span className="truncate text-[15px] text-body">{title}</span>
          </>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <Segmented<Locale>
            value={locale}
            onChange={setLocale}
            label="Interface language"
            options={LOCALES.map((l) => ({
              value: l,
              label: LOCALE_LABELS[l].short,
              title: LOCALE_LABELS[l].native,
            }))}
          />

          {modelMode ? (
            <Badge tone={modelMode === "deepseek" ? "green" : "neutral"}>
              <Dot tone={modelMode === "deepseek" ? "green" : "neutral"} />
              {modelMode === "deepseek" ? t.app.liveModel : t.app.sampleModel}
            </Badge>
          ) : null}

          <Button className="px-3 text-[14px]" onClick={onBackToCourses} disabled={busy}>
            Your courses
          </Button>
        </div>
      </div>
    </header>
  );
}

// ── 生成中:实时控制台 ────────────────────────────────────────
//
// ═══════════════════════════════════════════════════════════════
// 这里是「结构化事件」真正兑现的地方
// ═══════════════════════════════════════════════════════════════
// 整个控制台是 `events` 的**纯函数** —— 没有任何额外的状态需要同步。
// 因为后端把分节、工具、页数、状态都放进了独立字段(§6.1.1),
// 前端不必去正则拆 `detail` 那句中文。
//
// 反面教材:如果事件只有一个 detail 字符串,这段代码就得写
// `/^(\d+)\/(\d+) 节:(.+?)\(工具调用/` 这种正则,而且后端改一次措辞
// 就静默失效 —— 不会有任何测试变红。

type SectionLane = {
  index: number;
  title: string;
  status: "queued" | "writing" | "written" | "failed";
  turn: number;
  tool: string | null;
  detail: string;
  pages: number;
};

/** 把事件流折叠成「每节现在到哪了」。 */
function deriveSections(events: ProgressEvent[]): SectionLane[] {
  const lanes = new Map<number, SectionLane>();

  const lane = (index: number, title: string | null): SectionLane => {
    let found = lanes.get(index);
    if (!found) {
      found = {
        index,
        title: title ?? "",
        status: "queued",
        turn: 0,
        tool: null,
        detail: "",
        pages: 0,
      };
      lanes.set(index, found);
    }
    if (title) found.title = title;
    return found;
  };

  for (const e of events) {
    if (e.sectionIndex === null || e.sectionIndex === undefined) continue;
    const l = lane(e.sectionIndex, e.sectionTitle);

    if (e.kind === "section") {
      if (e.status === "started") l.status = "writing";
      else if (e.status === "written") l.status = "written";
      else if (e.status === "failed") l.status = "failed";
      if (l.status === "writing") l.detail = e.detail;
    } else if (e.kind === "turn") {
      l.status = "writing";
      l.turn = Number(e.detail.replace(/\D/g, "")) || l.turn;
      // 清掉上一轮工具留下的摘要 —— 否则「第 3 轮」旁边还挂着「画示意图」,
      // 看起来像是这一轮正在画图
      l.detail = "";
    } else if (e.kind === "tool") {
      l.status = "writing";
      l.tool = e.tool;
      l.detail = e.detail;
    } else if (e.kind === "slide") {
      l.status = "written";
      l.pages += 1;
      l.detail = e.detail;
    }
  }

  return [...lanes.values()].sort((a, b) => a.index - b.index);
}

/** 把事件流折叠成「最近写出的几页」。 */
function derivePages(events: ProgressEvent[]): string[] {
  const titles: string[] = [];
  for (const e of events) {
    if (e.kind !== "slide") continue;
    // 「「概念导入」写了 1 页:概念导入」→ 冒号后面才是页标题
    const after = e.detail.split(":").slice(1).join(":").trim();
    if (after) titles.push(...after.split("/").map((s) => s.trim()).filter(Boolean));
  }
  return titles;
}

const LANE_TONE = {
  queued: "neutral",
  writing: "blue",
  written: "green",
  failed: "amber",
} as const;

function GenerationConsole({
  events,
  elapsed,
  busy,
  onCancel,
}: {
  events: ProgressEvent[];
  elapsed: number;
  busy: boolean;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const current = events.at(-1);
  const percent = current?.percent ?? 0;
  const sections = useMemo(() => deriveSections(events), [events]);
  const pages = useMemo(() => derivePages(events), [events]);
  const slideCount = current?.slideCount ?? 0;

  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel>{t.progress.title}</SectionLabel>
        {busy ? (
          <Badge tone="blue">
            <Dot tone="blue" />
            {t.progress.live}
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[12px] text-muted">
          {t.progress.elapsed(elapsed)}
        </span>
        {busy ? (
          <Button className="min-h-0 px-3 py-1 text-[13px]" onClick={onCancel}>
            {t.progress.cancel}
          </Button>
        ) : null}
      </div>

      <div
        className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1"
        data-console="generation"
        data-percent={percent}
        data-sections={sections.length}
        data-slides={slideCount}
        data-events={events.length}
      >
        <span className="text-[32px] leading-none font-bold tracking-[-0.04em] text-ink tabular-nums">
          {percent}%
        </span>
        <span className="text-[15px] text-body">
          {current?.phase}
          {current?.detail ? ` — ${current.detail}` : ""}
        </span>
      </div>

      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-soft">
        <div
          className="h-full rounded-full bg-blue transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <ol className="mt-4 grid gap-1.5 sm:grid-cols-3">
        {PHASE_RANGES.map((p) => {
          const done = percent >= p.to;
          const active = percent >= p.from && percent < p.to;
          return (
            <li key={p.key} className="flex items-center gap-2 text-[13px]">
              <Dot tone={done ? "green" : active ? "blue" : "neutral"} />
              <span
                className={cx(
                  done ? "text-body" : active ? "font-semibold text-ink" : "text-muted",
                )}
              >
                {t.progress[p.key]}
              </span>
            </li>
          );
        })}
      </ol>

      {/* ── 每一节现在到哪了 ── 并发 3 节,所以会有三条同时亮 ── */}
      {sections.length ? (
        <div className="mt-5 border-t border-line pt-4">
          <div className="flex items-baseline justify-between">
            <SectionLabel>{t.progress.sections}</SectionLabel>
            <span className="text-[12px] text-muted">
              {t.progress.slidesWritten(slideCount)}
            </span>
          </div>

          <ul className="mt-2.5 space-y-1.5">
            {sections.map((l) => (
              <li key={l.index} className="flex items-center gap-2.5 text-[13px]">
                <Dot tone={LANE_TONE[l.status]} />
                <span className="w-[52px] shrink-0 font-mono text-[12px] text-muted">
                  {String(l.index + 1).padStart(2, "0")}
                </span>
                <span
                  className={cx(
                    "min-w-0 shrink-0 truncate",
                    l.status === "queued" ? "text-muted" : "font-medium text-ink",
                  )}
                  style={{ maxWidth: "12rem" }}
                >
                  {l.title || `...`}
                </span>
                <span className="min-w-0 flex-1 truncate text-muted">
                  {l.status === "written"
                    ? `${t.progress.written} · ${t.progress.slidesWritten(l.pages)}`
                    : l.status === "failed"
                      ? l.detail
                      : l.detail
                        ? l.detail
                        : l.turn
                          ? `${t.progress.writing} · ${t.progress.turnLabel(l.turn)}`
                          : t.progress.waiting}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* ── 最近写出的几页 —— 「第几张 ppt」 ── */}
      {pages.length ? (
        <div className="mt-4 border-t border-line pt-3">
          <SectionLabel>{t.progress.latestPages}</SectionLabel>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {pages.slice(-6).map((title, i) => (
              <span
                key={`${title}-${i}`}
                className="rounded-sm border border-line bg-soft px-2 py-0.5 text-[12px] text-body"
              >
                {title}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {events.length > 1 ? (
        <details className="mt-4">
          <summary className="cursor-pointer text-[12px] font-semibold text-muted">
            {t.progress.phaseLog}
          </summary>
          <ol className="mt-2 max-h-52 space-y-0.5 overflow-auto font-mono text-[11px]">
            {events.map((e, i) => (
              <li key={i}>
                <span className="text-muted">{String(e.percent).padStart(3, " ")}%</span> {e.phase}
                {" · "}
                {e.detail}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </Card>
  );
}

// ── 起手式:还没有产物 ────────────────────────────────────────

function Setup({
  topic,
  setTopic,
  audience,
  setAudience,
  duration,
  setDuration,
  objectives,
  setObjectives,
  materialText,
  setMaterialText,
  contentLang,
  setContentLang,
  busy,
  events,
  materials,
  elapsed,
  onCancel,
  course,
  chapter,
  onCreateCourse,
  onGenerate,
  onOutline,
}: {
  topic: string;
  setTopic: (v: string) => void;
  audience: string;
  setAudience: (v: string) => void;
  duration: number;
  setDuration: (v: number) => void;
  objectives: string;
  setObjectives: (v: string) => void;
  materialText: string;
  setMaterialText: (v: string) => void;
  contentLang: Locale;
  setContentLang: (v: Locale) => void;
  busy: boolean;
  events: ProgressEvent[];
  materials: MaterialReport[];
  elapsed: number;
  onCancel: () => void;
  course: TeacherCourse | null;
  chapter: TeacherChapter | null;
  onCreateCourse: () => void;
  onGenerate: () => void;
  onOutline: () => void;
}) {
  const { t } = useI18n();
  const buildingChapter = Boolean(course && chapter);

  return (
    <div className="mx-auto w-full max-w-[1180px] px-5 py-9 sm:px-8 sm:py-12">
      <header className="mb-9 max-w-[64ch]">
        {buildingChapter ? (
          <a href={`/courses/${course?.id}`} className="text-sm font-semibold text-blue">
            ← Back to {course?.title}
          </a>
        ) : null}
        <SectionLabel className={buildingChapter ? "mt-4" : undefined}>
          {buildingChapter ? "Chapter builder" : t.setup.eyebrow}
        </SectionLabel>
        <h1 className="mt-3 text-[clamp(2.25rem,5vw,3.75rem)] leading-[1.06] font-semibold tracking-[-0.06em] text-ink">
          {buildingChapter ? `Build ${chapter?.title}` : t.setup.headline}
        </h1>
        <p className="mt-3 text-[16px] leading-[1.6] text-body">
          {buildingChapter
            ? "Set the teaching brief for this chapter, then generate its editable draft."
            : t.setup.lede}
        </p>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] lg:items-start">
        <Card className="p-6">
          <SectionLabel>{t.setup.brief}</SectionLabel>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label={buildingChapter ? "Chapter topic" : t.setup.topic}>
                <input className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} />
              </Field>
            </div>
            <Field label={t.setup.audience}>
              <input
                className={inputCls}
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
              />
            </Field>
            <Field label={t.setup.length} hint={t.setup.minutes}>
              <input
                type="number"
                className={inputCls}
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </Field>
            <div className="sm:col-span-2">
              <Field label={t.setup.objectives} hint={t.setup.onePerLine}>
                <textarea
                  rows={3}
                  className={inputCls}
                  value={objectives}
                  onChange={(e) => setObjectives(e.target.value)}
                />
              </Field>
            </div>

            {/* 教材语言 —— 和界面语言是两条轴,所以放在这里而不是页头 */}
            <div className="sm:col-span-2">
              <span className="text-[13px] font-semibold text-body">
                {t.setup.contentLanguage}
              </span>
              <Segmented<Locale>
                className="mt-1.5 max-w-[340px]"
                value={contentLang}
                onChange={setContentLang}
                label={t.setup.contentLanguage}
                options={LOCALES.map((l) => ({
                  value: l,
                  label: LOCALE_LABELS[l].native,
                }))}
              />
              <p className="mt-1.5 text-[12px] text-muted">{t.setup.contentLanguageHint}</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <SectionLabel>{t.setup.materials}</SectionLabel>
          <p className="mt-3 text-[14px] leading-[1.55] text-body">{t.setup.materialsLede}</p>
          <textarea
            rows={9}
            className={cx(inputCls, "mt-3 font-mono text-[13px] leading-[1.6]")}
            value={materialText}
            onChange={(e) => setMaterialText(e.target.value)}
          />

          {materials.length ? (
            <ul className="mt-4 space-y-1.5 border-t border-line pt-4">
              {materials.map((m) => (
                <li key={m.filename} className="flex flex-wrap items-center gap-2 text-[13px]">
                  <Dot
                    tone={m.status === "ok" ? "green" : m.status === "degraded" ? "amber" : "neutral"}
                  />
                  <span className="font-mono text-[12px] text-ink">{m.filename}</span>
                  <span className="text-muted">
                    {m.detected_form} · {t.setup.pages(m.pages)} ·{" "}
                    {t.setup.chars(m.extracted_chars)}
                    {m.ocr_used ? ` · ${t.setup.ocr}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}

        </Card>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button variant="primary" className="min-h-[46px] px-6" onClick={course ? onGenerate : onCreateCourse} disabled={busy || Boolean(course && !chapter)}>
          {busy ? t.setup.working : course ? "Generate selected chapter" : "Create course draft"}
        </Button>
        <Button className="min-h-[46px]" onClick={onOutline} disabled={busy || !course}>
          {t.setup.outlineOnly}
        </Button>
        <p className="text-[13px] text-muted">
          {course
            ? `Selected chapter · generate its draft here, then review it before publishing.`
            : "Step 1 of 2 · create a course before generating its first chapter"}
        </p>
      </div>

      {events.length ? (
        <div className="mt-6">
          <GenerationConsole
            events={events}
            elapsed={elapsed}
            busy={busy}
            onCancel={onCancel}
          />
        </div>
      ) : null}
    </div>
  );
}

// ── 覆盖度条 ─────────────────────────────────────────────────

function CoverageStrip({
  coverage,
  issues,
}: {
  coverage: { id: string; text: string; count: number }[];
  issues: string[];
}) {
  const { t } = useI18n();
  const covered = coverage.filter((c) => c.count > 0).length;

  return (
    <div className="border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3">
        <SectionLabel>{t.coverage.label}</SectionLabel>
        <span className="text-[13px] font-semibold text-ink">
          {covered}/{coverage.length}
        </span>
        <ul className="flex flex-wrap items-center gap-1.5">
          {coverage.map((c) => (
            <li key={c.id}>
              <span
                title={c.text}
                className={cx(
                  "inline-flex items-center gap-1.5 rounded-full px-2 py-[3px] text-[12px] font-semibold",
                  c.count ? "bg-green-soft text-green" : "bg-amber-soft text-amber",
                )}
              >
                <Dot tone={c.count ? "green" : "amber"} />
                {c.id}
                <span className="font-normal opacity-75">
                  {c.count ? t.coverage.count(c.count) : t.coverage.notCovered}
                </span>
              </span>
            </li>
          ))}
        </ul>

        <span className={cx("ml-auto text-[12px]", issues.length ? "text-amber" : "text-green")}>
          {issues.length ? t.coverage.issues(issues.length) : t.coverage.passed}
        </span>
      </div>

      {issues.length ? (
        <ul className="mx-auto w-full max-w-[1600px] space-y-1 px-6 pb-3">
          {issues.map((s, i) => (
            <li key={i} className="text-[12px] text-amber">
              · {s}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

// ── 主页面 ────────────────────────────────────────────────────

export default function Studio() {
  const { t } = useI18n();
  const router = useRouter();

  const [topic, setTopic] = useState(DEFAULT_TOPIC);
  const [audience, setAudience] = useState(DEFAULT_AUDIENCE);
  const [duration, setDuration] = useState(45);
  const [objectives, setObjectives] = useState(DEFAULT_OBJECTIVES);
  const [materialText, setMaterialText] = useState(DEFAULT_MATERIAL);
  const [contentLang, setContentLangState] = useState<Locale>("zh-HK");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  /** 生成已经跑了多少秒 —— 等待时至少有个东西在动。 */
  const [elapsed, setElapsed] = useState(0);
  /** 用来取消在途的流。 */
  const abortRef = useRef<AbortController | null>(null);
  /** 完成后延迟切视图的定时器 —— 重新生成时要清掉,否则会串台。 */
  const revealRef = useRef<number | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [gen, setGen] = useState<GenerateResponse | null>(null);
  const [pkg, setPkg] = useState<CoursePackage | null>(null);
  const [course, setCourse] = useState<TeacherCourse | null>(null);
  const [chapter, setChapter] = useState<TeacherChapter | null>(null);
  const [chapters, setChapters] = useState<TeacherChapter[]>([]);
  const [patches, setPatches] = useState<Patch[]>([]);

  const [editMessage, setEditMessage] = useState("Slide 2 is too dense for a non-CS audience.");
  /**
   * L2 的实时步骤帧。
   *
   * 和 L1 存整条 `ProgressEvent` 不同,这里存**原始帧**:L2 的进度没有百分比,
   * 只有「第几轮 · 调了什么工具」。派生逻辑放在 ReviewMargin 里,和 L1 的
   * `deriveSections` 是一个路子 —— 界面是事件流的纯函数。
   */
  const [editFrames, setEditFrames] = useState<EditProgressEvent[]>([]);
  /**
   * 正在跑 L2 编辑。
   *
   * **不能用共享的 `busy`** —— 那个在「批准」「驳回」时也是 true,
   * 于是点一下批准,审阅栏会拿上一轮残留的步骤重新冒出来,
   * 看起来像 agent 又在改一遍。
   */
  const [editRunning, setEditRunning] = useState(false);
  const [reply, setReply] = useState("");
  const [callNames, setCallNames] = useState<string[]>([]);
  /** 提议期间产物有没有被改动 —— 前端自己比对的,不是听后端说的。 */
  const [integrity, setIntegrity] = useState<boolean | null>(null);

  const [editing, setEditing] = useState<string | null>(null);
  const [view, setView] = useState<"slides" | "plan">("slides");
  const [focusedTarget, setFocusedTarget] = useState<string | null>(null);
  /** 左栏高亮:当前滚动到哪一页。 */
  const [activeId, setActiveId] = useState<string | null>(null);

  // The editor is deliberately chapter-scoped. A direct visit goes to the
  // course catalogue; only the course detail page may open a chosen chapter.
  useEffect(() => {
    const courseId = window.localStorage.getItem("pathpilot.activeCourse");
    const chapterId = window.localStorage.getItem("pathpilot.activeChapter");
    if (!courseId || !chapterId) {
      router.replace("/courses");
      return;
    }
    void (async () => {
      try {
        const [nextCourse, nextChapter] = await Promise.all([
          api.course(courseId), api.chapter(courseId, chapterId),
        ]);
        setCourse(nextCourse);
        setChapter(nextChapter);
        setChapters(await Promise.all(nextCourse.chapterIds.map((id) => api.chapter(courseId, id))));
        // The chapter brief comes from the selected course, never the demo Git sample.
        setTopic(nextChapter.title === "Chapter 0" ? nextCourse.title : nextChapter.title);
        setAudience(nextCourse.audience);
        setDuration(nextCourse.durationMin);
        setObjectives(nextCourse.learningObjectives.map((item) => item.text).join("\n"));
        setMaterialText("");
        setContentLangState(normalizeLocale(nextCourse.language));
        if (nextChapter.package) {
          await api.activateChapter(courseId, chapterId);
          setPkg(nextChapter.package);
        }
      } catch (failure) {
        setError(failure instanceof Error ? failure.message : String(failure));
      }
    })();
  }, [router]);
  const setContentLang = useCallback((next: Locale) => {
    setContentLangState(next);
    window.localStorage.setItem(CONTENT_LANG_KEY, next);
  }, []);

  const payload = () => ({
    topic,
    audience,
    duration_min: duration,
    objectives: objectives
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
    material_text: materialText,
    use_real_model: true,
    language: contentLang,
  });

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError("");
    // 在**事件处理函数**里重置,而不是在 effect 里 ——
    // effect 里同步 setState 会触发级联渲染(react-hooks/set-state-in-effect)。
    setElapsed(0);
    try {
      return await fn();
    } catch (e) {
      // 教师点了「停止」不算错误 —— 别把 AbortError 当成故障弹出来
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        setError(e instanceof Error ? e.message : String(e));
      }
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  /** 取消在途的生成 —— 客户端断开后后端也会跟着取消,不会留孤儿协程(§13.4)。 */
  const onCancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    if (revealRef.current !== null) {
      window.clearTimeout(revealRef.current);
      revealRef.current = null;
    }
  };

  useEffect(() => () => {
    if (revealRef.current !== null) window.clearTimeout(revealRef.current);
  }, []);

  // 计时器:只在忙的时候走。
  //
  // 为什么数 tick 而不是记墙钟时间:`Date.now()` 是不纯的,React Compiler 的
  // purity 规则不允许它出现在组件的渲染路径上(而 `run()` 就是渲染路径里定义的)。
  // 对「2s / 3s」这种显示来说,数 tick 完全够用,而且更简单。
  useEffect(() => {
    if (!busy) return;
    const id = window.setInterval(() => setElapsed((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [busy]);

  const onOutline = () =>
    run(async () => {
      const r = await api.outline(payload());
      setGen((g) => (g ? { ...g, outline: r.outline, model_mode: r.model_mode } : g));
      setEvents([
        {
          phase: t.progress.outline,
          percent: 25,
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

  const onCreateCourse = () =>
    run(async () => {
      const created = await api.createCourse({
        title: topic,
        description: materialText,
        audience,
        durationMin: duration,
        language: contentLang,
      });
      const firstChapterId = created.chapterIds[0];
      if (!firstChapterId) throw new Error("Course creation did not create a first chapter.");
      setCourse(created);
      const firstChapter = await api.chapter(created.id, firstChapterId);
      setChapter(firstChapter);
      setChapters([firstChapter]);
    });

  const onCreateChapter = () =>
    run(async () => {
      if (!course) throw new Error("Create a course before adding chapters.");
      const next = await api.createChapter(course.id, {
        title: `Chapter ${course.chapterIds.length + 1}`,
        summary: "Teacher-created chapter draft",
      });
      setCourse((current) => current ? { ...current, chapterIds: [...current.chapterIds, next.id] } : current);
      setChapter(next);
      setChapters((items) => [...items, next]);
    });

  const onRenameChapter = (title: string) =>
    run(async () => {
      if (!course || !chapter) throw new Error("Choose a chapter before renaming it.");
      const updated = await api.updateChapter(course.id, chapter.id, { title: title.trim() });
      setChapter(updated);
      setChapters((items) => items.map((item) => item.id === updated.id ? updated : item));
    });

  const onSelectChapter = (selected: TeacherChapter) => {
    setChapter(selected);
    setPkg(selected.package ?? null);
    setPatches([]);
    setEvents([]);
    if (course && selected.package) {
      void api.activateChapter(course.id, selected.id)
        .catch((failure) => setError(failure instanceof Error ? failure.message : String(failure)));
    }
  };

  useEffect(() => {
    if (!course || !chapter || !pkg) return;
    void api.updateChapter(course.id, chapter.id, { package: pkg, status: "ready" })
      .then((updated) => {
        setChapter(updated);
        setChapters((items) => items.map((item) => item.id === updated.id ? updated : item));
      })
      .catch((failure) => setError(failure instanceof Error ? failure.message : String(failure)));
  }, [course?.id, chapter?.id, pkg]);

  const onGenerate = () =>
    run(async () => {
      if (!course || !chapter) {
        throw new Error("Create the course before generating its first chapter.");
      }
      // 每次重新生成都清干净 —— 否则上一次的进度会混进来
      if (revealRef.current !== null) {
        window.clearTimeout(revealRef.current);
        revealRef.current = null;
      }
      setEvents([]);
      setPatches([]);
      setReply("");
      setCallNames([]);
      setIntegrity(null);
      setEditing(null);
      setEditFrames([]);

      const controller = new AbortController();
      abortRef.current = controller;

      // ★ 流式生成:进度**边跑边来**,不再等生成完才一次性给。请求必须
      // 带着 course/chapter ownership，才能自动采用该课程的 syllabus。
      await api.generateChapterStream(course.id, chapter.id, payload(), {
        signal: controller.signal,
        onProgress: (ev) => {
          setEvents((old) => [...old, ev]);
        },
        onResult: (r) => {
          setGen(r);
          // The chapter-owned backend stream has already committed its package
          // and version record. Keep the selected chapter metadata in sync.
          setChapter(r.chapter);
          setChapters((items) => items.map((item) => item.id === r.chapter.id ? r.chapter : item));
          // ═══════════════════════════════════════════════════════
          // 为什么不立刻切到工作台
          // ═══════════════════════════════════════════════════════
          // 最后一批进度帧(58%→100%,包含全部「写了 N 页」)和这个 result
          // 事件往往落在同一个任务里,React 会把它们**批处理进同一次渲染** ——
          // 于是 `pkg` 和最后那批事件同时生效,Setup 直接卸载,
          // 控制台在 100% 上闪一下就没了,教师根本没看见「已写 3 张」。
          //
          // 这个洞是浏览器验证脚本抓出来的:它报「0 次采样」和
          // 「『已写 N 张』最多只有 0」,而当时后端每一帧都是对的。
          // 停留一下,让人看得见完成状态。
          revealRef.current = window.setTimeout(() => {
            revealRef.current = null;
            setPkg(r.package);
            setEvents(r.events);
            setView("slides");
          }, REVEAL_DELAY_MS);
        },
      });
      abortRef.current = null;
    });

  const onEdit = () =>
    run(async () => {
      const before = JSON.stringify(pkg);
      setEditFrames([]);
      setEditRunning(true);

      try {
        // ★ 流式编辑:能看见 agent 先读了哪一页、为什么这么改。
        //   工具调用序列本身没变(后端还是同一个 edit_artifact),
        //   变的只是「什么时候看得到」。
        await api.editStream(editMessage, true, {
          onProgress: (e) => setEditFrames((old) => [...old, e]),
          onResult: (r) => {
            setReply(r.reply);
            setCallNames(r.call_names);
            setPatches((old) => [...r.patches, ...old]);
            // ★ 后端说「产物没变」,这里自己再比一次 —— 不信口头承诺
            setIntegrity(before === JSON.stringify(r.package));
            setPkg(r.package);
          },
        });
      } finally {
        setEditRunning(false);
      }
    });

  // ── 教师端后几步:出题 / 组卷 / 白话化 ──
  // 三个都直接返回新的 package,和生成走同一条路 —— 它们产出新产物,
  // 不是「修改已有内容」,所以不走 patch。教师改某一页内容仍然只能走 patch。

  const onQuestions = () =>
    run(async () => {
      const r = await api.questions(2, true, contentLang);
      setPkg(r.package);
      setGen((g) => (g ? { ...g, model_mode: r.model_mode } : g));
    });

  const onPaper = (totalPoints: number, durationMin: number) =>
    run(async () => {
      const r = await api.paper({
        total_points: totalPoints,
        duration_min: durationMin,
        // 留空 = 覆盖全部目标,由后端从大纲取
        coverage: [],
        easy: 0,
        medium: 0,
        hard: 0,
      });
      setPkg(r.package);
    });

  const onGlossary = () =>
    run(async () => {
      const r = await api.glossary(true, contentLang);
      setPkg(r.package);
      setGen((g) => (g ? { ...g, model_mode: r.model_mode } : g));
    });

  const onApply = (id: string) =>
    run(async () => {
      const r = await api.apply(id);
      setPkg(r.package);
      setPatches((old) => old.map((p) => (p.id === id ? { ...p, status: "applied" } : p)));
      setIntegrity(null);
    });

  const onReject = (id: string) =>
    run(async () => {
      const r = await api.reject(id);
      setPkg(r.package);
      setPatches((old) => old.map((p) => (p.id === id ? { ...p, status: "rejected" } : p)));
    });

  /** 教师直接改 —— 不走 AI。后端仍生成一条 author="teacher" 的记录并立刻生效。 */
  const onManualSave = (kind: "slide" | "timeline", id: string, body: Record<string, unknown>) =>
    run(async () => {
      const r = await api.manualEdit(kind, id, body);
      setPkg(r.package);
      setPatches((old) => [r.patch, ...old]);
      setEditing(null);
    });

  const onBackToCourses = () => {
    onCancel();
    window.localStorage.removeItem("pathpilot.activeCourse");
    window.localStorage.removeItem("pathpilot.activeChapter");
    router.push("/courses");
  };

  const slides = useMemo(() => pkg?.slideDeck?.slides ?? [], [pkg]);
  const timeline = useMemo(() => pkg?.lessonPlan?.timeline ?? [], [pkg]);

  const pendingByTarget = useMemo(() => {
    const out: Record<string, number> = {};
    for (const p of patches) {
      if (p.status === "proposed") out[p.target_id] = (out[p.target_id] ?? 0) + 1;
    }
    return out;
  }, [patches]);

  const pending = useMemo(() => patches.filter((p) => p.status === "proposed"), [patches]);

  const coverage = useMemo(
    () =>
      (pkg?.project.learningObjectives ?? []).map((o) => ({
        id: o.id,
        text: o.text,
        count: slides.filter((s) => s.objectiveIds.includes(o.id)).length,
      })),
    [pkg, slides],
  );

  /** 点审阅栏里的一条改动 → 跳到画布上被改的那一页。 */
  const focusPatch = (p: Patch) => {
    const target = p.kind === "timeline" ? "plan" : "slides";
    setFocusedTarget(p.target_id);
    setView(target);
    window.setTimeout(() => {
      document
        .getElementById(`${target === "plan" ? "plan" : "slide"}-${p.target_id}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 60);
    window.setTimeout(() => setFocusedTarget(null), 2400);
  };

  /** 左侧目录主动控制翻页；不能只依赖嵌入式窄视图里的 hash 跳转。 */
  const jumpTo = useCallback((targetId: string) => {
    setActiveId(targetId);
    if (targetId.startsWith("slide-")) {
      // 幻灯片是单页画布，不是长文档。平滑滚动会触发上一页留下的
      // scroll listener，把刚点选的页又覆盖成旧页（常表现为点第 7 页却
      // 显示最后一页）。直接回到画布顶部，不参与「阅读线」定位。
      window.scrollTo({ top: 0 });
      return;
    }
    document.getElementById(targetId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  // ── 滚动定位:高亮左栏里当前在看的那一页 ──────────────────
  //
  // 一开始用 IntersectionObserver「取最靠上的可见项」,结果是错的:
  // 滚到第 3 页时第 2 页仍然和观察带相交,而它的 top 更小,于是永远被选中。
  //
  // 正确的规则是**阅读线**:视口顶部往下 150px 画一条线,当前页 = 最后一个
  // 越过这条线的元素。simple、可预测,而且在任何滚动位置都成立。
  useEffect(() => {
    // 单页课件的当前页只由左栏 / J-K 快捷键决定。这里若继续追踪滚动，
    // listener 会拿到一次渲染前的 DOM 节点并覆写刚点选的 slide ID。
    if (view === "slides") return;

    const ids = timeline.map((entry) => `plan-${entry.id}`);
    const nodes = ids
      .map((id) => document.getElementById(id))
      .filter((n): n is HTMLElement => n !== null);
    if (!nodes.length) return;

    // 略大于 scroll-mt-32(128px),否则滚到位的那一刻自己反而「没过线」。
    const READING_LINE = 150;
    let frame = 0;

    const update = () => {
      frame = 0;
      let current = nodes[0];
      for (const n of nodes) {
        if (n.getBoundingClientRect().top <= READING_LINE) current = n;
      }
      // 滚到底时直接认最后一页 —— 否则短页面上最后一页永远到不了阅读线,
      // 也就永远高亮不到(它已经贴在视口底部了,但它不是「当前在读的那页」)。
      const atBottom =
        window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      if (atBottom) current = nodes[nodes.length - 1];
      setActiveId(current.id);
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [pkg, view, slides, timeline]);

  const requestCoverage = (o: { id: string; text: string }) => setEditMessage(t.margin.coverGap(o.id, o.text));

  // ── 刷新之后把产物接回来 ────────────────────────────────────
  //
  // 没有这一步,生成结果只活在 React state 里:后端 `/state` 明明还留着
  // 那份产物,页面一刷新却回到 Setup —— 对教师来说就是「白做了」。
  //
  // 为什么要在挂载时拉而不是靠 localStorage:
  // 产物在**后端**。前端存一份副本的话,两边迟早不一致 ——
  // L2 改完产物以后,前端那份就是旧的。
  //
  // 失败不报错也不挡住用户:拉不回来最多是从头开始,比弹一个红条好。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Course detail owns the active chapter. Do not resurrect a package from
      // the old singleton endpoint over a deliberate chapter selection.
      if (window.localStorage.getItem("pathpilot.activeCourse")) return;
      try {
        const s = await api.state();
        if (cancelled || !s.has_package || !s.package) return;
        setPkg(s.package);
        setPatches(s.patches ?? []);
        setIntegrity((s.integrity_issues ?? []).length === 0);
        setGen((g) =>
          g ?? {
            model_mode: s.model_mode ?? "",
            events: [],
            materials: [],
            outline: null,
            package: s.package as CoursePackage,
            integrity_issues: s.integrity_issues ?? [],
            agents: [],
          },
        );
      } catch {
        // 后端没起来或状态已清 —— 停在 Setup 就行
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="min-h-screen">
      <AppHeader
        title={pkg ? pkg.project.meta.title : undefined}
        modelMode={gen?.model_mode}
        busy={busy}
        onBackToCourses={onBackToCourses}
      />

      {error ? (
        <div className="mx-auto w-full max-w-[1600px] px-6 pt-5">
          <ErrorBar message={error} onDismiss={() => setError("")} />
        </div>
      ) : null}

      {!pkg ? (
        <Setup
          topic={topic}
          setTopic={setTopic}
          audience={audience}
          setAudience={setAudience}
          duration={duration}
          setDuration={setDuration}
          objectives={objectives}
          setObjectives={setObjectives}
          materialText={materialText}
          setMaterialText={setMaterialText}
          contentLang={contentLang}
          setContentLang={setContentLang}
          busy={busy}
          events={events}
          materials={gen?.materials ?? []}
          course={course}
          chapter={chapter}
          onCreateCourse={onCreateCourse}
          onGenerate={onGenerate}
          onOutline={onOutline}
          elapsed={elapsed}
          onCancel={onCancel}
        />
      ) : (
        <>
          <CoverageStrip coverage={coverage} issues={gen?.integrity_issues ?? []} />

          <div className="mx-auto grid w-full max-w-[1600px] gap-6 px-6 py-7 lg:grid-cols-[210px_minmax(0,1fr)_360px]">
            {/* ── 左:导航(滚动时高亮当前页)─────────────── */}
            <aside className="lg:sticky lg:top-[92px] lg:self-start">
              <Segmented<"slides" | "plan">
                value={view}
                onChange={setView}
                label={t.keys.toggle}
                options={[
                  { value: "slides", label: t.rail.slides(slides.length) },
                  { value: "plan", label: t.rail.plan(timeline.length) },
                ]}
              />

              <nav className="mt-4">
                <ol className="space-y-px">
                  {view === "slides"
                    ? slides.map((s, i) => {
                        const isActive = activeId === `slide-${s.id}`;
                        return (
                          <li key={s.id}>
                            <button
                              type="button"
                              onClick={() => jumpTo(`slide-${s.id}`)}
                              aria-pressed={isActive}
                              className={cx(
                                "flex gap-2.5 rounded-sm px-2 py-1.5 text-[13px] leading-[1.35] transition-colors",
                                isActive
                                  ? "bg-blue-soft font-semibold text-blue"
                                  : "text-body hover:bg-soft hover:text-ink",
                              )}
                            >
                              <span className="font-mono text-[11px] opacity-70">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                              <span className="min-w-0 flex-1">{s.title}</span>
                              {pendingByTarget[s.id] ? <Dot tone="violet" /> : null}
                            </button>
                          </li>
                        );
                      })
                    : timeline.map((entry, i) => {
                        const isActive = activeId === `plan-${entry.id}`;
                        return (
                          <li key={entry.id}>
                            <button
                              type="button"
                              onClick={() => jumpTo(`plan-${entry.id}`)}
                              aria-pressed={isActive}
                              className={cx(
                                "flex gap-2.5 rounded-sm px-2 py-1.5 text-[13px] leading-[1.35] transition-colors",
                                isActive
                                  ? "bg-blue-soft font-semibold text-blue"
                                  : "text-body hover:bg-soft hover:text-ink",
                              )}
                            >
                              <span className="font-mono text-[11px] opacity-70">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                              <span className="min-w-0 flex-1">{entry.phase}</span>
                              {pendingByTarget[entry.id] ? <Dot tone="violet" /> : null}
                            </button>
                          </li>
                        );
                      })}
                </ol>
              </nav>

              <div className="mt-5 space-y-1.5 border-t border-line pt-3 text-[12px] text-muted">
                <p>
                  {t.rail.meta({
                    duration: pkg.project.meta.durationMin,
                    slides: slides.length,
                    assets: pkg.assets.length,
                  })}
                </p>
                <p className="break-words">{t.rail.forAudience(pkg.project.meta.audience)}</p>
                <p className="font-mono text-[11px] opacity-80">
                  {pkg.project.meta.language}
                </p>
              </div>

              {gen?.materials.length ? (
                <div className="mt-5 border-t border-line pt-3">
                  <SectionLabel>{t.rail.sources}</SectionLabel>
                  <ul className="mt-2 space-y-1">
                    {gen.materials.map((m) => (
                      <li key={m.filename} className="flex items-start gap-1.5 text-[12px]">
                        <span className="mt-[5px]">
                          <Dot
                            tone={
                              m.status === "ok"
                                ? "green"
                                : m.status === "degraded"
                                  ? "amber"
                                  : "neutral"
                            }
                          />
                        </span>
                        <span className="min-w-0 flex-1 break-words text-muted">
                          <span className="font-mono text-[11px] text-body">{m.filename}</span>
                          <br />
                          {t.setup.chars(m.extracted_chars)}
                          {m.ocr_used ? ` · ${t.setup.ocr}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {gen?.agents.length ? (
                <details className="mt-5 border-t border-line pt-3">
                  <summary className="cursor-pointer text-[12px] font-semibold text-muted">
                    {t.rail.runDetails}
                  </summary>
                  <ul className="mt-2 space-y-1 font-mono text-[11px] leading-[1.5] text-muted">
                    {gen.agents.map((a, i) => (
                      <li key={i} className="break-words">
                        §{i + 1} {t.rail.turns(a.turns)} · {a.stopped_by}
                        <br />
                        {a.call_names.join(" → ")}
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </aside>

            {/* ── 中:材料 ─────────────────────────────── */}
            <main className="min-w-0">
              <TeacherTools
                pkg={pkg}
                busy={busy}
                onQuestions={onQuestions}
                onPaper={onPaper}
                onGlossary={onGlossary}
              />

              {view === "slides" ? (
                slides.length ? (
                  <div className="space-y-4">
                    {slides.filter((s) => !activeId || activeId === `slide-${s.id}`).map((s) => {
                      const i = slides.findIndex((candidate) => candidate.id === s.id);
                      return (
                      <SlideCanvas
                        key={s.id}
                        slide={s}
                        index={i}
                        pendingCount={pendingByTarget[s.id] ?? 0}
                        active={focusedTarget === s.id}
                        current={activeId === `slide-${s.id}`}
                        editing={editing === `slide:${s.id}`}
                        busy={busy}
                        onEdit={() => setEditing(`slide:${s.id}`)}
                        onCancelEdit={() => setEditing(null)}
                        onSave={(body) => onManualSave("slide", s.id, body)}
                      />
                      );
                    })}
                  </div>
                ) : (
                  <p className="rounded-md border border-dashed border-line bg-surface px-5 py-10 text-center text-[15px] text-muted">
                    {t.slide.noSlides}
                  </p>
                )
              ) : (
                <LessonPlan
                  pkg={pkg}
                  editingId={editing?.startsWith("timeline:") ? editing.slice(9) : null}
                  busy={busy}
                  pendingByTarget={pendingByTarget}
                  onEdit={(id) => setEditing(`timeline:${id}`)}
                  onCancelEdit={() => setEditing(null)}
                  onSave={(id, body) => onManualSave("timeline", id, body)}
                />
              )}
            </main>

            {/* ── 右:审阅 ─────────────────────────────── */}
            <aside className="lg:sticky lg:top-[92px] lg:max-h-[calc(100vh-112px)] lg:self-start lg:overflow-y-auto">
              <ReviewMargin
                patches={patches}
                reply={reply}
                callNames={callNames}
                editFrames={editFrames}
                editBusy={editRunning}
                integrity={integrity}
                busy={busy}
                message={editMessage}
                onMessage={setEditMessage}
                onSend={onEdit}
                onApply={onApply}
                onReject={onReject}
                onFocusTarget={focusPatch}
                focusedTarget={focusedTarget}
                coverage={coverage}
                onRequestCoverage={requestCoverage}
              />
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
