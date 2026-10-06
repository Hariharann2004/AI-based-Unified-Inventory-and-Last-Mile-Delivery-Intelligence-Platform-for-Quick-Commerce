"""Read-only discovery of approved source CSVs, separate from operational imports."""

import csv
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from itertools import islice
from pathlib import Path

from unified_intelligence.core.config import PROJECT_ROOT


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    filename: str
    role: str
    purpose: str
    warning: str
    artifact_name: str | None = None


DATASETS = (
    DatasetSpec(
        "inventory",
        "Inventory operations",
        "supply_chain_dataset1.csv",
        "Operational inventory",
        "Demand estimation and derived stock-coverage risk.",
        "Stockout risk is a derived coverage label, not an observed fulfilment failure.",
        "inventory-source",
    ),
    DatasetSpec(
        "delivery",
        "Delivery operations (legacy)",
        "Quick_Commerce_Delivery_Logistics.csv",
        "Operational delivery (legacy)",
        "Compatibility source for the existing delivery ETA and delay models.",
        "Rating timing and supplied delay-label meaning remain unverified. "
        "This is not the Porter ETA research dataset.",
        "delivery-logistics-source",
    ),
    DatasetSpec(
        "porter-eta",
        "Porter Delivery Time Estimation",
        "Porter_Delivery_Time_Estimation.csv",
        "Separate ETA research benchmark",
        "Timestamp-based ETA research. The saved comparison is in Model evaluation "
        "under ETA research benchmark.",
        "Porter has no promised deadline or delay label and is not a replacement for "
        "the operational delivery model. Business provenance and load timing remain unverified.",
    ),
)


@lru_cache(maxsize=32)
def csv_summary(path_name, size, modified_ns, expected_sha256):
    """Cache only by source identity and file stat; never rewrite the source."""
    path = Path(path_name)
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("CSV checksum does not match the approved source manifest.")
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        columns = next(reader, [])
        if not columns or len(set(columns)) != len(columns):
            raise ValueError("CSV must contain unique column headers.")
        rows = sum(1 for row in reader if row)
    stat = path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (size, modified_ns):
        raise ValueError("CSV changed while being read. Refresh the dataset library.")
    return {"row_count": rows, "columns": columns, "sha256": digest.hexdigest()}


class DatasetService:
    def __init__(self, root=PROJECT_ROOT):
        self.root = Path(root).resolve()

    def spec(self, dataset_id):
        for spec in DATASETS:
            if spec.dataset_id == dataset_id:
                return spec
        raise KeyError("Dataset not found.")

    def path(self, dataset_id):
        spec = self.spec(dataset_id)
        path = (self.root / "data" / "raw" / spec.filename).resolve()
        if not path.is_relative_to(self.root / "data" / "raw"):
            raise ValueError("Dataset path must stay inside data/raw.")
        return path

    def expected_hash(self, spec):
        if spec.artifact_name:
            manifest = json.loads((self.root / "artifacts/manifest.json").read_text())
            for item in manifest["artifacts"]:
                if item["name"] == spec.artifact_name:
                    return item["sha256"]
            raise ValueError("Dataset is missing from the approved artifact manifest.")
        manifest = json.loads((self.root / "artifacts/delivery-benchmark-source.json").read_text())
        return manifest["csv_sha256"]

    def get(self, dataset_id):
        spec = self.spec(dataset_id)
        path = self.path(dataset_id)
        stat = path.stat()
        summary = csv_summary(str(path), stat.st_size, stat.st_mtime_ns, self.expected_hash(spec))
        return {
            "dataset_id": spec.dataset_id,
            "title": spec.title,
            "filename": spec.filename,
            "relative_path": f"data/raw/{spec.filename}",
            "role": spec.role,
            "purpose": spec.purpose,
            "warning": spec.warning,
            "available": True,
            "size_bytes": stat.st_size,
            **summary,
        }

    def catalog(self):
        datasets = []
        for spec in DATASETS:
            try:
                item = self.get(spec.dataset_id)
            except (OSError, ValueError, KeyError) as error:
                item = {
                    "dataset_id": spec.dataset_id,
                    "title": spec.title,
                    "filename": spec.filename,
                    "relative_path": f"data/raw/{spec.filename}",
                    "role": spec.role,
                    "purpose": spec.purpose,
                    "warning": spec.warning,
                    "available": False,
                    "error": str(error)
                    if not isinstance(error, OSError)
                    else "Source CSV or manifest unavailable. Follow dataset setup in README.",
                }
            datasets.append(item)
        return {"datasets": datasets}

    def preview(self, dataset_id, *, limit=10, offset=0):
        if not 1 <= limit <= 50 or offset < 0:
            raise ValueError("Preview limit must be 1–50 and offset must be nonnegative.")
        metadata = self.get(dataset_id)
        with self.path(dataset_id).open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            records = list(islice(reader, offset, offset + limit))
        return {"dataset": metadata, "records": records, "offset": offset, "limit": limit}

    def download_path(self, dataset_id):
        self.get(dataset_id)  # Verify source identity before serving the original bytes.
        return self.path(dataset_id)
