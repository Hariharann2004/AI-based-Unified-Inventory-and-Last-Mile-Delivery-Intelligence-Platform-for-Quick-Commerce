# Separate delivery ETA research benchmark

This workflow uses the [approved Kaggle candidate](delivery-dataset-selection.md),
not the existing operational delivery schema. It does not create fabricated warehouse,
distance, traffic or delay fields to force compatibility with the old model.

## Inspect the source

Run from the project root with the Python 3.12 backend environment activated:

```powershell
python -m unified_intelligence.inspect_delivery_research
```

The default input is the locally downloaded, ignored archive
`data/raw/porter_candidate_v1/porter-v1.zip`. Obtain version 1 from the Kaggle link
in the source manifest if it is absent. `--archive` and `--manifest` accept explicit
paths. The loader checks the CSV member's size, SHA-256, columns and row count.
It reads in memory, without extracting or writing raw rows to the repository.

Use `--output reports/research-source-local.json` to save a new aggregate report.
Existing output files are never replaced. A changed source must be reviewed and
versioned, not silently accepted by changing a hash to bypass verification.

The [source audit](../reports/porter_source_audit.json) reports 197,421 eligible
positive, finite durations and 7 rejected missing outcomes from 197,428 source rows.
All 138 durations above 180 minutes remain included. Missing inputs are preserved,
not filled with means computed from the entire dataset.

Creation timestamps are inputs; completion timestamps and elapsed minutes are
separate outcomes. The loader preserves source row indices. Timestamps use a
common arithmetic reference for parsing; this does not establish the business
timezone of naive source timestamps.

## Boundaries

This is research ingestion, not an import into Operations or SQLite. Its ETA target
includes preparation/waiting and is not the current CSV's delay flag. No customer
deadline exists. No serving model is replaced or promoted by source inspection.

A new source is not proof that model performance has improved. Research feature
construction and training stay separate from operational model promotion.

## Prediction-time features

The research feature builder allowlists order/store/category fields and source-clock
calendar values. It cannot accidentally include completion timestamps, elapsed time,
ratings or a delay flag even if a caller adds those columns. Invalid numeric inputs
become missing rather than zero. LightGBM handles numeric missingness natively.

Categorical vocabularies are fitted on training inputs only; unknown categories in
validation/test become missing. Native categories avoid allocating a large dense
one-hot matrix for thousands of stores. No whole-dataset mean imputation is used.

Fleet/load fields and two workload ratios require `include_load=True`; they are
excluded by default because their snapshot collection timing is unverified. Any
load-inclusive comparison must retain an explicit availability warning and an
order-only reference. Calendar fields use source-clock time, not verified local
peak-hour labels. Training/test protocols are implemented in the following phases.

## Train and test the separate ETA benchmark

```powershell
python -m unified_intelligence.benchmark_delivery --output reports/eta-research-local.json
```

This trains three predeclared LightGBM configurations (standard, regularized and
shallow) on the first 60% of whole source dates. Validation uses the next 20%; only
validation MAE chooses the configuration. The selected model is then evaluated on
the last 20%. Training outcomes completed after the validation cutoff are purged;
validation outcomes completed after the test cutoff are purged. Counts and source-row
index hashes make the actual partitions inspectable. No test-driven feature/tuning
choice or automatic refit/promotion follows evaluation.

Reports contain MAE/RMSE in minutes, R², median error and the fractions of predictions
within 5/10 minutes. R² is not classification accuracy, can be negative and is null
for a constant observed population. Compare against both training-mean and
training-median constant forecasts, not against scores from the old dataset.

`--include-load` enables the unverified fleet-snapshot assumption and prints a warning.
The default remains order-only. All eligible positive durations stay included; no
hard-coded 180-minute removal or clipping is applied to improve test scores.

The command creates temporary in-memory models and writes only a new research JSON
report. It never saves `.joblib` files, changes the artifact manifest or replaces the
models powering the workbench. Test results must not become tuning feedback for the
same holdout; future model changes need a new documented evaluation protocol/data.

The leakage controls follow [scikit-learn's guidance](https://scikit-learn.org/stable/common_pitfalls.html).
The bounded complexity configurations follow [LightGBM tuning guidance](https://lightgbm.readthedocs.io/en/stable/Parameters-Tuning.html).
