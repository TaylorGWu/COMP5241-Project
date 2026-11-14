/** Where the API lives, from the browser's point of view.
 *
 *  - server render: the process can reach its own backend on loopback;
 *  - local development (frontend on :3000, backend on :8000): talk to :8000;
 *  - deployed behind a reverse proxy: stay on the page's own origin, so `/api/...`
 *    goes through nginx instead of pointing at the visitor's own machine.
 *
 *  `NEXT_PUBLIC_API_BASE` still wins when a deployment splits the two hosts.
 */
const LOOPBACK = "http://127.0.0.1:8000";

function resolveBase(): string {
  if (typeof window === "undefined") return LOOPBACK;
  const { hostname, port } = window.location;
  const local =
    (hostname === "localhost" || hostname === "127.0.0.1") && port === "3000";
  return local ? `http://${hostname}:8000` : "";
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? resolveBase();
