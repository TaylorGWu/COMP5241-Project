# Local login cookie-site repair — 2026-10-28

## Report and cause

The supplied screenshot shows `localhost:3000/login` returning “The form expired”.
Both frontend API clients defaulted to `127.0.0.1:8000`. These are different sites
for browser SameSite cookie enforcement. Credentialed cross-site fetches do not
send the backend's SameSite=Lax CSRF challenge cookie, so refreshing the token
alone cannot repair the submission.

## Change and alternatives

`frontend/lib/api-base.ts` now shares the default endpoint between authentication,
normal API requests, media and exports. A localhost page uses localhost:8000;
127.0.0.1 retains its existing endpoint. Explicit NEXT_PUBLIC_API_BASE configuration
remains authoritative. No CSRF bypass, cookie weakening, account changes or new
authentication mechanism was introduced. A same-origin reverse proxy is a possible
deployment choice, but unnecessary for this narrow development fix.

## Verification

- New subprocess-based origin regression reproduced localhost's wrong endpoint
  before the fix; it passed afterward. Loopback and explicit deployment cases pass.
- Frontend tests: 82 passed, zero failed. TypeScript no-emit check passed.
- Actual Chrome at localhost:3000/login: a deliberately nonexistent diagnostic
  account returned “Email or password is incorrect”, rather than a CSRF rejection.
  No account was created; no real password was used or changed.
- This verifies browser challenge-cookie delivery and the pre-authentication
  boundary, not a successful login with the owner's credentials.

The implementation and regression were AI-assisted; the diagnostic asserts request
destination behaviour rather than generated prose. Existing security tests remain
in place. Configuring an explicit cross-site backend still requires an intentional
deployment cookie/proxy strategy; this change does not rewrite that configuration.
