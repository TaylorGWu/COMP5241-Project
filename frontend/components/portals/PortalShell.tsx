"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Link from "next/link";
import { AccountGate } from "@/components/AccountProvider";
import { PublicHeader } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";
import { portalCopy } from "@/lib/portal-copy";
import { progressPercent } from "@/lib/portal";

export function PortalShell({
  admin = false,
  children,
  action,
}: {
  admin?: boolean;
  children: ReactNode;
  /** Page-level control placed in the top bar, like the teacher workspace. */
  action?: ReactNode;
}) {
  const { locale } = useI18n();
  const c = portalCopy(locale);
  return (
    <AccountGate destination={admin ? "/admin" : "/student"}>
      <div className="portal public-page">
        <a href="#portal-content" className="portal-skip">
          {c.skip}
        </a>
        <PublicHeader simple action={action} />
        <main id="portal-content" className="portal-shell">
          {children}
        </main>
      </div>
    </AccountGate>
  );
}
export function PortalError({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  const { locale } = useI18n();
  return error ? (
    <div className="portal-error" role="alert">
      <p>{error}</p>
      {retry ? (
        <button type="button" onClick={retry}>
          {portalCopy(locale).retry}
        </button>
      ) : null}
    </div>
  ) : null;
}
export function PortalLoading() {
  const { locale } = useI18n();
  return (
    <div className="portal-loading" role="status">
      <p>{portalCopy(locale).loading}</p>
      <div />
      <div />
    </div>
  );
}
export function ProgressBar({ value }: { value: number }) {
  const { locale } = useI18n();
  const n = progressPercent({ completionPercent: value });
  return (
    <div className="portal-progress">
      <span>
        {portalCopy(locale).progress} <strong>{n}%</strong>
      </span>
      <progress max={100} value={n} aria-label={portalCopy(locale).progress} />
    </div>
  );
}
export function CourseLink({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  return (
    <Link
      className="portal-button"
      href={`/student/courses/${encodeURIComponent(id)}`}
    >
      {children}
    </Link>
  );
}

/** Each mounted identity owns its requests. Abort prevents late writes from updating a replacement identity. */
export function usePortalResource<T>(
  load: (signal: AbortSignal) => Promise<T>,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const request = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      void load(request.signal)
        .then((next) => {
          if (!request.signal.aborted) setData(next);
        })
        .catch((cause) => {
          if (!request.signal.aborted)
            setError(cause instanceof Error ? cause.message : "Request failed");
        })
        .finally(() => {
          if (!request.signal.aborted) setLoading(false);
        });
    }, 0);
    return () => {
      clearTimeout(timer);
      request.abort();
    };
  }, [load, revision]);
  const reload = useCallback(() => setRevision((n) => n + 1), []);
  return { data, setData, error, loading, reload };
}
export function usePortalWrite() {
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(false);
  const savedTimer = useRef<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (savedTimer.current) window.clearTimeout(savedTimer.current);
      request.current?.abort();
    };
  }, []);
  // The confirmation is feedback for one action, not a permanent state, so it
  // clears itself instead of sitting under the form until the next save.
  const confirm = () => {
    setSaved(true);
    if (savedTimer.current) window.clearTimeout(savedTimer.current);
    savedTimer.current = window.setTimeout(() => {
      if (mounted.current) setSaved(false);
    }, 2600);
  };
  const run = async <T,>(
    write: (signal: AbortSignal) => Promise<T>,
    accept?: (data: T) => void,
  ) => {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    setSaved(false);
    if (savedTimer.current) window.clearTimeout(savedTimer.current);
    try {
      const result = await write(controller.signal);
      if (mounted.current && !controller.signal.aborted) {
        accept?.(result);
        confirm();
      }
    } catch (cause) {
      if (mounted.current && !controller.signal.aborted)
        setError(cause instanceof Error ? cause.message : "Request failed");
    } finally {
      if (request.current === controller) request.current = null;
      if (mounted.current && !controller.signal.aborted) setBusy(false);
    }
  };
  return { run, busy, error, saved };
}
