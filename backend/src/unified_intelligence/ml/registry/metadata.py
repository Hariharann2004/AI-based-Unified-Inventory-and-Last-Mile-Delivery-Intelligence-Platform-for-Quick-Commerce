from __future__ import annotations

import hashlib
import platform
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any


def dataset_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _library_versions() -> dict[str, str]:
    return {name: version(name) for name in ("lightgbm", "pandas", "scikit-learn")}


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    name: str
    task: str
    target: str
    features: list[str]
    metrics: dict[str, float]
    data_fingerprint: str
    trained_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    python_version: str = field(default_factory=platform.python_version)
    library_versions: dict[str, str] = field(default_factory=_library_versions)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
