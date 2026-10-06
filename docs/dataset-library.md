# Source dataset visibility

All three original source CSVs are viewable in the main project's `data/raw`:
inventory (91,250 rows), legacy operational delivery (25,000 rows), and separate
Porter ETA research (197,428 rows). The restored legacy CSV is byte-identical to
the recovery copy retained under `data/archive/legacy_delivery`.

Open `Unified Intelligence.code-workspace` in VS Code. Its project-scoped setting
keeps ignored CSVs visible in Explorer. No dataset or model binary is added to Git.

## Review walkthrough

1. Restart Flask after this code change if the API is not using auto-reload.
2. Open Operations and locate **Project datasets · CSV preview & download**.
3. Porter is selected by default. Its location, actual counts and research role
   appear above **Preview original CSV** and **Download original CSV**.
4. Preview original rows. Use horizontal scrolling for all columns and previous/
   next controls to browse ten records at a time. Download contains the entire CSV,
   not just the preview. Missing source values remain missing.
5. Select Delivery operations (legacy) to show/download its original CSV. The
   existing Import local delivery button below still uses this legacy schema.
6. **View Porter ETA results** opens Model evaluation in ETA research mode. Source
   controls also remain available there when the saved research report is absent.

## Read-only API

- `GET /api/workbench/datasets`: allowlisted source metadata and availability.
- `GET /api/workbench/datasets/<id>/preview?limit=10&offset=0`: original CSV records.
- `GET /api/workbench/datasets/<id>/download`: complete original CSV attachment.

IDs are `inventory`, `delivery` and `porter-eta`. Clients cannot supply file paths.
Preview limits are 1–50 and offsets are nonnegative. CSV counts and SHA-256 are
checked from the local file and cached by file size, modification time and expected
manifest checksum. Missing or modified sources remain visible as unavailable and
cannot be silently downloaded. Source paths must resolve inside `data/raw`.

No prediction, import, database write, training, outcome imputation or serving-model
promotion occurs in these endpoints. Porter has no promised deadline/delay label;
its original business provenance and load observation timing remain unverified.
The legacy source retains its existing rating/label limitations.
