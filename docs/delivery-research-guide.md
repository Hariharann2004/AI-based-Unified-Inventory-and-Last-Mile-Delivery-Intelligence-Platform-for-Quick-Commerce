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

Safe feature construction, chronological training and comparative evaluation are
subsequent phases. A new source is not proof that model performance has improved.
