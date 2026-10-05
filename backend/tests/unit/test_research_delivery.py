import hashlib
import json
import zipfile

import pandas as pd
import pytest

from unified_intelligence.inspect_delivery_research import main
from unified_intelligence.ml.data_quality.research_delivery import load_research_delivery


@pytest.fixture()
def research_source(tmp_path):
    frame = pd.DataFrame(
        {
            "created_at": ["2025-01-01 10:00:00"] * 4,
            "actual_delivery_time": [
                "2025-01-01 10:30:00",
                None,
                "2025-01-01 09:00:00",
                "2025-01-02 10:00:00",
            ],
            "total_items": [2, 1, 3, None],
        }
    )
    data = frame.to_csv(index=False).encode()
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as destination:
        destination.writestr("dataset.csv", data)
    manifest = {
        "schema_version": 1,
        "dataset_id": "porter-kaggle-v1",
        "csv_member": "dataset.csv",
        "csv_bytes": len(data),
        "csv_sha256": hashlib.sha256(data).hexdigest(),
        "columns": list(frame.columns),
        "rows": len(frame),
        "source_url": "https://example.com/data",
        "license_as_listed": "CC BY-NC 4.0",
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, archive, manifest


def test_research_ingestion_keeps_extremes_and_separates_outcomes(research_source):
    path, archive, _ = research_source
    dataset = load_research_delivery(path, archive)
    assert dataset.inputs.index.tolist() == [0, 3]
    assert dataset.elapsed_minutes.tolist() == [30, 1440]
    assert "actual_delivery_time" not in dataset.inputs
    assert dataset.inputs.loc[3, "total_items"] != dataset.inputs.loc[3, "total_items"]
    assert dataset.audit["rejected_observed_targets"] == 2
    assert dataset.audit["observed_duration_minutes"]["over_180_minutes"] == 1
    assert dataset.audit["nonpositive_elapsed_rows"] == 1
    assert not dataset.audit["serving_models_modified"]
    assert not dataset.audit["promised_deadline_available"]
    json.dumps(dataset.audit, allow_nan=False)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("schema_version", 2, "Unsupported"),
        ("csv_bytes", 1, "byte size"),
        ("csv_sha256", "0" * 64, "checksum"),
        ("rows", 1, "row count"),
        ("columns", ["wrong"], "schema"),
    ],
)
def test_manifest_tampering_fails_closed(research_source, key, value, message):
    path, archive, manifest = research_source
    manifest[key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=message):
        load_research_delivery(path, archive)


def test_missing_timestamps_rejected_even_if_source_is_pinned(tmp_path):
    data = b"total_items\n1\n"
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as destination:
        destination.writestr("dataset.csv", data)
    manifest = {
        "schema_version": 1,
        "dataset_id": "porter-kaggle-v1",
        "csv_member": "dataset.csv",
        "csv_bytes": len(data),
        "csv_sha256": hashlib.sha256(data).hexdigest(),
        "rows": 1,
        "columns": ["total_items"],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="timestamps"):
        load_research_delivery(path, archive)


def test_inspection_cli_stdout_save_and_no_overwrite(research_source, tmp_path, capsys):
    path, archive, _ = research_source
    arguments = ["--manifest", str(path), "--archive", str(archive)]
    assert main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["eligible_observed_targets"] == 2
    output = tmp_path / "audit.json"
    assert main([*arguments, "--output", str(output)]) == 0
    assert json.loads(output.read_text())["rows"] == 4
    with pytest.raises(SystemExit) as error:
        main([*arguments, "--output", str(output)])
    assert error.value.code == 1


def test_inspection_cli_missing_source_is_clear(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main(["--manifest", str(tmp_path / "missing.json")])
    assert error.value.code == 1
    assert "Research source inspection failed" in capsys.readouterr().err
