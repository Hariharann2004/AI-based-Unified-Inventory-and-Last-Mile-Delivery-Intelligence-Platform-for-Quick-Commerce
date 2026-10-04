import hashlib
import io
import json

import pytest

from unified_intelligence.artifacts import ArtifactManager, ArtifactManifest


def write_manifest(path, artifact_path: str, content: bytes) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "artifacts": [
                    {
                        "name": "fixture",
                        "kind": "dataset",
                        "path": artifact_path,
                        "size_bytes": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_artifact_manager_verifies_checksum_and_size(tmp_path) -> None:
    content = b"stable artifact"
    artifact = tmp_path / "data" / "fixture.csv"
    artifact.parent.mkdir()
    artifact.write_bytes(content)
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, "data/fixture.csv", content)

    statuses = ArtifactManager(tmp_path, ArtifactManifest.load(manifest_path)).verify()

    assert statuses[0].valid is True
    assert statuses[0].reason == "verified"


def test_artifact_manager_reports_missing_file(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, "data/missing.csv", b"missing")

    status = ArtifactManager(tmp_path, ArtifactManifest.load(manifest_path)).verify()[0]

    assert status.valid is False
    assert status.reason == "missing"


def test_manifest_rejects_paths_outside_project(tmp_path) -> None:
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, "../secret", b"invalid")

    with pytest.raises(ValueError, match="stay inside"):
        ArtifactManifest.load(manifest_path)


def test_artifact_manager_syncs_verified_file_from_manifest_url(tmp_path, monkeypatch) -> None:
    content = b"downloadable artifact"
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest_path, "data/fixture.csv", content)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["artifacts"][0]["download_url"] = "https://example.test/fixture.csv"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    requested_urls = []

    def fake_urlopen(url):
        requested_urls.append(url)
        return io.BytesIO(content)

    monkeypatch.setattr("unified_intelligence.artifacts.manager.urlopen", fake_urlopen)

    statuses = ArtifactManager(tmp_path, ArtifactManifest.load(manifest_path)).sync()

    assert requested_urls == ["https://example.test/fixture.csv"]
    assert statuses[0].valid
    assert (tmp_path / "data" / "fixture.csv").read_bytes() == content
