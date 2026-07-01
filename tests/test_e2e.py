"""
test_e2e.py
"""

import sys, json
sys.path.insert(0, ".")

from src.sources.ats_extractor import load_and_extract
from src.sources.github_extractor import extract
from src.merger import merge

ats    = load_and_extract("data/ats_sample.json")
github = extract("torvalds")
record = merge(ats, github)

print(json.dumps(record.model_dump(), indent=2))