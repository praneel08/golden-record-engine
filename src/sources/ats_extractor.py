"""
ats_extractor.py
Maps a raw ATS JSON blob to canonical fields.
"""

from __future__ import annotations
import json
from typing import Optional
from src.normalizers import (
    normalize_email, normalize_phone, normalize_date,
    normalize_skill, normalize_country
)


_ATS_MAP = {
    "first_name": "emp_name_first",
    "last_name":  "emp_name_last",
    "email":      "contact_email",
    "phone":      "contact_phone",
    "github":     "github_username",
    "company":    "current_org",
    "title":      "job_title",
    "start":      "start_dt",
    "location":   "location_raw",
    "skills":     "tech_skills",
    "education":  "education",
}


def _get(blob: dict, key: str):
    return blob.get(_ATS_MAP.get(key, key))


def extract(raw: dict) -> Optional[dict]:
    """
    Takes a raw ATS JSON dict, returns a normalized intermediate dict.
    Returns None if the input is unusable.
    """
    if not raw or not isinstance(raw, dict):
        return None

    try:
        first = _get(raw, "first_name") or ""
        last  = _get(raw, "last_name")  or ""
        full_name = f"{first} {last}".strip() or None

        email = normalize_email(_get(raw, "email") or "")
        phone = normalize_phone(_get(raw, "phone") or "")

        loc_raw = _get(raw, "location") or ""
        location = {
            "city":    loc_raw.split(",")[0].strip() if loc_raw else None,
            "region":  None,
            "country": normalize_country(loc_raw),
        }

        raw_skills = _get(raw, "skills") or []
        skills = [s for s in (normalize_skill(sk) for sk in raw_skills) if s]

        raw_edu = _get(raw, "education") or []
        education = [
            {
                "institution": e.get("school"),
                "degree":      e.get("deg"),
                "field":       e.get("major"),
                "end_year":    e.get("grad_year"),
            }
            for e in raw_edu if isinstance(e, dict)
        ]

        experience = []
        company = _get(raw, "company")
        title   = _get(raw, "title")
        start   = normalize_date(_get(raw, "start") or "")
        if company or title:
            experience.append({
                "company": company,
                "title":   title,
                "start":   start,
                "end":     None,
                "summary": None,
            })

        github_user = _get(raw, "github")

        return {
            "full_name":       full_name,
            "emails":          [email] if email else [],
            "phones":          [phone] if phone else [],
            "location":        location,
            "github_username": github_user,
            "links":           {"github": f"https://github.com/{github_user}" if github_user else None},
            "skills":          skills,
            "experience":      experience,
            "education":       education,
            "source":          "ats_json",
        }

    except Exception as e:
        # don't crash the pipeline on a bad blob
        print(f"[ats_extractor] failed: {e}")
        return None


def load_and_extract(filepath: str) -> Optional[dict]:
    """Load a JSON file from disk and extract it."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return extract(raw)
    except Exception as e:
        print(f"[ats_extractor] could not load {filepath}: {e}")
        return None