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
    summarize_research_windows,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("artifacts/delivery-benchmark-source.json")
    )
    parser.add_argument(
        "--archive", type=Path, default=Path("data/raw/porter_candidate_v1/porter-v1.zip")
    )
    load_group = parser.add_mutually_exclusive_group()
    load_group.add_argument(
        "--include-load", action="store_true", help="Unverified snapshot-timing assumption."
    )
    load_group.add_argument(
        "--compare-load", action="store_true", help="Compare order-only with the load assumption."
    )
    parser.add_argument(
        "--all-windows", action="store_true", help="Three expanding chronological windows."
    )
    parser.add_argument(
        "--output", type=Path, help="New JSON file; existing reports cannot be overwritten."
    )
    args = parser.parse_args(argv)
    if args.output and args.output.exists():
        parser.exit(1, "Research benchmark failed: output already exists; choose a new filename.\n")
    try:
        dataset = load_research_delivery(args.manifest, args.archive)
        if args.include_load or args.compare_load:
            print(
                "WARNING: load snapshot timing is unverified; this is research only.",
                file=sys.stderr,
            )
        fractions = [0.6, 0.8, 1.0] if args.all_windows else [1.0]
        variants = [False, True] if args.compare_load else [args.include_load]
        windows = []
        for include_load in variants:
            for fraction in fractions:
                print(
                    f"Training window {fraction:.0%}; load assumption={include_load}. "
                    "Selection uses validation only.",
                    file=sys.stderr,
                )
                windows.append(
                    run_research_window(dataset, fraction=fraction, include_load=include_load)
                )
        report = {
            **research_metadata(dataset),
            "windows": windows,
            "summary": summarize_research_windows(windows),
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
