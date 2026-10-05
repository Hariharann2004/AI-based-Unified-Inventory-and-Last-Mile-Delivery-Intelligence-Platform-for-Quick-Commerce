# Improvement phases after the operations workbench

Each feature gets a dedicated branch, commit(s), tests and PR. PRs are dependent
when a feature uses its predecessor; CI remains pull-request-only. No PR is merged
and no branch is deleted without explicit approval.

| Phase | Feature | Completion gate |
|---|---|---|
| 1 | Current delivery-data audit | Reproducible aggregate evidence; baseline untouched |
| 2 | Kaggle dataset assessment | Verified listing/licence/schema; limitations and approval recorded |
| 3 | Approved dataset integration | Versioned source contract and adapter; original import preserved |
| 4 | Safe delivery features | Only inputs available at the declared prediction time; train-only preprocessing |
| 5 | Training and tuning | LightGBM on train/validation; untouched chronological test and reproducible settings |
| 6 | Comparative evaluation | Baselines, multiple cases, uncertainty and promotion/rollback decision |
| 7 | Full-import processing | Background progress, cancellation, record failures and safe resume |
| 8 | Evaluation interface | Clear metric meanings, baseline comparisons and scenario coverage |
| 9 | Guide-review export | Reproducible evidence report and charts with limitations |

Phase 1 implementation is on `feature/delivery-data-audit`. It adds a CLI, tests and
the current dataset's aggregate snapshot. Phase 2 assesses new data without making
it the serving model's input or inventing missing fields. Remaining phases are not
completed simply because their plan is documented here.

Full-import processing means one user action starts a job; the backend still handles
manageable chunks. It is inference, not model training. The existing evaluation
already evaluates the entire selected import; the operations page processes the
visible 20-record page. Keep these workflows separate in the interface and reports.

No requested feature implies a guaranteed accuracy percentage, a live production
feed, a fabricated observed deadline, or permission to publish raw data/binaries.
