"""
test_projector_torvalds.py
"""

import sys, json
sys.path.insert(0, ".")

from src.sources.ats_extractor import load_and_extract
from src.sources.github_extractor import extract
from src.merger import merge
from src.projector import project

ats    = load_and_extract("data/ats_sample.json")
github = extract("torvalds")
record = merge(ats, github).model_dump()

config = json.load(open("configs/config_torvalds_example.json"))

result = project(record, config)
print(json.dumps(result, indent=2))