"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authJson, AuthError, roleDestination, signOut, type Account, type SessionResponse } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";

type AccountContextValue = { user: Account | null; loading: boolean; error: string; refresh: () => Promise<Account | null>; accept: (user: Account) => void; logout: () => Promise<void> };
const AccountContext = createContext<AccountContextValue | null>(null);

export function AccountProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    try {
      const result = await authJson<SessionResponse>("/api/auth/me");
      setUser(result.user); setError(""); return result.user;
    } catch (cause) {
      setUser(null);
      setError(cause instanceof AuthError && cause.status === 401 ? "" : cause instanceof Error ? cause.message : "Connection unavailable");
      return null;
    } finally { setLoading(false); }
  }, []);
  useEffect(() => {
    void refresh();
    const expire = () => { setUser(null); setLoading(false); };
    window.addEventListener("coursework-session-expired", expire);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { window.removeEventListener("coursework-session-expired", expire); document.removeEventListener("visibilitychange", visible); };
  }, [refresh]);
  const logout = async () => { await signOut(); setUser(null); };
  return <AccountContext.Provider value={{ user, loading, error, refresh, accept: setUser, logout }}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  const context = useContext(AccountContext);
  if (!context) throw new Error("AccountProvider is required");
  return context;
}

export function AccountGate({ destination, children }: { destination: "/courses" | "/student" | "/admin" | "/application"; children: ReactNode }) {
  const account = useAccount();
  const router = useRouter();
  const pathname = usePathname();
  const { locale } = useI18n();
  const copy = publicCopy(locale);
  const allowed = account.user && roleDestination(account.user) === destination;
  useEffect(() => {
    if (account.loading || account.error) return;
    if (!account.user) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    else if (!allowed) router.replace(roleDestination(account.user));
  }, [account.loading, account.error, account.user, allowed, pathname, router]);
  if (!allowed) return <main className="account-check"><p role="status">{account.error || copy.sessionCheck}</p>{account.error ? <button onClick={() => void account.refresh()}>{copy.retry}</button> : null}</main>;
  return children;
}
