"use client";

/**
 * 审阅栏 —— 桌子对面那一侧。
 *
 * 这一栏只放「需要教师做决定的东西」。没有待确认改动时不显示审核占位,
 * 把空间留给课程内容和真正需要处理的反馈。
 *
 * 点任意一条改动会跳到画布上对应那一页 —— 改动和它改的东西必须能对上。
 */

import { useRef } from "react";
import { Badge, Button, Dot, SectionLabel, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { EditAttachment, EditPlan, EditProgressEvent, Patch } from "@/lib/api";

/**
 * 把 L2 的进度帧折叠成「agent 做了哪几步」。
 *
 * 后端对同一个工具会发**两条**帧:status="running"(开始)和
 * status="ok"/"error"(结束)。这里把后者并进前一行,而不是各占一行 ——
 * 否则一次三步的编辑会显示成六行,读起来像两次。
 *
 * 和 L1 的 `deriveSections` 同源:界面是事件流的纯函数,不额外存状态,
 * 也就不可能与事件流不同步。
 */
function deriveSteps(
  frames: EditProgressEvent[],
  roundLabel: (n: number) => string,
): { text: string; status: "running" | "ok" | "error" }[] {
  const rows: { text: string; status: "running" | "ok" | "error" }[] = [];

  for (const f of frames) {
    if (f.kind !== "tool") continue;
    const text = f.detail || f.tool || "";

    if (f.status === "running") {
      rows.push({ text: text ? `${roundLabel(f.turn)} · ${text}` : roundLabel(f.turn), status: "running" });
      continue;
    }

    // ok / error:并进上一行。上一行不在的话(理论上不该发生)就单起一行,
    // 宁可多显示一行,也不要静默丢掉一次工具调用。
    const last = rows.length - 1;
    const status = f.status === "error" ? "error" : "ok";
    if (last >= 0 && rows[last].status === "running") {
      rows[last] = { ...rows[last], status };
    } else {
      rows.push({ text, status });
    }
  }
  return rows;
}

/**
 * agent 正在干什么。
 *
 * 只在忙的时候显示 —— 结束后 `callNames` 那份「What the agent did」才是
 * 该看的东西,两处同时出现就是重复。
 */
function LiveSteps({ frames }: { frames: EditProgressEvent[] }) {
  const { t } = useI18n();
  const steps = deriveSteps(frames, t.margin.agentRound);
  const waitingForModel = frames.length === 0 || frames[frames.length - 1]?.kind === "turn";

  return (
    <div className="mt-2.5 rounded-md border border-line bg-soft px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Dot tone="blue" />
        <span className="text-[12px] font-semibold text-ink">{t.margin.agentWorking}</span>
      </div>

      <ol className="mt-1.5 space-y-1" data-agent-steps={steps.length}>
        {steps.map((s, i) => (
          <li key={i} className="flex items-start gap-2 text-[12px] leading-[1.5]">
            <span className="mt-[5px]">
              <Dot
                tone={s.status === "error" ? "amber" : s.status === "ok" ? "green" : "blue"}
              />
            </span>
            <span className={cx("min-w-0 flex-1", s.status === "running" ? "text-ink" : "text-body")}>
              {s.text}
            </span>
          </li>
        ))}
      </ol>

      {waitingForModel ? (
        <p className="mt-1.5 text-[12px] text-muted">{t.margin.agentWaiting}</p>
      ) : null}
    </div>
  );
}

type DiffTone = "add" | "remove" | "context";

function cleanDiffValue(value: string) {
  const trimmed = value.trim();
  return (trimmed.startsWith("'") && trimmed.endsWith("'")) || (trimmed.startsWith('"') && trimmed.endsWith('"'))
    ? trimmed.slice(1, -1)
    : trimmed;
}

/** Turn the storage diff into a compact reviewable unified diff, not a JSON dump. */
function toGitLines(text: string): { tone: DiffTone; marker: string; content: string }[] {
  return text.split("\n").map((raw) => raw.trimStart()).filter(Boolean).map((line) => {
    const tone: DiffTone = line.startsWith("+") ? "add" : line.startsWith("-") ? "remove" : "context";
    const content = tone === "context" ? line : line.slice(1).trimStart();
    const field = content.match(/^([a-zA-Z][\w]*):\s*(.*)$/);
    return {
      tone,
      marker: tone === "add" ? "+" : tone === "remove" ? "−" : " ",
      content: field ? `${field[1]}: ${cleanDiffValue(field[2])}` : cleanDiffValue(content),
    };
  });
}

/** A compact before/after review block: evidence without repository bookkeeping. */
function GitDiff({ patch }: { patch: Patch }) {
  const lines = toGitLines(patch.diff);
  if (!lines.length) return null;

  return (
    <div className="git-diff mt-2.5" data-git-diff="1">
      <div className="git-diff__body">
        {lines.map((line, index) => (
          <div
            key={`${line.marker}-${index}`}
            className={cx(
              "git-diff__line",
              line.tone === "add" && "git-diff__line--add",
              line.tone === "remove" && "git-diff__line--remove",
              line.tone === "context" && "git-diff__line--context",
            )}
          >
            <span aria-hidden>{line.marker}</span>
            <code>{line.content}</code>
          </div>
        ))}
      </div>
    </div>
  );
}

/** The review surface leads with the diff; teachers can open the reason when they need its context. */
function PatchReason({ reason }: { reason: string }) {
  const { t } = useI18n();
  const normalizedReason = reason.trim().replace(/\s+/g, " ");

  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-[12px] font-medium text-muted hover:text-body">
        {t.margin.viewReason}
      </summary>
      <p className="mt-1.5 text-[12px] leading-[1.5] text-body">{normalizedReason}</p>
    </details>
  );
}

/** Internal target IDs are useful to the system, but teachers should review a human-readable destination. */
function displayPatchTarget(patch: Patch) {
  const slideMatch = patch.kind === "slide" ? /^s(\d+)$/i.exec(patch.target_id) : null;
  if (slideMatch) return `Slide ${Number(slideMatch[1])}`;
  return `${patch.kind} · ${patch.target_id}`;
}

/** Keep the raw model reply available without letting it compete with the diff. */
function AgentReply({ reply, proposalCount }: { reply: string; proposalCount: number }) {
  const { t } = useI18n();

  return (
    <div className="mt-2.5">
      {proposalCount ? (
        <p className="flex items-center gap-2 text-[12px] leading-[1.45] text-body">
          <Dot tone="violet" />
          {t.margin.proposalSummary(proposalCount)}
        </p>
      ) : (
        <p className="text-[12px] leading-[1.5] text-body">{reply.slice(0, 140)}{reply.length > 140 ? "…" : ""}</p>
      )}
      <details className="mt-1.5">
        <summary className="cursor-pointer text-[12px] font-medium text-muted hover:text-body">
          {t.margin.viewAgentReply}
        </summary>
        <p className="mt-1.5 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm bg-soft px-2.5 py-2 text-[12px] leading-[1.55] text-body">
          {reply}
        </p>
      </details>
    </div>
  );
}

function PatchRow({
  patch,
  busy,
  active,
  onApply,
  onReject,
  onFocus,
}: {
  patch: Patch;
  busy: boolean;
  active: boolean;
  onApply: () => void;
  onReject: () => void;
  onFocus: () => void;
}) {
  const { t } = useI18n();
  const proposed = patch.status === "proposed";

  return (
    <li
      onClick={proposed ? onFocus : undefined}
      data-review-card-id={patch.id}
      className={cx(
        "rounded-md border bg-surface p-3",
        active ? "border-blue ring-2 ring-blue/25" : "border-line",
        proposed && "cursor-pointer",
      )}
    >
      <header className="flex flex-wrap items-center gap-1.5">
        <Badge tone={patch.author === "teacher" ? "blue" : "violet"}>
          {patch.author === "teacher" ? t.margin.authorYou : t.margin.authorAi}
        </Badge>
        {proposed ? <Badge tone="violet">{t.margin.waiting}</Badge> : null}
        <span className="text-[13px] text-body">
          {displayPatchTarget(patch)}
        </span>
      </header>

      <GitDiff patch={patch} />
      <PatchReason reason={patch.reason} />

      {proposed ? (
        <div className="mt-2.5 flex gap-2">
          <Button
            variant="primary"
            className="min-h-0 px-3 py-1.5 text-[13px]"
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation();
              onApply();
            }}
          >
            {t.margin.approve}
          </Button>
          <Button
            className="min-h-0 px-3 py-1.5 text-[13px]"
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation();
              onReject();
            }}
          >
            {t.margin.reject}
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-[12px] font-semibold text-muted">
          {patch.status === "applied" ? t.margin.applied : t.margin.rejected}
        </p>
      )}
    </li>
  );
}

/** 已决定的记录不是下一步行动：默认只保留可扫描摘要，需要时再展开证据。 */
function RecordedPatchRow({ patch }: { patch: Patch }) {
  const { t } = useI18n();
  const applied = patch.status === "applied";

  return (
    <li>
      <details className="review-record rounded-md border border-line bg-surface">
        <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2.5 text-[12px] marker:hidden">
          <span className={cx("review-record__status", applied ? "text-green" : "text-muted")}>
            {applied ? t.margin.applied : t.margin.rejected}
          </span>
          <span className="min-w-0 flex-1 truncate text-body">{displayPatchTarget(patch)}</span>
          <span className="review-record__chevron text-muted" aria-hidden>⌄</span>
        </summary>
        <div className="border-t border-line px-3 py-2.5">
          <GitDiff patch={patch} />
          <PatchReason reason={patch.reason} />
        </div>
      </details>
    </li>
  );
}

/** The plan makes the Agent's diagnosis visible before any edit is proposed. */
function AgentPlanCard({ plan, selectedIds, busy, onToggle, onRun }: {
  plan: EditPlan; selectedIds: string[]; busy: boolean; onToggle: (id: string) => void; onRun: () => void;
}) {
  const { t } = useI18n();
  return <section className="mt-3 rounded-md border border-blue/30 bg-blue-soft/40 p-3" aria-label={t.margin.planTitle}>
    <div className="flex items-center gap-2"><span className="grid size-5 place-items-center rounded-full bg-blue text-[10px] font-bold text-white">AI</span><h3 className="text-[13px] font-bold text-ink">{t.margin.planTitle}</h3></div>
    <p className="mt-2 text-[12px] leading-[1.5] text-body">{plan.summary}</p>
    {plan.findings.length ? <ul className="mt-3 space-y-1.5">{plan.findings.map((finding) => <li key={finding.id} className="rounded-sm bg-surface/85 px-2.5 py-2 text-[12px] leading-[1.45] text-body"><strong className="block text-ink">{finding.title}</strong>{finding.detail}</li>)}</ul> : null}
    {plan.actions.length ? <fieldset className="mt-3 space-y-2"><legend className="text-[11px] font-bold uppercase tracking-[0.08em] text-muted">{t.margin.planActions}</legend>{plan.actions.map((action) => <label key={action.id} className="flex cursor-pointer items-start gap-2 rounded-sm border border-line bg-surface px-2.5 py-2"><input type="checkbox" checked={selectedIds.includes(action.id)} disabled={busy} onChange={() => onToggle(action.id)} className="mt-0.5 size-3.5 accent-blue" /><span><strong className="block text-[12px] text-ink">{action.title}</strong><span className="block text-[12px] leading-[1.4] text-body">{action.detail}</span></span></label>)}<Button variant="primary" className="w-full" disabled={busy || !selectedIds.length} onClick={onRun}>{t.margin.runSelected(selectedIds.length)}</Button></fieldset> : null}
  </section>;
}

export function ReviewMargin({
  patches,
  reply,
  callNames,
  integrity,
  busy,
  message,
  attachments,
  editFrames,
  editBusy,
  onMessage,
  onAttachments,
  onSend,
  onApply,
  onReject,
  onFocusTarget,
  focusedPatchId,
  editPlan,
  selectedActionIds,
  onToggleAction,
  onRunPlan,
}: {
  patches: Patch[];
  reply: string;
  callNames: string[];
  /** null = 还没提过改动;true/false = 提议期间产物有没有被改动过。 */
  integrity: boolean | null;
  busy: boolean;
  message: string;
  attachments: EditAttachment[];
  /** L2 的实时进度帧(见 page.tsx 的 onEdit)。 */
  editFrames: EditProgressEvent[];
  /** 正在跑 L2。结束之后显示的是 callNames 那一份,不是这个。 */
  editBusy: boolean;
  onMessage: (v: string) => void;
  onAttachments: (images: EditAttachment[]) => void;
  onSend: () => void;
  onApply: (id: string) => void;
  onReject: (id: string) => void;
  onFocusTarget: (patch: Patch) => void;
  focusedPatchId: string | null;
  editPlan: EditPlan | null;
  selectedActionIds: string[];
  onToggleAction: (id: string) => void;
  onRunPlan: () => void;
}) {
  const { t } = useI18n();
  const imagePickerRef = useRef<HTMLInputElement>(null);
  const proposed = patches.filter((p) => p.status === "proposed");
  const settled = patches.filter((p) => p.status !== "proposed");
  const addFiles = (files: FileList | File[]) => {
    [...files].filter((file) => ["image/png", "image/jpeg", "image/webp"].includes(file.type)).slice(0, Math.max(0, 4 - attachments.length)).forEach((file) => {
      if (file.size > 3 * 1024 * 1024) return;
      const reader = new FileReader();
      reader.onload = () => onAttachments([...attachments, { id: crypto.randomUUID(), name: file.name, dataUrl: String(reader.result) }]);
      reader.readAsDataURL(file);
    });
  };

  return (
    <div className="studio-review-stack space-y-5" data-review-dock="1">
      {proposed.length ? (
        <section>
          <ul className="mt-2.5 space-y-2.5">
            {proposed.map((p, index) => (
              <PatchRow
                key={`${p.id}-${index}`}
                patch={p}
                busy={busy}
                active={focusedPatchId === p.id}
                onApply={() => onApply(p.id)}
                onReject={() => onReject(p.id)}
                onFocus={() => onFocusTarget(p)}
              />
            ))}
          </ul>
        </section>
      ) : null}

      <section className="studio-revision-composer" data-revision-composer="1">
        <div className="mb-3">
          <h2 className="text-[14px] font-semibold tracking-[-0.01em] text-ink">{t.margin.askChange}</h2>
          <p className="mt-1 text-[12px] leading-[1.45] text-muted">{t.margin.revisionHelp}</p>
        </div>
        <textarea
          rows={6}
          className={cx(inputCls, "resize-y")}
          aria-label={t.margin.askChange}
          value={message}
          placeholder={t.margin.placeholder}
          onChange={(e) => onMessage(e.target.value)}
          onPaste={(e) => { const files = e.clipboardData.files; if (files.length) { e.preventDefault(); addFiles(files); } }}
          onDrop={(e) => { e.preventDefault(); addFiles(e.dataTransfer.files); }}
          onDragOver={(e) => e.preventDefault()}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && message.trim() && !busy) { e.preventDefault(); onSend(); } }}
        />
        <input ref={imagePickerRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.currentTarget.value = ""; }} />
        {attachments.length ? <div className="mt-2 flex flex-wrap gap-2" data-revision-attachments="1">{attachments.map((image) => <div key={image.id} className="relative size-14 overflow-hidden rounded-md border border-line bg-surface"><img src={image.dataUrl} alt={image.name} className="size-full object-cover" /><button type="button" aria-label={`Remove ${image.name}`} className="absolute top-0.5 right-0.5 grid size-5 place-items-center rounded-full bg-ink/80 text-[11px] text-white" onClick={() => onAttachments(attachments.filter((item) => item.id !== image.id))}>×</button></div>)}</div> : null}
        <div className="mt-2 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2"><button type="button" className="rounded-md border border-line px-2 py-1 text-[11px] font-semibold text-body hover:bg-soft" onClick={() => imagePickerRef.current?.click()}>Add image</button><p className="text-[11px] leading-[1.4] text-muted">Enter to send · Shift+Enter for a new line</p></div>
          <Button className="shrink-0" variant="primary" disabled={busy || !message.trim()} onClick={onSend}>
            {t.margin.plan}
          </Button>
        </div>

        {busy && !editPlan ? <p className="mt-3 flex items-center gap-2 rounded-sm bg-soft px-3 py-2 text-[12px] text-body"><Dot tone="blue" />{t.margin.planPreparing}</p> : null}
        {editPlan ? <AgentPlanCard plan={editPlan} selectedIds={selectedActionIds} busy={busy || editBusy} onToggle={onToggleAction} onRun={onRunPlan} /> : null}

        {editBusy ? <LiveSteps frames={editFrames} /> : null}

        {reply ? <AgentReply reply={reply} proposalCount={proposed.length} /> : null}

        {integrity !== null ? (
          <p
            className={cx(
              "mt-2.5 rounded-sm px-3 py-2 text-[13px] leading-[1.45]",
              integrity ? "bg-green-soft text-green" : "bg-amber-soft text-amber",
            )}
          >
            {integrity ? t.margin.integrityOk : t.margin.integrityBad}
          </p>
        ) : null}

        {callNames.length ? (
          <details className="mt-2.5">
            <summary className="cursor-pointer text-[12px] font-semibold text-muted">
              {t.margin.agentDid(callNames.length)}
            </summary>
            <p className="mt-1.5 font-mono text-[11px] leading-[1.6] break-all text-muted">
              {callNames.join(" → ")}
            </p>
          </details>
        ) : null}
      </section>

      {settled.length ? (
        <section data-review-records="compact">
          <SectionLabel>{t.margin.recorded} · {settled.length}</SectionLabel>
          <ul className="mt-2.5 space-y-1.5">
                {settled.map((p, index) => <RecordedPatchRow key={`${p.id}-${index}`} patch={p} />)}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
