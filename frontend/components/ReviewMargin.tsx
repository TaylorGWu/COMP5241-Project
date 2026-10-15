"use client";

/**
 * 审阅栏 —— 桌子对面那一侧。
 *
 * 这一栏只放「需要教师做决定的东西」。而且它**空着的时候也要有用**:
 * 没有待确认改动时,这里显示还有哪些学习目标没人覆盖、以及改动历史,
 * 而不是一句「没东西」把一栏 360px 浪费掉。
 *
 * 点任意一条改动会跳到画布上对应那一页 —— 改动和它改的东西必须能对上。
 */

import { Badge, Button, Dot, SectionLabel, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { EditProgressEvent, Patch } from "@/lib/api";

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

/** 把后端给的 diff 文本按行着色。`+` 绿、`-` 琥珀,其余中性。 */
function Diff({ text }: { text: string }) {
  const lines = text.split("\n").filter((l) => l.trim().length);
  if (!lines.length) return null;
  return (
    <pre className="mt-2 overflow-x-auto rounded-sm bg-soft p-2.5 font-mono text-[12px] leading-[1.6]">
      {lines.map((l, i) => (
        <div
          key={i}
          className={cx(
            "whitespace-pre",
            l.startsWith("+") && "text-green",
            l.startsWith("-") && "text-amber",
          )}
        >
          {l}
        </div>
      ))}
    </pre>
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
      className={cx(
        "rounded-md border bg-surface p-3",
        active ? "border-blue ring-2 ring-blue/25" : "border-line",
        proposed && "cursor-pointer",
      )}
    >
      <header className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-[11px] text-muted">{patch.id}</span>
        <Badge tone={patch.author === "teacher" ? "blue" : "violet"}>
          {patch.author === "teacher" ? t.margin.authorYou : t.margin.authorAi}
        </Badge>
        <span className="text-[13px] text-body">
          {patch.kind} → <span className="font-mono text-[12px]">{patch.target_id}</span>
        </span>
      </header>

      <p className="mt-1.5 text-[13px] leading-[1.5] text-body">{patch.reason}</p>
      <Diff text={patch.diff} />

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

export function ReviewMargin({
  patches,
  reply,
  callNames,
  integrity,
  busy,
  message,
  editFrames,
  editBusy,
  onMessage,
  onSend,
  onApply,
  onReject,
  onFocusTarget,
  focusedTarget,
  coverage,
  onRequestCoverage,
}: {
  patches: Patch[];
  reply: string;
  callNames: string[];
  /** null = 还没提过改动;true/false = 提议期间产物有没有被改动过。 */
  integrity: boolean | null;
  busy: boolean;
  message: string;
  /** L2 的实时进度帧(见 page.tsx 的 onEdit)。 */
  editFrames: EditProgressEvent[];
  /** 正在跑 L2。结束之后显示的是 callNames 那一份,不是这个。 */
  editBusy: boolean;
  onMessage: (v: string) => void;
  onSend: () => void;
  onApply: (id: string) => void;
  onReject: (id: string) => void;
  onFocusTarget: (patch: Patch) => void;
  focusedTarget: string | null;
  /** 每个学习目标被多少页课件引用。0 = 缺口。 */
  coverage: { id: string; text: string; count: number }[];
  /** 点一个缺口 → 把「请补上这个目标」写进输入框。 */
  onRequestCoverage: (objective: { id: string; text: string }) => void;
}) {
  const { t } = useI18n();
  const proposed = patches.filter((p) => p.status === "proposed");
  const settled = patches.filter((p) => p.status !== "proposed");
  const gaps = coverage.filter((c) => c.count === 0);

  return (
    <div className="space-y-5">
      <section>
        <SectionLabel>{t.margin.waiting}</SectionLabel>
        {proposed.length ? (
          <ul className="mt-2.5 space-y-2.5">
            {proposed.map((p) => (
              <PatchRow
                key={p.id}
                patch={p}
                busy={busy}
                active={focusedTarget === p.target_id}
                onApply={() => onApply(p.id)}
                onReject={() => onReject(p.id)}
                onFocus={() => onFocusTarget(p)}
              />
            ))}
          </ul>
        ) : (
          <p className="mt-2.5 rounded-sm border border-dashed border-line bg-surface px-3 py-2.5 text-[13px] leading-[1.45] text-muted">
            {t.margin.nothingWaiting}
          </p>
        )}
      </section>

      {/* ── 覆盖度缺口。审阅栏空着的时候,这里才是它该显示的东西 ── */}
      <section>
        <SectionLabel>{t.coverage.gapsTitle}</SectionLabel>
        {gaps.length ? (
          <ul className="mt-2.5 space-y-1.5">
            {gaps.map((g) => (
              <li key={g.id}>
                <button
                  type="button"
                  onClick={() => onRequestCoverage(g)}
                  className="flex w-full items-start gap-2 rounded-sm border border-amber/30 bg-amber-soft px-3 py-2 text-left transition-colors hover:border-amber/60"
                >
                  <span className="mt-[5px]">
                    <Dot tone="amber" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-mono text-[11px] font-bold text-amber">{g.id}</span>
                    <span className="block text-[13px] leading-[1.45] text-ink">{g.text}</span>
                    <span className="mt-0.5 block text-[12px] text-amber">{t.coverage.gapHint}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2.5 flex items-start gap-2 rounded-sm bg-green-soft px-3 py-2.5 text-[13px] leading-[1.45] text-green">
            <span className="mt-[5px]">
              <Dot tone="green" />
            </span>
            {t.coverage.allCovered}
          </p>
        )}
      </section>

      <section>
        <SectionLabel>{t.margin.askChange}</SectionLabel>
        <div className="mt-2.5 flex gap-2">
          <input
            className={inputCls}
            value={message}
            placeholder={t.margin.placeholder}
            onChange={(e) => onMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !busy && message.trim()) onSend();
            }}
          />
          <Button variant="primary" disabled={busy || !message.trim()} onClick={onSend}>
            {t.margin.send}
          </Button>
        </div>

        {editBusy ? <LiveSteps frames={editFrames} /> : null}

        {reply ? (
          <p className="mt-2.5 rounded-md border border-violet/25 bg-violet-soft px-3 py-2.5 text-[14px] leading-[1.5] text-ink">
            {reply}
          </p>
        ) : null}

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

      <section>
        <SectionLabel>{t.margin.recorded}</SectionLabel>
        {settled.length ? (
          <ul className="mt-2.5 space-y-2.5">
            {settled.map((p) => (
              <PatchRow
                key={p.id}
                patch={p}
                busy={busy}
                active={false}
                onApply={() => {}}
                onReject={() => {}}
                onFocus={() => {}}
              />
            ))}
          </ul>
        ) : (
          <p className="mt-2.5 text-[13px] text-muted">{t.margin.historyEmpty}</p>
        )}
      </section>
    </div>
  );
}
