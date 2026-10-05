# Delivery dataset decision

Assessed on 2026-10-05. There is no universal "best Kaggle dataset": selection
depends on the target, documented origin, licence and prediction-time inputs.
This is a comparison of four candidates, not an exhaustive catalogue ranking.

## Recommended and approved research candidate

Use [Porter Delivery Time Estimation by Ranit Sarkar](https://www.kaggle.com/datasets/ranitsarkar01/porter-delivery-time-estimation)
as a **separate ETA research benchmark**, not an automatic replacement for the
quick-commerce delay model. The user approved this approach on 2026-10-05.

Kaggle's public metadata lists version 1 and a CC BY-NC 4.0 licence. Attribution:
Ranit Sarkar, *Porter Delivery Time Estimation*, Kaggle, version 1. Keep the raw
download local and excluded from Git. Verify source rights before commercial use
or redistribution; the uploader's licence does not independently prove provenance.

The downloaded `dataset.csv` has 197,428 rows and 14 columns, including order
creation/completion timestamps, order composition, store category and fleet/order
load fields. These make it a useful candidate for chronological ETA experiments.
The listing calls it Porter data but does not establish the original collection
chain. Do not claim independently verified Porter, DoorDash or Indian operations.

The target is elapsed time from order creation to completion, including preparation
and waiting, **not just rider travel time**. Missing delivery timestamps occur in
7 rows; 138 observed durations exceed 180 minutes. The maximum is about 141,948
minutes and requires investigation. The median is 44.33 minutes, so this dataset
is not evidence of a 10-minute quick-commerce service.

There is **no recorded promised deadline or delay flag** in these 14 columns.
Evaluate ETA using MAE, RMSE, R² and errors across periods/load cases. A configurable
30/45/60-minute threshold would be a policy scenario, not an observed customer SLA
or the old `delayed` label. Do not manufacture weather, traffic, rider identity,
vehicle, distance or warehouse inputs that this dataset does not contain.

## Other candidates and reasons not to select them first

| Candidate | Useful qualities | Limitation for this project |
|---|---|---|
| [Food Delivery Dataset — Gaurav Malik](https://www.kaggle.com/datasets/gauravmalik26/food-delivery-dataset) | Food-delivery learning dataset; separate train/test/submission files | Metadata licence says "Other (specified in description)", but the description retrieved does not establish clear reuse terms or collection provenance. Needs clarification before integration. |
| [Brazilian E-Commerce Public Dataset — Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | Provider describes anonymised real commercial orders; roughly 100k orders from 2016–2018; CC BY-NC-SA 4.0 | Stronger origin documentation, but parcel e-commerce is a different domain from short-horizon local delivery. A useful separate logistics study, not a drop-in quick-commerce benchmark. |
| [Food Delivery Time Prediction — Denis Kuznetz](https://www.kaggle.com/datasets/denkuznetz/food-delivery-time-prediction) | Compact distance/weather/traffic/time dataset; Apache 2.0 listing | The listing does not establish an operational collection chain. Insufficient evidence to present as a verified real-world performance benchmark. |

The existing CSV remains the baseline. Neither Kaggle popularity nor an online
notebook's high score is an acceptance test. Do not cherry-pick a dataset because
it is easier to predict or compare percentages across incompatible targets.

## Reproducible source and integration gates

The [source manifest](../artifacts/delivery-benchmark-source.json) pins the candidate
CSV bytes and records the approval boundary. The public metadata and file-list
endpoints used for assessment were `/api/v1/datasets/view/<owner>/<slug>` and
`/api/v1/datasets/list/<owner>/<slug>` on `www.kaggle.com`.

1. Load only the pinned CSV from the separate research download; reject changed bytes.
2. Parse timestamps and observed duration; report every invalid target explicitly.
3. Keep missing input values for train-fitted processing; never fill from test data.
4. Declare prediction at order creation. Treat fleet/load fields as candidate snapshots
   whose collection timing still needs verification; provide an order-only ablation.
5. Split by whole source dates in chronological order. Train and tune before exposing
   the test outcomes. Document timezone uncertainty rather than guessing a city.
6. Report a training-mean baseline, multiple temporal windows and segment sizes.
   Report extreme durations instead of silently deleting them to improve scores.
7. Keep experiments separate from serving artifacts. Promotion, operational schema
   changes and deadline-derived classifications need separate review decisions.

Source timestamps are present, but their original timezone is not documented in the
listing retrieved. Their source-clock order can be used provisionally for research;
local peak-hour interpretation is not verified. Numeric monetary units are also
unspecified; do not display order prices as INR or another currency without evidence.
