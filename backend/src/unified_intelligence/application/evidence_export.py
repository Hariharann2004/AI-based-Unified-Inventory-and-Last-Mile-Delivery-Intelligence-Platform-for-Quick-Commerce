"""Offline, escaped evidence exports; no raw datasets, model binaries or remote assets."""

import hashlib
import json
import math
import re
from html import escape

from unified_intelligence.infrastructure.persistence.workbench_store import now


class ExportConflict(ValueError):
    pass


def printable(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}" if math.isfinite(value) else "—"
    return str(value)


def table(headers, rows):
    head = "".join(f"<th scope='col'>{escape(str(item))}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(printable(item))}</td>" for item in row) + "</tr>"
        for row in rows
    )
    return (
        f"<div class='scroll'><table><thead><tr>{head}</tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def plot(title, points, x_label, y_label, bounded=False):
    """Numeric-only SVG coordinates; all displayed strings HTML-escaped."""
    points = [
        (float(x), float(y))
        for x, y in points
        if isinstance(x, (int, float))
        and isinstance(y, (int, float))
        and math.isfinite(x)
        and math.isfinite(y)
    ]
    if not points:
        return f"<p>{escape(title)}: no plot evidence.</p>"
    low = 0 if bounded else min(0, min(min(point) for point in points))
    high = 1 if bounded else max(1, max(max(point) for point in points)) * 1.05
    scale = high - low
    x_pos = lambda value: 70 + (value - low) / scale * 450  # noqa: E731
    y_pos = lambda value: 250 - (value - low) / scale * 200  # noqa: E731
    circles = "".join(
        f"<circle cx='{x_pos(x):.2f}' cy='{y_pos(y):.2f}' r='3'>"
        f"<title>{x:.3f}, {y:.3f}</title></circle>"
        for x, y in points
    )
    curve = ""
    if bounded:
        coordinates = " ".join(f"{x_pos(x):.2f},{y_pos(y):.2f}" for x, y in points)
        curve = f"<polyline points='{coordinates}' class='curve'/>"
    ticks = "".join(
        f"<text x='{x_pos(value):.2f}' y='273' text-anchor='middle'>{value:.2f}</text>"
        f"<text x='60' y='{y_pos(value):.2f}' text-anchor='end'>{value:.2f}</text>"
        for value in [low, (low + high) / 2, high]
    )
    return (
        f"<figure><figcaption>{escape(title)}</figcaption>"
        f"<svg viewBox='0 0 600 330' role='img' aria-label='{escape(title, quote=True)}'>"
        "<path d='M70 50V250H520' class='axis'/>"
        f"<path d='M70 250L520 50' class='reference'/>{curve}{circles}{ticks}"
        f"<text x='295' y='311' text-anchor='middle'>{escape(x_label)}</text>"
        f"<text transform='translate(18,150) rotate(-90)' text-anchor='middle'>"
        f"{escape(y_label)}</text></svg><p>{len(points)} displayed evidence points.</p></figure>"
    )


def bars(title, pairs, unit):
    pairs = [
        (label, value)
        for label, value in pairs
        if isinstance(value, (int, float)) and math.isfinite(value)
    ]
    maximum = max([1, *(value for _, value in pairs)])
    rows = "".join(
        f"<div class='bar-row'><span>{escape(str(label))}</span>"
        f"<strong>{value:.3f} {escape(unit)}</strong>"
        f"<div class='track'><div style='width:{max(0, value) / maximum * 100:.2f}%'></div>"
        "</div></div>"
        for label, value in pairs
        if math.isfinite(value)
    )
    return f"<figure><figcaption>{escape(title)}</figcaption>{rows}</figure>"


def operational_window(window, unit):
    classification = window["classification"]
    evidence = bars(
        "Regression MAE · lower is better",
        [
            ("LightGBM", window["regression"]["mae"]),
            ("Training-mean baseline", window["constant_baseline"]["mae"]),
        ],
        unit,
    )
    evidence += table(
        ["Regression model", f"MAE ({unit})", f"RMSE ({unit})"],
        [
            [name, values.get("mae"), values.get("rmse")]
            for name, values in [
                ("LightGBM", window["regression"]),
                ("Training mean", window["constant_baseline"]),
            ]
        ],
    )
    evidence += table(
        ["Policy", "Threshold", "Accuracy", "Precision", "Recall", "F1", "ROC AUC", "AP"],
        [
            [name, policy.get("threshold")]
            + [
                policy.get("metrics", {}).get(key)
                for key in ["accuracy", "precision", "recall", "f1", "roc_auc", "average_precision"]
            ]
            for name, policy in [
                ("Validation-selected", classification),
                ("Action policy", window["action_threshold"]),
                ("Training-majority baseline", window.get("classification_baseline", {})),
            ]
        ],
    )
    matrix = classification["confusion_matrix"]
    evidence += "<h3>Risk confusion matrix · actual / predicted</h3>" + table(
        ["Actual / predicted", "No risk", "Risk"],
        [["No risk", *matrix[0]], ["Risk", *matrix[1]]],
    )
    if not window.get("classification_baseline"):
        evidence += "<p class='warning'>Legacy report: training-majority baseline unavailable.</p>"
    if matrix[1][0] + matrix[1][1] and classification["metrics"].get("recall") == 0:
        evidence += (
            "<p class='warning'>No observed risk detected. Accuracy alone is misleading.</p>"
        )
    evidence += "<div class='charts'>" + plot(
        "Actual versus predicted · sampled test records",
        [(p["actual"], p["predicted"]) for p in window["samples"]],
        f"Actual ({unit})",
        f"Predicted ({unit})",
    )
    evidence += plot(
        "Precision–recall evidence",
        [(p["recall"], p["precision"]) for p in classification["precision_recall"]],
        "Recall",
        "Precision",
        True,
    )
    evidence += (
        plot(
            "Probability calibration",
            [(p["predicted"], p["observed"]) for p in classification["calibration"]],
            "Mean predicted risk",
            "Observed risk fraction",
            True,
        )
        + "</div>"
    )
    evidence += "<h3>Segment coverage</h3>" + table(
        ["Segment", "Test count", f"MAE ({unit})", f"RMSE ({unit})"],
        [[s["segment"], s["count"], s["mae"], s["rmse"]] for s in window["segments"]],
    )
    return evidence


def research_window(window):
    evidence = table(
        ["Estimator", "MAE (min)", "RMSE (min)", "R²", "Within ±10 min (fraction)"],
        [
            [name]
            + [
                metrics.get(key)
                for key in ["mae_minutes", "rmse_minutes", "r2", "within_10_minutes_fraction"]
            ]
            for name, metrics in [("LightGBM", window["test"]), *window["baselines"].items()]
        ],
    )
    evidence += bars(
        "ETA MAE versus training-only baselines · lower is better",
        [("LightGBM", window["test"]["mae_minutes"])]
        + [(name, value["mae_minutes"]) for name, value in window["baselines"].items()],
        "min",
    )
    evidence += bars(
        "Absolute error distribution · all test records",
        [(item["interval"], item["rows"]) for item in window["absolute_error_histogram"]],
        "records",
    )
    evidence += plot(
        "Observed versus predicted · sampled test records",
        [
            (p["observed_minutes"], p["predicted_minutes"])
            for p in window["sampled_test_predictions"]
        ],
        "Observed minutes",
        "Predicted minutes",
    )
    evidence += "<h3>Held-out cases · overlapping diagnostic groups</h3>" + table(
        ["Case", "Records", "Model MAE (min)", "Median baseline MAE (min)"],
        [
            [
                name,
                case["rows"],
                (case.get("model") or {}).get("mae_minutes"),
                (case.get("training_median_baseline") or {}).get("mae_minutes"),
            ]
            for name, case in window["test_cases"].items()
        ],
    )
    return evidence


STYLE = """
:root{font-family:Arial,sans-serif;color:#142e39;background:#f3f7f8}
body{max-width:1120px;margin:40px auto;padding:0 24px;line-height:1.6}
header{border-top:7px solid #087d76;padding:24px 0}h1{font-size:34px;line-height:1.2}
h2{margin-top:36px}section,figure,details{background:white;border:1px solid #dce5e8;
border-radius:12px;padding:22px;margin:20px 0}figure{margin:0}figcaption{font-weight:bold}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;
border-bottom:1px solid #dce5e8}th{background:#eef5f5}.scroll{overflow:auto;margin:16px 0}
.warning{background:#fff4e1;padding:12px;border-left:4px solid #c8811d}
.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:24px 0}
svg{width:100%;height:auto;fill:#087d76}svg text{fill:#455e67;font-size:12px}
.axis{fill:none;stroke:#75939b}.reference{fill:none;stroke:#afbfc3;stroke-dasharray:5 5}
.curve{fill:none;stroke:#087d76;stroke-width:2}.bar-row{margin:14px 0}
.bar-row strong{float:right}.track{height:10px;background:#e2eeed;clear:both}
.track div{height:100%;background:#087d76}pre{white-space:pre-wrap;overflow-wrap:anywhere;
font-size:11px}.hash{overflow-wrap:anywhere;font-family:monospace}footer{margin:30px 0}
@media(max-width:700px){.charts{grid-template-columns:1fr}body{padding:0 12px}}
@media print{body{max-width:none;margin:0;background:white;font-size:10pt}
section{break-before:page;border:0;padding:0}figure,table{break-inside:avoid}
.charts{grid-template-columns:1fr}.scroll{overflow:visible}details{border:0}
summary{font-weight:bold}pre{font-size:8pt}h1{font-size:24pt}.raw-evidence{display:none}}
"""


def render_html(evidence):
    report = evidence["report"]
    research = evidence["evidence_type"] == "eta_research"
    title = "ETA research evidence" if research else "Operational held-out evaluation"
    unit = "units" if report.get("kind") == "inventory" else "min"
    body = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'\">"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{STYLE}</style></head><body><header>"
        "<p>UNIFIED INTELLIGENCE / GUIDE-REVIEW EVIDENCE</p>"
        f"<h1>{title}</h1><p>Exported UTC: {escape(evidence['exported_at'])}</p>"
        f"<p>Evidence ID: {escape(evidence['evidence_id'])}</p>"
        f"<p class='hash'>Report SHA-256: {evidence['report_sha256']}</p></header>"
        f"<p>{escape(str(report['protocol']))}</p>"
        "<p class='warning'>Research evidence, not a production readiness certificate. "
        "Serving models are unchanged. Overlapping windows and cases are not independent trials. "
        "Scatter plots are sampled; overall metrics use all held-out records.</p>"
    )
    if research:
        body += (
            "<p class='warning'>No observed promised deadline: ETA errors are not delay accuracy. "
            "Load snapshots have unverified timing. No research model is promoted. "
            "The saved benchmark does not record a run timestamp; "
            "export time is not training time.</p>"
        )
    else:
        body += (
            "<p>MAE/RMSE measure target-unit errors (lower is better). Accuracy counts all "
            "correct labels; recall measures detected risks. A majority classifier can have high "
            "accuracy while missing risk. Threshold choice uses validation, "
            "never test outcomes.</p>"
        )
    body += "<h2>Limitations</h2>" + "".join(
        f"<p class='warning'>{escape(str(warning))}</p>" for warning in report.get("warnings", [])
    )
    provenance = {
        "envelope": evidence["provenance"],
        "source_audit": report.get("source_audit"),
        "features": report.get("features"),
        "library_versions": report.get("library_versions"),
        "model": report.get("model"),
        "note": report.get("note"),
        "summary": report.get("summary"),
    }
    source = report.get("source_audit", {})
    body += "<h2>Source and experiment provenance</h2>" + table(
        ["Field", "Value"],
        [
            ["Source dataset", source.get("dataset_id") or evidence["provenance"].get("import_id")],
            [
                "Source SHA-256",
                source.get("csv_sha256") or evidence["provenance"].get("data_fingerprint"),
            ],
            ["Source listing", source.get("source_url")],
            [
                "Accepted observed targets",
                source.get("eligible_observed_targets") or report.get("accepted_targets"),
            ],
            [
                "Rejected observed targets",
                source.get("rejected_observed_targets", report.get("rejected_targets")),
            ],
            ["Library versions", json.dumps(report.get("library_versions", {}))],
            [
                "Model settings",
                report.get("model", "See recorded operational protocol and repository settings"),
            ],
        ],
    )
    body += (
        "<details class='raw-evidence'><summary>Detailed source audit and summary</summary><pre>"
        + escape(json.dumps(provenance, indent=2, ensure_ascii=False, allow_nan=False))
        + "</pre></details><p>Risk scores and tolerance rates in tables are fractions (0–1), "
        "not percentages. R² can be negative.</p>"
    )
    summary_rows = []
    for index, window in enumerate(report["windows"]):
        if research:
            label = "Load snapshot assumption" if window["include_load"] else "Order-only"
            summary_rows.append(
                [
                    index + 1,
                    label,
                    window["test"]["rows"],
                    window["test"]["mae_minutes"],
                    window["baselines"]["training_median"]["mae_minutes"],
                ]
            )
        else:
            summary_rows.append(
                [
                    window["window"],
                    report.get("kind"),
                    window["counts"]["test"],
                    window["regression"]["mae"],
                    window["constant_baseline"]["mae"],
                ]
            )
    body += "<h2>All-window comparison</h2>" + table(
        [
            "Evidence window",
            "Variant / task",
            "Test records",
            f"Model MAE ({unit})",
            f"Training {'median' if research else 'mean'} MAE ({unit})",
        ],
        summary_rows,
    )
    for index, window in enumerate(report["windows"]):
        label = (
            ("Load snapshot assumption" if window.get("include_load") else "Order-only")
            if research
            else f"{report.get('kind', '')} models"
        )
        body += f"<section><h2>Evidence window {index + 1} · {escape(label)}</h2>"
        counts = window["partition"]["counts"] if research else window["counts"]
        body += table(["Partition", "Records"], list(counts.items()))
        body += research_window(window) if research else operational_window(window, unit)
        if research:
            setup = {
                key: window.get(key)
                for key in [
                    "partition",
                    "features",
                    "load_availability_status",
                    "selected_configuration",
                    "selection_metric",
                ]
            }
            body += "<h3>Window protocol</h3><pre>" + escape(json.dumps(setup, indent=2)) + "</pre>"
        body += "</section>"
    body += (
        "<details class='raw-evidence'><summary>"
        "Complete machine-readable evidence (expand)</summary>"
        f"<pre>{escape(json.dumps(evidence, indent=2, ensure_ascii=False, allow_nan=False))}</pre>"
        "</details><footer>Offline report · no remote assets or scripts. "
        "Open in a browser and use Print → Save as PDF if needed. "
        "This evidence export is not the final project document.</footer></body></html>"
    )
    return body


def export_evidence(payload, evidence_type, format_name):
    if format_name not in {"json", "html"}:
        raise ValueError("Export format must be json or html.")
    if evidence_type == "operational" and payload.get("status") != "completed":
        raise ExportConflict("Only completed evaluations can be exported.")
    report = payload.get("report")
    if not report or not report.get("windows"):
        raise ExportConflict("Completed evidence with test windows is required.")
    canonical = json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False)
    identifier = payload.get("benchmark_id") or payload.get("evaluation_id")
    evidence = {
        "export_schema_version": 1,
        "exported_at": now(),
        "evidence_type": evidence_type,
        "evidence_id": str(identifier),
        "report_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "provenance": {
            key: value for key, value in payload.items() if key not in {"report", "worker_id"}
        },
        "report": report,
        "scope": (
            "Saved evaluation evidence only; no raw datasets, models or final project document."
        ),
    }
    filename_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(identifier))[:80]
    filename = f"{evidence_type}-{filename_id}.{format_name}"
    if format_name == "json":
        return json.dumps(evidence, indent=2, ensure_ascii=False, allow_nan=False), filename
    return render_html(evidence), filename
