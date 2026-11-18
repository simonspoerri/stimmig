"""``stimmig-evals``: score the extraction against labelled datasets.

Without ``--live`` it replays recorded model answers (no API key, as in CI).
With ``--live`` it calls the model, records the first run's answers and
repeats the remaining runs to measure the spread.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from ..config import get_settings
from ..llm import AnthropicProvider, LlmProvider, RecordingProvider, ReplayProvider
from .dataset import Split, load_datasets
from .run import check_thresholds, load_thresholds, run_evals, to_markdown

REPORTS_DIR = Path(__file__).resolve().parents[3] / "evals" / "reports"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stimmig-evals")
    parser.add_argument("--live", action="store_true", help="call the model and re-record (needs an API key)")
    parser.add_argument(
        "--runs", type=int, default=None, help="repetitions per item (default: 3 live, 1 replay)"
    )
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    parser.add_argument("--dataset", help="only this dataset")
    parser.add_argument("--model", default=None, help="model id (default: STIMMIG_MODEL)")
    parser.add_argument("--no-gate", action="store_true", help="report only, don't fail on thresholds")
    args = parser.parse_args(argv)

    model = args.model or get_settings().model
    runs = args.runs or (3 if args.live else 1)
    if not args.live and runs > 1:
        parser.error("--runs > 1 only makes sense with --live; replayed answers don't vary")

    live = AnthropicProvider() if args.live else None

    def provider_for_run(index: int) -> LlmProvider:
        if live is None:
            return ReplayProvider()
        return RecordingProvider(live) if index == 0 else live

    datasets = [d for d in load_datasets() if not args.dataset or d.name == args.dataset]
    if not datasets:
        parser.error("no datasets found")
    splits = cast(tuple[Split, ...], ("dev", "test") if args.split == "all" else (args.split,))

    report = run_evals(datasets, provider_for_run, model, runs=runs, splits=splits)
    failures = check_thresholds(report, load_thresholds())

    # Only a full live run is the report of record; partial or replay runs stay local.
    suffix = "" if args.live and args.split == "all" and not args.dataset else ".local"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / f"latest{suffix}.json").write_text(json.dumps(report.to_json(), indent=2) + "\n")
    markdown = to_markdown(report)
    (REPORTS_DIR / f"latest{suffix}.md").write_text(markdown)
    sys.stdout.write(markdown)

    if failures and not args.no_gate:
        sys.exit(1)
