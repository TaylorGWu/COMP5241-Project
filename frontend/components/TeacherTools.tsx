"use client";

/**
 * 教师端后几步 —— 出题、组卷、术语白话化、导出。
 *
 * ═══════════════════════════════════════════════════════════════
 * 为什么单独一个组件,而不是塞进审阅栏
 * ═══════════════════════════════════════════════════════════════
 * 审阅栏的职责是「要我决定什么」—— 待确认的改动、覆盖度缺口。
 * 这一块是「再产出点什么」,性质不同:它不产生待确认的东西,
 * 出题和组卷都是直接生成新产物。
 *
 * 混在一起的话,审阅栏上会同时出现「需要你点同意」和「点一下就行」,
 * 而那正是最容易让人误点的地方。
 *
 * ═══════════════════════════════════════════════════════════════
 * 组卷的状态是算出来的,不是记住的
 * ═══════════════════════════════════════════════════════════════
 * 组卷接口返回 `ok` / `reason`。但刷新页面之后那个响应就没了 ——
 * 只剩产物里的卷子。所以这里**从产物现算**总分配不配得上约束,
 * 而不是依赖上一次的响应。这样刷新前后看到的是同一件事。
 */

import { useState, type ReactNode } from "react";

import { Button, Card, Dot, Field, SectionLabel, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { exportUrls, type CoursePackage, type Question } from "@/lib/api";

export function TeacherTools({
  pkg,
  courseId,
  chapterId,
  section,
  busy,
  onQuestions,
  onPaper,
  onGlossary,
}: {
  pkg: CoursePackage;
  courseId: string;
  chapterId: string;
  section: "questions" | "glossary" | "paper";
  busy: boolean;
  onQuestions: () => void;
  onPaper: (totalPoints: number, durationMin: number) => void;
  onGlossary: () => void;
}) {
  const { t } = useI18n();

  const questions = pkg.questionSet?.questions ?? [];
  const paper = pkg.examPaper ?? null;
  const glossary = pkg.project.glossary ?? [];

  // A teacher-entered target takes priority; otherwise derive it from the
  // current IR so newly generated questions do not leave a stale 100-point default.
  const [totalInput, setTotalInput] = useState<number | null>(null);
  const availablePoints = questions.reduce((sum, question) => sum + question.points, 0);
  const total = totalInput ?? paper?.constraints.totalPoints ?? (availablePoints || 100);
  const [duration, setDuration] = useState<number>(
    paper?.constraints.durationMin ?? 90,
  );

  // 卷子实际多少分 —— 从产物现算,刷新前后一致
  const pickedIds = new Set(paper?.sections.flatMap((s) => s.questionIds) ?? []);
  const actualPoints = questions
    .filter((q) => pickedIds.has(q.id))
    .reduce((sum, q) => sum + q.points, 0);
  const targetPoints = paper?.constraints.totalPoints ?? 0;
  const paperExact = paper !== null && actualPoints === targetPoints;

  return (
    <section
      className="min-w-0"
      // data-* 是给验证脚本读的**稳定契约**。断言文字的话,
      // 改一次文案或加一种语言,脚本就会「通过」—— 因为它什么都没匹配到。
      data-teacher-tools="1"
      data-questions={questions.length}
      data-glossary={glossary.length}
      data-paper={paper ? (paperExact ? "exact" : "short") : "none"}
      data-paper-points={actualPoints}
      data-paper-target={targetPoints}
    >
      {section === "questions" ? (
        <ToolCard
          title={t.tools.questions}
          action={
            <Button
              data-question-action="regenerate"
              className="min-h-0 shrink-0 px-3 py-1.5 text-[12px]"
              disabled={busy}
              onClick={onQuestions}
            >
              {questions.length ? t.tools.questionsAgain : t.tools.generateQuestions}
            </Button>
          }
        >
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
            <p className="text-muted">
              {questions.length ? t.tools.questionsNote(questions.length) : t.tools.notYet}
            </p>
            {questions.length ? (
              <p className="flex items-center gap-2 text-body">
                <Dot tone="green" />
                {t.tools.difficultySpread(
                  Math.min(...questions.map((q) => q.difficulty)),
                  Math.max(...questions.map((q) => q.difficulty)),
                )}
              </p>
            ) : null}
          </div>
          {questions.length ? <QuestionPreview questions={questions} /> : null}
        </ToolCard>
      ) : null}
      {section === "glossary" ? (
        <ToolCard title={t.tools.glossary}>
          <p className="text-[13px] leading-[1.45] text-muted">
            {glossary.length ? t.tools.glossaryNote(glossary.length) : t.tools.notYet}
          </p>
          <Button className="mt-3 min-h-0 w-full px-3 py-2 text-[13px]" disabled={busy} onClick={onGlossary}>
            {t.tools.generateGlossary}
          </Button>
          {glossary.length ? (
            <dl className="mt-4 divide-y divide-line border-t border-line" data-glossary-preview="1">
              {glossary.map((entry) => (
                <div key={entry.term} className="grid gap-1 py-3 sm:grid-cols-[minmax(120px,0.32fr)_1fr] sm:gap-5">
                  <dt className="text-[14px] font-semibold text-ink">{entry.term}</dt>
                  <dd className="text-[13px] leading-[1.55] text-body">{entry.plain}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </ToolCard>
      ) : null}
      {section === "paper" ? (
        <div className="space-y-3">
        <ToolCard title={t.tools.paper}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.tools.paperTotal}>
              <input type="number" data-field="total" className={cx(inputCls, "py-2 text-[14px]")} value={total} onChange={(e) => setTotalInput(Number(e.target.value))} />
            </Field>
            <Field label={t.tools.paperDuration}>
              <input type="number" data-field="duration" className={cx(inputCls, "py-2 text-[14px]")} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
            </Field>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="primary" className="min-h-0 px-4 py-2 text-[13px]" disabled={busy || questions.length === 0} onClick={() => onPaper(total, duration)}>
              {t.tools.generatePaper}
            </Button>
            {paper ? (
              <span className={cx("flex items-center gap-2 text-[12px]", paperExact ? "text-body" : "text-amber")} data-paper={paperExact ? "exact" : "short"}>
                <Dot tone={paperExact ? "green" : "amber"} />
                {paperExact ? t.tools.paperExact(targetPoints) : t.tools.paperShort(actualPoints, targetPoints)}
              </span>
            ) : <span className="text-[12px] text-muted">{t.tools.notYet}</span>}
          </div>
        </ToolCard>

        </div>
      ) : null}
    </section>
  );
}

/** Export is an action beside the material tabs, not another document to review. */
export function ExportMenu({
  pkg,
  courseId,
  chapterId,
  label,
}: {
  pkg: CoursePackage;
  courseId: string;
  chapterId: string;
  label: string;
}) {
  const { t } = useI18n();
  const [includeQuestions, setIncludeQuestions] = useState(false);
  const questions = pkg.questionSet?.questions ?? [];
  const paper = pkg.examPaper ?? null;

  return (
    <details className="relative" data-export-menu="1">
      <summary className="flex min-h-10 cursor-pointer list-none items-center rounded-md px-3.5 text-[13px] font-semibold text-muted transition-colors hover:bg-soft hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-blue [&::-webkit-details-marker]:hidden">
        {label}
      </summary>
      <div className="absolute top-full right-0 z-30 mt-2 w-[288px] rounded-md border border-line bg-surface p-3 shadow-card">
        <label className="flex cursor-pointer items-center gap-2 text-[13px] leading-[1.4] text-body">
          <input
            type="checkbox"
            checked={includeQuestions}
            disabled={questions.length === 0}
            onChange={(event) => setIncludeQuestions(event.target.checked)}
          />
          Include questions after the lesson
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          <ExportLink kind="deck" href={exportUrls.deck(courseId, chapterId, includeQuestions)} label={t.tools.exportDeck} />
          <ExportLink kind="plan" href={exportUrls.lessonPlan()} label={t.tools.exportPlan} />
          <ExportLink kind="exam-teacher" href={exportUrls.examPaper(true)} label={t.tools.exportExamTeacher} disabled={!paper} />
          <ExportLink kind="exam-student" href={exportUrls.examPaper(false)} label={t.tools.exportExamStudent} disabled={!paper} />
        </div>
        <p className="mt-3 text-[12px] leading-[1.45] text-muted">{t.tools.exportNote}</p>
      </div>
    </details>
  );
}

/**
 * 题库是教师端的真实产物，不能只用「已生成 4 题」代替它。
 * 教师可先作答查看反馈；这只是预览，不会计入学生记录或改动题库。
 */
function QuestionPreview({ questions }: { questions: Question[] }) {
  return (
    <ol className="mt-4 space-y-3 border-t border-line pt-3" data-question-preview="1">
      {questions.map((question, index) => {
        return <QuestionTrial key={question.id} question={question} index={index} />;
      })}
    </ol>
  );
}

function QuestionTrial({ question, index }: { question: Question; index: number }) {
  const [selected, setSelected] = useState<string | null>(null);
  const answer = question.options.find((option) => option.id === question.answer)?.text ?? question.answer;
  const correct = selected === question.answer;
  return (
    <li className="rounded-sm border border-line bg-soft p-3" data-question-id={question.id} data-question-interaction="trial">
      <div className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-muted"><span>Q{index + 1}</span><span className="rounded-full bg-surface px-2 py-0.5">{question.type}</span><span>{question.points} pts · difficulty {question.difficulty}</span></div>
      <p className="mt-2 text-[14px] font-semibold leading-[1.45] text-ink">{question.stem}</p>
      {question.options.length ? <div className="mt-3 grid gap-2 sm:grid-cols-2">{question.options.map((option) => <button key={option.id} type="button" onClick={() => setSelected(option.id)} className={cx("rounded-sm border px-3 py-2 text-left text-[13px] leading-[1.4] transition-colors", selected === option.id ? (correct ? "border-green bg-green-soft text-ink" : "border-amber bg-amber-soft text-ink") : "border-line bg-surface text-body hover:border-blue")}>{option.id}. {option.text}</button>)}</div> : null}
      {selected ? <div className={cx("mt-3 border-t pt-2 text-[13px] leading-[1.45]", correct ? "border-green/30 text-green" : "border-amber/35 text-body")}><p className="font-semibold">{correct ? "Correct" : `Not quite — answer: ${answer}`}</p><p className="mt-1 text-muted">{question.explanation}</p></div> : <p className="mt-3 text-[12px] text-muted">Choose an option to preview learner feedback.</p>}
    </li>
  );
}

function ToolCard({
  title,
  action,
  className,
  children,
}: {
  title: string;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <Card className={cx("p-4", className)}>
      <header className="flex min-h-8 items-center justify-between gap-3">
        <SectionLabel>{title}</SectionLabel>
        {action}
      </header>
      <div className="mt-3">{children}</div>
    </Card>
  );
}

/**
 * 下载链接。
 *
 * 用 `<a download>` 而不是 fetch 之后造 Blob —— 后端已经给了
 * `Content-Disposition`,浏览器自己会下。少一次内存拷贝,也少一段代码。
 */
function ExportLink({
  kind,
  href,
  label,
  disabled = false,
}: {
  kind: string;
  href: string;
  label: string;
  disabled?: boolean;
}) {
  if (disabled) {
    return (
      <span
        data-export={kind}
        data-export-ready="false"
        className="rounded-sm border border-line bg-soft px-2 py-0.5 text-[12px] text-muted"
      >
        {label}
      </span>
    );
  }
  return (
    <a
      data-export={kind}
      data-export-ready="true"
      href={href}
      className="rounded-sm border border-line bg-surface px-2 py-0.5 text-[12px] text-body transition-colors hover:border-blue hover:text-blue focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue"
    >
      {label}
    </a>
  );
}
