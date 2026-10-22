"use client";

/**
 * 基础控件。
 *
 * 这一层只负责「长什么样」,不含业务。数值全部来自 globals.css 里的设计令牌,
 * 和 `docs/prototypes/styles.css` 是同一套。
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

export type Tone = "neutral" | "blue" | "green" | "violet" | "amber";

const BADGE_TONE: Record<Tone, string> = {
  neutral: "bg-soft text-body",
  blue: "bg-blue-soft text-blue",
  green: "bg-green-soft text-green",
  violet: "bg-violet-soft text-violet",
  amber: "bg-amber-soft text-amber",
};

const DOT_TONE: Record<Tone, string> = {
  neutral: "bg-muted",
  blue: "bg-blue",
  green: "bg-green",
  violet: "bg-violet",
  amber: "bg-amber",
};

export function Badge({
  tone = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2 py-[3px] text-[12px] font-semibold whitespace-nowrap",
        BADGE_TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/** 徽标里的小圆点。用来在不增加文字的情况下区分状态。 */
export function Dot({ tone = "neutral" }: { tone?: Tone }) {
  return <span className={cx("h-[6px] w-[6px] shrink-0 rounded-full", DOT_TONE[tone])} aria-hidden />;
}

/** Compact section label without decorative markers. */
export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cx("text-[12px] font-bold text-body", className)}>{children}</p>
  );
}

/**
 * 分段切换。视图切换、界面语言、教材语言共用同一个控件 ——
 * 同一种交互只应该有一种长相。
 */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: T;
  options: { value: T; label: string; title?: string }[];
  onChange: (v: T) => void;
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cx("flex rounded-sm border border-line bg-surface p-0.5", className)}
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          title={o.title ?? o.label}
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "flex-1 rounded-[6px] px-2.5 py-1.5 text-[13px] font-semibold whitespace-nowrap transition-colors",
            value === o.value ? "bg-blue-soft text-blue" : "text-body hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "quiet";
};export function Button({ variant = "ghost", className, ...props }: ButtonProps) {
  const variants = {
    primary: "bg-blue text-white hover:bg-blue-deep",
    ghost: "border border-line bg-surface text-ink hover:bg-soft",
    quiet: "text-body hover:text-ink",
  };
  return (
    <button
      className={cx(
        "inline-flex min-h-[38px] items-center justify-center gap-2 rounded-sm px-4 text-[15px] font-semibold transition-colors active:translate-y-px disabled:cursor-not-allowed disabled:border-transparent disabled:bg-[#e4e9f1] disabled:text-[#596b82] disabled:shadow-none disabled:active:translate-y-0",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <section className={cx("rounded-md border border-line bg-surface shadow-card", className)}>
      {children}
    </section>
  );
}

/** 输入框统一样式。焦点环交给 globals.css 里的 `:focus-visible`,这里不覆盖。 */
export const inputCls =
  "w-full rounded-sm border border-line bg-surface px-3 py-2 text-[15px] text-ink placeholder:text-muted focus:border-blue";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-[13px] font-semibold text-body">{label}</span>
      {hint ? <span className="ml-2 text-[12px] text-muted">{hint}</span> : null}
      <span className="mt-1.5 block">{children}</span>
    </label>
  );
}

/**
 * 出错时的提示条。
 * 文案规则:说清发生了什么、下一步能做什么,不道歉、不含糊。
 */
export function ErrorBar({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-amber/30 bg-amber-soft px-4 py-3">
      <p className="flex-1 text-[14px] leading-[1.5] text-amber">{message}</p>
      {onDismiss ? (
        <button
          onClick={onDismiss}
          className="text-[13px] font-semibold text-amber underline underline-offset-2"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}
