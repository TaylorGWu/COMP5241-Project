/** Keep local credentialed requests on the page's site (SameSite=Lax). */
const localHost = typeof window !== "undefined" && window.location.hostname === "localhost"
  ? "localhost"
  : "127.0.0.1";

// A deployment's explicit endpoint remains authoritative; never rewrite it.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? `http://${localHost}:8000`;
