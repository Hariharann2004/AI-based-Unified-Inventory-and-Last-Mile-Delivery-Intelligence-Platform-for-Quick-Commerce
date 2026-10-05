import pandas as pd
import pytest

from unified_intelligence.ml.training.pipeline import TrainingPipeline


@pytest.mark.parametrize("legacy_in_raw", [False, True])
def test_legacy_training_source_paths_without_training(tmp_path, monkeypatch, legacy_in_raw):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    directory = raw if legacy_in_raw else raw.parent / "archive" / "legacy_delivery"
    directory.mkdir(parents=True, exist_ok=True)
    expected = directory / "Quick_Commerce_Delivery_Logistics.csv"
    expected.touch()
    calls = []

    def read_csv(path):
        calls.append(path)
        if len(calls) == 2:
            raise ValueError("Stop before training")
        return pd.DataFrame()

    monkeypatch.setattr(pd, "read_csv", read_csv)
    pipeline = TrainingPipeline(raw, None, tmp_path / "reports")
    with pytest.raises(ValueError, match="Stop before training"):
        pipeline.run()
    assert calls == [raw / "supply_chain_dataset1.csv", expected]
