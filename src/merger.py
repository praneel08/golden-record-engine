"""
merger.py
---------
Golden Record Engine. Resolves conflicts between ATS and GitHub using
S_final = W_base + M_dynamic (field-specific bonuses, capped at 1.0).
"""

from __future__ import annotations
import re
import hashlib
from typing import Optional
from src.schema import (
    GoldenRecord, Location, Links, Skill, Experience, Education, ProvenanceEntry
)

# Base trust weights
_W = {"ats_json": 0.75, "github_api": 0.60}

# Validation patterns
_E164    = re.compile(r"^\+[1-9]\d{6,14}$")
_EMAIL   = re.compile(r"^[^@]+@[^@]+\.[^@]+$")
_YYYYMM  = re.compile(r"^\d{4}-\d{2}$")
_ISO2    = re.compile(r"^[A-Z]{2}$")
_SKILL   = re.compile(r"^[a-z][a-z0-9+#.\-]*$")  # lowercase, no version numbers


# ---------------------------------------------------------------------------
# Field-specific format bonuses
# ---------------------------------------------------------------------------

def _format_bonus(value, field_type: str) -> float:
    """Return the format bonus for a value based on its field type."""
    if field_type == "phone":
        return 0.15 if isinstance(value, str) and _E164.match(value) else 0.0
    if field_type == "email":
        return 0.10 if isinstance(value, str) and _EMAIL.match(value) else 0.0
    if field_type == "date":
        return 0.08 if isinstance(value, str) and _YYYYMM.match(value) else 0.0
    if field_type == "country":
        return 0.08 if isinstance(value, str) and _ISO2.match(value) else 0.0
    if field_type == "skill":
        return 0.05 if isinstance(value, str) and _SKILL.match(value) else 0.0
    if field_type == "number":
        return 0.05 if isinstance(value, (int, float)) and value > 0 else 0.0
    if field_type == "string":
        return 0.03 if isinstance(value, str) and value.strip() else 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def _is_garbage(value) -> bool:
    """Garbage penalty: None, empty, whitespace, 'N/A', empty list, number <= 0."""
    if value is None:
        return True
    if isinstance(value, str) and (not value.strip() or value.strip().upper() == "N/A"):
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    if isinstance(value, (int, float)) and value <= 0:
        return True
    return False


def _score(value, source: str, field_type: str) -> float:
    """
    S_final = W_base + format_bonus(field_type), capped at 1.0.
    Garbage → 0.0 immediately.
    """
    if _is_garbage(value):
        return 0.0
    base  = _W.get(source, 0.5)
    bonus = _format_bonus(value, field_type)
    return min(1.0, base + bonus)


# ---------------------------------------------------------------------------
# Scalar resolver
# ---------------------------------------------------------------------------

def _resolve(field: str, field_type: str,
             ats_val, gh_val,
             provenance: list,
             ats_method: str = "direct_mapping",
             gh_method: str  = "direct_mapping"):
    """
    Compare S_final for both sources. Highest wins. Tie → ATS.
    Appends provenance entry. Returns (winning_value, confidence).
    """
    s_ats = _score(ats_val, "ats_json",   field_type)
    s_gh  = _score(gh_val,  "github_api", field_type)

    if s_ats >= s_gh:
        winner, source, score, method = ats_val, "ats_json",   s_ats, ats_method
    else:
        winner, source, score, method = gh_val,  "github_api", s_gh,  gh_method

    if not _is_garbage(winner):
        provenance.append(ProvenanceEntry(
            field=field,
            source=source,
            method=method,
            confidence_score=round(score, 4),
        ))

    return winner, round(score, 4)


# ---------------------------------------------------------------------------
# List resolver (skills)
# ---------------------------------------------------------------------------

def _resolve_skills(ats_skills: list, gh_skills: list, provenance: list) -> list[Skill]:
    """
    Union all unique skills.
    Shared skill → min(1.0, max(S_ats, S_gh) + 0.1).
    Single-source skill → that source's S_final.
    """
    ats_map = {s: _score(s, "ats_json",   "skill") for s in ats_skills}
    gh_map  = {s: _score(s, "github_api", "skill") for s in gh_skills}
    all_skills = sorted(set(ats_map) | set(gh_map))

    result = []
    for name in all_skills:
        in_ats = name in ats_map
        in_gh  = name in gh_map

        if in_ats and in_gh:
            conf    = min(1.0, max(ats_map[name], gh_map[name]) + 0.1)
            sources = ["ats_json", "github_api"]
        elif in_ats:
            conf    = ats_map[name]
            sources = ["ats_json"]
        else:
            conf    = gh_map[name]
            sources = ["github_api"]

        result.append(Skill(name=name, confidence=round(conf, 4), sources=sources))

    if result:
        avg = sum(s.confidence for s in result) / len(result)
        provenance.append(ProvenanceEntry(
            field="skills",
            source="ats_json+github_api",
            method="union_with_confidence_boost",
            confidence_score=round(avg, 4),
        ))

    return result


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------

def block(ats: Optional[dict], github: Optional[dict]) -> dict:
    """Match ATS + GitHub to same candidate. Email first, name fallback."""
    key = None
    if ats and github:
        shared = set(ats.get("emails", [])) & set(github.get("emails", []))
        if shared:
            key = f"email:{next(iter(shared))}"
        else:
            a = (ats.get("full_name") or "").strip().lower()
            g = (github.get("full_name") or "").strip().lower()
            if a and a == g:
                key = f"name:{a}"
    return {"ats": ats, "github": github, "block_key": key}


# ---------------------------------------------------------------------------
# Main merge
# ---------------------------------------------------------------------------

def merge(ats: Optional[dict], github: Optional[dict]) -> GoldenRecord:
    """
    Merge one ATS dict + one GitHub dict into a single GoldenRecord.
    Applies S_final scoring to every field. Populates provenance throughout.
    """
    provenance: list[ProvenanceEntry] = []
    ats = ats or {}
    gh  = github or {}

    # full_name
    full_name, _ = _resolve(
        "full_name", "string",
        ats.get("full_name"), gh.get("full_name"),
        provenance,
        ats_method="concatenated_first_last",
        gh_method="mapped_from_name",
    )

    # headline — GitHub bio is the natural source
    headline, _ = _resolve(
        "headline", "string",
        ats.get("headline"), gh.get("headline"),
        provenance,
        gh_method="mapped_from_bio",
    )

    # years_experience — GitHub account age heuristic
    years_exp, _ = _resolve(
        "years_experience", "number",
        ats.get("years_experience"), gh.get("years_experience"),
        provenance,
        gh_method="derived_from_account_age",
    )

    # emails — union, deduplicated; score each individually for provenance
    ats_emails = ats.get("emails", [])
    gh_emails  = gh.get("emails",  [])
    all_emails = list(dict.fromkeys(ats_emails + gh_emails))
    if all_emails:
        best_source = "ats_json" if ats_emails else "github_api"
        provenance.append(ProvenanceEntry(
            field="emails",
            source=best_source,
            method="union_deduplicated",
            confidence_score=round(_score(all_emails[0], best_source, "email"), 4),
        ))

    # phones — ATS only (GitHub never exposes phones)
    all_phones = ats.get("phones", [])
    if all_phones:
        provenance.append(ProvenanceEntry(
            field="phones",
            source="ats_json",
            method="normalized_E164",
            confidence_score=round(_score(all_phones[0], "ats_json", "phone"), 4),
        ))

    # location — ATS preferred, GitHub fallback per sub-field
    ats_loc = ats.get("location", {}) or {}
    gh_loc  = gh.get("location",  {}) or {}

    city,    _ = _resolve("location.city",    "string",  ats_loc.get("city"),    gh_loc.get("city"),    provenance)
    region,  _ = _resolve("location.region",  "string",  ats_loc.get("region"),  gh_loc.get("region"),  provenance)
    country, _ = _resolve("location.country", "country", ats_loc.get("country"), gh_loc.get("country"), provenance)
    location = Location(city=city, region=region, country=country)

    # links — merge both, GitHub owns github link
    ats_links = ats.get("links", {}) or {}
    gh_links  = gh.get("links",  {}) or {}
    links = Links(
        linkedin=ats_links.get("linkedin") or gh_links.get("linkedin"),
        github=gh_links.get("github")      or ats_links.get("github"),
        portfolio=gh_links.get("portfolio") or ats_links.get("portfolio"),
    )

    # skills
    skills = _resolve_skills(
        ats.get("skills", []),
        gh.get("skills",  []),
        provenance,
    )

    # experience + education — ATS owns these, GitHub has none
    experience = [Experience(**e) for e in ats.get("experience", []) if isinstance(e, dict)]
    education  = [Education(**e)  for e in ats.get("education",  []) if isinstance(e, dict)]

    # candidate_id
    seed = all_emails[0] if all_emails else (full_name or "unknown")
    candidate_id = hashlib.md5(seed.encode()).hexdigest()[:12]

    # overall_confidence — mean of all provenance scores
    scores = [p.confidence_score for p in provenance if p.confidence_score > 0]
    overall = round(sum(scores) / len(scores), 4) if scores else 0.0

    return GoldenRecord(
        candidate_id=candidate_id,
        full_name=full_name,
        emails=all_emails,
        phones=all_phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years_exp,
        skills=skills,
        experience=experience,
        education=education,
        provenance=provenance,
        overall_confidence=overall,
    )