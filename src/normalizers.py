"""
normalizers.py
--------------
All data cleaning functions for the Eightfold pipeline.
Every value passes through here before entering the Golden Record.

Rules (from design spec):
  Phones  → E.164 format (+14155551234). Drop invalid numbers.
  Dates   → YYYY-MM. Drop unparseable dates.
  Skills  → Lowercase, strip version numbers, trim whitespace.
  Emails  → Lowercase, trim whitespace.
  Country → ISO-3166 alpha-2 (e.g. "US").
"""

from __future__ import annotations
import re
from typing import Optional

import phonenumbers
from dateutil import parser as dateparser


# ---------------------------------------------------------------------------
# Phone  →  E.164
# ---------------------------------------------------------------------------

def normalize_phone(raw: str, default_region: str = "US") -> Optional[str]:
    """
    Parse any phone string and return E.164 format.
    Returns None if the number is invalid or unparseable.

    Examples:
        "(415) 555-1234"  →  "+14155551234"
        "not-a-phone"     →  None
    """
    if not raw or not isinstance(raw, str):
        return None
    try:
        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.E164
            )
    except phonenumbers.NumberParseException:
        pass
    return None


# ---------------------------------------------------------------------------
# Date  →  YYYY-MM
# ---------------------------------------------------------------------------

def normalize_date(raw: str) -> Optional[str]:
    """
    Parse any date string and return YYYY-MM format.
    Returns None if unparseable.

    Examples:
        "2024-01-15T00:00:00Z"  →  "2024-01"
        "January 2022"          →  "2022-01"
        "garbage"               →  None
    """
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = dateparser.parse(raw, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m")
    except (ValueError, OverflowError):
        pass
    return None


# ---------------------------------------------------------------------------
# Skill  →  canonical (lowercase, no version numbers)
# ---------------------------------------------------------------------------

# Strip version patterns like "3.9", "v2", "2.x", " 3" at end of skill name
_VERSION_RE = re.compile(r"\s*v?\d+(\.\d+)*x?\s*$", re.IGNORECASE)

def normalize_skill(raw: str) -> Optional[str]:
    """
    Canonicalize a skill name: lowercase, strip version numbers, trim.
    Returns None if result is empty.

    Examples:
        "Python 3.9"   →  "python"
        "  TypeScript " →  "typescript"
        "Node.js v18"  →  "node.js"
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = _VERSION_RE.sub("", raw).strip().lower()
    return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Email  →  lowercase + trimmed
# ---------------------------------------------------------------------------

def normalize_email(raw: str) -> Optional[str]:
    """
    Lowercase and strip an email address.
    Returns None if result is empty or has no @ sign.

    Examples:
        "J.Doe@Example.com"  →  "j.doe@example.com"
        "  bad-email "       →  None
    """
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()
    return cleaned if "@" in cleaned else None


# ---------------------------------------------------------------------------
# Country  →  ISO-3166 alpha-2
# ---------------------------------------------------------------------------

# Country name/code lookup
_COUNTRY_MAP = {
    "united states": "US", "usa": "US", "us": "US", "u.s.": "US", "u.s.a.": "US",
    "india": "IN", "in": "IN",
    "united kingdom": "GB", "uk": "GB", "gb": "GB",
    "canada": "CA", "ca": "CA",
    "germany": "DE", "de": "DE",
    "france": "FR", "fr": "FR",
    "australia": "AU", "au": "AU",
    "singapore": "SG", "sg": "SG",
    "netherlands": "NL", "nl": "NL",
    "japan": "JP", "jp": "JP",
    "china": "CN", "cn": "CN",
    "brazil": "BR", "br": "BR",
}

# City → country fallback for GitHub-style bare city strings
_CITY_COUNTRY_MAP = {
    "san francisco": "US", "new york": "US", "seattle": "US",
    "los angeles": "US", "austin": "US", "boston": "US",
    "chicago": "US", "denver": "US", "atlanta": "US",
    "bangalore": "IN", "bengaluru": "IN", "mumbai": "IN",
    "delhi": "IN", "hyderabad": "IN", "pune": "IN",
    "london": "GB", "manchester": "GB",
    "toronto": "CA", "vancouver": "CA",
    "berlin": "DE", "munich": "DE",
    "paris": "FR",
    "sydney": "AU", "melbourne": "AU",
    "singapore": "SG",
    "amsterdam": "NL",
    "tokyo": "JP",
    "beijing": "CN", "shanghai": "CN",
    "são paulo": "BR",
}

def normalize_country(raw: str) -> Optional[str]:
    """
    Return ISO-3166 alpha-2 country code from a free-text location string.
    First tries explicit country match, then falls back to city lookup.
    Returns None if unrecognized.

    Examples:
        "San Francisco, US"  →  "US"   (country token match)
        "San Francisco"      →  "US"   (city fallback)
        "United States"      →  "US"
        "India"              →  "IN"
    """
    if not raw or not isinstance(raw, str):
        return None

    parts = [p.strip().lower() for p in raw.split(",")]

    # Pass 1 — try each comma-part against country map (last part first)
    for part in reversed(parts):
        if part in _COUNTRY_MAP:
            return _COUNTRY_MAP[part]

    # Pass 2 — try each comma-part against city map
    for part in parts:
        if part in _CITY_COUNTRY_MAP:
            return _CITY_COUNTRY_MAP[part]

    return None