# Operations workbench reference

## What is automated

Prediction inputs are retrieved from validated stored CSV records. Batch processing
applies the four existing LightGBM models and transparent policies, saves cases and
exposes evidence. Automatic replay advances a bounded historical sequence without
manual feature entry. Operators still choose imports, start runs and review drafts.
This is local historical automation, not an always-on live production integration.

## Review walkthrough

1. Start the backend and frontend using the README. Open Operations.
2. Import the local inventory and delivery datasets. Existing file hashes are reused;
   reports show accepted/rejected counts. CSV uploads use the same validation path.
3. Choose inventory, filter by exact `WH_1` / `SKU_1`, and analyze a case or process the
   displayed page. Inputs are loaded automatically. A page contains up to 20 records.
4. In Cases, inspect priority, stock/risk evidence, model contributions and provenance.
   Expand model identity/inputs. Approve a draft or dismiss with a reviewer label and
   reason. These are local audited transitions, not real purchases or messages.
5. In Replay, prepare a step-by-step run, advance five records, then try automatic
   replay and pause/continue. The UI caps runs at 100 records; the API supports 500.
   Inventory uses recorded dates; delivery uses source-row order, not verified time.
6. Run Depleted stock, Extended supplier lead time or Peak-hour traffic pressure.
   Combined stress requires two selected records and an explicit mapping reason;
   it never claims the independent datasets describe the same real order.
7. In Model evaluation, start evaluation of an entire import or select an existing
   completed report. Inspect all three windows/splits, confusion matrices, precision-
   recall, calibration, actual/predicted plots and warehouse/traffic segments.

## Evidence and boundaries

- Model contributions describe model influence, not causality. Classification
  contributions are log-odds, not additive probability percentages.
- Stress inputs are labelled synthetic and original records remain unchanged.
- Replay snapshots source IDs and serving-model hashes; model changes require a new run.
  Failed records are recorded and consumed, not silently skipped as successful cases.
- Cases are deduplicated by inputs, model identity and provenance. Review does not
  reopen a previously reviewed case. Draft execution remains disabled.
- Outcomes are stored separately from prediction inputs. Held-out evaluation trains
  temporary models and selects thresholds on validation data, never test data.
- Serving models retain the original feature contract, including delivery rating.
  The newer delivery evaluation excludes rating; its weaker results are intentional
  evidence of a stricter protocol, not a regression hidden by a flattering metric.
- Interrupted evaluation jobs are marked failed after API restart. Rerun explicitly.
  The worker assumes one local API process; no durable queue or authenticated users.
- Imports, cases, replay and evaluation reports live in the configured local SQLite
  database (`data/platform.db` by default), which is ignored by Git.

## Validation recorded on 2026-10-04

58 backend tests passed (88.89% total coverage); 23 frontend tests passed (98.96%
line coverage, 93.49% branch coverage). Backend/frontend lint, formatting and frontend
production build passed. Full local datasets accepted 91,250 inventory and 25,000
delivery rows. Three evaluation windows/splits completed per dataset; see
[evaluation methodology](evaluation-methodology.md) for measured results and limits.

Live browser checks verified stored input retrieval, case analysis, native model
explanations, a five-record replay step, a labelled depleted-stock scenario, internal
draft approval and its persisted audit entry, and both inventory/delivery report charts.
Evaluation layouts were inspected at 1280px desktop and 390px mobile widths.

The six branches/PRs are documented in [implementation phases](implementation-phases.md).
Datasets, serving model binaries and the local database are not uploaded in those PRs.
