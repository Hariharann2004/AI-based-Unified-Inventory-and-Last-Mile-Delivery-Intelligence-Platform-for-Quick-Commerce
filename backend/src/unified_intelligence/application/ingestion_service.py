import csv
import hashlib
import io
import uuid
from pathlib import Path

from pydantic import ValidationError

from unified_intelligence.api.schemas.delivery import DeliveryPredictionRequest
from unified_intelligence.api.schemas.inventory import InventoryPredictionRequest
from unified_intelligence.infrastructure.persistence.workbench_store import now

MODELS = {"inventory": InventoryPredictionRequest, "delivery": DeliveryPredictionRequest}
FILENAMES = {
    "inventory": "supply_chain_dataset1.csv",
    "delivery": "Quick_Commerce_Delivery_Logistics.csv",
}
LOCAL_DATASETS = {
    "inventory": Path("data/raw/supply_chain_dataset1.csv"),
    # Legacy serving schema remains isolated from the separate Porter ETA source.
    "delivery": Path("data/archive/legacy_delivery/Quick_Commerce_Delivery_Logistics.csv"),
}
MAX_BYTES = 15 * 1024 * 1024


def validate_kind(kind):
    if kind not in MODELS:
        raise ValueError("kind must be inventory or delivery.")
    return kind


class IngestionService:
    def __init__(self, store):
        self.store = store

    def ingest(self, content, kind, source):
        validate_kind(kind)
        if len(content) > MAX_BYTES:
            raise ValueError("CSV exceeds the 15 MiB import limit.")
        try:
            reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        except UnicodeDecodeError as error:
            raise ValueError("CSV must use UTF-8 encoding.") from error
        model = MODELS[kind]
        aliases = {field.alias or name for name, field in model.model_fields.items()}
        required = {
            field.alias or name for name, field in model.model_fields.items() if field.is_required()
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        records, rejected, total = [], [], 0
        import_id = str(uuid.uuid4())
        for position, raw in enumerate(reader):
            total += 1
            if total > 100_000:
                raise ValueError("CSV exceeds the 100,000 row import limit.")
            try:
                inputs = model.model_validate({k: v for k, v in raw.items() if k in aliases})
                serialized = inputs.model_dump(by_alias=True, mode="json")
                records.append(
                    {
                        "record_id": f"{import_id}:{position}",
                        "position": position,
                        "occurred_at": serialized.get("Date"),
                        "inputs": serialized,
                        "outcomes": {
                            k: v for k, v in raw.items() if k not in aliases and k is not None
                        },
                    }
                )
            except ValidationError as error:
                if len(rejected) < 20:
                    rejected.append(
                        {
                            "row": position + 2,
                            "fields": sorted({str(e["loc"][0]) for e in error.errors()}),
                        }
                    )
        if not records:
            raise ValueError("CSV contains no valid operational records.")
        metadata = {
            "import_id": import_id,
            "kind": kind,
            "source": source,
            "fingerprint": hashlib.sha256(content).hexdigest(),
            "created_at": now(),
            "total_rows": total,
            "accepted_rows": len(records),
            "rejected_rows": total - len(records),
            "rejection_samples": rejected,
            "provenance": "historical_dataset",
            "order_linkage": "independent_dataset",
        }
        return self.store.save_import(metadata, records)
