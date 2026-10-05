"""CLI for a read-only legacy delivery-data audit; JSON output contains aggregates only."""

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from unified_intelligence.ml.data_quality.delivery import audit_delivery_frame


def audit_delivery_csv(path: Path, source_url: str | None = None, license_name: str | None = None):
    data = path.read_bytes()
    header = next(csv.reader(io.StringIO(data.decode("utf-8-sig"))), [])
    if (
        not header
        or len(set(header)) != len(header)
        or any(not column.strip() for column in header)
    ):
        raise ValueError("CSV requires nonempty, unique column names.")
    frame = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    report = audit_delivery_frame(frame)
    report["source"] = {
        "filename": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "source_url": source_url,
        "license": license_name,
        "provenance_status": "caller_supplied_unverified" if source_url else "unverified",
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--source-url", help="Optional source citation; not verified by this CLI.")
    parser.add_argument("--license", dest="license_name", help="Optional source-stated licence.")
    parser.add_argument(
        "--output", type=Path, help="New JSON file; existing files are never replaced."
    )
    args = parser.parse_args(argv)
    try:
        report = audit_delivery_csv(args.csv, args.source_url, args.license_name)
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(rendered)
            print(f"Audit saved to {args.output}")
        else:
            print(rendered, end="")
    except (OSError, ValueError, UnicodeError, csv.Error) as error:
        parser.exit(1, f"Delivery audit failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
