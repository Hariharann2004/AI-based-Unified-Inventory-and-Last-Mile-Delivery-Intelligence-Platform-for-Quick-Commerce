# Delivery-data audit: evidence before replacement

## What this phase does

The audit is a read-only command. It checks the legacy delivery CSV's schema,
missing/invalid values, duplicated inputs, class balance, segment rates, rating
association and the relationship between its delay flag and recorded times.
It neither trains models nor changes labels, imports, predictions or serving binaries.
Only aggregate counts and the source file's SHA-256 are saved in the report.

From the repository root, with the Python 3.12 environment activated:

```powershell
python -m unified_intelligence.audit_delivery data/archive/legacy_delivery/Quick_Commerce_Delivery_Logistics.csv
```

To save a new report:

```powershell
python -m unified_intelligence.audit_delivery data/archive/legacy_delivery/Quick_Commerce_Delivery_Logistics.csv --output reports/delivery-audit-local.json
```

The output file must not already exist: the command never replaces an existing file.
Optional `--source-url` and `--license` record caller-supplied citations, not verified
provenance. Missing columns and invalid labels remain visible in the report.
This command audits the legacy schema; a different dataset needs its own contract.

## Verified findings (2026-10-05)

The reproducible snapshot is [delivery_data_audit.json](../reports/delivery_data_audit.json).

| Check | Finding | Meaning |
|---|---|---|
| Rows | 25,000 | Complete local CSV, not just the visible 20-row page |
| Missing cells / duplicate complete rows | 0 / 0 | Basic completeness does not establish valid labels |
| Delayed / not delayed | 6,669 / 18,331 | Delayed class is 26.676% |
| Always predict the majority class | 73.324% | Descriptive full-data baseline; not a held-out model score |
| Delay agrees with actual time > expected time | 9,389 / 25,000 (37.556%) | The source's delay definition needs clarification |
| Identical inputs excluding ratings | 25,000 distinct groups | No duplicate input groups were found |

The delay disagreement does **not** prove that the dataset is synthetic or incorrect.
The flag could use another business definition. Do not replace it with a new label
without documenting that decision.

Ratings have a very strong association with the flag: ratings 1 and 2 are always
labelled delayed; ratings 4 and 5 are never labelled delayed in this CSV. This is
exploratory association, not evidence of availability at prediction time. If ratings
are collected after the delivery, including them would leak future information.
The existing workbench evaluation already excludes `delivery_rating`; serving
artifacts still contain it and are not automatically replaced by this phase.

Traffic segment delay rates are approximately 26.4–26.8%; workload rates approximately
25.9–27.4%. These marginal rates alone cannot establish the usefulness of combinations
of inputs. They are reasons to investigate, not proof that a model cannot learn.

The exact original Kaggle dataset URL, collection method, licence and delay definition
are unverified. The user confirms Kaggle as the download site but cannot currently
identify the source listing. We do not invent provenance from the filename.

## How to explain the earlier 73% result

Accuracy alone can reward predicting the frequent class. In the user's third test
window, the operational threshold of 0.7 produced 73.50% accuracy but detected none
of the 1,322 delayed deliveries. The always-not-delayed baseline for that test window
is 73.56%, not the full-dataset 73.324% above. These are different populations.

The validation-selected threshold in that window produced 66.72% accuracy, 36.58%
precision, 35.25% recall and F1 35.90%. It detected some delays but still needs work.
Present precision, recall, F1, ROC-AUC and ETA MAE alongside accuracy. Do not compare
the old rating-inclusive training results directly with the stricter evaluation.

See [evaluation methodology](evaluation-methodology.md) for the measured split protocol.

## Next gate

Assess replacement datasets for provenance, licence, prediction-time inputs,
timestamps and observed outcomes. Keep the old dataset as a baseline. A suitable
ETA dataset without recorded deadlines is not automatically a suitable delay
classification dataset. Dataset selection and target changes require an explicit,
documented decision before integration and promotion.
