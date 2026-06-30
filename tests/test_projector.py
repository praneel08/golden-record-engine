"""
test_projector.py
------------------
Runs the merged sindre+github record through all three on_missing config modes.
Run from project root: python tests/test_projector.py
"""

import sys, json
sys.path.insert(0, ".")

from src.sources.ats_extractor import load_and_extract
from src.sources.github_extractor import extract
from src.merger import merge
from src.projector import project

ats    = load_and_extract("data/ats_sindre.json")
github = extract("sindresorhus")
record = merge(ats, github).model_dump()

configs = ["config_null.json", "config_omit.json", "config_error.json"]

for cfg_file in configs:
    print(f"\n=== {cfg_file} ===")
    config = json.load(open(f"configs/{cfg_file}"))
    try:
        result = project(record, config)
        print(json.dumps(result, indent=2))
    except ValueError as e:
        print(f"Expected error raised: {e}")