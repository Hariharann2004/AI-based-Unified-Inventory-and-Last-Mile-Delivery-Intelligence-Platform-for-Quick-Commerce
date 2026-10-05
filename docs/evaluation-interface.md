# Evaluation evidence interface

The Model evaluation area has two distinct modes:

1. **Operational evaluation** trains fresh temporary LightGBM models from the entire
   selected import. It reports validation-selected risk thresholds separately from
   the 0.7 action policy, regression error against a training-mean baseline and a
   training-majority classifier baseline. Old saved reports remain readable; rerun
   them to obtain the new baseline. Accuracy alone is not successful risk detection.
2. **ETA research benchmark** reads the saved Porter comparison in
   `reports/porter_eta_benchmark.json`. It does not train from the browser or change
   serving models. Compare order-only and opt-in load-assumption variants, three
   chronological windows, constant baselines, case coverage and complete error bins.

MAE/RMSE are measured in target units, not percentages. R² can be negative. Within
±10 minutes is a tolerance rate, not classification accuracy. No observed promised
deadline exists in the research source, so it cannot validate delay labels.
Overlapping windows/cases are not independent trials. Sparse cases show a dash,
not a fabricated score. Scatter plots sample at most 100 rows; overall metrics and
histograms use all test records, including extreme outcomes.

The API only reads the approved server-owned benchmark path and checks its source
checksum against the manifest. Unknown IDs are rejected; clients cannot supply paths.
See [research commands](delivery-research-guide.md) to refresh the saved evidence.
