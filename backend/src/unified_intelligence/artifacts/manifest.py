from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    name: str
    kind: str
    path: str
    size_bytes: int
    sha256: str
    download_url: str | None = None

    def __post_init__(self) -> None:
        candidate = PurePosixPath(self.path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Artifact path must stay inside the project: {self.path}")
        if self.kind not in {"dataset", "model"}:
            raise ValueError(f"Unsupported artifact kind: {self.kind}")
        if len(self.sha256) != 64:
            raise ValueError(f"Invalid SHA-256 digest for artifact: {self.name}")
        if self.download_url is not None and not self.download_url.startswith("https://"):
            raise ValueError(f"Artifact download URL must use HTTPS: {self.name}")


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: int
    artifacts: tuple[ArtifactEntry, ...]

    @classmethod
    def load(cls, path: Path) -> ArtifactManifest:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported artifact manifest schema version.")
        return cls(
            schema_version=payload["schema_version"],
            artifacts=tuple(ArtifactEntry(**entry) for entry in payload["artifacts"]),
        )
