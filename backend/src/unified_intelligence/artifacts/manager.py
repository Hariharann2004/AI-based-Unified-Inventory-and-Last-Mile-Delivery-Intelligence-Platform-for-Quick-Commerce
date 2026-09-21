from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

from unified_intelligence.artifacts.manifest import ArtifactEntry, ArtifactManifest


@dataclass(frozen=True, slots=True)
class ArtifactStatus:
    name: str
    path: Path
    valid: bool
    reason: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactManager:
    """Verify and hydrate Git-ignored artifacts described by a tracked manifest."""

    def __init__(self, project_root: Path, manifest: ArtifactManifest) -> None:
        self.project_root = project_root.resolve()
        self.manifest = manifest

    def _target(self, entry: ArtifactEntry) -> Path:
        target = (self.project_root / entry.path).resolve()
        if self.project_root not in target.parents:
            raise ValueError(f"Artifact path escapes the project: {entry.path}")
        return target

    def verify(self) -> list[ArtifactStatus]:
        statuses = []
        for entry in self.manifest.artifacts:
            target = self._target(entry)
            if not target.is_file():
                statuses.append(ArtifactStatus(entry.name, target, False, "missing"))
            elif target.stat().st_size != entry.size_bytes:
                statuses.append(ArtifactStatus(entry.name, target, False, "size mismatch"))
            elif _sha256(target) != entry.sha256:
                statuses.append(ArtifactStatus(entry.name, target, False, "checksum mismatch"))
            else:
                statuses.append(ArtifactStatus(entry.name, target, True, "verified"))
        return statuses

    def sync(self, base_url: str) -> list[ArtifactStatus]:
        if not base_url.startswith(("https://", "http://")):
            raise ValueError("Artifact base URL must use HTTP or HTTPS.")
        for entry, status in zip(self.manifest.artifacts, self.verify(), strict=True):
            if status.valid:
                continue
            target = self._target(entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            url = urljoin(f"{base_url.rstrip('/')}/", entry.path)
            descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, suffix=".download")
            try:
                with os.fdopen(descriptor, "wb") as destination, urlopen(url) as response:
                    while chunk := response.read(1024 * 1024):
                        destination.write(chunk)
                temporary = Path(temporary_name)
                if (
                    temporary.stat().st_size != entry.size_bytes
                    or _sha256(temporary) != entry.sha256
                ):
                    raise ValueError(f"Downloaded artifact failed verification: {entry.name}")
                temporary.replace(target)
            finally:
                Path(temporary_name).unlink(missing_ok=True)
        return self.verify()
