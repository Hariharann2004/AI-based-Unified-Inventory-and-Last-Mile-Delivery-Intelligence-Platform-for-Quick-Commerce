# Operations workbench phases

Each phase has a dedicated branch and dependent PR. Merge in order only after approval.

| Phase | Branch | Acceptance criteria |
|---|---|---|
| 1 Data | feature/dataset-ingestion | Validated CSV imports, provenance, deduplication and stored records |
| 2 Predictions | feature/explainable-batches | Batch processing, failures, calculations and contributions |
| 3 Workflow | feature/case-workflows | Cases, internal action drafts and audited transitions |
| 4 Replay | feature/historical-replay | Deterministic replay and reproducible scenarios |
| 5 Evaluation | feature/model-evaluation | Isolated evaluation, chronological windows and chart evidence |
| 6 Interface | feature/operations-workbench | Operations, cases, replay and evaluation with responsive charts |

Phases 1–5 have open PRs #3–#7 with passing backend/frontend checks. Phase 6 is
the final interface PR. Each phase is implemented on top of the previous phase,
not as an independent copy of `main`. Merge in order, retargeting the next PR to
`main` after its predecessor merges. This implementation does not authorize merges
or branch deletion; those remain explicit review actions.

LightGBM remains the only trained algorithm. The datasets are independent: no inferred
order-level join. Replay is not live telemetry; stress cases are not accuracy evaluation.
Approvals save internal drafts, not purchases or customer messages. Stockout labels
remain derived. Delivery rating availability must be reviewed before operational use.
CI stays PR-only. No datasets, binaries or local databases are published.
