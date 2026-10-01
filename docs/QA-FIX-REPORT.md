# TsekMate QA Fix Report

- **Branch:** `QA-audit` (the original audit is [`docs/QA-AUDIT.md`](QA-AUDIT.md), kept unchanged as the record)
- **Date:** 2026-10-01
- **Base:** `main` at `ec61f7f`
- **Who fixed and verified:** the same assistant that wrote the audit. **This is not an independent review.** A second
  reviewer should look at the auth design (`apps/api/app/auth.py`, `apps/api/app/main.py`), the grading state machine
  (`apps/api/app/services/jobs.py`), and migration 005 before merging.

Statuses used: **FIXED & VERIFIED** (fixed, with a test or run in this environment showing it), **FIXED — LIVE
VERIFICATION REQUIRED** (fixed, but the proof needs Supabase, Docker, Cloud Run, or the real Claude API, none of which
exist here), **STILL OPEN**.

---

## 1. Summary

### Findings

The original audit's summary table says 12 Medium findings, but its body lists 13 (S-3, S-4, S-5, S-6, B-6 to B-14).
This report uses the body.

| | Critical | High | Medium | Low | Total |
|---|---|---|---|---|---|
| Original findings (`QA-AUDIT.md`) | 1 | 6 | 13 | 16 | 36 |
| New findings found while fixing (N-1 to N-6) | 0 | 1 | 2 | 3 | 6 |

### Status

| Status | Original 36 | New 6 | All 42 |
|---|---|---|---|
| FIXED & VERIFIED | 29 | 3 | 32 |
| FIXED — LIVE VERIFICATION REQUIRED | 5 | 2 | 7 |
| STILL OPEN | 2 | 1 | 3 |

**Still open:**
- **N-3 (High):** an Anthropic key-like value is in the public git history of `main`. The key must be revoked by its
  owner.
- **P-1 (Low):** N+1 queries.
- **P-3 (Low):** grading job state lives in one process.

See section 5.

### Evidence

| Check | Result |
|---|---|
| Backend tests (`cd apps/api && python -m pytest -q`) | **121 passed**, 0 failed (71 existing + 50 new in `tests/test_qa_fixes.py`) |
| QA reproduction probe (`cd apps/api && python ../../docs/qa/repro_probe.py`) | **18 passed**, 0 failed (it now asserts the safe behavior for every original check) |
| Web type check (`npm run typecheck` = `tsc -b`) | Passes |
| Web production build (`npm run build`) | Passes; largest chunk 376 kB (ClassSummary + charts), main chunk 204 kB, no size warning |
| `npm audit` | **0 vulnerabilities** (was 4: 1 high, 3 moderate) |
| Frontend unit tests / lint | **None configured** in `apps/web/package.json` (no test or lint script). Frontend behavior was checked in a real browser instead (next two rows) |
| Browser workflow, Chromium + Playwright, real API + Vite dev server (`docs/qa` section 6) | **26 / 26 steps passed**, no browser console errors |
| Browser checks of frontend-only fixes | **6 / 6 passed** (CSV, settings retry, oversize file, threshold, failed-paper confirm, local date) |

The browser runs used the real API with **only the model call replaced by a local fake** (there is no Anthropic key
here). Everything else was the real code: auth, store, upload validation, the grading pipeline with Pydantic
validation and retry, identity matching, routing, and the web app.

---

## 2. Security verification

- **API authentication:**
  - Every route except `GET /api/health`, `POST /api/auth/signin`, and `GET /api/images/{path}` (expiring HMAC
    signature) is declared on an `APIRouter` whose dependency is `auth.require_teacher`.
  - `test_every_route_except_the_public_ones_requires_sign_in` walks **every registered route (40+)**, including
    included routers. Each one returns 401 with no token, a garbage bearer token, a Basic header, or a malformed token.
  - Tokens are HMAC-SHA256 signed and expire (`SESSION_HOURS`). They are bound to the teacher email and the current
    password, and revoked on sign-out (stored server side).
  - Tampered, forged, expired, old-password, and signed-out tokens are all refused (tests). Sign-in is throttled after
    5 failures per client.
- **Unauthenticated API testing:**
  - Direct requests in the probe, pytest, and the browser run all got 401: lists, gradebook, roster, paper detail,
    grade, regrade, approve, delete, settings, profile, and all adapter routes.
  - The browser run also confirmed that the old token stops working right after **Log out**.
- **Authorization / IDOR:**
  - TsekMate has **one teacher account**, configured by env vars, and every activity, roster, and paper belongs to it.
  - So a signed-in teacher is authorized for everything, and there is no second account whose data an ID change could
    reach. Changing IDs only yields 404, or 409 for invalid state.
  - Per-class or per-teacher authorization does not exist because the data model has no owner column. It is listed
    under the README's *Limits* and is needed before adding a second teacher.
- **Health endpoint:** the public `/api/health` returns exactly `{"ok": true}`. Store, AI configuration, model, and
  environment moved to the signed-in `/api/admin/health`. Tested.
- **Upload validation:**
  - The type comes from the file's bytes: JPEG, PNG, and WEBP are opened by Pillow (with a pixel limit checked before
    decoding); PDF is checked by its header and end marker.
  - HTML labeled as JPEG, damaged PNG/JPEG, truncated PDF, GIF, text, and empty files are refused.
  - Limits: 10 MB per file, 100 files per request, 40 MP per image. Tested.
- **Secrets / default credentials:**
  - No fallback secret remains. `APP_ENV=production` refuses to start when `AUTH_SECRET`/`IMAGE_SIGNING_SECRET` are
    missing, a known placeholder, shorter than 32 characters, or equal to each other, or when the teacher password is
    missing, `tsekmate`, or shorter than 10 characters (tested).
  - Development uses random per-process secrets (tested), and `.env.example` holds empty placeholders only.
  - `.env`, `.env.*`, `apps/api/.env`, and `apps/web/.env` are git-ignored (`git check-ignore`). The built web bundle
    contains no secret names or values (scanned `dist/`).
  - Secrets are never logged; config warnings name the variable, not the value.
  - **But see N-3:** a key-like value is still in the git history.
- **Adapter export:** `/adapter/*` returns student IDs and grades, so it now requires the teacher session like every
  other data route (401 anonymous, 200 signed in; tested). No public exception remains.

---

## 3. Findings

Format per finding: **Issue · Severity · Root cause · Fix · Files changed · Regression test · Verification · Status.**
Test names refer to `apps/api/tests/test_qa_fixes.py` unless stated otherwise. "Probe #n" refers to the numbered checks
in `docs/qa/repro_probe.py`.

### S-1 The API had no authentication
- **Severity:** Critical
- **Root cause:** sign-in compared the password and returned the profile but issued no credential. No route checked
  the caller, and the web app's "session" was just a `localStorage` flag.
- **Fix:**
  - New `app/auth.py`: signed bearer tokens (HMAC-SHA256, expiry, bound to teacher email and password), revocation
    list, and sign-in throttling.
  - `main.py` puts every protected route on `api = APIRouter(dependencies=[Depends(auth.require_teacher)])`, so new
    routes are protected by default.
  - New `GET /api/auth/me` and `POST /api/auth/signout`.
  - The web client sends `Authorization: Bearer`; a 401 clears the session and returns to sign-in, and Log out revokes
    the token on the server.
- **Files changed:** `apps/api/app/auth.py`, `apps/api/app/main.py`, `apps/web/src/lib/api.ts`,
  `apps/web/src/lib/session.ts`, `apps/web/src/pages/SignIn.tsx`, `apps/web/src/components/layout/ProfileMenu.tsx`,
  `apps/web/src/components/layout/Sidebar.tsx`
- **Regression test:**
  - `test_every_route_except_the_public_ones_requires_sign_in`
  - `test_unauthenticated_requests_cannot_read_or_change_anything`
  - `test_sign_in_issues_a_token_that_works_until_sign_out`
  - `test_tampered_expired_and_old_password_tokens_are_refused`
  - `test_sign_in_is_throttled_after_repeated_failures`
  - `test_image_links_need_a_valid_signature`
  - Probe #1
- **Verification:** all pass. The browser run covers the redirect to sign-in, wrong password, login, authenticated use
  of every screen, logout, and old-token refusal.
- **Status:** **FIXED & VERIFIED**

### S-2 Unsafe default secrets and credentials
- **Severity:** High
- **Root cause:** `IMAGE_SIGNING_SECRET` fell back to `local-dev-only-secret` (`.env.example`: `change-me`), and the
  demo password `tsekmate` was the default everywhere.
- **Fix:**
  - `config.py` has no known fallbacks.
  - In production it raises `ConfigError` for missing, placeholder, or short secrets or a weak password.
  - In development it uses random per-process secrets, and the demo password works only there.
  - The Dockerfile sets `APP_ENV=production`, and FastAPI's `/docs` is turned off in production.
  - `.env.example` has empty placeholders.
- **Files changed:** `apps/api/app/config.py`, `apps/api/app/main.py`, `apps/api/.env.example`, `apps/api/Dockerfile`,
  `README.md`
- **Regression test:** `test_production_refuses_missing_or_default_secrets`,
  `test_development_never_uses_a_known_secret`
- **Verification:** both pass. The repo and the `dist/` scan found no secrets in the tree or bundle.
- **Status:** **FIXED & VERIFIED** (the Docker image itself was not built here; see S-8)

### S-3 CORS allowed every `*.vercel.app` origin
- **Severity:** Medium
- **Root cause:** a hard-coded `allow_origin_regex`.
- **Fix:** removed. Only `CORS_ORIGINS` applies, plus an optional explicit `CORS_ORIGIN_REGEX`. Methods and headers are
  limited to what the app uses.
- **Files changed:** `apps/api/app/main.py`, `apps/api/app/config.py`, `README.md`
- **Regression test:** `test_cors_allows_only_configured_origins`
- **Verification:** passes. The local origin is allowed; `evil.vercel.app`, a look-alike domain, and `null` get no
  `Access-Control-Allow-Origin`.
- **Status:** **FIXED & VERIFIED**

### S-4 `/api/health` disclosed the model and setup
- **Severity:** Medium
- **Root cause:** one endpoint served both liveness and admin details.
- **Fix:** public `/api/health` returns `{"ok": true}`; details moved to the signed-in `/api/admin/health`.
- **Files changed:** `apps/api/app/main.py`, `README.md`
- **Regression test:** `test_public_health_discloses_nothing`, probe #11
- **Verification:** pass
- **Status:** **FIXED & VERIFIED**

### S-5 Uploads buffered fully, trusted the declared type, and had no pixel limit
- **Severity:** Medium
- **Root cause:** `await f.read()` before checking the size, `content_type` taken from the client, and Pillow opening
  files without a size check.
- **Fix:** new `services/uploads.py`:
  - sniffs the signature; Pillow verifies the format and size before decoding;
  - checks the PDF header and `%%EOF`;
  - `Image.MAX_IMAGE_PIXELS` is set process-wide.
  - The route reads files in 1 MB chunks and stops just past the limit, caps the file count, and stores each file
    under the **detected** type's extension.
- **Files changed:** `apps/api/app/services/uploads.py`, `apps/api/app/main.py`, `apps/api/app/services/core.py`
- **Regression test:**
  - `test_fake_and_damaged_uploads_are_rejected`
  - `test_oversized_and_too_many_uploads_are_rejected`
  - `test_real_images_keep_their_type_whatever_the_browser_says` (JPEG/PNG/WEBP)
  - `test_pdf_is_stored_and_graded_as_a_document`
  - Probe #15
- **Verification:**
  - All pass: fake HTML labeled as JPEG gets 415, nothing is stored.
  - Remaining note: Starlette's multipart parser still writes the whole request body to a temporary file before the
    route runs. Request size should also be capped at the proxy; Cloud Run caps it at 32 MiB (see N-4).
- **Status:** **FIXED & VERIFIED**

### S-6 Vulnerable frontend dependencies
- **Severity:** Medium
- **Root cause:** react-router 6.x (open redirect advisories) and vite 5 / esbuild ≤ 0.24.2 (dev server).
- **Fix:**
  - Upgraded to `react-router-dom` ^7.18.4 and `vite` ^7.3.6 (with `@vitejs/plugin-react` ^4.7).
  - Removed the v6 `future` flags (now the default).
  - Sign-in's `from` return path accepts same-app paths only; `//` and backslashes are rejected.
- **Files changed:** `apps/web/package.json`, `apps/web/package-lock.json`, `apps/web/src/main.tsx`,
  `apps/web/src/pages/SignIn.tsx`
- **Regression test:** none (dependency versions)
- **Verification:** `npm audit` reports 0 vulnerabilities; type check, build, and the 26-step browser run pass on the
  new versions.
- **Status:** **FIXED & VERIFIED**

### S-7 CSV export allowed formula injection
- **Severity:** Low
- **Root cause:** `downloadCsv` quoted commas, quotes, and LF only.
- **Fix:** text cells starting with `= + - @`, tab, or CR get a leading `'`, and CR is quoted. Numbers (including
  negative numbers) are unchanged.
- **Files changed:** `apps/web/src/lib/format.ts`
- **Regression test:** browser check "S-7 CSV export neutralizes formula cells"
- **Verification:** passes; the exact CSV output was compared byte for byte.
- **Status:** **FIXED & VERIFIED**

### S-8 Container ran as root
- **Severity:** Low
- **Root cause:** no `USER` in the Dockerfile.
- **Fix:** the Dockerfile creates `tsekmate` (uid 10001), which owns `/app` so the caches stay writable, and uses
  `USER tsekmate`.
- **Files changed:** `apps/api/Dockerfile`
- **Regression test:** none
- **Verification:** **not built** (no Docker daemon in this environment).
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### B-1 Papers could get stuck in `grading` forever
- **Severity:** High
- **Root cause:** `grading` was written to the paper row, but its owner existed only in process memory. A restart or a
  crashed thread left the row with no owner, and nothing ever released it. Grade again, delete, and grade-all all
  refused or skipped `grading`, and the web page polled forever.
- **Fix:**
  - Each grading run gets a `grading_attempt` id, written with a compare-and-set on the old status.
  - `jobs.recover_stale()` releases papers whose run is gone (marked before this process started, or older than
    `GRADING_STALE_MINUTES`, default 30). They go back to `uploaded` (never graded) or `failed` with an "interrupted"
    reason and a notification.
  - It never touches papers being graded in this process or inside a processing Saver batch.
  - It runs at startup and on grade, progress, regrade, and delete.
  - A crash inside a grading thread marks the paper `failed`.
  - The progress endpoint reports `stopped` papers and `pending` counts, and the web page stops polling when nothing
    is running and offers **Grade remaining papers**.
  - New store method `update_where` does compare-and-set: one atomic `UPDATE … WHERE` on Postgres, and under the lock
    in the memory store.
- **Files changed:** `apps/api/app/services/jobs.py`, `apps/api/app/store/base.py`, `apps/api/app/store/memory.py`,
  `apps/api/app/store/supabase_store.py`, `apps/api/app/main.py`,
  `apps/api/db/migrations/005_grading_attempts_unique_student.sql`, `apps/api/db/schema.sql`,
  `apps/web/src/pages/Grading.tsx`, `apps/web/src/lib/types.ts`
- **Regression test:**
  - `test_paper_left_grading_by_a_previous_process_is_released`
  - `test_stale_paper_from_this_process_is_released_after_the_timeout`
  - `test_paper_in_a_processing_batch_and_in_flight_papers_are_never_released`
  - `test_crash_inside_a_grading_thread_marks_the_paper_failed`
  - Probe #7, #7b, #7c
- **Verification:**
  - All pass. The restart is simulated by moving `PROCESS_STARTED`.
  - Covered: retry after release grades cleanly; release does not touch completed grades; delete works; the progress
    endpoint reports `running: false` once nothing is grading.
  - A real restart on Supabase / Cloud Run is in the live list.
- **Status:** **FIXED & VERIFIED**

### B-2 Approving during a re-grade lost the approval
- **Severity:** High
- **Root cause:** `approve()` didn't check the status. The grader then deleted the review row (which held the
  approval) and overwrote the status unconditionally.
- **Fix:**
  - Approve, review edits, student assignment, and delete are refused (409) while a paper is `grading`.
  - Approve and assign are compare-and-set on the status (and student) they read, so a concurrent change makes them
    fail cleanly instead of writing.
  - The grader saves its result only if the paper is still `grading` **with the same attempt id**. Otherwise it
    discards the result and deletes the AI row it had just added, leaving no trace.
  - The review draft is cleared only after a successful compare-and-set.
- **Files changed:** `apps/api/app/services/core.py`, `apps/api/app/services/jobs.py`
- **Regression test:**
  - `test_approve_is_refused_while_grade_again_runs_and_the_result_is_deterministic`
  - `test_stale_grading_result_never_overwrites_a_newer_teacher_action`
  - `test_concurrent_approvals_and_grade_again_end_in_one_consistent_state`
  - Probe #6
- **Verification:** all pass. A late result arriving after the teacher hand-graded and approved is discarded; status,
  approval, and scores survive.
- **Status:** **FIXED & VERIFIED**

### B-3 NaN/Infinity corrupted activities and papers permanently
- **Severity:** High
- **Root cause:**
  - FastAPI accepts `NaN`/`Infinity` in JSON, and Pydantic `float` allowed them.
  - The range checks are false for NaN, so the value was stored: in the rubric, the scores, and the **`edit_log`**.
    That is why the paper stayed broken after the score was reset: the log still held NaN.
  - Every response that contained it then failed JSON encoding.
- **Fix:**
  - All request models inherit `In` with `allow_inf_nan=False`, so these are 422 before any store write.
  - `math.isfinite` checks are also in `rubric_problems` and `patch_review`.
  - The custom 422 handler no longer echoes inputs (see N-1).
- **Files changed:** `apps/api/app/models.py`, `apps/api/app/grading/scoring.py`, `apps/api/app/services/core.py`,
  `apps/api/app/main.py`
- **Regression test:**
  - `test_non_finite_numbers_are_rejected_everywhere_and_never_stored`, run for each of `NaN`, `Infinity`, and
    `-Infinity`. It covers rubric points, rubric total, criterion scores, unit points, rubric update, settings
    threshold, and rubric draft points, and checks that nothing is stored and every page still loads.
  - Probe #2, #2b, #5, #5b
- **Verification:** all pass; valid values still work.
- **Status:** **FIXED & VERIFIED**

### B-4 PDF/WEBP read back from Supabase as JPEG
- **Severity:** High
- **Root cause:** `SupabaseStore.get_image` returned `image/jpeg` for every non-PNG file.
- **Fix:**
  - The content type comes from the extension (`.pdf`, `.webp`, `.png`, `.jpg`/`.jpeg`).
  - Files are stored under the detected type's extension (S-5).
  - PDFs reach Claude as `document` blocks.
- **Files changed:** `apps/api/app/store/supabase_store.py`, `apps/api/app/services/core.py`
- **Regression test:**
  - `test_supabase_store_reads_files_back_with_their_real_type` (fake Supabase client)
  - `test_pdf_is_stored_and_graded_as_a_document` (memory store, full pipeline: the request block is
    `document`/`application/pdf`)
  - `test_real_images_keep_their_type_whatever_the_browser_says` (signed URL serves the right type with `nosniff`)
- **Verification:** pass. Not run against a real Supabase bucket or the real Claude API.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### B-5 One upload could give a student two papers
- **Severity:** High
- **Root cause:** IDs in a request were checked only against existing papers, not against each other. There was no
  uniqueness rule in the store or database, and no lock across concurrent requests.
- **Fix:**
  - The whole request is refused when an ID repeats, a student already has a paper, or the **same photo** is already
    in the activity or appears twice in the request (this blocks double-clicks and repeated requests).
  - `core.assignment_lock` serializes every write that gives a paper a student: upload, teacher assignment, and AI
    matching.
  - Unique index `(activity_id, student_id) where student_id is not null` in migration 005 and `schema.sql`, mirrored
    by the memory store (`UniqueViolation`, mapped to 409).
  - Unidentified papers are unlimited and stay unidentified. Legitimate reassignment still works.
- **Files changed:** `apps/api/app/services/core.py`, `apps/api/app/services/jobs.py`, `apps/api/app/store/base.py`,
  `apps/api/app/store/memory.py`, `apps/api/app/store/supabase_store.py`, `apps/api/app/main.py`, migration 005,
  `schema.sql`
- **Regression test:**
  - `test_one_student_can_not_get_two_papers`
  - `test_the_same_photo_can_not_be_uploaded_twice`
  - `test_concurrent_assignments_give_the_student_to_exactly_one_paper` (6 parallel requests: exactly one 200)
  - `test_store_itself_refuses_a_second_paper_for_a_student`
  - `test_supabase_compare_and_set_none_filters_and_unique_violation` (SQLSTATE 23505 maps to `UniqueViolation`)
  - Probe #3
- **Verification:** all pass. The Postgres index itself must be created by running migration 005 (live list).
- **Status:** **FIXED & VERIFIED** (application and store), with the database index in the live list

### B-6 "Save draft" silently changed approved grades
- **Severity:** Medium
- **Root cause:** edits to an approved paper changed the live scores the gradebook reads, without re-approval.
- **Fix:**
  - A save that **changes** an approved paper withdraws the approval: status goes back to `ready`/`needs_review`,
    `approved: false`, and the edit is logged. The gradebook and adapter leave it out until it is approved again.
  - A save that changes nothing keeps the approval.
  - The web app explains this after saving.
- **Files changed:** `apps/api/app/services/core.py`, `apps/web/src/pages/ReviewDetail.tsx`
- **Regression test:** `test_editing_an_approved_paper_withdraws_the_approval_until_approved_again`, probe #10
- **Verification:** passes; the browser run step "Editing the approved paper withdraws approval" passes.
- **Status:** **FIXED & VERIFIED**

### B-7 Invalid unit edits caused 500s
- **Severity:** Medium
- **Root cause:** `unit_edits` was an untyped `dict`, so `float(None)` and `float("x")` raised.
- **Fix:** a typed `UnitEdit` model:
  - finite `points_awarded` between 0 and 1000, never null;
  - the `verdict` enum;
  - strings for text, with length limits;
  - `extra="forbid"`;
  - `null` allowed only for `error_type`.
  - Feedback and free-text lengths are also limited, and activity `date` must be `YYYY-MM-DD`.
- **Files changed:** `apps/api/app/models.py`, `apps/api/app/main.py`, `apps/api/app/services/core.py`,
  `apps/api/app/services/ai_text.py`
- **Regression test:** `test_invalid_unit_edit_types_are_422_and_valid_edits_still_work` (9 invalid shapes),
  `test_activity_date_must_be_a_real_date`, probe #4
- **Verification:** pass
- **Status:** **FIXED & VERIFIED**

### B-8 Background work stalls on Cloud Run and is single-process
- **Severity:** Medium
- **Root cause:** grading threads and the batch poller need CPU between requests; job state is in memory.
- **Fix:**
  - The documented deploy command now uses `--no-cpu-throttling --min-instances=1 --max-instances=1` (Dockerfile
    header and README).
  - B-1 recovery means a restart or scale-down no longer strands papers.
  - Progress also reports papers being graded by another instance (N-2).
- **Files changed:** `apps/api/Dockerfile`, `README.md`, `apps/api/app/services/jobs.py`
- **Regression test:** B-1 tests
- **Verification:** needs a Cloud Run deployment.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### B-9 Dashboard "approved today" depended on the time of day
- **Severity:** Medium
- **Root cause:** sample approvals were dated `now − 1h − 3 min·n` and could cross local midnight in Asia/Manila.
- **Fix:**
  - The seed anchors "today" and "yesterday" to the local day and shrinks the spacing so every approval stays after
    local midnight.
  - `dashboard()` accepts `now` for tests.
- **Files changed:** `apps/api/app/seed.py`, `apps/api/app/services/core.py`
- **Regression test:** `test_seeded_dashboard_is_the_same_at_any_hour` (7 hours × 3 minutes, including Manila
  00:00, 00:01, 00:30)
- **Verification:**
  - Passes. A sweep of every hour of the day (minutes 0, 1, and 30) also gave 26 approved today and 12 awaiting
    review each time.
- **Status:** **FIXED & VERIFIED**

### B-10 `async def upload` blocked the event loop
- **Severity:** Medium
- **Root cause:** synchronous storage writes and Pillow work inside an `async` route.
- **Fix:** validation and `core.add_uploads` run in the thread pool (`run_in_threadpool`).
- **Files changed:** `apps/api/app/main.py`
- **Regression test:** `test_upload_work_does_not_block_other_requests`
- **Verification:** passes. A mutation check (temporarily calling `add_uploads` directly) made it **fail**, so the test
  detects the regression.
- **Status:** **FIXED & VERIFIED**

### B-11 Supabase `reset()` never finished once uploads existed
- **Severity:** Medium
- **Root cause:** Storage lists sub-folders as entries without an id. Removing those paths deletes nothing, so the
  `while True` loop repeated forever.
- **Fix:** `_files_under()` walks folders recursively with paging, then removes files in chunks. There is no unbounded
  loop.
- **Files changed:** `apps/api/app/store/supabase_store.py`
- **Regression test:** `test_supabase_reset_removes_nested_uploads_and_finishes` (fake storage that, like Supabase,
  ignores folder removals)
- **Verification:** passes with the fake. Needs a real Supabase project.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### B-12 Opening Parent update made a paid AI call every time
- **Severity:** Medium
- **Root cause:** the page called `POST /parent-message` (AI) on mount.
- **Fix:**
  - New `GET /api/submissions/{id}/parent-message` returns the saved draft (no AI).
  - The page loads that and offers **Draft a message with AI** / **Draft a new version** buttons.
- **Files changed:** `apps/api/app/main.py`, `apps/web/src/pages/ParentUpdate.tsx`, `apps/web/src/lib/api.ts`,
  `apps/web/src/lib/types.ts`
- **Regression test:** `test_parent_message_rules` (a model call during GET fails the test)
- **Verification:** passes; the browser run step "Parent update: no AI call on open, draft on request, approve" passes.
- **Status:** **FIXED & VERIFIED**

### B-13 No warning about unsaved review edits
- **Severity:** Medium
- **Root cause:** a `dirty` flag existed but nothing checked it.
- **Fix:** new `useUnsavedChanges` hook:
  - `beforeunload` covers closing or reloading the tab;
  - a capture-phase click guard runs on every in-app link before React Router's `<Link>`;
  - `confirmLeave()` covers Back, Next paper, Leave flagged, and Grade again.
- **Files changed:** `apps/web/src/lib/useUnsavedChanges.ts`, `apps/web/src/pages/ReviewDetail.tsx`
- **Regression test:** browser run step "Edit score + unsaved-changes guard"
- **Verification:** passes: after editing a score, clicking the sidebar Gradebook link shows the confirm; dismissing it
  keeps the page.
- **Status:** **FIXED & VERIFIED** (the `beforeunload` prompt cannot be exercised headless; the link path was)

### B-14 Class summary page triggered a paid AI call
- **Severity:** Medium
- **Root cause:** `GET /class-summary` generated misconception names whenever the errors changed. Seed summaries had a
  `"seed"` signature that never refreshed.
- **Fix:**
  - GET only reads the cache and reports `ai_summary.stale`.
  - New `POST /class-summary/refresh` makes the one AI call when the teacher asks.
  - The seed stores the real error signature, so seeded summaries go stale correctly.
  - The signature includes the error type, so a changed error type counts.
- **Files changed:** `apps/api/app/services/core.py`, `apps/api/app/main.py`, `apps/api/app/seed.py`,
  `apps/web/src/pages/ClassSummary.tsx`, `apps/web/src/lib/api.ts`, `apps/web/src/lib/types.ts`
- **Regression test:** `test_opening_the_class_summary_never_calls_the_ai`
- **Verification:** passes (0 calls on GET, 1 on refresh, 0 on the next GET).
- **Status:** **FIXED & VERIFIED**

### B-15 Approve without checking the paper's state
- **Severity:** Low
- **Root cause:** a failed paper with no scores could be approved at 0 by a stray click.
- **Fix:**
  - The server refuses approval of `grading`/`uploaded` papers (B-2).
  - The web app asks for confirmation before approving an AI-failed paper with no scores entered.
  - Re-approving an approved paper remains intended ("Save and re-approve").
- **Files changed:** `apps/api/app/services/core.py`, `apps/web/src/pages/ReviewDetail.tsx`
- **Regression test:** browser check "B-15 approving an AI-failed paper with no scores asks first"; probe #9
- **Verification:** passes; cancelling leaves the paper unapproved.
- **Status:** **FIXED & VERIFIED**

### B-16 Parent message could be approved for an unapproved paper
- **Severity:** Low
- **Root cause:** the approve endpoint checked existence only.
- **Fix:**
  - **Chosen rule:** parent messages (read, draft, approve) exist only for papers whose grade is approved. This is
    the same rule the drafting step already had, because a message must never describe an unreviewed grade.
  - There is no legitimate case for messaging about an unapproved grade in this product.
- **Files changed:** `apps/api/app/main.py`
- **Regression test:** `test_parent_message_rules`, probe #12
- **Verification:** pass (409 for unapproved, 200 for approved)
- **Status:** **FIXED & VERIFIED**

### B-17 Student view showed unapproved results
- **Severity:** Low
- **Correction:** on re-check, the page **already** showed "Your feedback is not ready yet" for unapproved papers. The
  original finding overstated the problem.
- **Root cause:** the remaining exposure was the API, which returned any paper's draft to anyone.
- **Fix:** the API now requires the teacher session (S-1).
- **Files changed:** none beyond S-1
- **Regression test:** browser run step "Student view: approved shows score, unapproved hidden"
- **Verification:** passes
- **Status:** **FIXED & VERIFIED**

### B-18 Review screen hard-coded the 0.75 threshold
- **Severity:** Low
- **Root cause:** `needsCheck` used a literal.
- **Fix:** it uses `useThreshold()` (the Settings value).
- **Files changed:** `apps/web/src/pages/ReviewDetail.tsx`
- **Regression test:** browser check "B-18 review flags follow the Settings threshold"
- **Verification:** passes: 0 flagged problems at 0.75, 5 at 0.95 on the same paper.
- **Status:** **FIXED & VERIFIED**

### B-19 Create Activity date defaulted to the UTC date; the backend accepted any string
- **Severity:** Low
- **Root cause:** `toISOString().slice(0, 10)`; `date: str`.
- **Fix:** a local-date helper in the web app; the API validates `YYYY-MM-DD`.
- **Files changed:** `apps/web/src/pages/CreateActivity.tsx`, `apps/api/app/models.py`
- **Regression test:** browser check "B-19 the new activity date is the local day (Asia/Manila, 00:30)";
  `test_activity_date_must_be_a_real_date`
- **Verification:** pass (`2026-10-02` at 00:30 Manila; the old code would give `2026-10-01`)
- **Status:** **FIXED & VERIFIED**

### B-20 A failed settings request was cached forever
- **Severity:** Low
- **Root cause:** the rejected promise stayed in `inflight`.
- **Fix:** `inflight` is cleared on failure.
- **Files changed:** `apps/web/src/lib/appSettings.ts`
- **Regression test:** browser check "B-20 a failed settings request is retried"
- **Verification:** passes (first call rejected, second resolved)
- **Status:** **FIXED & VERIFIED**

### B-21 Upload input quirks
- **Severity:** Low
- **Root cause:** the input value was never reset, the help text omitted WEBP, and there was no client-side size check.
- **Fix:**
  - The input resets after each pick.
  - The help text says "JPG, PNG, WEBP or PDF".
  - Files over 10 MB are refused before anything is sent.
- **Files changed:** `apps/web/src/pages/Upload.tsx`
- **Regression test:** browser checks "B-21 files over 10 MB are refused before uploading" (no request is sent) and an
  input check that the file input's value is empty after a pick, so the same file can be picked again
- **Verification:** pass
- **Status:** **FIXED & VERIFIED**

### B-22 Store inconsistencies
- **Severity:** Low
- **Root cause:**
  - Supabase `delete(x=None)` used `= NULL`.
  - Criterion names were compared without `strip()` during validation.
  - `reroute` skipped `updated_at`.
- **Fix:**
  - A shared `_filter` uses `IS NULL` for `None` in select, delete, and update_where.
  - `check_against` strips names.
  - `reroute` uses compare-and-set and sets `updated_at`.
- **Files changed:** `apps/api/app/store/supabase_store.py`, `apps/api/app/models.py`,
  `apps/api/app/services/settings.py`
- **Regression test:** `test_supabase_compare_and_set_none_filters_and_unique_violation` (fake client);
  `test_settings_threshold_reroutes_and_profile` (existing)
- **Verification:** passes with the fake client. A real PostgREST run is needed.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### B-23 A roster change could hide approved grades
- **Severity:** Low
- **Root cause:** the gradebook listed roster students only.
- **Fix:** approved papers of students no longer on the class roster are listed as "Approved (not on the class
  roster)".
- **Files changed:** `apps/api/app/services/core.py`
- **Regression test:** `test_approved_grade_stays_in_the_gradebook_when_the_student_leaves_the_roster`
- **Verification:** passes
- **Status:** **FIXED & VERIFIED**

### B-24 CSV object URL revoked immediately
- **Severity:** Low
- **Root cause:** `revokeObjectURL` right after `click()`.
- **Fix:** revoked after 1 s.
- **Files changed:** `apps/web/src/lib/format.ts`
- **Regression test:** browser checks (S-7 and the workflow's CSV export both complete a download)
- **Verification:** pass in Chromium. Safari and Firefox were not tested.
- **Status:** **FIXED & VERIFIED**

### P-1 N+1 queries
- **Severity:** Low
- **Root cause:** `list_activities` builds a full bundle per activity; `queue_row` recomputes `effective()`.
- **Fix:** none (performance work, out of scope for a correctness/security pass)
- **Files changed:** none
- **Regression test:** none
- **Verification:** none
- **Status:** **STILL OPEN**

### P-2 Large JS bundle
- **Severity:** Low
- **Root cause:** every page and recharts were in one chunk.
- **Fix:** routes are `React.lazy` chunks; Sign-in stays eager.
- **Files changed:** `apps/web/src/App.tsx`
- **Regression test:** none
- **Verification:** the build shows the main chunk at 204 kB (was 714 kB), charts only in the ClassSummary chunk, and
  no size warning. The browser run loads every page.
- **Status:** **FIXED & VERIFIED**

### P-3 Per-process job state
- **Severity:** Low
- **Root cause:** `_jobs` and `scoring.THRESHOLD` are module state.
- **Fix:** partial:
  - In-flight tracking is now cleared per paper.
  - Recovery (B-1) covers lost state.
  - Deployment is documented as single-instance (B-8).
  - `_jobs` still keeps one entry per activity, and the threshold is still per process.
- **Files changed:** `apps/api/app/services/jobs.py`
- **Regression test:** B-1 tests
- **Verification:** —
- **Status:** **STILL OPEN** (acceptable with a single instance; must change before scaling out)

### P-4 Missing test coverage
- **Severity:** Low
- **Root cause:** no tests for auth, the Supabase store, restart recovery, or non-finite input.
- **Fix:** 50 new tests in `tests/test_qa_fixes.py`, plus a fake Supabase client for store logic. Existing fixtures sign
  in; `conftest.py` pins a development, memory-store, no-AI environment whatever a local `.env` says.
- **Files changed:** `apps/api/tests/*`
- **Regression test:** itself
- **Verification:** 121 pass. A real Supabase run is still in the live list.
- **Status:** **FIXED & VERIFIED**

---

## 4. New findings while fixing

### N-1 A 422 response that echoed NaN became a 500
- **Severity:** Medium
- **Root cause:** FastAPI's default validation handler returns the submitted `input`. A NaN input cannot be encoded as
  JSON, so the response itself crashed. This would have defeated the B-3 fix.
- **Fix:** a custom `RequestValidationError` handler returns `type`, `loc`, and `msg` only, never the submitted values.
- **Files changed:** `apps/api/app/main.py`
- **Regression test:** `test_non_finite_numbers_are_rejected_everywhere_and_never_stored`
- **Verification:** passes (it failed with a 500 before this handler)
- **Status:** **FIXED & VERIFIED**

### N-2 Progress missed papers graded outside the last local job
- **Severity:** Low
- **Root cause:** progress listed only the ids of this process's last job for the activity.
- **Fix:** every paper still `grading` is included and keeps `running` true.
- **Files changed:** `apps/api/app/services/jobs.py`
- **Regression test:** `test_stale_paper_from_this_process_is_released_after_the_timeout`
- **Verification:** passes (it failed before the fix)
- **Status:** **FIXED & VERIFIED**

### N-3 A key-like Anthropic credential is in the public git history
- **Severity:** High
- **Root cause:**
  - Commit `a9b82be` ("Restore .env.example …") put a value starting `sk-ant-usr-…` into `apps/api/.env.example`.
  - `ecc2c69` removed it from the file, but it remains in the history of `main` on GitHub.
  - This report does not repeat the value.
- **Fix:**
  - **Not fixable from this branch:** removing it from history needs a force-push to `main`, which is not allowed.
  - Required action for the owner: **revoke/rotate that key in the Anthropic Console now** (treat it as exposed),
    then decide whether to purge history (for example with `git filter-repo`) in a coordinated force-push.
  - The other key-like strings in history (`sk-ant-api03-SECRETSECRET…`, `AIzaSyAbcdef…`) are fake test fixtures.
- **Files changed:** none
- **Regression test:** none
- **Verification:** `git log --all -p` scan (values redacted in output)
- **Status:** **STILL OPEN**

### N-4 One multi-file upload could exceed Cloud Run's 32 MiB request limit
- **Severity:** Medium
- **Root cause:** the web app sent every selected file in one request (up to 100 × 10 MB).
- **Fix:** the web app uploads in batches of at most 24 MB / 50 files and reports partial progress if a later batch
  fails.
- **Files changed:** `apps/web/src/pages/Upload.tsx`
- **Regression test:** browser run (single-batch path)
- **Verification:** multi-batch behavior needs a real class set against Cloud Run.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### N-5 The sign-in throttle would count the proxy's address on Cloud Run
- **Severity:** Low
- **Root cause:** a risk in this branch's new throttle: without proxy headers, all clients share the front end's
  address, so one attacker could lock everyone out for 10 minutes.
- **Fix:** the Dockerfile starts uvicorn with `--proxy-headers --forwarded-allow-ips="*"` (only Google's front end can
  reach a Cloud Run container).
- **Files changed:** `apps/api/Dockerfile`
- **Regression test:** none
- **Verification:** needs Cloud Run.
- **Status:** **FIXED — LIVE VERIFICATION REQUIRED**

### N-6 Concurrent sign-outs could drop a revocation
- **Severity:** Low
- **Root cause:** read-modify-write of the revoked-token list.
- **Fix:** a lock around revocation.
- **Files changed:** `apps/api/app/auth.py`
- **Regression test:** `test_parallel_sign_outs_all_stick` (20 parallel sign-outs)
- **Verification:** passes. A passing concurrency test cannot prove the absence of a race; the guarantee comes from the
  lock. It is per process, so with more than one instance, use a database-side append.
- **Status:** **FIXED & VERIFIED**

---

## 5. Remaining issues (still open)

1. **N-3 (High):** revoke the Anthropic key committed in `a9b82be`; optionally purge history with a coordinated
   force-push.
2. **P-1 (Low):** N+1 queries on the activity list and dashboard. Correct, but slow on Supabase as data grows.
3. **P-3 (Low):** job progress and the confidence threshold are per process. Fine with the documented single
   instance; must move to the database before scaling out.

Also not built, by design:
- **Multi-teacher authorization:** the data model has one teacher, so there is no per-class ownership.
- **Mobile layout:** this branch only checked that sign-in fits a 390 px viewport with no horizontal scroll. The
  mobile work lives on the separate `orange-mobile-fix` / `frontend-improvements` branches. They change the same pages
  as this branch (SignIn, Upload, Grading, ReviewDetail, ParentUpdate, ClassSummary), so merging both will need
  conflict resolution.

## 6. Needs live / deployment verification

- **Supabase:**
  - run migration `005_grading_attempts_unique_student.sql` (fix any duplicate papers it reports);
  - confirm `update_where` compare-and-set and the unique index (23505 → 409) on real PostgREST;
  - confirm `get_image` types for PDF and WEBP;
  - confirm `reset()` with nested uploads (`python scripts/seed.py --reset`);
  - confirm `delete(x=None)`.
- **Claude API:** grading of a real PDF (document block) and a small WEBP. The Batch (Saver) path with the new attempt
  ids.
- **Docker:** build the image; confirm it runs as `tsekmate` (non-root) and refuses to start without the three secrets
  (`APP_ENV=production` is set in the image).
- **Cloud Run:**
  - `--no-cpu-throttling --min-instances=1 --max-instances=1`: grading and the Saver poller keep running between
    requests;
  - a restart mid-grading releases papers;
  - the throttle sees real client IPs (`--proxy-headers`);
  - a multi-batch class upload stays under 32 MiB per request.
- **Vercel:** set `CORS_ORIGINS` to the exact web origin (the `*.vercel.app` wildcard is gone). If preview deployments
  must call the API, set a narrow `CORS_ORIGIN_REGEX`.
- **Browsers other than Chromium:** CSV download timing (B-24) and the `beforeunload` prompt (B-13).

## 7. How the browser checks were run

1. The API started from the working tree with `APP_ENV=development` and the memory store. `app.grading.llm.call` was
   replaced by a local fake that answers from the activity in the prompt and can be told to return broken JSON. This
   was a test harness only, not part of the repo.
2. `npx vite` served `apps/web`.
3. Two Playwright (Chromium) scripts drove the app:
   - the workflow: unauthenticated API, sign-in (wrong and right password), dashboard, create activity, open
     activity, edit rubric, upload, duplicate photo refused, AI grading, student identified, review, edit score,
     unsaved-changes guard, save, approve, edit-after-approve, re-approve, gradebook, CSV export, additional upload,
     AI failure, Grade again, student view, parent update, notifications, class summary, logout and token revocation,
     narrow viewport;
   - the frontend-only fixes listed above.

**Limitations:**
- The multi-step Create Activity **form** was not driven. The activity was created through the same API call the form
  makes, with the browser's session token.
- No real handwriting, Claude responses, Supabase, Docker, or Cloud Run were involved.
