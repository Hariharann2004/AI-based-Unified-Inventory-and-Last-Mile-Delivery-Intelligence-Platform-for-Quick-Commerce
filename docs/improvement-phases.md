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

Phase 2 is on `feature/delivery-dataset-selection`. The user approved the
[Porter ETA research benchmark](delivery-dataset-selection.md) as a separate dataset
on 2026-10-05. Its versioned source manifest is tracked; the raw download is not.
The approval is not permission to replace the serving model or invent delay labels.

Phase 3 research ingestion is on `feature/delivery-research-ingestion`: a
checksum-verified loader separates order inputs from completion outcomes, reports
invalid targets and retains extreme durations. It is deliberately separate from the
operational import/model contract. See the [research guide](delivery-research-guide.md).

Phase 4 is on `feature/delivery-research-features`: allowlisted order-creation inputs,
train-only categorical vocabularies, explicit missingness and opt-in load ablation.
No outcome columns or whole-dataset imputations enter the feature builder.

Phase 5 is on `feature/delivery-research-training`: isolated LightGBM candidates,
chronological whole-date partitions with outcome-availability purging, validation-only
selection and held-out ETA metrics against constant baselines. Serving promotion is
not part of this phase.

Phase 6 is on `feature/delivery-research-comparison`: three expanding chronological
windows, order-only/load-assumption comparisons, constant baselines, overlapping
diagnostic cases and complete test error histograms. This is an offline research
benchmark, not yet a new screen in the Operations interface. No serving promotion
is automatic; phases 7–9 remain the full-import/UI/export work.

The first full-source comparison is saved in `reports/porter_eta_benchmark.json`;
the [results explanation](delivery-research-results.md) records the modest measured
performance and the decision not to promote either research model. This does not
complete the future operational integration or UI/export phases.

Phase 7 is on `feature/full-import-processing`: a full-import background job with
per-record checkpoints, progress, cooperative cancellation, explicit failed retries,
lease-based restart recovery and pinned source/model versions. Operations exposes
the controls without removing visible-page processing. See the
[full-import guide](full-import-processing.md). Phases 8–9 are next.

Phase 8 is on `feature/evaluation-evidence-ui`: metric explanations, training-only
baselines, zero-recall warnings, all-window comparisons and a separate saved ETA
research view. See the [evaluation interface guide](evaluation-interface.md).

Full-import processing means one user action starts a job; the backend still handles
manageable chunks. It is inference, not model training. The existing evaluation
already evaluates the entire selected import; the operations page processes the
visible 20-record page. Keep these workflows separate in the interface and reports.

No requested feature implies a guaranteed accuracy percentage, a live production
feed, a fabricated observed deadline, or permission to publish raw data/binaries.
