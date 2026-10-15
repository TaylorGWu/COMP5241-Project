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

import { useEffect, useState } from "react";

import { Button, Dot, Field, SectionLabel, cx, inputCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { exportUrls, type CoursePackage } from "@/lib/api";

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
    <div
      className="mt-5 border-t border-line pt-4"
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

      {/* ── 出题 ── */}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <Button
          className="min-h-0 px-3 py-1.5 text-[13px]"
          disabled={busy}
          onClick={onQuestions}
        >
          {questions.length ? t.tools.questionsAgain : t.tools.questions}
        </Button>
        <span className="text-[12px] text-muted">
          {questions.length ? t.tools.questionsNote(questions.length) : t.tools.notYet}
        </span>
      </div>

      {questions.length ? (
        <div className="mt-1.5 flex items-center gap-2 text-[12px] text-muted">
          <Dot tone="green" />
          {t.tools.difficultySpread(
            Math.min(...questions.map((q) => q.difficulty)),
            Math.max(...questions.map((q) => q.difficulty)),
          )}
        </div>
      ) : null}

      {/* ── 组卷 ── */}
      <div className="mt-3 border-t border-line pt-3">
        <div className="grid grid-cols-2 gap-2">
          <Field label={t.tools.paperTotal}>
            <input
              type="number"
              data-field="total"
              className={cx(inputCls, "py-1 text-[13px]")}
              value={total}
              onChange={(e) => setTotal(Number(e.target.value))}
            />
          </Field>
          <Field label={t.tools.paperDuration}>
            <input
              type="number"
              data-field="duration"
              className={cx(inputCls, "py-1 text-[13px]")}
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
            />
          </Field>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button
            className="min-h-0 px-3 py-1.5 text-[13px]"
            disabled={busy || questions.length === 0}
            onClick={() => onPaper(total, duration)}
          >
            {t.tools.paper}
          </Button>
          {paper ? (
            <span
              className={cx(
                "flex items-center gap-2 text-[12px]",
                paperExact ? "text-body" : "text-amber",
              )}
              data-paper={paperExact ? "exact" : "short"}
            >
              <Dot tone={paperExact ? "green" : "amber"} />
              {paperExact
                ? t.tools.paperExact(targetPoints)
                : t.tools.paperShort(actualPoints, targetPoints)}
            </span>
          ) : (
            <span className="text-[12px] text-muted">{t.tools.notYet}</span>
          )}
        </div>
      </div>

      {/* ── 术语白话化 ── */}
      <div className="mt-3 border-t border-line pt-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            className="min-h-0 px-3 py-1.5 text-[13px]"
            disabled={busy}
            onClick={onGlossary}
          >
            {t.tools.glossary}
          </Button>
          <span className="text-[12px] text-muted">
            {glossary.length ? t.tools.glossaryNote(glossary.length) : t.tools.notYet}
          </span>
        </div>
      </div>

      {/* ── 导出 ── */}
      <div className="mt-3 border-t border-line pt-3">
        <SectionLabel>{t.tools.export}</SectionLabel>
        <div className="mt-2 flex flex-wrap gap-1.5">
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
        <p className="mt-1.5 text-[11px] text-muted">{t.tools.exportNote}</p>
      </div>
    </div>
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
