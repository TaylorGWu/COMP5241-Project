"use client";

import { createContext, Fragment, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authJson, AuthError, roleDestination, signOut, type Account, type SessionResponse } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";

type AccountContextValue = { user: Account | null; loading: boolean; error: string; refresh: (options?: { preserveOnError?: boolean }) => Promise<Account | null>; accept: (user: Account) => void; logout: () => Promise<void> };
const AccountContext = createContext<AccountContextValue | null>(null);

export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const pendingRefresh = useRef<AbortController | null>(null);
  const identityRevision = useRef(0);
  const cancelRefresh = useCallback(() => {
    pendingRefresh.current?.abort();
    pendingRefresh.current = null;
  }, []);
  const refresh = useCallback(async (options?: { preserveOnError?: boolean }) => {
    cancelRefresh();
    const request = new AbortController();
    pendingRefresh.current = request;
    try {
      const result = await authJson<SessionResponse>("/api/auth/me", { signal: request.signal });
      if (request.signal.aborted) return null;
      setUser(result.user); setError(""); return result.user;
    } catch (cause) {
      if (request.signal.aborted) return null;
      if (options?.preserveOnError && !(cause instanceof AuthError && cause.status === 401)) throw cause;
      setUser(null);
      setError(cause instanceof AuthError && cause.status === 401 ? "" : cause instanceof Error ? cause.message : "Connection unavailable");
      return null;
    } finally {
      if (pendingRefresh.current === request) { pendingRefresh.current = null; setLoading(false); }
    }
  }, [cancelRefresh]);
  useEffect(() => {
    // Let StrictMode cleanup cancel the scheduled initial restoration.
    const initial = window.setTimeout(() => { void refresh(); }, 0);
    const expire = () => { identityRevision.current++; cancelRefresh(); setUser(null); setError(""); setLoading(false); };
    window.addEventListener("coursework-session-expired", expire);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.clearTimeout(initial); cancelRefresh(); window.removeEventListener("coursework-session-expired", expire); document.removeEventListener("visibilitychange", visible); };
  }, [cancelRefresh, refresh]);
  const accept = (next: Account) => { identityRevision.current++; cancelRefresh(); setUser(next); setError(""); setLoading(false); };
  const logout = async () => {
    const revision = ++identityRevision.current;
    cancelRefresh();
    await signOut();
    if (identityRevision.current !== revision) return;
    identityRevision.current++;
    cancelRefresh(); setUser(null); setError(""); setLoading(false);
  };
  return <AccountContext.Provider value={{ user, loading, error, refresh, accept, logout }}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  const context = useContext(AccountContext);
  if (!context) throw new Error("AccountProvider is required");
  return context;
}

export function AccountGate({ destination, children }: { destination: "/courses" | "/student" | "/admin" | "/application" | "/profile"; children: ReactNode }) {
  const account = useAccount();
  const router = useRouter();
  const pathname = usePathname();
  const { locale } = useI18n();
  const copy = publicCopy(locale);
  const allowed = account.user && (destination === "/profile" ? account.user.role === "instructor" : roleDestination(account.user) === destination);
  useEffect(() => {
    if (account.loading || account.error) return;
    if (!account.user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!allowed) router.replace(roleDestination(account.user));
  }, [account.loading, account.error, account.user, allowed, pathname, router]);
  if (!allowed) return <main className="account-check"><p role="status">{account.error || copy.sessionCheck}</p>{account.error ? <button onClick={() => void account.refresh()}>{copy.retry}</button> : null}</main>;
  return <Fragment key={account.user?.id}>{children}</Fragment>;
}
