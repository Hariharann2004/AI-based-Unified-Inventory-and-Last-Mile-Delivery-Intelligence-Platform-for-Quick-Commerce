import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from unified_intelligence import benchmark_delivery
from unified_intelligence.ml.evaluation.research_delivery import (
    chronological_partition,
    eta_metrics,
    run_research_window,
    train_candidate,
)
from unified_intelligence.ml.features.research_delivery import (
    CATEGORICAL_COLUMNS,
    ORDER_NUMERIC_COLUMNS,
)


@pytest.fixture()
def research_dataset():
    created = pd.Series(pd.date_range("2025-01-01", periods=60, freq="12h", tz="UTC"))
    elapsed = pd.Series(np.arange(60, dtype=float) + 10)
    inputs = pd.DataFrame(
        {column: np.ones(60) for column in [*CATEGORICAL_COLUMNS, *ORDER_NUMERIC_COLUMNS]}
    )
    inputs["created_at"] = created.astype(str)
    completed = created + pd.to_timedelta(elapsed, unit="m")
    return SimpleNamespace(
        inputs=inputs, created_at=created, completed_at=completed, elapsed_minutes=elapsed, audit={}
    )


def test_chronological_partitions_keep_dates_whole_and_purge_future_outcomes(research_dataset):
    data = research_dataset
    data.completed_at.iloc[0] = pd.Timestamp("2025-02-01", tz="UTC")
    data.completed_at.iloc[36] = pd.Timestamp("2025-02-01", tz="UTC")
    (train, validation, test), metadata = chronological_partition(data)
    assert len(train) == 35 and len(validation) == 11 and len(test) == 12
    assert set(train).isdisjoint(validation) and set(validation).isdisjoint(test)
    dates = [set(data.created_at.iloc[part].dt.date) for part in [train, validation, test]]
    assert dates[0].isdisjoint(dates[1]) and dates[1].isdisjoint(dates[2])
    assert max(data.created_at.iloc[train]) < min(data.created_at.iloc[validation])
    assert max(data.created_at.iloc[validation]) < min(data.created_at.iloc[test])
    assert metadata["purged_unavailable_training_outcomes"] == 1
    assert metadata["purged_unavailable_validation_outcomes"] == 1


@pytest.mark.parametrize("fraction", [0, -1, 1.1])
def test_invalid_window_fraction_rejected(research_dataset, fraction):
    with pytest.raises(ValueError, match="fraction"):
        chronological_partition(research_dataset, fraction)


def test_insufficient_dates_or_outcomes_rejected(research_dataset):
    with pytest.raises(ValueError, match="ten whole dates"):
        chronological_partition(research_dataset, 0.1)
    research_dataset.completed_at[:] = pd.Timestamp("2026-01-01", tz="UTC")
    with pytest.raises(ValueError, match="two outcomes"):
        chronological_partition(research_dataset)


def test_candidates_only_see_training_and_validation_before_selected_test(research_dataset):
    calls = []

    class FakeModel:
        def __init__(self, configuration):
            self.name = configuration["name"]

        def predict(self, features):
            calls.append(("predict", self.name, features.index.tolist()))
            offset = {"standard": 1, "regularized": 0, "shallow": 2}[self.name]
            return features.index.to_numpy(dtype=float) + 10 + offset

    def trainer(features, target, configuration):
        calls.append(("fit", configuration["name"], features.index.tolist()))
        assert max(features.index) == 35
        assert target.index.equals(features.index)
        return FakeModel(configuration)

    report = run_research_window(research_dataset, trainer=trainer)
    assert report["selected_configuration"]["name"] == "regularized"
    assert report["test"]["mae_minutes"] == 0
    assert report["baselines"]["training_mean"]["mae_minutes"] > 0
    test_calls = [call for call in calls if call[0] == "predict" and max(call[2]) > 47]
    assert test_calls == [("predict", "regularized", list(range(48, 60)))]
    assert calls[-1] == test_calls[0]
    assert report["include_load"] is False
    assert report["partition"]["counts"] == {"train": 36, "validation": 12, "test": 12}
    assert len(report["partition"]["source_row_index_sha256"]["test"]) == 64
    json.dumps(report, allow_nan=False)


def test_eta_metrics_units_and_undefined_r2():
    result = eta_metrics([10, 20, 30], [12, 22, 40])
    assert result["mae_minutes"] == pytest.approx(14 / 3)
    assert result["within_5_minutes_fraction"] == pytest.approx(2 / 3)
    assert result["within_10_minutes_fraction"] == 1
    assert eta_metrics([10, 10], [11, 11])["r2"] is None
    with pytest.raises(ValueError, match="finite"):
        eta_metrics([10, 20], [10, np.inf])
    with pytest.raises(ValueError, match="shape"):
        eta_metrics([10, 20], [10])


def test_real_lightgbm_candidate_smoke():
    features = pd.DataFrame({"value": np.arange(40, dtype=float)})
    model = train_candidate(
        features,
        pd.Series(np.arange(40, dtype=float)),
        {"num_leaves": 7, "min_child_samples": 5, "reg_lambda": 1},
    )
    assert np.isfinite(model.predict(features)).all()


def test_benchmark_cli_existing_output_does_not_train(tmp_path, monkeypatch, capsys):
    output = tmp_path / "report.json"
    output.write_text("user report")
    monkeypatch.setattr(
        benchmark_delivery, "load_research_delivery", lambda *args: pytest.fail("must not load")
    )
    with pytest.raises(SystemExit) as error:
        benchmark_delivery.main(["--output", str(output)])
    assert error.value.code == 1
    assert output.read_text() == "user report"
    assert "output already exists" in capsys.readouterr().err


def test_benchmark_cli_save_and_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        benchmark_delivery, "load_research_delivery", lambda *args: SimpleNamespace(audit={})
    )
    monkeypatch.setattr(
        benchmark_delivery,
        "run_research_window",
        lambda *args, **kwargs: {"include_load": kwargs["include_load"]},
    )
    output = tmp_path / "report.json"
    assert benchmark_delivery.main(["--include-load", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["windows"][0]["include_load"] is True
    assert "unverified" in capsys.readouterr().err


def test_benchmark_cli_load_error_is_clear(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        benchmark_delivery.main(["--manifest", str(tmp_path / "missing.json")])
    assert error.value.code == 1
    assert "Research benchmark failed" in capsys.readouterr().err
