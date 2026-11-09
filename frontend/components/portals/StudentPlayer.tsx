"use client";
import {
  useCallback,
  useEffect,
  useState,
  useRef,
  type FormEvent,
} from "react";
import Link from "next/link";
import { SlideFrame } from "@/components/SlideCanvas";
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
  return (
    <PortalShell>
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
  const safeSlide = slide ? studentRenderSlide(slide, c.quizGuide) : undefined;
  return (
    <>
      <Link href={studentCourseHref(courseId)} className="portal-text-link">
        {c.courseBack}
      </Link>
      <header className="portal-title">
        <h1>{data.chapter.title}</h1>
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
                  <span>{i + 1}</span>
                  <span>{entry.title}</span>
                  {data.progress.visitedSlideIds.includes(entry.id) ? (
                    <small>{c.complete}</small>
                  ) : null}
                </button>
              </li>
            ))}
          </ol>
          <a className="portal-text-link" href="#portal-practice">
            {c.practice}
          </a>
          {data.chapter.glossary.length ? (
            <a className="portal-text-link" href="#portal-glossary">
              {c.glossary}
            </a>
          ) : null}
        </aside>
        <div className="portal-reading" ref={readingRef} tabIndex={-1}>
          <section aria-label={c.outline}>
            {safeSlide ? (
              <>
                <SlideFrame slide={safeSlide} className="portal-slide" />
                {slide.visuals.map((entry) =>
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
          {data.chapter.glossary.length ? (
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
        </div>
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
