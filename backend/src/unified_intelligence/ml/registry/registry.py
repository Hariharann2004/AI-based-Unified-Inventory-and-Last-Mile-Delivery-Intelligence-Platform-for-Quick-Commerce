import json
from pathlib import Path

from unified_intelligence.ml.registry.metadata import ModelMetadata
from unified_intelligence.utils.modeling import LightGBMArtifact


class FileModelRegistry:
    """Store model binaries and auditable metadata together on the filesystem."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, artifact: LightGBMArtifact, metadata: ModelMetadata) -> tuple[Path, Path]:
        self.root.mkdir(parents=True, exist_ok=True)
        model_path = self.root / f"{metadata.name}.joblib"
        metadata_path = self.root / f"{metadata.name}.metadata.json"
        artifact.save(model_path)
        metadata_path.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
        return model_path, metadata_path

    def load(self, name: str) -> LightGBMArtifact:
        return LightGBMArtifact.load(self.root / f"{name}.joblib")

    def read_metadata(self, name: str) -> dict:
        return json.loads((self.root / f"{name}.metadata.json").read_text(encoding="utf-8"))
