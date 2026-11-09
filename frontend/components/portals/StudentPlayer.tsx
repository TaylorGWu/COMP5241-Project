"use client";
import {
  useCallback,
  useEffect,
  useState,
  useRef,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import Link from "next/link";
import { SlideFrame } from "@/components/SlideCanvas";
import type { Slide } from "@/lib/api";
import { PortalIcon } from "./PortalIcon";
import { authFetch } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import {
  portalApi,
  studentCourseHref,
  studentChapterHref,
  optionText,
  studentRenderSlide,
  studentSlideFigure,
  prepareAttempt,
  mergeProgress,
  type AttemptSubmission,
  type ChapterDetail,
  type Question,
  type Result,
} from "@/lib/portal";
import {
  PortalShell,
  PortalError,
  PortalLoading,
  ProgressBar,
  usePortalResource,
  usePortalWrite,
} from "./PortalShell";
/**
 * A slide is laid out at the width the teacher reviewed it at, then scaled to fit
 * whatever room the learner has. Same width means the same line breaks, the same
 * figure size and the same reading-guide column - the learner sees the reviewed
 * page, just smaller, instead of a reflow that can clip the last bullet.
 */
/**
 * Learner assets sit behind the session cookie, so a bare <img src> hits the page's
 * own origin and 404s. Fetch once with the session and hand the renderer a blob URL.
 */
function useStudentAssetUrl(url?: string) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    if (!url) {
      setSrc("");
      return;
    }
    const controller = new AbortController();
    let objectUrl = "";
    void authFetch(url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("unavailable");
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!controller.signal.aborted) setSrc("");
      });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  return src;
}

/** True below the width where a scaled slide stops being legible. */
function useNarrowViewport() {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 720px)");
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return narrow;
}

//: How many question/answer pairs the panel keeps before it clears itself.
const TUTOR_HISTORY = 5;

const SLIDE_WIDTH = 966;
const THUMB_WIDTH = 800;

function ScaledSlide({
  slide,
  diagramUrl,
  thumbnail = false,
}: {
  slide: Slide;
  diagramUrl?: string;
  thumbnail?: boolean;
}) {
  const resolvedDiagram = useStudentAssetUrl(diagramUrl);
  const boxRef = useRef<HTMLDivElement>(null);
  const [boxWidth, setBoxWidth] = useState(0);
  const narrow = useNarrowViewport();
  const width = thumbnail ? THUMB_WIDTH : SLIDE_WIDTH;
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const measure = () => setBoxWidth(box.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);
  const scale = boxWidth ? boxWidth / width : 1;
  // A fixed 16:9 page cannot be read at phone width - the type would be ~7px.
  // Phones get the same slide reflowed for reading; every wider view shows the
  // page exactly as the teacher reviewed it.
  if (narrow && !thumbnail) {
    return (
      <SlideFrame
        slide={slide}
        diagramUrl={resolvedDiagram || undefined}
        className="portal-slide"
      />
    );
  }
  return (
    <div
      ref={boxRef}
      className={thumbnail ? "portal-stage portal-stage--thumb" : "portal-stage"}
      style={{ height: boxWidth ? (boxWidth * 9) / 16 : undefined }}
    >
      <div
        className="portal-stage__canvas"
        style={{
          width,
          height: (width * 9) / 16,
          transform: `scale(${scale})`,
          visibility: boxWidth ? "visible" : "hidden",
        }}
      >
        <SlideFrame
          slide={slide}
          diagramUrl={resolvedDiagram || undefined}
          thumbnail={thumbnail}
        />
      </div>
    </div>
  );
}

export function StudentPlayer({
  courseId,
  chapterId,
}: {
  courseId: string;
  chapterId: string;
}) {
  const load = useCallback(
    (signal: AbortSignal) => portalApi.chapter(courseId, chapterId, signal),
    [courseId, chapterId],
  );
  const resource = usePortalResource(load);
  const { locale } = useI18n();
  const copy = portalCopy(locale);
  return (
    <PortalShell
      action={
        <Link
          href={studentCourseHref(courseId)}
          className="portal-button portal-button--quiet portal-button--back"
        >
          <PortalIcon name="chevron" /> {copy.courseBack}
        </Link>
      }
    >
      <PortalError error={resource.error} retry={resource.reload} />
      {resource.loading ? (
        <PortalLoading />
      ) : resource.data ? (
        <Lesson
          key={`${courseId}/${chapterId}`}
          initial={resource.data}
          courseId={courseId}
          chapterId={chapterId}
          reload={resource.reload}
        />
      ) : null}
    </PortalShell>
  );
}
function Lesson({
  initial,
  courseId,
  chapterId,
  reload,
}: {
  initial: ChapterDetail;
  courseId: string;
  chapterId: string;
  reload: () => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [data, setData] = useState(initial);
  const [index, setIndex] = useState(
    Math.max(
      0,
      initial.chapter.slides.findIndex(
        (slide) => slide.id === initial.progress.lastSlideId,
      ),
    ),
  );
  const [progressError, setProgressError] = useState("");
  const [saving, setSaving] = useState(false);
  const [retry, setRetry] = useState(0);
  const slide = data.chapter.slides[index];
  const readingRef = useRef<HTMLDivElement>(null);
  // Open the next question the learner has to answer; a fully answered chapter
  // opens the first one so its feedback stays visible without expanding all.
  const firstOpenQuestion =
    data.chapter.questions.find((question) => !data.results[question.id])?.id ??
    data.chapter.questions[0]?.id ??
    null;
  const [openQuestion, setOpenQuestion] = useState<string | null>(
    firstOpenQuestion,
  );
  // A wrong answer can send the learner back to the slide that teaches it.
  const reviewSlide = (slideId: string) => {
    const target = data.chapter.slides.findIndex(
      (entry) => entry.id === slideId,
    );
    if (target < 0) return;
    setIndex(target);
    setView("slides");
    readingRef.current?.scrollIntoView();
    readingRef.current?.focus();
  };
  useEffect(() => {
    if (!slide) return;
    const request = new AbortController();
    const timer = setTimeout(() => {
      setSaving(true);
      setProgressError("");
      void portalApi
        .progress(courseId, chapterId, slide.id, request.signal)
        .then((result) => {
          if (!request.signal.aborted)
            setData((current) => ({
              ...current,
              progress: mergeProgress(current.progress, result.progress),
            }));
        })
        .catch((cause) => {
          if (!request.signal.aborted)
            setProgressError(
              cause instanceof Error ? cause.message : c.progressFailed,
            );
        })
        .finally(() => {
          if (!request.signal.aborted) setSaving(false);
        });
    }, 0);
    return () => {
      clearTimeout(timer);
      request.abort();
    };
  }, [courseId, chapterId, slide, c.progressFailed, retry]);
  // One question at a time, kept on screen with its answer: the learner can see
  // what the answer was grounded in without leaving the slide.
  // Slides, practice and the glossary are three views of one chapter, not one
  // long page: the teacher's chapter does the same with its material tabs.
  const [view, setView] = useState<"slides" | "practice" | "glossary">("slides");
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<
    { id: string; question: string; answer?: string }[]
  >([]);
  const tutor = usePortalWrite();
  const askTutor = (event: FormEvent) => {
    event.preventDefault();
    ask();
  };
  /** Enter sends, Shift+Enter is a new line. */
  const askOnEnter = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    ask();
  };
  const ask = () => {
    const text = question.trim();
    if (!text || !slide) return;
    const id = `${Date.now()}`;
    // History is capped: the sixth question clears the previous five rather than
    // growing the panel without limit.
    setAsked((current) =>
      [...(current.length >= TUTOR_HISTORY ? [] : current), { id, question: text }],
    );
    setQuestion("");
    void tutor.run(
      async (signal) => {
        const reply = await portalApi.tutor(
          courseId,
          chapterId,
          slide.id,
          text,
          signal,
        );
        setAsked((current) =>
          current.map((entry) =>
            entry.id === id ? { ...entry, answer: reply.answer } : entry,
          ),
        );
        return reply;
      },
      () => undefined,
    );
  };
  const safeSlide = slide ? studentRenderSlide(slide, c.quizGuide) : undefined;
  const figure = slide ? studentSlideFigure(slide) : undefined;
  return (
    <>
      <header className="portal-title">
        <div className="portal-title-head">
          <h1>{data.chapter.title}</h1>
        </div>
        {/* Bar and save state travel together, so a taller title cannot strand
            the label below the fold of the header row. */}
        <div className="portal-title-status">
          <ProgressBar value={data.progress.completionPercent} />
          <p role="status">
            {saving
              ? c.savingProgress
              : progressError
                ? ""
                : data.progress.completed
                  ? c.finished
                  : c.saved}
          </p>
        </div>
      </header>
      <PortalError error={progressError} retry={() => setRetry((n) => n + 1)} />
      <div className="portal-player">
        <aside className="portal-outline">
          <h2>{c.outline}</h2>
          <ol>
            {data.chapter.slides.map((entry, i) => (
              <li key={entry.id}>
                <button
                  type="button"
                  onClick={() => setIndex(i)}
                  aria-current={i === index ? "step" : undefined}
                >
                  <span className="portal-outline__number">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  {/* The rail shows the same slide the stage shows, so the list
                      and the canvas can never disagree. */}
                  <ScaledSlide
                    slide={studentRenderSlide(entry, c.quizGuide)}
                    diagramUrl={studentSlideFigure(entry)}
                    thumbnail
                  />
                  <span className="portal-outline__title">{entry.title}</span>
                  {data.progress.visitedSlideIds.includes(entry.id) ? (
                    <span className="portal-outline__done">
                      <PortalIcon name="check" />
                      <span className="sr-only">{c.complete}</span>
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ol>
          <div className="portal-outline__actions">
            {/* No jump to the practice panel: it is on screen beside the slide. */}
            {data.chapter.glossary.length ? (
              <a
                className="portal-button portal-button--quiet"
                href="#portal-glossary"
              >
                {c.glossary}
              </a>
            ) : null}
          </div>
        </aside>
        <div className="portal-reading" ref={readingRef} tabIndex={-1}>
          <nav className="portal-tabs portal-tabs--reading" aria-label={c.outline}>
            <button
              type="button"
              aria-current={view === "slides" ? "page" : undefined}
              onClick={() => setView("slides")}
            >
              {c.slides}
            </button>
            <button
              type="button"
              aria-current={view === "practice" ? "page" : undefined}
              onClick={() => setView("practice")}
            >
              {c.practice}
            </button>
            {data.chapter.glossary.length ? (
              <button
                type="button"
                aria-current={view === "glossary" ? "page" : undefined}
                onClick={() => setView("glossary")}
              >
                {c.glossary}
              </button>
            ) : null}
          </nav>
          {data.previousChapter || data.nextChapter ? (
            <nav
              className={`portal-chapter-nav${data.previousChapter ? "" : " portal-chapter-nav--first"}${data.nextChapter ? "" : " portal-chapter-nav--last"}`}
            >
              {data.previousChapter ? (
                <Link
                  className="portal-chapter-nav__link portal-chapter-nav__link--prev"
                  href={studentChapterHref(courseId, data.previousChapter.id)}
                >
                  <span className="portal-chapter-nav__label">
                    <PortalIcon name="arrow" /> {c.previousChapter}
                  </span>
                  <span className="portal-chapter-nav__title">
                    {data.previousChapter.title}
                  </span>
                </Link>
              ) : (
                <span />
              )}
              {data.nextChapter ? (
                <Link
                  className="portal-chapter-nav__link portal-chapter-nav__link--next"
                  href={studentChapterHref(courseId, data.nextChapter.id)}
                >
                  <span className="portal-chapter-nav__label">
                    {c.nextChapter} <PortalIcon name="arrow" />
                  </span>
                  <span className="portal-chapter-nav__title">
                    {data.nextChapter.title}
                  </span>
                </Link>
              ) : (
                <span />
              )}
            </nav>
          ) : null}
          {view === "slides" ? (
          <section aria-label={c.outline}>
            {safeSlide ? (
              <>
                <ScaledSlide slide={safeSlide} diagramUrl={figure} />
                {slide.visuals
                  .filter((entry) => entry.url && entry.url !== figure)
                  .map((entry) =>
                    entry.url ? (
                      <StudentAsset
                        key={entry.url}
                        url={entry.url}
                        alt={entry.altText?.trim() || c.figure}
                      />
                    ) : null,
                  )}
                <div className="portal-slide-controls">
                  <button
                    type="button"
                    disabled={index === 0}
                    onClick={() => setIndex((i) => i - 1)}
                  >
                    {c.previous}
                  </button>
                  <span>
                    {index + 1} / {data.chapter.slides.length}
                  </span>
                  <button
                    type="button"
                    disabled={index >= data.chapter.slides.length - 1}
                    onClick={() => setIndex((i) => i + 1)}
                  >
                    {c.next}
                  </button>
                </div>
              </>
            ) : (
              <p className="portal-empty">{c.noSlides}</p>
            )}
          </section>
          ) : null}
          {view === "glossary" && data.chapter.glossary.length ? (
            <section id="portal-glossary" className="portal-glossary">
              <h2>{c.glossary}</h2>
              <dl>
                {data.chapter.glossary.map((entry) => (
                  <div key={entry.term}>
                    <dt>{entry.term}</dt>
                    <dd>{entry.plain}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}
        {view === "practice" ? (
        <section id="portal-practice" className="portal-practice">
          <h2>{c.practice}</h2>
          <p>{c.practiceHint}</p>
          {data.chapter.questions.length ? (
            data.chapter.questions.map((question, questionIndex) => (
              <Practice
                key={question.id}
                question={question}
                index={questionIndex}
                open={openQuestion === question.id}
                onToggle={() =>
                  setOpenQuestion(
                    openQuestion === question.id ? null : question.id,
                  )
                }
                result={data.results[question.id]}
                courseId={courseId}
                chapterId={chapterId}
                reload={reload}
                onReviewSlide={reviewSlide}
                accept={(result) =>
                  setData((current) => ({
                    ...current,
                    progress: mergeProgress(
                      current.progress,
                      result.progress,
                    ),
                    results: {
                      ...current.results,
                      [question.id]: result.result,
                    },
                  }))
                }
              />
            ))
          ) : (
            <p>{c.noQuestions}</p>
          )}
        </section>
        ) : null}
        </div>
        <aside className="portal-tutor">
          <h2>{c.tutor}</h2>
          {/* Only the page itself: the hints, the grounding label and the
              objectives were three lines of explanation around one field. */}
          {safeSlide ? (
            <div className="portal-tutor__slide">
              <ScaledSlide slide={safeSlide} diagramUrl={figure} thumbnail />
            </div>
          ) : null}
          <div className="portal-tutor__log" aria-live="polite">
            {tutor.error ? (
              <p className="portal-tutor__said portal-tutor__said--error">
                {tutor.error}
              </p>
            ) : null}
            {asked.map((entry, turn) => (
              /* Only the newest answer stays open; asking again folds the rest,
                 and any of them can be reopened. */
              <details
                key={entry.id}
                className="portal-tutor__turn"
                open={turn === asked.length - 1}
              >
                <summary className="portal-tutor__question">
                  {entry.question}
                </summary>
                <p className="portal-tutor__said">
                  {entry.answer ?? c.tutorThinking}
                </p>
              </details>
            ))}
          </div>
          <form className="portal-tutor__form" onSubmit={askTutor}>
            <label>
              <span className="sr-only">{c.tutorAsk}</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={askOnEnter}
                placeholder={c.tutorPlaceholder}
                rows={3}
                maxLength={600}
                aria-keyshortcuts="Enter"
              />
            </label>
            <button
              type="submit"
              className="portal-button"
              disabled={tutor.busy || question.trim().length < 2}
            >
              {tutor.busy ? c.tutorThinking : c.tutorSend}
            </button>
            <p className="portal-tutor__key">{c.tutorEnterHint}</p>
          </form>
        </aside>
      </div>
    </>
  );
}
function StudentAsset({ url, alt }: { url: string; alt: string }) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const [src, setSrc] = useState("");
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    let objectUrl = "";
    const timer = setTimeout(() => {
      setSrc("");
      setError("");
      void authFetch(url, { signal: request.signal })
        .then(async (response) => {
          if (!response.ok) throw new Error(c.error);
          const blob = await response.blob();
          if (!request.signal.aborted) {
            objectUrl = URL.createObjectURL(blob);
            setSrc(objectUrl);
          }
        })
        .catch((cause) => {
          if (!request.signal.aborted)
            setError(cause instanceof Error ? cause.message : c.error);
        });
    }, 0);
    return () => {
      clearTimeout(timer);
      request.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, retry, c.error]);
  return (
    <figure>
      {src ? (
        // A private authenticated blob URL must not pass through image optimization.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          onError={() => {
            setError(c.error);
            setSrc("");
          }}
        />
      ) : error ? (
        <PortalError error={error} retry={() => setRetry((n) => n + 1)} />
      ) : (
        <p role="status">{c.loading}</p>
      )}
      <figcaption>{alt}</figcaption>
    </figure>
  );
}
function Practice({
  question,
  index,
  result,
  courseId,
  chapterId,
  accept,
  reload,
  onReviewSlide,
  open,
  onToggle,
}: {
  question: Question;
  index: number;
  result?: Result;
  courseId: string;
  chapterId: string;
  accept: (result: Awaited<ReturnType<typeof portalApi.attempt>>) => void;
  reload: () => void;
  onReviewSlide: (slideId: string) => void;
  open: boolean;
  onToggle: () => void;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  const write = usePortalWrite();
  const [choice, setChoice] = useState(result?.selectedOptionId ?? "");
  const [retrying, setRetrying] = useState(false);
  const submission = useRef<AttemptSubmission | null>(null);
  const shown = result && !retrying ? result : null;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!choice) return;
    submission.current = prepareAttempt(
      submission.current,
      question.id,
      choice,
      question.revision,
      () => crypto.randomUUID(),
    );
    const payload = submission.current;
    void write.run(
      (signal) => portalApi.attempt(courseId, chapterId, payload, signal),
      (next) => {
        accept(next);
        setRetrying(false);
        submission.current = null;
      },
    );
  };
  return (
    <section className="portal-question" data-open={open ? "" : undefined}>
      {/* One row per question keeps a long practice set scannable; the options
          and feedback only take space for the question being worked on. */}
      <h3 className="portal-question-head">
        <button
          type="button"
          className="portal-question-toggle"
          aria-expanded={open}
          onClick={onToggle}
        >
          <span className="portal-question-index">{index + 1}</span>
          <span className="portal-question-stem">{question.stem}</span>
          <span
            className={`portal-question-state${
              result ? (result.correct ? " is-correct" : " is-wrong") : ""
            }`}
          >
            {result ? (result.correct ? c.correct : c.incorrect) : c.notAnswered}
          </span>
          <PortalIcon name="chevron" />
        </button>
      </h3>
      {open ? (
        <form onSubmit={submit}>
          <fieldset disabled={write.busy || !!shown}>
            <legend className="sr-only">{question.stem}</legend>
            {question.options.map((option) => (
              <label className="portal-option" key={option.id}>
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option.id}
                  checked={choice === option.id}
                  onChange={() => setChoice(option.id)}
                  required
                />
                <span>{option.text}</span>
              </label>
            ))}
          </fieldset>
          {shown ? (
            <div
              className={`portal-answer ${shown.correct ? "is-correct" : ""}`}
              role="status"
            >
              <strong>{shown.correct ? c.correct : c.incorrect}</strong>
              <p>
                {c.yourAnswer}:{" "}
                {optionText(question.options, shown.selectedOptionId)}
              </p>
              {!shown.correct ? (
                <p>
                  {c.correctAnswer}:{" "}
                  {optionText(question.options, shown.correctOptionId)}
                </p>
              ) : null}
              <p>{shown.explanation}</p>
              <small>{c.resultSaved}</small>
              {shown.reviewSlideId ? (
                <button
                  type="button"
                  onClick={() => onReviewSlide(shown.reviewSlideId!)}
                >
                  {c.reviewRelated}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => {
                  setRetrying(true);
                  setChoice("");
                  submission.current = null;
                }}
              >
                {c.retryAnswer}
              </button>
            </div>
          ) : (
            <button className="portal-button" disabled={write.busy || !choice}>
              {write.busy ? c.saving : c.check}
            </button>
          )}
          <PortalError
            error={
              write.error === "Question changed; reload chapter"
                ? c.questionChanged
                : write.error
            }
            retry={
              write.error === "Question changed; reload chapter"
                ? reload
                : undefined
            }
          />
        </form>
      ) : null}
    </section>
  );
}
