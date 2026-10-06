import hashlib
import importlib
import json
from dataclasses import replace

import pytest

from unified_intelligence.application.dataset_service import DATASETS, DatasetService, csv_summary


@pytest.fixture()
def dataset_service(tmp_path):
    (tmp_path / "data/raw").mkdir(parents=True)
    (tmp_path / "artifacts").mkdir()
    artifacts = []
    for spec in DATASETS:
        content = (
            b"created_at,actual_delivery_time,store_id\n2015-01-01,2015-01-02,1\n2015-01-02,,2\n"
        )
        (tmp_path / "data/raw" / spec.filename).write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        if spec.artifact_name:
            artifacts.append({"name": spec.artifact_name, "sha256": digest})
        else:
            (tmp_path / "artifacts/delivery-benchmark-source.json").write_text(
                json.dumps({"csv_sha256": digest})
            )
    (tmp_path / "artifacts/manifest.json").write_text(json.dumps({"artifacts": artifacts}))
    return DatasetService(tmp_path)


def test_catalog_preserves_independent_dataset_roles(dataset_service):
    items = dataset_service.catalog()["datasets"]
    assert [item["dataset_id"] for item in items] == ["inventory", "delivery", "porter-eta"]
    assert all(item["available"] and item["row_count"] == 2 for item in items)
    assert all(item["relative_path"].startswith("data/raw/") for item in items)
    assert items[-1]["role"] == "Separate ETA research benchmark"
    assert "not a replacement" in items[-1]["warning"]
    assert "unverified" in items[1]["warning"]


def test_preview_keeps_missing_values_and_source_bytes(dataset_service):
    path = dataset_service.path("porter-eta")
    before = path.read_bytes()
    preview = dataset_service.preview("porter-eta", limit=1, offset=1)
    assert preview["dataset"]["columns"] == ["created_at", "actual_delivery_time", "store_id"]
    assert preview["records"] == [
        {"created_at": "2015-01-02", "actual_delivery_time": "", "store_id": "2"}
    ]
    assert dataset_service.preview("porter-eta", offset=2)["records"] == []
    assert dataset_service.download_path("porter-eta") == path
    assert path.read_bytes() == before


@pytest.mark.parametrize("limit,offset", [(0, 0), (51, 0), (10, -1)])
def test_bounded_preview(dataset_service, limit, offset):
    with pytest.raises(ValueError, match="Preview limit"):
        dataset_service.preview("porter-eta", limit=limit, offset=offset)


def test_modified_and_missing_sources_are_visible_but_not_served(dataset_service):
    path = dataset_service.path("porter-eta")
    path.write_bytes(b"created_at\nchanged\n")
    item = dataset_service.catalog()["datasets"][-1]
    assert item["available"] is False
    assert "checksum" in item["error"]
    with pytest.raises(ValueError, match="checksum"):
        dataset_service.download_path("porter-eta")
    path.unlink()
    assert dataset_service.catalog()["datasets"][-1]["available"] is False
    with pytest.raises(KeyError):
        dataset_service.preview("../secret")


def test_source_header_stat_manifest_and_path_guards(dataset_service, monkeypatch):
    path = dataset_service.path("porter-eta")
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="changed while"):
        csv_summary(str(path), stat.st_size + 1, stat.st_mtime_ns, digest)
    content = b"duplicate,duplicate\n1,2\n"
    path.write_bytes(content)
    manifest_path = dataset_service.root / "artifacts/delivery-benchmark-source.json"
    manifest_path.write_text(json.dumps({"csv_sha256": hashlib.sha256(content).hexdigest()}))
    with pytest.raises(ValueError, match="unique column"):
        dataset_service.get("porter-eta")
    (dataset_service.root / "artifacts/manifest.json").write_text('{"artifacts": []}')
    with pytest.raises(ValueError, match="missing from"):
        dataset_service.get("inventory")
    monkeypatch.setattr(
        dataset_service, "spec", lambda _id: replace(DATASETS[-1], filename="../secret.csv")
    )
    with pytest.raises(ValueError, match="inside data/raw"):
        dataset_service.path("porter-eta")


def test_dataset_api_preview_download_and_unknown_ids(client, monkeypatch, dataset_service):
    module = importlib.import_module("unified_intelligence.api.workbench")
    monkeypatch.setattr(module, "DatasetService", lambda: dataset_service)
    assert len(client.get("/api/workbench/datasets").json["datasets"]) == 3
    preview = client.get("/api/workbench/datasets/porter-eta/preview?limit=1&offset=1")
    assert preview.status_code == 200
    assert preview.json["records"][0]["actual_delivery_time"] == ""
    downloaded = client.get("/api/workbench/datasets/porter-eta/download")
    assert downloaded.status_code == 200
    assert downloaded.data == dataset_service.path("porter-eta").read_bytes()
    assert "attachment" in downloaded.headers["Content-Disposition"]
    assert "Porter_Delivery_Time_Estimation.csv" in downloaded.headers["Content-Disposition"]
    assert downloaded.headers["X-Content-Type-Options"] == "nosniff"
    downloaded.close()
    for action in ["preview", "download"]:
        assert client.get(f"/api/workbench/datasets/unknown/{action}").status_code == 404
    for query in ["limit=0", "limit=51", "offset=-1", "limit=oops", "offset=oops"]:
        assert client.get(f"/api/workbench/datasets/porter-eta/preview?{query}").status_code == 400
    dataset_service.path("porter-eta").write_bytes(b"changed")
    assert client.get("/api/workbench/datasets/porter-eta/download").status_code == 400
    dataset_service.path("porter-eta").unlink()
    assert client.get("/api/workbench/datasets/porter-eta/preview").status_code == 503
