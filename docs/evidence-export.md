# Guide-review evidence exports

After an operational evaluation completes, use **Download JSON** or **Download
printable HTML** in Model evaluation. The separate ETA research area offers the
same controls for the saved Porter evidence. Downloads contain every test window,
not only the currently selected one. They never include raw datasets or joblib files.

- JSON preserves all metrics, sampled chart points, configuration/protocol fields,
  source provenance and warnings. `report_sha256` hashes the canonical report object
  using sorted JSON keys, UTF-8, `ensure_ascii=False` and standard JSON separators.
- HTML contains offline charts, baseline comparisons, confusion matrices or case
  coverage, all-window tables and source/experiment provenance. Text is escaped;
  no scripts or remote assets are used. Complete JSON evidence is available in an
  expandable section, hidden in print to avoid printing thousands of sample lines.
- Open the HTML download in a browser, then Print → Save as PDF for guide review.
  The export timestamp is UTC; it is not a research training-run timestamp.

API endpoints (formats are only `json` and `html`):

```text
GET /api/workbench/evaluations/<evaluation_id>/export?format=html
GET /api/workbench/research-benchmarks/porter-eta-v1/export?format=json
```

Unknown IDs return 404, unfinished/failed operational evaluations return 409 and
unsupported formats return 400. Responses are attachments with no-store, nosniff
and a restrictive Content Security Policy. The research reader only accepts its
fixed benchmark ID and checks the approved source manifest.

Do not call ETA tolerance rates “accuracy”, mix metrics across different datasets,
or treat overlapping windows as independent trials. Legacy reports clearly show
missing baseline evidence; rerun them to get the training-majority baseline.
This feature exports evaluation evidence. The final project document is a separate
next task; no serving model, external workflow or deployment is promoted here.
