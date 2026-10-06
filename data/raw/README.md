# Project source CSVs

Open these original CSV files in VS Code or Excel. They are intentionally ignored
by Git, but remain visible in the supplied `Unified Intelligence.code-workspace`.

| File | Original rows | Role |
| --- | ---: | --- |
| `supply_chain_dataset1.csv` | 91,250 | Inventory operations |
| `Quick_Commerce_Delivery_Logistics.csv` | 25,000 | Existing delivery-model compatibility |
| `Porter_Delivery_Time_Estimation.csv` | 197,428 | Separate ETA research benchmark |

Porter is the unchanged approved Kaggle CSV, not generated data. It has no promised
deadline or delay label and does not replace the current delivery model. Its seven
missing completion outcomes remain in this raw file; research evaluation excludes
them. The legacy delivery CSV retains its rating-timing and delay-label limitations.

In the interface, open **Operations → Project datasets · CSV preview & download**
to select any source, preview original rows or download the complete CSV. Choose
**View Porter ETA results** to open its separate saved research comparison.
The same source controls appear under **Model evaluation → ETA research benchmark**.
Previewing a CSV does not import it, train a model or generate cases.

Do not save spreadsheet edits over these originals: their checksums are verified
against `artifacts/manifest.json` and `artifacts/delivery-benchmark-source.json`.
The archived legacy CSV remains a recovery copy in `data/archive/legacy_delivery`.
The original Porter ZIP remains in `porter_candidate_v1` for source recovery.
