# Phases 7–9 verification (2026-10-06)

Implementation is on three dependent feature branches, not merged to `main`.
The runtime remains a local research system; these checks are not a production
readiness certification or a guarantee of model accuracy.

## Automated checks

- Backend: 121 tests passed; 92.17% coverage. Ruff lint and format checks passed.
- Frontend: 33 tests passed; 99.19% line coverage, 94.08% branch coverage.
  ESLint, Prettier and the production build passed. Test workers are bounded at two
  to avoid machine-overload timeouts; assertions and coverage gates are unchanged.
- Artifact verification: both original CSVs and all four serving model checksums
  match the existing manifest. No serving model was retrained or promoted.
- Job tests cover inventory/delivery, record errors, failed retries, cancellation,
  restart/lease recovery, stale-worker protection, model/source mismatch, duplicate
  admission and a crash after case save but before the job checkpoint.
- Export tests cover all operational/research windows, baselines, diagnostic cases,
  HTML escaping, finite chart coordinates, legacy evidence, JSON report hashes,
  sanitized filenames, incomplete jobs, unknown IDs and response security headers.

## Browser and runtime checks

An isolated temporary SQLite database was used on API port 5001 and frontend 5174.
The user's operational database and servers on their usual ports were not changed.

- Process all three test records completed with three successes and zero failures
  using the existing serving models; progress and case-navigation controls rendered.
- A separate 120-row artificial test fixture produced an actual temporary held-out
  evaluation, verifying baseline/threshold/all-window UI integration. Its easy labels
  and perfect test scores are **not project performance evidence**.
- The saved full-source Porter benchmark rendered its actual results, variants,
  limitations, case counts and charts. The exported HTML layout was inspected using
  the same renderer on a local QA route, including its summary and window tables.
- The browser export button reached the HTML endpoint successfully (HTTP 200).
  Automated capture of the in-app browser's blob download timed out; saved-file
  completion in the user's normal browser still needs a manual check. The download
  client and endpoint tests passed. No final project document was generated.
- Visual inspection prompted a responsive processing-button fix and clearer research
  labels. All QA-only routes/databases are outside the committed application.

## Remaining checks and boundaries

Run a full-size import locally to measure runtime/disk use on your machine; the
browser smoke test intentionally used three records, not all 91,250. Save a JSON
and HTML download in your normal browser before your guide review. Printed PDF
pagination is browser-dependent and was not automatically verified. Review/merge
dependent PRs only after explicit approval. Authentication, distributed workers,
live feeds, observed deadline labels and serving promotion remain future scope.
