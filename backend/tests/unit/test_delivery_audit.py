import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from unified_intelligence.audit_delivery import audit_delivery_csv, main
from unified_intelligence.ml.data_quality.delivery import AUDIT_FEATURES, audit_delivery_frame


def test_audit_counts_baseline_time_agreement_and_segments_without_mutating():
    frame = pd.DataFrame(
        {
            "delayed": ["Yes", "No", " yes ", "unknown"],
            "delivery_time_minutes": [30, 10, 10, 50],
            "expected_time_minutes": [20, 20, 20, 20],
            "delivery_rating": [1, 5, 2, 5],
            "Traffic_Level": ["High", "Low", "Low", "High"],
        }
    )
    original = frame.copy(deep=True)
    report = audit_delivery_frame(frame)
    pd.testing.assert_frame_equal(frame, original)
    assert report["target"]["valid_labels"] == 3
    assert report["target"]["invalid_or_missing_labels"] == 1
    assert report["target"]["majority_baseline_accuracy"] == pytest.approx(2 / 3)
    assert report["time_label_comparison"]["agreement_rate"] == pytest.approx(2 / 3)
    assert report["time_label_comparison"]["excluded_rows"] == 1
    assert report["rating_delay_rates"][0]["delay_rate"] == 1
    assert report["segment_delay_rates"]["Traffic_Level"][0]["valid_labels"] == 1
    assert "distance_km" in report["missing_columns"]
    assert report["input_groups"] is None
    json.dumps(report, allow_nan=False)


def test_numeric_invalids_and_comparison_denominators():
    frame = pd.DataFrame(
        {
            "delayed": ["yes"] * 7,
            "delivery_time_minutes": [10, None, "bad", np.inf, -1, "", 20],
            "expected_time_minutes": [5, 5, 5, 5, 5, 5, -1],
        }
    )
    report = audit_delivery_frame(frame)
    assert report["numeric_profiles"]["delivery_time_minutes"] == {
        "missing": 2,
        "non_numeric": 1,
        "non_finite": 1,
        "negative": 1,
        "valid_nonnegative": 2,
    }
    assert report["time_label_comparison"]["compared_rows"] == 1
    assert report["time_label_comparison"]["agreement_rate"] == 1
    assert report["missing_cells_by_column"]["delivery_time_minutes"] == 2
    assert any("Numeric quality" in message for message in report["warnings"])
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"delayed": [None, "bad"]})])
def test_empty_and_invalid_targets_return_null_not_invented_scores(frame):
    report = audit_delivery_frame(frame)
    assert report["target"]["delay_rate"] is None
    assert report["target"]["majority_baseline_accuracy"] is None
    assert report["time_label_comparison"] is None
    assert report["rating_delay_rates"] is None
    json.dumps(report, allow_nan=False)


def test_duplicate_inputs_and_conflicting_labels():
    frame = pd.DataFrame([{column: "same" for column in AUDIT_FEATURES}] * 3)
    frame["delayed"] = ["yes", "no", "no"]
    frame["delivery_time_minutes"] = 10
    report = audit_delivery_frame(frame)
    assert report["input_groups"]["distinct_input_groups"] == 1
    assert report["input_groups"]["duplicate_input_rows_beyond_first"] == 2
    assert report["input_groups"]["groups_with_conflicting_valid_labels"] == 1
    assert report["duplicate_rows_beyond_first"] == 1
    assert "delivery_rating" not in report["input_groups"]["features"]


def test_segment_null_and_invalid_label_denominators():
    frame = pd.DataFrame({"Traffic_Level": [None, "High"], "delayed": ["yes", "unknown"]})
    rates = audit_delivery_frame(frame)["segment_delay_rates"]["Traffic_Level"]
    assert next(rate for rate in rates if rate["value"] is None)["delay_rate"] == 1
    assert next(rate for rate in rates if rate["value"] == "High")["delay_rate"] is None


def test_csv_identity_and_cli_output_are_reproducible(tmp_path, capsys):
    csv_path = tmp_path / "delivery.csv"
    data = b"delayed,delivery_time_minutes,expected_time_minutes\nyes,30,20\n"
    csv_path.write_bytes(data)
    report = audit_delivery_csv(csv_path, "https://example.com/data", "unknown")
    assert report["source"]["sha256"] == hashlib.sha256(data).hexdigest()
    assert report["source"]["provenance_status"] == "caller_supplied_unverified"
    assert report == audit_delivery_csv(csv_path, "https://example.com/data", "unknown")
    assert main([str(csv_path)]) == 0
    output_report = json.loads(capsys.readouterr().out)
    assert output_report["source"]["source_url"] is None
    destination = tmp_path / "report.json"
    assert main([str(csv_path), "--output", str(destination)]) == 0
    assert json.loads(destination.read_text())["rows"] == 1
    with pytest.raises(SystemExit) as error:
        main([str(csv_path), "--output", str(destination)])
    assert error.value.code == 1
    assert json.loads(destination.read_text())["rows"] == 1
    assert csv_path.read_bytes() == data


@pytest.mark.parametrize("data", [b"", b"delayed,delayed\nyes,no\n", b",delayed\n1,yes\n"])
def test_bad_csv_headers_fail_explicitly(tmp_path, data):
    path = tmp_path / "bad.csv"
    path.write_bytes(data)
    with pytest.raises(ValueError, match="column names"):
        audit_delivery_csv(path)


def test_duplicate_dataframe_columns_rejected():
    with pytest.raises(ValueError, match="unique column"):
        audit_delivery_frame(pd.DataFrame([[1, 2]], columns=["delayed", "delayed"]))


def test_cli_missing_input_has_clear_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as error:
        main([str(tmp_path / "missing.csv")])
    assert error.value.code == 1
    assert "Delivery audit failed" in capsys.readouterr().err
