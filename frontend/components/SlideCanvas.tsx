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

import { useState } from "react";

import { Badge, Button, Dot, Field, cx, inputCls } from "@/components/ui";
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

function SlideTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-5 text-[27px] leading-[1.14] font-bold tracking-[-0.035em] text-ink">
      {children}
    </h3>
  );
}

function Bullets({ items, twoCol }: { items: string[]; twoCol?: boolean }) {
  if (!items.length) return null;
  return (
    <ul className={twoCol ? "columns-2 gap-9" : "space-y-3"}>
      {items.map((b, i) => (
        <li
          key={i}
          className={cx(
            "flex break-inside-avoid gap-3 text-[17px] leading-[1.42] text-ink",
            twoCol && "mb-3",
          )}
        >
          <span className="mt-[9px] h-[5px] w-[5px] shrink-0 rounded-full bg-blue" aria-hidden />
          <span>{b}</span>
        </li>
      ))}
    </ul>
  );
}

/** 按 layout 渲染版面。每个分支都只读 IR,不读任何界面状态。 */
function SlideBody({ slide }: { slide: Slide }) {
  const { t } = useI18n();
  const { layout, title, bullets } = slide;
  const visual = slide.visuals[0];

  if (layout === "title") {
    return (
      <div className="flex h-full flex-col justify-center">
        <h3 className="max-w-[20ch] text-[36px] leading-[1.06] font-bold tracking-[-0.045em] text-ink">
          {title}
        </h3>
        {bullets[0] ? (
          <p className="mt-4 max-w-[46ch] text-[17px] leading-[1.5] text-body">{bullets[0]}</p>
        ) : null}
      </div>
    );
  }

  if (layout === "twoCol") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle>{title}</SlideTitle>
        <Bullets items={bullets} twoCol />
      </div>
    );
  }

  if (layout === "diagram") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle>{title}</SlideTitle>
        <div className="flex min-h-0 flex-1 gap-6">
          {/* 图还没渲染成 PNG 之前把源码显示出来 ——
              一个空框说明不了任何事,源码至少告诉你这张图会画成什么。 */}
          <div className="flex flex-1 flex-col justify-center gap-2.5 overflow-hidden rounded-sm border border-dashed border-line bg-soft px-5 py-4">
            <p className="font-mono text-[11px] font-bold tracking-[0.08em] text-muted uppercase">
              {visual?.kind ?? "figure"} ·{" "}
              {visual?.assetId ? visual.assetId : t.slide.notGenerated}
            </p>
            {visual?.spec?.code ? (
              <pre className="overflow-hidden font-mono text-[13px] leading-[1.5] whitespace-pre-wrap text-body">
                {visual.spec.code}
              </pre>
            ) : (
              <p className="text-[13px] text-muted">{t.slide.noSource}</p>
            )}
          </div>
          {bullets.length ? (
            <div className="w-[38%] overflow-hidden">
              <Bullets items={bullets.slice(0, 4)} />
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  if (layout === "code") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle>{title}</SlideTitle>
        <div className="min-h-0 flex-1 overflow-hidden rounded-sm bg-ink px-5 py-4">
          <ul className="space-y-2 font-mono text-[15px] leading-[1.5] text-[#d9e0e9]">
            {bullets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  if (layout === "quiz") {
    return (
      <div className="flex h-full flex-col">
        <SlideTitle>{title}</SlideTitle>
        <ol className="space-y-3">
          {bullets.map((b, i) => (
            <li
              key={i}
              className="flex items-center gap-3 rounded-sm border border-line px-4 py-3 text-[16px] text-ink"
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
      <SlideTitle>{title}</SlideTitle>
      <Bullets items={bullets} />
    </div>
  );
}

export function SlideFrame({ slide, className }: { slide: Slide; className?: string }) {
  return (
    <div
      className={cx(
        "slide-body aspect-video w-full overflow-hidden rounded-md border border-line bg-surface px-8 py-7",
        className,
      )}
    >
      <SlideBody slide={slide} />
    </div>
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
  index,
  pendingCount,
  active,
  current,
  editing,
  busy,
  onEdit,
  onCancelEdit,
  onSave,
}: {
  slide: Slide;
  index: number;
  pendingCount: number;
  /** 从审阅栏点进来定位到这一页 —— 强提示。 */
  active: boolean;
  /** 只是滚到这里 —— 弱提示,不要和上面那个抢注意力。 */
  current: boolean;
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: (payload: Record<string, unknown>) => void;
}) {
  const { t } = useI18n();
  const pending = pendingCount > 0;

  return (
    <article
      id={`slide-${slide.id}`}
      className={cx(
        "scroll-mt-32 rounded-lg border bg-surface p-4 shadow-card transition-shadow",
        active
          ? "border-blue ring-2 ring-blue/25"
          : pending
            ? "border-violet/45 ring-2 ring-violet/20"
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
        {pending ? (
          <Badge tone="violet">{t.slide.proposed(pendingCount)}</Badge>
        ) : null}
        {!editing ? (
          <Button
            variant="quiet"
            className="ml-auto min-h-0 px-2 py-1 text-[13px]"
            onClick={onEdit}
            disabled={busy}
          >
            {t.slide.edit}
          </Button>
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
          <SlideFrame slide={slide} />
          <footer className="mt-3 space-y-2">
            {slide.speakerNotes ? (
              <p className="border-l-2 border-line pl-3 text-[13px] leading-[1.5] text-body italic">
                {slide.speakerNotes}
              </p>
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
