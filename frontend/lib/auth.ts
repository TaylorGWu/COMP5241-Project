/** Cookie credentials stay in the browser; this module never stores a bearer token. */
import { API_BASE as AUTH_API_BASE } from "./api-base.ts";
export { AUTH_API_BASE };
export type AccountRole = "student" | "instructor" | "admin";
export type AccountStatus = "active" | "pending" | "approved" | "rejected";
export type Account = { id: string; name: string; email: string; role: AccountRole; status: AccountStatus; reviewReason: string | null; qualificationSubmitted?: boolean };
export type SessionResponse = { user: Account; csrfToken: string };
export type Application = Account & { qualificationFilename: string; submittedAt: number };

export function roleDestination(user: Pick<Account, "role" | "status">): string {
  if (user.role === "instructor") return user.status === "approved" ? "/courses" : "/application";
  return user.role === "admin" ? "/admin" : "/student";
}

export function safeDestination(next: string | null | undefined, user: Pick<Account, "role" | "status">): string {
  const home = roleDestination(user);
  if (!next || !next.startsWith("/") || next.startsWith("//") || /[\\%\u0000-\u0020]/.test(next)) return home;
  const pathname = next.split(/[?#]/)[0];
  if (pathname.split("/").some((segment) => segment === "." || segment === "..")) return home;
  if (pathname !== home && !pathname.startsWith(`${home}/`)) return home;
  return next;
}

export function validateQualification(file: Pick<File, "size" | "type">): "size" | "type" | "empty" | null {
  if (file.size === 0) return "empty";
  if (file.size > 5 * 1024 * 1024) return "size";
  if (!["application/pdf", "image/png", "image/jpeg"].includes(file.type)) return "type";
  return null;
}

export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) { csrfToken = token; }

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  const unsafe = !["GET", "HEAD", "OPTIONS"].includes(method);
  const secureHeaders = async () => {
    if (!csrfToken) {
      const response = await fetch(`${AUTH_API_BASE}/api/auth/csrf`, { credentials: "include", cache: "no-store", signal: init.signal });
      if (!response.ok) throw new AuthError("Unable to establish a secure session. Please try again.", response.status);
      csrfToken = (await response.json()).csrfToken;
    }
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  };
  if (unsafe) await secureHeaders();
  const request = () => fetch(`${AUTH_API_BASE}${path}`, { ...init, headers, credentials: "include", cache: "no-store" });
  let response = await request();
  // These endpoints validate CSRF before writing. Only their explicit expired-form
  // rejection is safe to retry; private mutations must never be replayed.
  if (method === "POST" && ["/api/auth/login", "/api/auth/register"].includes(path) && response.status === 403 && !init.signal?.aborted) {
    const payload = await response.clone().json().catch(() => ({}));
    if (payload.detail === "The form expired. Reload and try again.") {
      csrfToken = null;
      await secureHeaders();
      response = await request();
    }
  }
  if (response.status === 401 && !init.signal?.aborted && (["/api/auth/me", "/api/auth/logout", "/api/auth/profile", "/api/auth/avatar", "/api/auth/qualification"].includes(path) || !path.startsWith("/api/auth/"))) {
    csrfToken = null;
    if (typeof window !== "undefined") window.dispatchEvent(new Event("coursework-session-expired"));
  }
  return response;
}

export async function authJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await authFetch(path, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((entry: { msg?: string }) => entry.msg).filter(Boolean).join(" ") : `Request failed (${response.status})`;
    throw new AuthError(message, response.status);
  }
  if (payload.csrfToken && !init.signal?.aborted) setCsrfToken(payload.csrfToken);
  return payload as T;
}

export async function signOut(): Promise<void> {
  try { await authJson("/api/auth/logout", { method: "POST" }); }
  catch (cause) { if (!(cause instanceof AuthError) || cause.status !== 401) throw cause; }
  setCsrfToken(null);
}
