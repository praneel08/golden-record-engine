"""
main.py
-------
CLI entry point for the candidate data transformer.

Modes:
  --ats only                    -> raw ATS extraction output
  --github only                 -> raw GitHub extraction output
  --ats + --github               -> merged GoldenRecord (default schema)
  --ats + --github + --config    -> custom projected output
"""

from __future__ import annotations
import argparse
import json
import sys

from src.sources.ats_extractor import load_and_extract as extract_ats
from src.sources.github_extractor import extract_from_url as extract_github
from src.merger import merge
from src.projector import project


def _print_json(data) -> None:
    print(json.dumps(data, indent=2))


def _fail(message: str) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-source candidate data transformer."
    )
    parser.add_argument("--ats", help="Path to the ATS JSON blob.")
    parser.add_argument("--github", help="GitHub username or profile URL.")
    parser.add_argument("--config", help="Path to a projection config JSON.")
    args = parser.parse_args()

    if args.config and not (args.ats and args.github):
        _fail("--config requires both --ats and --github to be provided.")

    if not args.ats and not args.github:
        _fail("Provide at least one of --ats or --github.")

    # Mode 1: ATS extractor only
    if args.ats and not args.github:
        result = extract_ats(args.ats)
        if result is None:
            _fail(f"Could not extract ATS data from '{args.ats}'.")
        _print_json(result)
        return

    # Mode 2: GitHub extractor only
    if args.github and not args.ats:
        result = extract_github(args.github)
        if result is None:
            _fail(f"Could not fetch GitHub data for '{args.github}'.")
        _print_json(result)
        return

    # Mode 3 & 4: both sources present
    ats_data = extract_ats(args.ats)
    if ats_data is None:
        _fail(f"Could not extract ATS data from '{args.ats}'.")

    github_data = extract_github(args.github)
    if github_data is None:
        _fail(f"Could not fetch GitHub data for '{args.github}'.")

    record = merge(ats_data, github_data)

    # Mode 3: default merged output
    if not args.config:
        _print_json(record.model_dump())
        return

    # Mode 4: custom projection
    try:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        _fail(f"Could not load config '{args.config}': {e}")

    try:
        projected = project(record.model_dump(), config)
    except ValueError as e:
        _fail(str(e))

    _print_json(projected)


if __name__ == "__main__":
    main()