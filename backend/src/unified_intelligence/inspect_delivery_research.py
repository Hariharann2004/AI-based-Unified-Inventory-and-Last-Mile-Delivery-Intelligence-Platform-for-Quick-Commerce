"""Inspect the checksum-pinned ETA research dataset without importing or training it."""

import argparse
import json
import zipfile
from pathlib import Path

from unified_intelligence.ml.data_quality.research_delivery import (
    default_research_source,
    load_research_delivery,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("artifacts/delivery-benchmark-source.json")
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--csv", type=Path, help="Exact, checksum-pinned source CSV.")
    source_group.add_argument(
        "--archive", type=Path, help="Original ZIP, as an alternative to CSV."
    )
    parser.add_argument(
        "--output", type=Path, help="New JSON file; never overwrite an existing report."
    )
    args = parser.parse_args(argv)
    try:
        source = args.csv or args.archive or default_research_source()
        dataset = load_research_delivery(args.manifest, source)
        rendered = json.dumps(dataset.audit, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(rendered)
            print(f"Research source audit saved to {args.output}")
        else:
            print(rendered, end="")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Research source inspection failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
