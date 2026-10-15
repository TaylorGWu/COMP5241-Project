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

import { useEffect, useState, type ReactNode } from "react";

import { Button, Card, Dot, Field, SectionLabel, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { exportUrls, type CoursePackage, type Question } from "@/lib/api";

export function TeacherTools({
  pkg,
  busy,
  onQuestions,
  onPaper,
  onGlossary,
}: {
  pkg: CoursePackage;
  busy: boolean;
  onQuestions: () => void;
  onPaper: (totalPoints: number, durationMin: number) => void;
  onGlossary: () => void;
}) {
  const { t } = useI18n();

  const questions = pkg.questionSet?.questions ?? [];
  const paper = pkg.examPaper ?? null;
  const glossary = pkg.project.glossary ?? [];

  // 默认总分取卷子自己的约束,其次按题量估一个整数
  const [total, setTotal] = useState<number>(
    paper?.constraints.totalPoints ?? 100,
  );
  const [duration, setDuration] = useState<number>(
    paper?.constraints.durationMin ?? 90,
  );

  // 题库刚生成时，旧的固定 100 分通常凑不出来（例如只有 30 分题目）。
  // 没有现成试卷时，把默认目标同步到可用总分，确保教师第一次点「组卷」
  // 得到的是一份可用的卷子；教师仍可自行改成其他分值。
  useEffect(() => {
    if (paper) return;
    const availablePoints = questions.reduce((sum, question) => sum + question.points, 0);
    if (availablePoints > 0) setTotal(availablePoints);
  }, [paper, questions]);

  // 卷子实际多少分 —— 从产物现算,刷新前后一致
  const pickedIds = new Set(paper?.sections.flatMap((s) => s.questionIds) ?? []);
  const actualPoints = questions
    .filter((q) => pickedIds.has(q.id))
    .reduce((sum, q) => sum + q.points, 0);
  const targetPoints = paper?.constraints.totalPoints ?? 0;
  const paperExact = paper !== null && actualPoints === targetPoints;

  return (
    <section
      className="mt-6 border-t border-line pt-5"
      // data-* 是给验证脚本读的**稳定契约**。断言文字的话,
      // 改一次文案或加一种语言,脚本就会「通过」—— 因为它什么都没匹配到。
      data-teacher-tools="1"
      data-questions={questions.length}
      data-glossary={glossary.length}
      data-paper={paper ? (paperExact ? "exact" : "short") : "none"}
      data-paper-points={actualPoints}
      data-paper-target={targetPoints}
    >
      <SectionLabel>{t.tools.title}</SectionLabel>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ToolCard title={t.tools.questions}>
          <p className="text-[13px] leading-[1.45] text-muted">
            {questions.length ? t.tools.questionsNote(questions.length) : t.tools.notYet}
          </p>
          {questions.length ? (
            <p className="mt-2 flex items-center gap-2 text-[12px] text-body">
              <Dot tone="green" />
              {t.tools.difficultySpread(
                Math.min(...questions.map((q) => q.difficulty)),
                Math.max(...questions.map((q) => q.difficulty)),
              )}
            </p>
          ) : null}
          <Button className="mt-3 min-h-0 w-full px-3 py-2 text-[13px]" disabled={busy} onClick={onQuestions}>
            {questions.length ? t.tools.questionsAgain : t.tools.questions}
          </Button>
          {questions.length ? <QuestionPreview questions={questions} /> : null}
        </ToolCard>

        <ToolCard title={t.tools.glossary}>
          <p className="text-[13px] leading-[1.45] text-muted">
            {glossary.length ? t.tools.glossaryNote(glossary.length) : t.tools.notYet}
          </p>
          <Button className="mt-3 min-h-0 w-full px-3 py-2 text-[13px]" disabled={busy} onClick={onGlossary}>
            {t.tools.glossary}
          </Button>
        </ToolCard>

        <ToolCard title={t.tools.paper} className="md:col-span-2">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.tools.paperTotal}>
              <input type="number" data-field="total" className={cx(inputCls, "py-2 text-[14px]")} value={total} onChange={(e) => setTotal(Number(e.target.value))} />
            </Field>
            <Field label={t.tools.paperDuration}>
              <input type="number" data-field="duration" className={cx(inputCls, "py-2 text-[14px]")} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
            </Field>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="primary" className="min-h-0 px-4 py-2 text-[13px]" disabled={busy || questions.length === 0} onClick={() => onPaper(total, duration)}>
              {t.tools.paper}
            </Button>
            {paper ? (
              <span className={cx("flex items-center gap-2 text-[12px]", paperExact ? "text-body" : "text-amber")} data-paper={paperExact ? "exact" : "short"}>
                <Dot tone={paperExact ? "green" : "amber"} />
                {paperExact ? t.tools.paperExact(targetPoints) : t.tools.paperShort(actualPoints, targetPoints)}
              </span>
            ) : <span className="text-[12px] text-muted">{t.tools.notYet}</span>}
          </div>
        </ToolCard>

        <ToolCard title={t.tools.export} className="md:col-span-2">
          <div className="flex flex-wrap gap-2">
          <ExportLink
            kind="deck"
            href={exportUrls.deck()}
            label={t.tools.exportDeck}
          />
          <ExportLink
            kind="plan"
            href={exportUrls.lessonPlan()}
            label={t.tools.exportPlan}
          />
          <ExportLink
            kind="exam-teacher"
            href={exportUrls.examPaper(true)}
            label={t.tools.exportExamTeacher}
            disabled={!paper}
          />
          <ExportLink
            kind="exam-student"
            href={exportUrls.examPaper(false)}
            label={t.tools.exportExamStudent}
            disabled={!paper}
          />
          </div>
          <p className="mt-3 text-[12px] leading-[1.45] text-muted">{t.tools.exportNote}</p>
        </ToolCard>
      </div>
    </section>
  );
}

/**
 * 题库是教师端的真实产物，不能只用「已生成 4 题」代替它。
 * 默认把题干、选项、答案与解释都放在同一张卡内，生成完成后无需再寻找入口。
 */
function QuestionPreview({ questions }: { questions: Question[] }) {
  return (
    <ol className="mt-4 space-y-3 border-t border-line pt-3" data-question-preview="1">
      {questions.map((question, index) => {
        const answer = question.options.find((option) => option.id === question.answer)?.text ?? question.answer;
        return (
          <li key={question.id} className="rounded-sm border border-line bg-soft p-3" data-question-id={question.id}>
            <div className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-muted">
              <span>Q{index + 1}</span>
              <span className="rounded-full bg-surface px-2 py-0.5">{question.type}</span>
              <span>{question.points} pts · difficulty {question.difficulty}</span>
            </div>
            <p className="mt-2 text-[14px] font-semibold leading-[1.45] text-ink">{question.stem}</p>
            {question.options.length ? (
              <ul className="mt-2 space-y-1 text-[13px] leading-[1.4] text-body">
                {question.options.map((option) => (
                  <li key={option.id} className="flex gap-2">
                    <span className="font-mono text-muted">{option.id}.</span>
                    <span>{option.text}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="mt-2 border-t border-line pt-2 text-[13px] leading-[1.4] text-body">
              <span className="font-semibold text-green">Answer: </span>{answer}
            </p>
            <p className="mt-1 text-[12px] leading-[1.4] text-muted">{question.explanation}</p>
          </li>
        );
      })}
    </ol>
  );
}

function ToolCard({ title, className, children }: { title: string; className?: string; children: ReactNode }) {
  return (
    <Card className={cx("p-4", className)}>
      <SectionLabel>{title}</SectionLabel>
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
