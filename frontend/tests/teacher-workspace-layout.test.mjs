import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const pagePath = new URL("../app/courses/[courseId]/chapters/[chapterId]/page.tsx", import.meta.url);
const reviewMarginPath = new URL("../components/ReviewMargin.tsx", import.meta.url);
const teacherToolsPath = new URL("../components/TeacherTools.tsx", import.meta.url);
const nextConfigPath = new URL("../next.config.ts", import.meta.url);
const themePath = new URL("../lib/theme.tsx", import.meta.url);
const layoutPath = new URL("../app/layout.tsx", import.meta.url);
const stylesPath = new URL("../app/globals.css", import.meta.url);
const systemSettingsPath = new URL("../components/SystemSettings.tsx", import.meta.url);
const slideCanvasPath = new URL("../components/SlideCanvas.tsx", import.meta.url);
const i18nConfigPath = new URL("../lib/i18n-config.ts", import.meta.url);

test("chapter workspace keeps generated artifacts in dedicated tabs", async () => {
  const source = await readFile(pagePath, "utf8");
  for (const tab of ["slides", "plan", "questions", "glossary", "paper"]) {
    assert.match(source, new RegExp(`value: "${tab}"`));
  }
  assert.match(source, /data-workspace-tab=\{tab\.value\}/);
});

test("workspace derives revision target from the material tab and removes slide thumbnail rail", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /const \[revisionTarget, setRevisionTarget\]/);
  assert.match(source, /editChapterStream\(courseId, chapterId,/);
  assert.match(source, /revisionTarget, true, editAttachments/);
  assert.doesNotMatch(source, /w-44 shrink-0 snap-start/);
});

test("review sidebar stays quiet until there is a real review decision", async () => {
  const source = await readFile(reviewMarginPath, "utf8");
  assert.doesNotMatch(source, /aria-pressed=\{revisionTarget === target\}/);
  assert.doesNotMatch(source, /t\.margin\.nothingWaiting/);
});

test("each proposed patch labels its pending decision and animation starts from the slide header", async () => {
  const review = await readFile(reviewMarginPath, "utf8");
  const page = await readFile(pagePath, "utf8");
  const canvas = await readFile(slideCanvasPath, "utf8");

  assert.match(review, /<Badge tone="violet">\{t\.margin\.waiting\}<\/Badge>/);
  assert.doesNotMatch(review, /data-animation-request="1"/);
  assert.doesNotMatch(review, /onRequestAnimation/);
  assert.match(page, /requestCurrentSlideAnimation/);
  assert.match(page, /onRequestAnimation=\{requestCurrentSlideAnimation\}/);
  assert.doesNotMatch(page, /animationTarget=/);
  assert.match(canvas, /t\.slide\.generateAnimation/);
  assert.match(canvas, /onRequestAnimation/);
});

test("proposed revisions show only before-and-after lines, without repository chrome", async () => {
  const source = await readFile(reviewMarginPath, "utf8");
  assert.match(source, /data-git-diff="1"/);
  assert.match(source, /git-diff__line--add/);
  assert.match(source, /git-diff__line--remove/);
  assert.doesNotMatch(source, /git-diff__header/);
  assert.doesNotMatch(source, /git-diff__hunk/);
  assert.doesNotMatch(source, /diff --courseware/);
  assert.doesNotMatch(source, /<pre className="mt-2 overflow-x-auto rounded-sm bg-soft/);
});

test("review reasons stay collapsed until a teacher explicitly asks for them", async () => {
  const review = await readFile(reviewMarginPath, "utf8");

  assert.match(review, /function PatchReason[\s\S]*?<details className="mt-2">/);
  assert.match(review, /<summary[^>]*>[\s\S]*?\{t\.margin\.viewReason\}/);
  assert.doesNotMatch(review, /if \(shortReason\.length <= 120\)/);
});

test("review cards use teacher-readable slide names and hide internal patch identifiers", async () => {
  const review = await readFile(reviewMarginPath, "utf8");

  assert.match(review, /function displayPatchTarget/);
  assert.match(review, /return `Slide \$\{Number\(slideMatch\[1\]\)\}`/);
  assert.match(review, /\{displayPatchTarget\(patch\)\}/);
  assert.doesNotMatch(review, /<span className="font-mono text-\[11px\] text-muted">\{patch\.id\}<\/span>/);
});

test("review lists disambiguate duplicate patch ids without changing patch actions", async () => {
  const review = await readFile(reviewMarginPath, "utf8");

  assert.match(review, /proposed\.map\(\(p, index\) => \(/);
  assert.match(review, /key=\{`\$\{p\.id\}-\$\{index\}`\}/);
  assert.match(review, /settled\.map\(\(p, index\) => <RecordedPatchRow key=\{`\$\{p\.id\}-\$\{index\}`\}/);
  assert.match(review, /onApply=\{\(\) => onApply\(p\.id\)\}/);
  assert.match(review, /onReject=\{\(\) => onReject\(p\.id\)\}/);
});

test("slide workspace renders one stage with carousel triangle controls", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /data-slide-stage="1"/);
  assert.match(source, /data-slide-carousel="1"/);
  assert.match(source, /data-slide-direction="previous"/);
  assert.match(source, /data-slide-direction="next"/);
  assert.match(source, /aria-label="Previous slide"/);
  assert.match(source, /aria-label="Next slide"/);
  assert.match(source, />\s*◀\s*</);
  assert.match(source, />\s*▶\s*</);
  assert.doesNotMatch(source, /slides\.filter\(\(s\) => !activeId/);
});

test("diagram canvas localizes its teaching cues instead of hard-coding English chrome", async () => {
  const source = await readFile(slideCanvasPath, "utf8");
  const messages = await readFile(i18nConfigPath, "utf8");

  assert.match(source, /t\.slide\.diagramCaption/);
  assert.match(source, /t\.slide\.diagramReadingGuide/);
  assert.match(messages, /diagramCaption:/);
  assert.match(messages, /diagramReadingGuide:/);
});

test("questions put regeneration in the card header instead of a full-width banner", async () => {
  const source = await readFile(teacherToolsPath, "utf8");
  assert.match(source, /<ToolCard\s+title=\{t\.tools\.questions\}\s+action=\{/);
  assert.match(source, /data-question-action="regenerate"/);
  assert.doesNotMatch(source, /className="mt-3 min-h-0 w-full px-3 py-2 text-\[13px\]" disabled=\{busy\} onClick=\{onQuestions\}/);
});

test("coverage strip stays quiet when cross-reference checks pass", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.doesNotMatch(source, /<CoverageStrip coverage=/);
});

test("chapter setup inherits its audience and the outline keeps secondary status compact", async () => {
  const source = await readFile(pagePath, "utf8");

  assert.match(source, /data-inherited-course-audience="1"/);
  assert.match(source, /audience:\s*course\?\.audience \?\? audience/);
  assert.match(source, /data-coverage-summary="collapsed"/);
  assert.match(source, /aria-label=\{t\.coverage\.gapsTitle\}/);
  assert.doesNotMatch(source, /t\.rail\.runDetails/);
});

test("studio redesign gives navigation, material, and revision distinct roles", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /data-studio-shell="1"/);
  assert.match(source, /className="studio-outline"/);
  assert.match(source, /data-studio-material-tabs="1"/);
  assert.match(source, /className="studio-review-dock /);

  const review = await readFile(reviewMarginPath, "utf8");
  assert.match(review, /data-review-dock="1"/);
  assert.doesNotMatch(review, /coverage:/);
  assert.doesNotMatch(review, /t\.coverage\.allCovered/);
});

test("slide workspace keeps a visual outline and gives AI revision a full composer", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /data-slide-outline="1"/);
  assert.match(source, /import \{ SlideCanvas, SlideThumbnail \}/);
  assert.match(source, /<SlideThumbnail/);
  assert.match(source, /className="studio-slide-stage studio-slide-stage--large/);

  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  assert.match(canvas, /export function SlideThumbnail/);
  assert.match(canvas, /<SlideFrame slide=\{slide\} diagramUrl=\{diagramUrl\} thumbnail/);
  assert.match(canvas, /function DiagramPreview\(\{ url, alt, labels, thumbnail = false \}/);
  assert.match(canvas, /data-template="course-flow"/);

  const review = await readFile(reviewMarginPath, "utf8");
  assert.match(review, /data-revision-composer="1"/);
  assert.match(review, /<textarea/);
  assert.match(review, /t\.margin\.askChange/);
  assert.match(review, /t\.margin\.placeholder/);
});

test("revision composer supports image-assisted instructions without adding visual dividers", async () => {
  const review = await readFile(reviewMarginPath, "utf8");
  const page = await readFile(pagePath, "utf8");
  const css = await readFile(stylesPath, "utf8");

  assert.match(review, /onPaste=/);
  assert.match(review, /onDrop=/);
  assert.match(review, /type="file"/);
  assert.match(review, /onKeyDown=/);
  assert.match(review, /shiftKey/);
  assert.match(page, /editAttachments/);
  assert.match(css, /\.studio-review-dock \{ min-width: 0; border-left: 0;/);
  assert.match(css, /\.studio-outline__body \{ padding-right: \.8rem; border-right: 0;/);
});

test("a proposed slide revision is actionable on the slide it changes", async () => {
  const page = await readFile(pagePath, "utf8");
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  const review = await readFile(reviewMarginPath, "utf8");

  assert.match(page, /focusedField=\{focusedSlidePatch\?\.target_id === activeSlide\.id/);
  assert.match(review, /data-review-card-id=\{patch\.id\}/);
  assert.match(review, /onApply: \(id: string\) => void/);
  assert.match(review, /onReject: \(id: string\) => void/);
  assert.match(canvas, /data-review-target=/);
  assert.doesNotMatch(canvas, /data-slide-field-review=/);
});

test("the selected review card connects to its slide region without injecting controls into the slide", async () => {
  const page = await readFile(pagePath, "utf8");
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.match(page, /const \[focusedPatchId, setFocusedPatchId\]/);
  assert.match(page, /<ReviewConnector patch=\{focusedSlidePatch\} isTargetActive=/);
  assert.match(canvas, /data-review-target=/);
  assert.doesNotMatch(canvas, /data-slide-field-review=/);
  assert.doesNotMatch(canvas, /onApplyPatch/);
  assert.doesNotMatch(canvas, /onRejectPatch/);
});

test("proposed bullet text does not get injected into the slide preview", async () => {
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");

  assert.doesNotMatch(canvas, /data-slide-bullet-review/);
  assert.doesNotMatch(canvas, /建議改為/);
});

test("settled review records stay compact until a teacher opens one", async () => {
  const review = await readFile(reviewMarginPath, "utf8");

  assert.match(review, /data-review-records="compact"/);
  assert.match(review, /<details className="review-record\b/);
  assert.match(review, /<GitDiff patch=\{patch\} \/>/);
});

test("question preview supports a teacher trial answer and export keeps questions optional", async () => {
  const tools = await readFile(new URL("../components/TeacherTools.tsx", import.meta.url), "utf8");
  const api = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");

  assert.match(tools, /data-question-interaction/);
  assert.match(tools, /setSelected/);
  assert.match(tools, /Include questions after the lesson/);
  assert.match(api, /includeQuestions/);
});

test("export is a dropdown immediately after the exam paper, not a separate workspace page", async () => {
  const workspace = await readFile(new URL("../app/courses/[courseId]/chapters/[chapterId]/page.tsx", import.meta.url), "utf8");
  const tools = await readFile(new URL("../components/TeacherTools.tsx", import.meta.url), "utf8");

  assert.match(workspace, /import \{ ExportMenu, TeacherTools \} from "@\/components\/TeacherTools"/);
  assert.match(workspace, /\{ value: "paper", label: t\.tools\.paper \},[\s\S]*<ExportMenu/);
  assert.doesNotMatch(workspace, /value: "export"/);
  assert.match(tools, /export function ExportMenu/);
  assert.match(tools, /<details className="relative"/);
});

test("visual polish stays in the stylesheet and covers interaction states", async () => {
  const css = await readFile(new URL("../app/globals.css", import.meta.url), "utf8");

  assert.match(css, /\[data-teacher-tools\] \[data-question-interaction="trial"\]/);
  assert.match(css, /\[data-export="deck"\]/);
  assert.match(css, /::selection/);
  assert.match(css, /prefers-reduced-motion/);
});

test("concept animation previews only orchestrate existing slide regions", async () => {
  const api = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");
  const preview = await readFile(new URL("../components/SlideAnimationPreview.tsx", import.meta.url), "utf8");
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  const page = await readFile(pagePath, "utf8");
  const css = await readFile(stylesPath, "utf8");

  assert.match(api, /animation\?: SlideAnimation \| null/);
  assert.match(preview, /prefers-reduced-motion: reduce/);
  assert.match(preview, /setElapsed\(finishAt\)/);
  assert.match(preview, /Pause animation|t\.slide\.pauseAnimation/);
  assert.match(preview, /Replay animation|t\.slide\.replayAnimation/);
  assert.match(canvas, /<SlideAnimationPreview animation=\{slide\.animation\}/);
  assert.match(canvas, /thumbnail = false/);
  assert.doesNotMatch(canvas, /<SlideAnimationPreview[\s\S]*thumbnail/);
  assert.match(css, /\.slide-animation-target--waiting/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
  assert.match(page, /data-slide-animation-indicator="1"/);
  assert.match(page, /s\.animation/);
});

test("global polish gives every teacher route a responsive surface contract", async () => {
  const css = await readFile(stylesPath, "utf8");

  for (const selector of [
    ".course-library-page .teacher-nav",
    ".course-create-page .teacher-nav",
    ".course-header .course-back",
    ".studio-shell .studio-material-tabs",
    "main :is(input, select, textarea)",
  ]) assert.match(css, new RegExp(selector.replace(/[.[\]()]/g, "\\$&")));
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.course-create-page/);
});

test("a stale API response cannot insert an empty patch into the revision state", async () => {
  const page = await readFile(pagePath, "utf8");
  const api = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");

  assert.match(page, /if \(!r\.patch\) throw new Error\(/);
  assert.match(page, /if \(p\?\.status === "proposed"\)/);
  assert.match(api, /patch\?: Patch/);
});

test("reloading a chapter restores its pending review decisions", async () => {
  const page = await readFile(pagePath, "utf8");
  const api = await readFile(new URL("../lib/api.ts", import.meta.url), "utf8");

  assert.match(page, /const activation = await api\.activateChapter\(courseId, chapterId\)/);
  assert.match(page, /setPatches\(activation\.patches \?\? \[\]\)/);
  assert.match(api, /ChapterActivationResponse/);
});

test("global system settings replace chapter-local controls and hide development chrome", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.doesNotMatch(source, /data-studio-settings="1"/);

  const layout = await readFile(layoutPath, "utf8");
  assert.match(layout, /<SystemSettings \/>/);

  const config = await readFile(nextConfigPath, "utf8");
  assert.match(config, /devIndicators:\s*false/);
});

test("global system settings combine appearance and interface language", async () => {
  const source = await readFile(systemSettingsPath, "utf8");
  assert.match(source, /data-global-system-settings="1"/);
  assert.match(source, /useTheme\(\)/);
  assert.match(source, /setPreference/);
  assert.match(source, /useI18n\(\)/);
  assert.match(source, /setLocale/);

  const theme = await readFile(themePath, "utf8");
  assert.match(theme, /type ThemePreference = "system" \| "light" \| "dark"/);
  assert.match(theme, /localStorage\.setItem/);
  assert.match(theme, /document\.documentElement\.dataset\.theme/);

  const layout = await readFile(layoutPath, "utf8");
  assert.match(layout, /<ThemeProvider>/);

  const styles = await readFile(stylesPath, "utf8");
  assert.match(styles, /\[data-theme="dark"\]/);
});

test("teacher-facing product copy does not call the workspace a studio", async () => {
  const brand = await readFile(new URL("../lib/brand.ts", import.meta.url), "utf8");
  const courses = await readFile(new URL("../app/courses/page.tsx", import.meta.url), "utf8");
  assert.match(brand, /PRODUCT_NAME = "Coursework"/);
  assert.doesNotMatch(courses, /Teaching studio/);
});

test("course checks live with the course map and lesson plan precedes slides", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /data-course-coverage="1"/);
  assert.doesNotMatch(source, /<ReviewMargin[\s\S]*coverage=\{coverage\}/);

  const plan = source.indexOf('{ value: "plan"');
  const slides = source.indexOf('{ value: "slides"');
  assert.ok(plan >= 0 && slides >= 0 && plan < slides, "Plan should be the first material tab");
});

test("left course map keeps a material index for questions, glossary, and assessment", async () => {
  const source = await readFile(pagePath, "utf8");
  assert.match(source, /data-chapter-material-index="1"/);
  assert.match(source, /value: "questions"/);
  assert.match(source, /value: "glossary"/);
  assert.match(source, /value: "paper"/);
  assert.doesNotMatch(source, /view === "questions" \? t\.tools\.questionsNote/);
});

test("teacher workspace has deliberate desktop, tablet, and phone layout rules", async () => {
  const page = await readFile(pagePath, "utf8");
  const styles = await readFile(stylesPath, "utf8");

  assert.match(page, /<details className="studio-outline" open>/, "Course navigation should remain visible by default at every breakpoint");
  assert.match(page, /studio-shell mx-auto w-full max-w-\[1960px\] px-3 py-4 sm:px-4 lg:px-5/, "The editing surface should use the viewport efficiently on wide screens");
  assert.match(styles, /\.studio-shell \{ display: grid; grid-template-columns: 210px minmax\(0, 1fr\) 270px; gap: \.75rem;/, "The side rails should stay compact so the slide canvas gets the primary width");
  assert.match(styles, /@media \(max-width: 1280px\)[\s\S]*?\.studio-review-dock/);
  assert.match(styles, /@media \(max-width: 1023px\)[\s\S]*?\.studio-outline:not\(\[open\]\)/);
  assert.match(styles, /@media \(max-width: 639px\)[\s\S]*?\.studio-slide-stage--large \.slide-body/);
  assert.match(styles, /@media \(max-width: 560px\)[\s\S]*?\.teacher-nav nav/);
});
