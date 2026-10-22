"use client";

/**
 * 课件画布 —— 教师端的招牌组件。
 *
 * 这里刻意**不把幻灯片渲染成字段列表**。教师审的是「这一页讲台上放出来长什么样」,
 * 不是 `{title, bullets, layout}`。所以每一页按 16:9 真实版面渲染,
 * 版面分歧(title / bullets / twoCol / diagram / code / quiz)都走同一份 IR。
 *
 * 顺带一个好处:渲染器和将来的 pptx 导出器读的是同一份 IR,
 * 所以画布上看到的版面就是导出后拿到的版面。
 */

import { useRef, useState } from "react";

import { Badge, Button, Dot, Field, cx, inputCls } from "@/components/ui";
import { SlideAnimationPreview, type AnimationPresentation } from "@/components/SlideAnimationPreview";
import { useI18n } from "@/lib/i18n";
import type { Messages } from "@/lib/i18n-config";
import type { Slide } from "@/lib/api";

const LAYOUTS = ["title", "bullets", "diagram", "twoCol", "code", "quiz"] as const;

/** 版面名走词典;遇到后端新增的未知版面就原样显示,不崩。 */
function layoutLabel(t: Messages, layout: string): string {
  switch (layout) {
    case "title":
      return t.slide.layoutTitle;
    case "bullets":
      return t.slide.layoutBullets;
    case "diagram":
      return t.slide.layoutDiagram;
    case "twoCol":
      return t.slide.layoutTwoCol;
    case "code":
      return t.slide.layoutCode;
    case "quiz":
      return t.slide.layoutQuiz;
    default:
      return layout;
  }
}

function animationTargetClass(presentation: AnimationPresentation | undefined, target: string): string {
  if (!presentation?.animatedTargets.has(target)) return "";
  return cx(
    "slide-animation-target",
    !presentation.revealedTargets.has(target) && "slide-animation-target--waiting",
    presentation.emphasizedTarget === target && "slide-animation-target--emphasis",
  );
}

function SlideTitle({ children, targetId, highlighted, presentation }: { children: React.ReactNode; targetId?: string; highlighted?: boolean; presentation?: AnimationPresentation }) {
  return (
    <h3
      data-review-target={targetId}
      className={cx("mb-5 text-[27px] leading-[1.14] font-bold tracking-[-0.035em] text-ink", highlighted && "review-target-highlight", animationTargetClass(presentation, "title"))}
    >
      {children}
    </h3>
  );
}

function Bullets({ items, twoCol, spread, presentation, targetIndices }: { items: string[]; twoCol?: boolean; spread?: boolean; presentation?: AnimationPresentation; targetIndices?: number[] }) {
  if (!items.length) return null;
  return (
    <ul className={cx(
      twoCol ? "columns-2 gap-9" : spread ? "flex flex-1 flex-col justify-evenly py-1" : "space-y-4",
    )}>
      {items.map((b, i) => (
        <li
          key={i}
          className={cx(
            "flex break-inside-avoid gap-3 text-[17px] leading-[1.56] text-ink",
            twoCol && "mb-4",
            animationTargetClass(presentation, `bullet:${targetIndices?.[i] ?? i}`),
          )}
        >
          <span className="mt-[10px] h-[5px] w-[5px] shrink-0 rounded-full bg-blue" aria-hidden />
          <span className="min-w-0 flex-1">{b}</span>
        </li>
      ))}
    </ul>
  );
}

function AnimatedVisual({ target, presentation, children }: { target: string; presentation?: AnimationPresentation; children: React.ReactNode }) {
  return <div className={cx("h-full", animationTargetClass(presentation, target))}>{children}</div>;
}

/** 当本机浏览器拦截资源请求时，仍从同一页 IR 的要点画出可审阅的原生 SVG。 */
function DiagramFallback({ title, labels }: { title: string; labels: string[] }) {
  const steps = (labels.length ? labels : ["建立分支", "完成修改", "程式碼審查", "合併回主線"])
    .slice(0, 4)
    .map((label) => label.length > 17 ? `${label.slice(0, 16)}…` : label);
  return (
    <svg data-template="course-flow" viewBox="0 0 920 390" role="img" aria-label={`${title} concept map`} className="h-full w-full" preserveAspectRatio="xMidYMid meet">
      <defs><marker id="course-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#315fc6" /></marker></defs>
      <rect width="920" height="390" rx="24" fill="#f8fbff" />
      <path d="M104 246 H818" stroke="#315fc6" strokeWidth="7" strokeLinecap="round" markerEnd="url(#course-arrow)" />
      <path d="M266 246 C334 246 318 114 420 114 H626 C702 114 692 246 760 246" fill="none" stroke="#16806a" strokeWidth="7" strokeLinecap="round" />
      {steps.map((label, index) => {
        const x = 46 + index * 205;
        const y = index === 1 || index === 2 ? 66 : 276;
        return <g key={`${label}-${index}`}><rect x={x} y={y} width="172" height="68" rx="14" fill={index === 1 || index === 2 ? "#ddf4ec" : "#e7eeff"} stroke={index === 1 || index === 2 ? "#9bd8c8" : "#b6c9f5"} strokeWidth="2" /><text x={x + 14} y={y + 41} fill="#172033" fontFamily="Arial, Hiragino Sans GB, sans-serif" fontSize="17" fontWeight="600">{label}</text></g>;
      })}
      <text x="46" y="34" fill="#728198" fontFamily="Arial, Hiragino Sans GB, sans-serif" fontSize="13" fontWeight="700" letterSpacing="1.6">COURSE FLOW</text>
    </svg>
  );
}

/** 和 PPTX 使用同一个后端资源；资源不可达时不留空白，而是保留可审阅的 SVG。 */
function DiagramPreview({ url, alt, labels, thumbnail = false }: { url?: string; alt: string; labels: string[]; thumbnail?: boolean }) {
  const { t } = useI18n();
  const [failed, setFailed] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  if (!url || failed) {
    return <DiagramFallback title={alt} labels={labels} />;
  }
  if (thumbnail) {
    // 缩略图不是第二个交互入口,只呈现同一份图表内容。
    // 这样不会在左侧索引的按钮里再嵌套一个“放大图表”按钮。
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt="" className="max-h-full max-w-full object-contain" onError={() => setFailed(true)} />;
  }
  return (
    <>
      <button
        type="button"
        aria-label={t.slide.expandDiagram}
        onClick={() => dialogRef.current?.showModal()}
        className="group relative flex h-full w-full cursor-zoom-in items-center justify-center rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
      >
        {/* The backend renders this image from IR; Next image optimization adds no value. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt={alt} className="max-h-full max-w-full object-contain" onError={() => setFailed(true)} />
        <span className="absolute bottom-2 right-2 rounded-sm bg-surface/95 px-2 py-1 text-[11px] font-semibold text-ink shadow-sm group-hover:text-blue">
          {t.slide.expandDiagram}
        </span>
      </button>
      <dialog
        ref={dialogRef}
        aria-label={alt}
        className="m-auto max-h-[90vh] w-[min(94vw,1500px)] max-w-none overflow-hidden rounded-md border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-ink/75"
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-line bg-surface px-5 py-3">
          <span className="min-w-0 truncate text-[14px] font-semibold">{alt}</span>
          <button
            type="button"
            onClick={() => dialogRef.current?.close()}
            className="min-h-11 rounded-sm border border-line px-4 text-[14px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
          >
            {t.slide.closeDiagram}
          </button>
        </div>
        <div className="max-h-[calc(90vh-69px)] overflow-auto bg-white p-5">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt={alt} className="mx-auto max-h-[75vh] max-w-none" />
        </div>
      </dialog>
    </>
  );
}

function ComparisonFrame({ items, presentation }: { items: string[]; presentation?: AnimationPresentation }) {
  const left = items.filter((_, index) => index % 2 === 0);
  const right = items.filter((_, index) => index % 2 === 1);
  return (
    <div className="grid min-h-0 flex-1 grid-cols-2 gap-4">
      {[left, right].map((column, index) => (
        <section key={index} className={cx("flex min-h-0 flex-col rounded-lg border p-4", index ? "border-emerald-200 bg-emerald-50/45" : "border-blue/20 bg-blue-soft/45")}>
          <p className="mb-3 text-[11px] font-bold tracking-[0.08em] text-muted uppercase">{index ? "Safer move" : "Trade-off"}</p>
          <Bullets items={column} spread presentation={presentation} targetIndices={index ? items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 1) : items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 0)} />
        </section>
      ))}
    </div>
  );
}

function BalancedBulletColumns({ items, presentation }: { items: string[]; presentation?: AnimationPresentation }) {
  const columns = [
    items.filter((_, index) => index % 2 === 0),
    items.filter((_, index) => index % 2 === 1),
  ];
  return (
    <div className="grid min-h-0 flex-1 grid-cols-2 gap-8">
      {columns.map((column, index) => (
        <div key={index} className="flex min-h-0 flex-col">
          <Bullets items={column} spread presentation={presentation} targetIndices={index ? items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 1) : items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 0)} />
        </div>
      ))}
    </div>
  );
}

function ScenarioFrame({ title, items, presentation }: { title: string; items: string[]; presentation?: AnimationPresentation }) {
  const columns = [
    items.filter((_, index) => index % 2 === 0),
    items.filter((_, index) => index % 2 === 1),
  ];
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-amber-200 bg-[#fffaf1] p-5">
      <p className="mb-4 text-[11px] font-bold tracking-[0.08em] text-amber-700 uppercase">Engineering case</p>
      <h4 className="mb-4 text-[20px] font-semibold leading-tight text-ink">{title}</h4>
      <div className="grid min-h-0 flex-1 grid-cols-2 gap-8">
        {columns.map((column, index) => (
          <div key={index} className="flex min-h-0 flex-col">
            <Bullets items={column} spread presentation={presentation} targetIndices={index ? items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 1) : items.map((_, itemIndex) => itemIndex).filter((itemIndex) => itemIndex % 2 === 0)} />
          </div>
        ))}
      </div>
    </div>
  );
}

function EvidenceFrame({ items, presentation }: { items: string[]; presentation?: AnimationPresentation }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-lg border border-line bg-soft/55 p-5">
      <p className="mb-4 text-[11px] font-bold tracking-[0.08em] text-muted uppercase">Evidence to inspect</p>
      <Bullets items={items} spread presentation={presentation} />
    </div>
  );
}

/** 按 layout 渲染版面。每个分支都只读 IR,不读任何界面状态。 */
function SlideBody({ slide, diagramUrl, thumbnail = false, focusedField, presentation }: { slide: Slide; diagramUrl?: string; thumbnail?: boolean; focusedField?: string | null; presentation?: AnimationPresentation }) {
  const { t } = useI18n();
  const { layout, title, bullets, visualPurpose } = slide;
  const visual = slide.visuals.find((item) => item.kind === "diagram");
  const figure = visual ? <AnimatedVisual target={`visual:${visual.id}`} presentation={presentation}><DiagramPreview key={diagramUrl} url={diagramUrl} alt={`${title} diagram`} labels={bullets} thumbnail={thumbnail} /></AnimatedVisual> : null;
  const titleTargetId = `slide:${slide.id}:title`;
  const titleFocused = focusedField === "title";

  if (visualPurpose === "comparison" || visualPurpose === "scenario" || visualPurpose === "evidence") {
    const treatment = visualPurpose === "comparison"
      ? <ComparisonFrame items={bullets} presentation={presentation} />
      : visualPurpose === "scenario"
        ? <ScenarioFrame title={title} items={bullets} presentation={presentation} />
        : <EvidenceFrame items={bullets} presentation={presentation} />;
    return (
      <div className="flex h-full flex-col">
        <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
        {treatment}
      </div>
    );
  }

  if (layout === "title") {
    return (
      <div className="flex h-full flex-col justify-center">
        <h3 data-review-target={titleTargetId} className={cx("max-w-[20ch] text-[36px] leading-[1.06] font-bold tracking-[-0.045em] text-ink", titleFocused && "review-target-highlight", animationTargetClass(presentation, "title"))}>
          {title}
        </h3>
        {bullets[0] ? (
          <p className={cx("mt-4 max-w-[46ch] text-[17px] leading-[1.5] text-body", animationTargetClass(presentation, "bullet:0"))}>{bullets[0]}</p>
        ) : null}
        {figure ? <div className="mt-5 h-[38%] max-w-[65%]">{figure}</div> : null}
      </div>
    );
  }

  if (layout === "twoCol") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
        <div className="flex min-h-0 flex-1 gap-5">
          {figure ? (
            <div className="flex min-w-0 flex-1 flex-col"><Bullets items={bullets} spread presentation={presentation} /></div>
          ) : (
            <BalancedBulletColumns items={bullets} presentation={presentation} />
          )}
          {figure ? <div className="flex w-[42%] min-w-0 flex-col rounded-sm border border-line bg-soft p-3">{figure}</div> : null}
        </div>
      </div>
    );
  }

  if (layout === "diagram") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
        <div className="flex min-h-0 flex-1 gap-6">
          <div className="flex flex-1 flex-col justify-center overflow-hidden rounded-lg border border-[#cbd8ee] bg-white px-6 py-5 shadow-[0_8px_20px_rgb(49_95_198_/_0.06)]">
            <div className="mb-3 flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-blue" aria-hidden /><p className="text-[11px] font-bold tracking-[0.08em] text-blue">{t.slide.diagramCaption}</p></div>
            <div className="min-h-0 flex-1">{figure ?? <p className="text-[13px] text-muted">{t.slide.notGenerated}</p>}</div>
          </div>
          {bullets.length ? (
            <div className="flex w-[38%] flex-col overflow-hidden border-l-2 border-blue pl-5 pt-1">
              <p className="mb-3 text-[11px] font-bold tracking-[0.08em] text-muted">{t.slide.diagramReadingGuide}</p>
              <Bullets items={bullets.slice(0, 4)} spread presentation={presentation} />
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  if (layout === "code") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
        <div className="flex min-h-0 flex-1 gap-4">
          <div className="min-w-0 flex-1 overflow-hidden rounded-sm bg-ink px-5 py-4">
            <ul className="space-y-2 font-mono text-[15px] leading-[1.5] text-[#d9e0e9]">
              {bullets.map((b, i) => (
                <li key={i} className={animationTargetClass(presentation, `bullet:${i}`)}>{b}</li>
              ))}
            </ul>
          </div>
          {figure ? <div className="flex w-[46%] min-w-0 flex-col rounded-sm border border-line bg-soft p-3">{figure}</div> : null}
        </div>
      </div>
    );
  }

  if (layout === "quiz") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
        <ol className="flex min-h-0 flex-1 flex-col justify-evenly">
          {bullets.map((b, i) => (
            <li
              key={i}
              className={cx("flex items-center gap-3 rounded-sm border border-line px-4 py-3 text-[16px] text-ink", animationTargetClass(presentation, `bullet:${i}`))}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full border border-line text-[12px] font-bold text-muted">
                {String.fromCharCode(65 + i)}
              </span>
              <span>{b}</span>
            </li>
          ))}
        </ol>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <SlideTitle targetId={titleTargetId} highlighted={titleFocused} presentation={presentation}>{title}</SlideTitle>
      <div className="flex min-h-0 flex-1 gap-5">
        <div className="flex min-w-0 flex-1 flex-col"><Bullets items={bullets} spread presentation={presentation} /></div>
        {figure ? <div className="flex w-[42%] min-w-0 flex-col rounded-sm border border-line bg-soft p-3">{figure}</div> : null}
      </div>
    </div>
  );
}

export function SlideFrame({
  slide,
  diagramUrl,
  className,
  thumbnail = false,
  focusedField,
  presentation,
}: {
  slide: Slide;
  diagramUrl?: string;
  className?: string;
  thumbnail?: boolean;
  focusedField?: string | null;
  presentation?: AnimationPresentation;
}) {
  const regionTarget = !thumbnail && focusedField && focusedField !== "title"
    ? `slide:${slide.id}:${focusedField}`
    : undefined;
  return (
    <div
      data-review-target={!thumbnail ? `slide:${slide.id}:slide` : undefined}
      className={cx(
        "slide-body aspect-video w-full overflow-hidden rounded-md border border-line bg-surface px-8 py-7",
        className,
      )}
    >
      <div data-review-target={regionTarget} className={cx("h-full", regionTarget && "review-target-highlight")}>
        <SlideBody slide={slide} diagramUrl={diagramUrl} thumbnail={thumbnail} focusedField={focusedField} presentation={presentation} />
      </div>
    </div>
  );
}

/**
 * 左侧课件索引使用和主舞台完全相同的 IR 渲染器。
 * 缩小的是一张真实 16:9 幻灯片,而不是用几根装饰线假装缩略图;
 * 因此标题、要点、图表与主视图永远不会漂移。
 */
export function SlideThumbnail({ slide, diagramUrl }: { slide: Slide; diagramUrl?: string }) {
  return (
    <span className="studio-real-thumbnail" data-real-slide-thumbnail="1" aria-hidden>
      <span className="studio-real-thumbnail__canvas">
        <SlideFrame slide={slide} diagramUrl={diagramUrl} thumbnail className="w-[800px] rounded-sm px-16 py-14" />
      </span>
    </span>
  );
}

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
  const { t } = useI18n();
  const [title, setTitle] = useState(slide.title);
  const [layout, setLayout] = useState(slide.layout);
  const [bullets, setBullets] = useState(slide.bullets.join("\n"));
  const [notes, setNotes] = useState(slide.speakerNotes);

  return (
    <div className="rounded-md border border-blue/40 bg-blue-soft/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t.slide.fieldTitle}>
          <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <Field label={t.slide.fieldLayout}>
          <select
            className={inputCls}
            value={layout}
            onChange={(e) => setLayout(e.target.value)}
          >
            {LAYOUTS.map((l) => (
              <option key={l} value={l}>
                {layoutLabel(t, l)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="mt-3 grid gap-3">
        <Field label={t.slide.fieldBullets} hint={t.setup.onePerLine}>
          <textarea
            rows={4}
            className={inputCls}
            value={bullets}
            onChange={(e) => setBullets(e.target.value)}
          />
        </Field>
        <Field label={t.slide.fieldNotes}>
          <textarea
            rows={3}
            className={inputCls}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          disabled={busy}
          onClick={() =>
            onSave({
              title,
              layout,
              bullets: bullets
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean),
              speakerNotes: notes,
            })
          }
        >
          {t.slide.save}
        </Button>
        <Button disabled={busy} onClick={onCancel}>
          {t.slide.cancel}
        </Button>
        <p className="text-[12px] text-muted">{t.slide.saveNote}</p>
      </div>
    </div>
  );
}

export function SlideCanvas({
  slide,
  diagramUrl,
  index,
  active,
  focusedField,
  current,
  editing,
  busy,
  onEdit,
  onRequestAnimation,
  onCancelEdit,
  onSave,
}: {
  slide: Slide;
  diagramUrl?: string;
  index: number;
  /** 从审阅栏点进来定位到这一页 —— 强提示。 */
  active: boolean;
  /** The selected review patch points to this field without changing its content. */
  focusedField?: string | null;
  /** 只是滚到这里 —— 弱提示,不要和上面那个抢注意力。 */
  current: boolean;
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  /** Creates a proposed animation for this visible slide; it is never applied automatically. */
  onRequestAnimation: () => void;
  onCancelEdit: () => void;
  onSave: (payload: Record<string, unknown>) => void;
}) {
  const { t } = useI18n();

  return (
    <article
      id={`slide-${slide.id}`}
      className={cx(
        "scroll-mt-32 rounded-lg border bg-surface p-4 shadow-card transition-shadow",
        active
          ? "border-blue ring-2 ring-blue/25"
          : current
            ? "border-blue/45"
            : "border-line",
      )}
    >
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <span className="font-mono text-[12px] text-muted">
          {String(index + 1).padStart(2, "0")} · {slide.id}
        </span>
        <Badge>{layoutLabel(t, slide.layout)}</Badge>
        {slide.origin === "sourced" ? (
          <Badge tone="blue">
            <Dot tone="blue" />
            {t.slide.sourced}
          </Badge>
        ) : (
          <Badge tone="amber">
            <Dot tone="amber" />
            {t.slide.aiAdded}
          </Badge>
        )}
        {!editing ? (
          <div className="ml-auto flex items-center gap-1.5">
            <Button
              variant="quiet"
              className="min-h-0 px-2 py-1 text-[13px] text-blue"
              onClick={onRequestAnimation}
              disabled={busy}
            >
              {t.slide.generateAnimation}
            </Button>
            <Button
              variant="quiet"
              className="min-h-0 px-2 py-1 text-[13px]"
              onClick={onEdit}
              disabled={busy}
            >
              {t.slide.edit}
            </Button>
          </div>
        ) : null}
      </header>

      {editing ? (
        <SlideEditor
          key={slide.id}
          slide={slide}
          busy={busy}
          onSave={onSave}
          onCancel={onCancelEdit}
        />
      ) : (
        <>
              {slide.animation ? (
                <SlideAnimationPreview animation={slide.animation}>
                  {(presentation) => (
                    <SlideFrame
                      slide={slide}
                      diagramUrl={diagramUrl}
                      focusedField={focusedField}
                      presentation={presentation}
                    />
                  )}
                </SlideAnimationPreview>
              ) : (
                <SlideFrame
                  slide={slide}
                  diagramUrl={diagramUrl}
                  focusedField={focusedField}
                />
              )}
              <footer className="mt-3 space-y-2">
                {slide.speakerNotes ? (
                  <div>
                    <p
                      data-review-target={focusedField === "speakerNotes" ? `slide:${slide.id}:speakerNotes` : undefined}
                      className={cx("border-l-2 border-line pl-3 text-[13px] leading-[1.5] text-body italic", focusedField === "speakerNotes" && "review-target-highlight")}
                    >
                      {slide.speakerNotes}
                    </p>
                  </div>
                ) : null}
            <div className="flex flex-wrap items-center gap-1.5">
              {slide.objectiveIds.map((o) => (
                <Badge key={o}>{o}</Badge>
              ))}
              {slide.sourceRefs.map((r, i) => (
                <span
                  key={i}
                  className="rounded bg-soft px-1.5 py-0.5 font-mono text-[11px] text-muted"
                >
                  {r.materialId}
                  {r.page != null ? ` p.${r.page}` : ""}
                </span>
              ))}
              {slide.visuals.map((v) => (
                <span
                  key={v.id}
                  className="rounded bg-soft px-1.5 py-0.5 font-mono text-[11px] text-muted"
                >
                  {v.kind} · {v.assetId ?? t.slide.notGenerated}
                </span>
              ))}
            </div>
          </footer>
        </>
      )}
    </article>
  );
}
