"""Pinned research-source ingestion, isolated from operational delivery records."""

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ResearchDeliveryDataset:
    inputs: pd.DataFrame
    elapsed_minutes: pd.Series
    created_at: pd.Series
    completed_at: pd.Series
    audit: dict


def load_research_delivery(manifest_path: Path, archive_path: Path) -> ResearchDeliveryDataset:
    """Read the pinned CSV in memory; never extract, import to SQLite or rewrite data."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("dataset_id") != "porter-kaggle-v1":
        raise ValueError("Unsupported research source manifest.")
    with zipfile.ZipFile(archive_path) as archive:
        member = archive.getinfo(manifest["csv_member"])
        if member.file_size != manifest["csv_bytes"]:
            raise ValueError("Research CSV byte size differs from the pinned source.")
        data = archive.read(member)
    digest = hashlib.sha256(data).hexdigest()
    if digest != manifest["csv_sha256"]:
        raise ValueError("Research CSV checksum differs from the pinned source.")
    frame = pd.read_csv(io.BytesIO(data))
    if list(frame.columns) != manifest["columns"] or len(frame) != manifest["rows"]:
        raise ValueError("Research CSV schema or row count differs from the pinned source.")
    required = {"created_at", "actual_delivery_time"}
    if not required.issubset(frame):
        raise ValueError("Research CSV requires creation and completion timestamps.")
    # UTC is a common arithmetic reference, NOT a verified timezone claim for naive timestamps.
    created = pd.to_datetime(frame["created_at"], format="ISO8601", errors="coerce", utc=True)
    completed = pd.to_datetime(
        frame["actual_delivery_time"], format="ISO8601", errors="coerce", utc=True
    )
    elapsed = (completed - created).dt.total_seconds() / 60
    valid = created.notna() & completed.notna() & np.isfinite(elapsed) & (elapsed > 0)
    observed = elapsed.loc[valid]
    audit = {
        "dataset_id": manifest["dataset_id"],
        "source_url": manifest["source_url"],
        "license_as_listed": manifest["license_as_listed"],
        "csv_sha256": digest,
        "rows": len(frame),
        "eligible_observed_targets": int(valid.sum()),
        "rejected_observed_targets": int((~valid).sum()),
        "invalid_creation_timestamps": int(created.isna().sum()),
        "invalid_completion_timestamps": int(completed.isna().sum()),
        "nonpositive_elapsed_rows": int((elapsed.notna() & (elapsed <= 0)).sum()),
        "duplicate_rows_beyond_first": int(frame.duplicated().sum()),
        "missing_cells_by_column": {column: int(frame[column].isna().sum()) for column in frame},
        "observed_duration_minutes": {
            "median": float(observed.median()) if len(observed) else None,
            "maximum": float(observed.max()) if len(observed) else None,
            "over_180_minutes": int((observed > 180).sum()),
            "extreme_duration_policy": "Retain finite positive durations; no clipping/removal.",
        },
        "timezone_status": "Unverified; naive timestamps use a common source-clock reference.",
        "target": "Elapsed order-creation to delivery-completion minutes, including waiting/prep.",
        "promised_deadline_available": False,
        "original_business_provenance": "unverified",
        "operational_database_modified": False,
        "serving_models_modified": False,
    }
    # Original source row indices remain stable for partitioning/reproducibility.
    return ResearchDeliveryDataset(
        inputs=frame.loc[valid].drop(columns="actual_delivery_time").copy(),
        elapsed_minutes=elapsed.loc[valid].copy(),
        created_at=created.loc[valid].copy(),
        completed_at=completed.loc[valid].copy(),
        audit=audit,
    )
