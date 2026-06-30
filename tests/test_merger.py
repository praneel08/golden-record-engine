"""
test_merger.py
--------------
Two-candidate test suite for the Golden Record merger.
Candidate 1: normal conflict resolution
Candidate 2: garbage/missing data stress test
"""

import sys
sys.path.insert(0, ".")

from src.merger import merge, _score, _resolve_skills

PASS = "OK  "
FAIL = "FAIL"
results = []

def check(label, got, expected):
    ok = got == expected if not isinstance(expected, float) else abs(got - expected) < 0.001
    results.append((label, ok, got, expected))
    print((PASS if ok else FAIL) + " " + label + ("" if ok else f" | got {got!r} expected {expected!r}"))


# ===========================================================================
# SECTION 1 — Scoring function unit tests (exact math verification)
# ===========================================================================

print("\n=== SCORING FUNCTION (S_final = W_base + bonus) ===")

check("phone E.164 ATS → 0.75+0.15=0.90",  _score("+14155552671", "ats_json",   "phone"),   0.90)
check("email valid GH  → 0.60+0.10=0.70",  _score("j@example.com","github_api", "email"),   0.70)
check("date YYYY-MM ATS→ 0.75+0.08=0.83",  _score("2024-01",      "ats_json",   "date"),    0.83)
check("country ISO2 ATS → 0.75+0.08=0.83", _score("US",           "ats_json",   "country"), 0.83)
check("skill canonical ATS→0.75+0.05=0.80",_score("python",       "ats_json",   "skill"),   0.80)
check("skill canonical GH →0.60+0.05=0.65",_score("python",       "github_api", "skill"),   0.65)
check("string ATS → 0.75+0.03=0.78",       _score("Jonathan Doe", "ats_json",   "string"),  0.78)
check("number>0 GH → 0.60+0.05=0.65",      _score(4.5,            "github_api", "number"),  0.65)

print("\n--- Garbage penalty → 0.0 ---")
check("None",         _score(None,    "ats_json", "string"), 0.0)
check("empty string", _score("",      "ats_json", "string"), 0.0)
check("whitespace",   _score("   ",   "ats_json", "string"), 0.0)
check("N/A string",   _score("N/A",   "ats_json", "phone"),  0.0)
check("empty list",   _score([],      "ats_json", "skill"),  0.0)
check("number <= 0",  _score(0,       "ats_json", "number"), 0.0)
check("negative num", _score(-1,      "ats_json", "number"), 0.0)


# ===========================================================================
# SECTION 2 — Skills merge unit test
# ===========================================================================

print("\n=== SKILLS MERGE ===")

prov = []
skills = _resolve_skills(
    ["python", "typescript", "postgresql"],  # ATS
    ["python", "c", "javascript"],           # GitHub
    prov
)
skill_map = {s.name: s for s in skills}

check("python merged from both sources",
      set(skill_map["python"].sources), {"ats_json", "github_api"})

# max(0.80, 0.65) + 0.1 = 0.90
check("python confidence boosted → 0.90",
      skill_map["python"].confidence, 0.90)

check("typescript ATS-only, source correct",
      skill_map["typescript"].sources, ["ats_json"])

check("typescript confidence → 0.80",
      skill_map["typescript"].confidence, 0.80)

check("c GitHub-only, source correct",
      skill_map["c"].sources, ["github_api"])

check("c confidence → 0.65",
      skill_map["c"].confidence, 0.65)

check("all 5 unique skills present",
      len(skills), 5)

check("provenance entry created for skills",
      len(prov), 1)


# ===========================================================================
# SECTION 3 — Candidate 1: Normal merge with real conflicts
# ===========================================================================

print("\n=== CANDIDATE 1: Normal conflict resolution ===")

ats1 = {
    "full_name":       "Jonathan Doe",
    "emails":          ["j.doe@example.com"],
    "phones":          ["+14155552671"],
    "location":        {"city": "San Francisco", "region": "CA", "country": "US"},
    "links":           {"github": "https://github.com/jdoe"},
    "headline":        None,               # ATS has no headline → GitHub should win
    "years_experience": None,              # ATS has no years → GitHub should win
    "skills":          ["python", "typescript", "postgresql"],
    "experience":      [{"company": "Yahoo", "title": "Software Engineer II",
                         "start": "2024-01", "end": None, "summary": None}],
    "education":       [{"institution": "Stanford University",
                         "degree": "Bachelor of Science",
                         "field": "Computer Science", "end_year": 2022}],
    "source": "ats_json",
}

gh1 = {
    "full_name":       "Jonathan Doe",
    "emails":          [],
    "phones":          [],
    "location":        {"city": "San Francisco", "region": None, "country": "US"},
    "links":           {"github": "https://github.com/jdoe", "portfolio": None, "linkedin": None},
    "headline":        "Backend Engineer specializing in Python data pipelines.",
    "years_experience": 4.5,
    "skills":          ["python", "c", "javascript"],
    "experience":      [],
    "education":       [],
    "source": "github_api",
}

r1 = merge(ats1, gh1)

check("candidate_id generated",             bool(r1.candidate_id),          True)
check("full_name → ATS wins",               r1.full_name,                   "Jonathan Doe")
check("headline → GitHub wins (ATS null)",  r1.headline,                    "Backend Engineer specializing in Python data pipelines.")
check("years_experience → GitHub wins",     r1.years_experience,            4.5)
check("phone present and E.164",            "+14155552671" in r1.phones,    True)
check("email present",                      "j.doe@example.com" in r1.emails, True)
check("location city → ATS",               r1.location.city,               "San Francisco")
check("location country → ATS",            r1.location.country,            "US")
check("experience from ATS",               len(r1.experience),             1)
check("education from ATS",               len(r1.education),              1)
check("python merged both sources",         any(s.name == "python" and
                                            "ats_json" in s.sources and
                                            "github_api" in s.sources
                                            for s in r1.skills),            True)
check("python confidence boosted > 0.80",   any(s.name == "python" and
                                            s.confidence > 0.80
                                            for s in r1.skills),            True)
check("provenance populated",               len(r1.provenance) > 0,         True)
check("overall_confidence > 0",             r1.overall_confidence > 0,      True)


# ===========================================================================
# SECTION 4 — Candidate 2: Garbage/missing data stress test
# ===========================================================================

print("\n=== CANDIDATE 2: Garbage and missing data stress test ===")

ats2 = {
    "full_name":        "N/A",             # garbage → GitHub should win
    "emails":           [],                # empty → GitHub wins
    "phones":           ["N/A"],           # garbage phone
    "location":         {"city": None, "region": None, "country": None},
    "links":            {},
    "headline":         None,
    "years_experience": -1,               # invalid number → garbage
    "skills":           [],               # empty → GitHub skills only
    "experience":       [],
    "education":        [],
    "source": "ats_json",
}

gh2 = {
    "full_name":        "Jane Smith",
    "emails":           ["jane@example.com"],
    "phones":           [],
    "location":         {"city": "Seattle", "region": None, "country": "US"},
    "links":            {"github": "https://github.com/jsmith", "portfolio": None, "linkedin": None},
    "headline":         "ML Engineer at Google.",
    "years_experience": 6.0,
    "skills":           ["python", "tensorflow", "go"],
    "experience":       [],
    "education":        [],
    "source": "github_api",
}

r2 = merge(ats2, gh2)

check("name → GitHub wins (ATS is N/A)",    r2.full_name,                   "Jane Smith")
check("headline → GitHub wins",             r2.headline,                    "ML Engineer at Google.")
check("years_exp → GitHub wins (ATS -1)",   r2.years_experience,            6.0)
check("email from GitHub",                  "jane@example.com" in r2.emails, True)
check("garbage phone dropped",              r2.phones,                      [])
check("location city → GitHub fallback",    r2.location.city,               "Seattle")
check("skills from GitHub only",            len(r2.skills) >= 3,            True)
check("all skills tagged github_api",       all("github_api" in s.sources
                                            for s in r2.skills),            True)
check("no crash on all-garbage ATS",        True,                           True)
check("provenance still populated",         len(r2.provenance) > 0,         True)
check("overall_confidence > 0",             r2.overall_confidence > 0,      True)


# ===========================================================================
# SUMMARY
# ===========================================================================

print()
passed = sum(1 for _, ok, _, _ in results if ok)
failed = sum(1 for _, ok, _, _ in results if not ok)
print(f"{passed} passed, {failed} failed")