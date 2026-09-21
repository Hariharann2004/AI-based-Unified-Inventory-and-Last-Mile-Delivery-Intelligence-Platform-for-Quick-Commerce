import json

from unified_intelligence.ml.registry import ModelMetadata, dataset_fingerprint


def test_model_metadata_is_serializable_and_traceable(tmp_path) -> None:
    dataset = tmp_path / "dataset.csv"
    dataset.write_text("value\n1\n", encoding="utf-8")
    metadata = ModelMetadata(
        name="test_model", task="regression", target="value", features=["value"],
        metrics={"mae": 0.1}, data_fingerprint=dataset_fingerprint(dataset),
    )

    payload = metadata.to_dict()

    assert payload["name"] == "test_model"
    assert len(payload["data_fingerprint"]) == 64
    assert payload["library_versions"]["lightgbm"]
    json.dumps(payload)
