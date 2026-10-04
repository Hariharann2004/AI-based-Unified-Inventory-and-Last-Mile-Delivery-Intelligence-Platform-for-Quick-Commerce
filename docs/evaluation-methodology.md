# Held-out workbench evaluation

Evaluation trains temporary LightGBM models without loading or overwriting serving
artifacts. Source import SHA-256 and library versions are saved with each local report.
Model settings remain 300 estimators, learning rate 0.05, 31 leaves and seed 42.

Inventory uses three expanding windows ending at 60%, 80% and 100% of available dates.
Each uses roughly 60/20/20 training/validation/test dates. Whole dates stay together.
Demand is daily tabular prediction, not a multi-step forecast. Stockout labels are derived.

Delivery uses three 60/20/20 grouped splits with seeds 42, 43 and 44. Identical feature
vectors stay together. No verified timestamp exists in the application schema, so this
is not temporal backtesting. `delivery_rating` is excluded from evaluation because
pre-delivery availability is unverified. Serving artifacts still contain that feature;
evaluation models are not automatically promoted.

Classification thresholds are chosen from 0.35, 0.5 and 0.7 using validation F1 only.
Both the selected threshold and the operational 0.7 threshold are reported on test rows.
Reports include precision, recall, F1, ROC-AUC, average precision, Brier score,
calibration counts, confusion matrices, precision-recall points, regression errors,
segment counts and a sampled actual/predicted plot. The constant demand/ETA baseline
is the training-target mean, a reference formula rather than another trained algorithm.

## Full-dataset verification

Locally verified on 2026-10-04: all 91,250 inventory and 25,000 delivery rows imported
without input rejection. Three windows completed for each dataset; no serving binaries
were modified. Latest inventory window: demand MAE 4.7815, stockout precision 0.5000,
recall 0.3262, F1 0.3948. Delivery without rating: ETA MAE 3.2681–3.3102 minutes,
delay ROC-AUC 0.6170–0.6407 across the three splits. These are measured results, not
claims of improved production performance. Earlier inventory periods have substantially
different risk prevalence and performance; inspect all windows rather than one headline.

## Runtime boundaries

POST `/api/workbench/evaluations` with `kind` and `import_id` starts a bounded local
background job; GET `/evaluations` or `/evaluations/<id>` reads persisted status/results.
The entire selected import is evaluated. Jobs are local, single-process workers, not a
durable distributed queue: restart interrupts unfinished jobs. Restarted jobs must be
rerun explicitly. Keep the API local until authentication/authorization is implemented.
Stress scenarios and replay never count as held-out accuracy evaluation.
