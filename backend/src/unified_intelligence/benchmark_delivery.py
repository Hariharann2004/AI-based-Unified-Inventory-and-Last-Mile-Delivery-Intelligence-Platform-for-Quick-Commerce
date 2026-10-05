"""Run isolated chronological ETA training/evaluation and save aggregate research evidence."""

import argparse
import json
import sys
import zipfile
from pathlib import Path

from unified_intelligence.ml.data_quality.research_delivery import load_research_delivery
from unified_intelligence.ml.evaluation.research_delivery import (
    research_metadata,
    run_research_window,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("artifacts/delivery-benchmark-source.json")
    )
    parser.add_argument(
        "--archive", type=Path, default=Path("data/raw/porter_candidate_v1/porter-v1.zip")
    )
    parser.add_argument(
        "--include-load", action="store_true", help="Unverified snapshot-timing assumption."
    )
    parser.add_argument(
        "--output", type=Path, help="New JSON file; existing reports cannot be overwritten."
    )
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.exit(1, "Research benchmark failed: output already exists; choose a new filename.\n")
    try:
        dataset = load_research_delivery(args.manifest, args.archive)
        if args.include_load:
            print(
                "WARNING: load snapshot timing is unverified; this is research only.",
                file=sys.stderr,
            )
        print(
            "Training three candidates; choosing on validation before evaluating test.",
            file=sys.stderr,
        )
        report = {
            **research_metadata(dataset),
            "windows": [run_research_window(dataset, include_load=args.include_load)],
        }
        rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(rendered)
            print(f"Research benchmark saved to {args.output}")
        else:
            print(rendered, end="")
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Research benchmark failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
