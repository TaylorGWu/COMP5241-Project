# Teacher profile implementation plan

Approved scope: optional teacher photo, name, biography, institution/independent status,
position, university, degree, experience and multiple subjects. Registration stays
short. Qualification review alone grants teacher access. Include status-refresh feedback.

## Implementation

- [x] Add isolated API tests for persisted profiles, validation, role isolation,
  CSRF, private avatars, safe image decoding, and unchanged approval status.
  Run `pytest tests/test_teacher_profile.py` and observe missing-route failures.
- [x] Add a versioned SQLite profile/avatar migration without changing existing
  users or qualifications. Implement private teacher-owned profile and avatar
  endpoints; administrators can inspect submitted applicants' profile and photo.
  Run the new tests plus auth regression suites.
- [x] Add a localized `/profile` form and teacher navigation entries, reusing the
  current Geist/blue-grey tokens, native labelled select controls, searchable
  multi-select subjects, independent/institution choice and image preview.
  Keep private images authenticated and provide save/error/retry states.
- [x] Improve application refresh with request lock, checking/unchanged feedback,
  explicit failure, approved navigation and rejection display.
- [x] Verify real UI at desktop/mobile, upload/replace/remove, persistence,
  keyboard interaction and pending/rejected/approved boundaries using isolated
  test data. Run frontend tests, TypeScript, build and backend regression tests.
- [x] Update current interface/README documentation and record verification.

No commits, pushes or real-user account mutations are part of this request.

Verification completed 2026-10-24. See
`docs/design/teacher-profile-verification.md` for evidence and its boundaries.
