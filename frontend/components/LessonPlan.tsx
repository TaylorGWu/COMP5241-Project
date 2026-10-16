"use client";

/**
 * 教案视图。
 *
 * 教案**本来就是一条时间线**(一节课 45 分钟),所以这里用序号和分钟刻度是有信息量的,
 * 不是装饰:左边那列是累计分钟,教师一眼能看出哪个环节吃掉了时间。
 */

import { useState } from "react";

import { Badge, Button, Field, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CoursePackage, TimelineEntry } from "@/lib/api";

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
  const { t } = useI18n();
  const [phase, setPhase] = useState(entry.phase);
  const [minutes, setMinutes] = useState(String(entry.minutes));
  const [teacherAction, setTeacherAction] = useState(entry.teacherAction);
  const [studentAction, setStudentAction] = useState(entry.studentAction);
  const [check, setCheck] = useState(entry.checkUnderstanding);

  return (
    <div className="rounded-md border border-blue/40 bg-blue-soft/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t.plan.fieldPhase}>
          <input className={inputCls} value={phase} onChange={(e) => setPhase(e.target.value)} />
        </Field>
        <Field label={t.plan.fieldMinutes}>
          <input
            type="number"
            className={inputCls}
            value={minutes}
            onChange={(e) => setMinutes(e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-3 grid gap-3">
        <Field label={t.plan.fieldTeacher}>
          <textarea
            rows={2}
            className={inputCls}
            value={teacherAction}
            onChange={(e) => setTeacherAction(e.target.value)}
          />
        </Field>
        <Field label={t.plan.fieldStudents}>
          <textarea
            rows={2}
            className={inputCls}
            value={studentAction}
            onChange={(e) => setStudentAction(e.target.value)}
          />
        </Field>
        <Field label={t.plan.fieldCheck}>
          <textarea
            rows={2}
            className={inputCls}
            value={check}
            onChange={(e) => setCheck(e.target.value)}
          />
        </Field>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          variant="primary"
          disabled={busy}
          onClick={() =>
            onSave({
              phase,
              minutes: Number(minutes),
              teacherAction,
              studentAction,
              checkUnderstanding: check,
            })
          }
        >
          {t.slide.save}
        </Button>
        <Button disabled={busy} onClick={onCancel}>
          {t.slide.cancel}
        </Button>
        <p className="text-[12px] text-muted">{t.plan.saveNote}</p>
      </div>
    </div>
  );
}

export function LessonPlan({
  pkg,
  editingId,
  busy,
  pendingByTarget,
  onEdit,
  onCancelEdit,
  onSave,
}: {
  pkg: CoursePackage;
  editingId: string | null;
  busy: boolean;
  pendingByTarget: Record<string, number>;
  onEdit: (id: string) => void;
  onCancelEdit: () => void;
  onSave: (id: string, payload: Record<string, unknown>) => void;
}) {
  const { t } = useI18n();
  const timeline = pkg.lessonPlan?.timeline ?? [];

  if (!timeline.length) {
    return (
      <p className="rounded-md border border-dashed border-line bg-surface px-5 py-10 text-center text-[15px] text-muted">
        {t.plan.empty}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {pkg.lessonPlan?.overview ? (
        <p className="max-w-[70ch] text-[15px] leading-[1.6] text-body">
          {pkg.lessonPlan.overview}
        </p>
      ) : null}

      <ol className="space-y-1">
        {timeline.map((entry, i) => {
          const start = timeline.slice(0, i).reduce((minutes, previous) => minutes + previous.minutes, 0);
          const editing = editingId === entry.id;
          const pending = (pendingByTarget[entry.id] ?? 0) > 0;

          return (
            <li key={entry.id} id={`plan-${entry.id}`} className="flex scroll-mt-32 gap-4">
              <div className="w-10 shrink-0 pt-[18px] text-right">
                <span className="font-mono text-[12px] text-muted">{start}′</span>
              </div>

              <div className="relative flex-1 border-l border-line pb-3 pl-6">
                <span
                  className="absolute top-[19px] -left-[5px] h-[9px] w-[9px] rounded-full border-2 border-canvas bg-blue"
                  aria-hidden
                />

                {editing ? (
                  <TimelineEditor
                    key={entry.id}
                    entry={entry}
                    busy={busy}
                    onSave={(payload) => onSave(entry.id, payload)}
                    onCancel={onCancelEdit}
                  />
                ) : (
                  <div
                    className={cx(
                      "rounded-md border bg-surface p-4 shadow-card",
                      pending ? "border-violet/45 ring-2 ring-violet/20" : "border-line",
                    )}
                  >
                    <header className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[12px] text-muted">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <h3 className="text-[17px] font-bold tracking-[-0.02em] text-ink">
                        {entry.phase}
                      </h3>
                      <Badge>
                        {entry.minutes} {t.setup.minutes}
                      </Badge>
                      {pending ? (
                        <Badge tone="violet">{t.slide.proposed(pendingByTarget[entry.id])}</Badge>
                      ) : null}
                      <Button
                        variant="quiet"
                        className="ml-auto min-h-0 px-2 py-1 text-[13px]"
                        onClick={() => onEdit(entry.id)}
                        disabled={busy}
                      >
                        {t.slide.edit}
                      </Button>
                    </header>

                    <dl className="mt-3 grid gap-2.5 text-[15px] leading-[1.5] sm:grid-cols-2">
                      <div>
                        <dt className="text-[12px] font-bold text-muted">{t.plan.teacher}</dt>
                        <dd className="mt-0.5 text-ink">{entry.teacherAction}</dd>
                      </div>
                      <div>
                        <dt className="text-[12px] font-bold text-muted">{t.plan.students}</dt>
                        <dd className="mt-0.5 text-ink">{entry.studentAction}</dd>
                      </div>
                    </dl>

                    {entry.checkUnderstanding ? (
                      <p className="mt-3 border-l-2 border-green/40 bg-green-soft/60 py-1.5 pl-3 text-[14px] leading-[1.5] text-green">
                        {t.plan.check}: {entry.checkUnderstanding}
                      </p>
                    ) : null}

                    {entry.slideIds.length ? (
                      <div className="mt-3 flex flex-wrap items-center gap-1.5">
                        <span className="text-[12px] text-muted">{t.plan.slides}</span>
                        {entry.slideIds.map((s) => (
                          <button
                            key={s}
                            type="button"
                            onClick={() =>
                              document
                                .getElementById(`slide-${s}`)
                                ?.scrollIntoView({ behavior: "smooth", block: "center" })
                            }
                            className="rounded bg-soft px-1.5 py-0.5 font-mono text-[11px] text-blue"
                          >
                            {s}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
