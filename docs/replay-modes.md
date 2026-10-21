# Historical replay and mixed-priority demonstration

The Replay & scenarios page separates chronological processing from deliberately
selected saved examples. Both use exactly Critical, High and Normal priorities;
the priority rules and trained models are unchanged.

## Historical replay: date selection

1. Choose the inventory import in Historical replay.
2. Optionally set a start date, an end date, or both. Both boundary dates are included.
3. Prepare a step-by-step replay or start automatic replay.
4. Inspect the requested range, actual selected dates and eligible-record count.

Dates apply only to the next run, not an already prepared run. Empty boundaries
are open-ended. Records remain in date/source-row order. The UI takes up to the
first 100 matches; a range with more matching rows is not claimed to be fully
processed. The API allows up to 500. Reversed/invalid ranges are rejected, and an
empty range produces a useful error instead of silently switching periods.

Delivery operational records have no verified timestamps. Their replay retains
source-row ordering and rejects date filters; it does not substitute Porter data.
Existing saved replays remain readable and their selected IDs are unchanged.

`POST /api/workbench/replays` accepts optional ISO `start_date` and `end_date`
alongside `kind`, `import_id` and `limit`. A run snapshots its requested range,
selected dates and eligible-record count. Stepped events include their source date.

## Mixed-priority demonstration: saved evidence only

1. Choose a record type/import in the separate Mixed-priority demonstration panel.
2. Choose 1, 3, 5 or 10 saved cases per available priority (default: three).
3. Click Load mixed-priority demonstration.
4. Inspect available counts, selected counts and recorded dates, then open original
   cases to show their calculations, predictions and model identities.

The read endpoint is
`GET /api/workbench/replay-demonstrations?kind=inventory&import_id=<id>&per_priority=3`.
The API accepts 1–10 per priority, at most 30 cases. It does not train, predict,
create cases, approve drafts or persist a new replay.

Selection uses only saved `historical_dataset` assessments matching the chosen
import, kind and unchanged source inputs. Synthetic scenarios and replay copies
are excluded. Each source record contributes its latest eligible saved assessment
only, avoiding duplicate model versions. Priority must match its saved decision.
Within each priority, selection prefers evenly spread distinct recorded dates;
remaining slots are filled by other distinct records in source order. Selection
is deterministic for the same saved data.

This is a deliberately selected demonstration, **not** a representative sample,
chronological replay, new prediction run or accuracy evaluation. Do not calculate
accuracy or infer population priority proportions from its selected counts.
Saved assessments can reflect earlier model versions; their linked evidence shows
the actual model identity. Source records and original case/audit state stay intact.
Delivery cases without recorded dates make no chronological-coverage claim.

If a priority is absent, its count stays zero and the UI explains it. No source
values or outputs are changed to fill missing groups. Process additional genuine
records in Operations if more saved examples are needed. Changing form selections
does not silently relabel a displayed snapshot; loaded source metadata is shown.

Scenario laboratory remains separate and unchanged: it modifies copies for labelled
stress tests, never historical observations or accuracy evidence.
