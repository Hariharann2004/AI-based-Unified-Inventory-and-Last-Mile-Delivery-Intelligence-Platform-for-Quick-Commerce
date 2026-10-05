# ETA research results — 2026-10-05

This is the first full-source run of the separate approved Kaggle ETA benchmark.
The [machine-readable evidence](../reports/porter_eta_benchmark.json) includes the
source checksum, library versions, all validation candidates, partition hashes,
baselines, diagnostic cases, error histograms and sampled prediction points.
See the [research guide](delivery-research-guide.md) to reproduce it.

## Results in easy terms

MAE is the average absolute error in minutes: **lower is better**. The constant
baseline predicts the median delivery duration learned from the training partition.
The model must beat that simple reference to justify its added complexity.

| Source-date window end | Held-out records | Median baseline MAE | Order-only MAE | Load-assumption MAE |
|---|---:|---:|---:|---:|
| First 60% of dates | 26,450 | 13.8844 min | 12.9073 min | 11.8317 min |
| First 80% of dates | 35,428 | 12.2152 min | 15.7053 min | 11.5369 min |
| All dates | 43,474 | 14.0419 min | 12.2627 min | 11.4574 min |

Order-only beats the median baseline in two of three windows, but fails in the
middle window. The optional load assumption beats it in all three. This is not a
guarantee of future performance: its snapshot timing still needs source confirmation.
The windows overlap and their scores cannot be treated as independent experiments.

Latest-window order-only: median absolute error 9.22 minutes; 53.36% of predictions
within 10 minutes; RMSE 31.89 minutes; R² 0.0649. Load assumption: median error 8.42
minutes; 57.62% within 10 minutes; RMSE 31.55 minutes; R² 0.0845.
These are modest results. R² is not classification accuracy, and being within 10
minutes is a separately labelled tolerance measure, not a general accuracy score.
The middle-window order-only R² is negative (-0.3223), indicating a poor period.

## Honest limits and controls

- The source contains 197,428 rows, with seven missing completion outcomes rejected.
- All finite positive durations are retained at ingestion, including 138 above 180
  minutes. Training/validation additionally purge outcomes unavailable by their
  respective cutoffs; there is no duration-based pruning or clipping to raise scores.
- Each variant/window tunes three fixed LightGBM configurations using validation
  MAE only; the shallow configuration was selected in all six runs. No test-driven
  retuning follows this report.
- Latest partitions: 109,170 training, 44,401 validation and 43,474 test rows.
  Outcome-availability purging excluded 200 training and 176 validation rows.
- Latest test includes 27 durations above 180 minutes. Their errors stay in the
  primary score; the higher RMSE reflects sensitivity to large errors.
- Cases include seen/unseen stores, source-clock weekdays/weekends and extreme
  durations. Duration cases use outcomes for reporting only, never as model inputs.
- The dataset lacks recorded promised deadlines, distances, traffic/weather and a
  documented business timezone. Its median duration is about 44 minutes; it is not
  verified 10-minute quick-commerce evidence.
- Source collection provenance is unverified. The load variant is explicitly an
  assumption-based research ablation, not an operationally validated improvement.

## Promotion decision and next implementation

**Do not promote either research variant to the workbench's serving model yet.**
Confirm source/input timing and operational compatibility first. The original
delay classifier, ETA model, inventory models, raw baseline and artifact checksums
remain unchanged. Scores from the old dataset are not directly comparable with this
new domain/target; this report claims no improvement to the old delay accuracy.

The next software phases are full-import background processing, clearer evaluation
screens and guide-review exports. Those do not themselves improve model accuracy.
For stronger predictive evidence, obtain documented order-time distance/route and
workload information, plus genuine promised deadlines if delay classification is
required. Future tuning must use a new documented protocol/holdout rather than
feeding these already observed test results back into the same experiment.

Dataset attribution: Ranit Sarkar, [Porter Delivery Time Estimation](https://www.kaggle.com/datasets/ranitsarkar01/porter-delivery-time-estimation),
Kaggle version 1, listed CC BY-NC 4.0. Raw data is local and not published in these PRs.
