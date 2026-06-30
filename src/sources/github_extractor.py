"""
github_extractor.py
Fetches a public GitHub profile and repos, returns canonical intermediate dict.
"""

from __future__ import annotations
import requests
from datetime import datetime
from typing import Optional
from src.normalizers import normalize_email, normalize_skill, normalize_country


BASE = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}


def _get(url: str) -> Optional[dict | list]:
    """Make a GET request, return parsed JSON or None on any failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
        print(f"[github_extractor] {url} returned {r.status_code}")
    except Exception as e:
        print(f"[github_extractor] request failed: {e}")
    return None


def _years_experience(created_at: str) -> Optional[float]:
    """Estimate experience from GitHub account age."""
    try:
        created = datetime.strptime(created_at[:10], "%Y-%m-%d")
        delta = (datetime.utcnow() - created).days / 365.25
        return round(delta, 1)
    except Exception:
        return None


def _extract_skills(username: str) -> list[str]:
    """Pull unique non-null languages from public repos."""
    repos = _get(f"{BASE}/users/{username}/repos?per_page=100")
    if not repos or not isinstance(repos, list):
        return []
    seen = set()
    skills = []
    for repo in repos:
        lang = repo.get("language")
        if lang:
            normalized = normalize_skill(lang)
            if normalized and normalized not in seen:
                seen.add(normalized)
                skills.append(normalized)
    return skills


def extract(username: str) -> Optional[dict]:
    """
    Fetch a GitHub profile by username, return normalized intermediate dict.
    Returns None if the profile is unreachable or unusable.
    """
    if not username:
        return None

    profile = _get(f"{BASE}/users/{username}")
    if not profile or not isinstance(profile, dict):
        return None

    # guard against rate limit response
    if "message" in profile:
        print(f"[github_extractor] API message: {profile['message']}")
        return None

    email = normalize_email(profile.get("email") or "")
    loc_raw = profile.get("location") or ""
    blog = profile.get("blog") or ""

    location = {
        "city":    loc_raw.split(",")[0].strip() if loc_raw else None,
        "region":  None,
        "country": normalize_country(loc_raw),
    }

    skills = _extract_skills(username)

    return {
        "full_name":        profile.get("name"),
        "emails":           [email] if email else [],
        "phones":           [],
        "location":         location,
        "links": {
            "github":    profile.get("html_url"),
            "portfolio": blog if blog.startswith("http") else None,
            "linkedin":  None,
        },
        "headline":         profile.get("bio"),
        "years_experience": _years_experience(profile.get("created_at") or ""),
        "skills":           skills,
        "experience":       [],   # GitHub doesn't expose work history
        "education":        [],   # GitHub doesn't expose education
        "source":           "github_api",
    }


def extract_from_url(github_url: str) -> Optional[dict]:
    """Accept a full GitHub URL and extract the profile."""
    try:
        username = github_url.rstrip("/").split("/")[-1]
        return extract(username)
    except Exception as e:
        print(f"[github_extractor] bad URL {github_url}: {e}")
        return None