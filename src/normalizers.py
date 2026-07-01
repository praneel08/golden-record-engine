"""
normalizers.py
All data cleaning functions for the pipeline.
"""

from __future__ import annotations
import re
from typing import Optional

import phonenumbers
from dateutil import parser as dateparser


# phone -> E.164

def normalize_phone(raw: str, default_region: str = "US") -> Optional[str]:
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


# date -> YYYY-MM

def normalize_date(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    try:
        dt = dateparser.parse(raw, fuzzy=True)
        if dt:
            return dt.strftime("%Y-%m")
    except (ValueError, OverflowError):
        pass
    return None


# skill -> canonical form, strip version numbers

_VERSION_RE = re.compile(r"\s*v?\d+(\.\d+)*x?\s*$", re.IGNORECASE)

def normalize_skill(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    cleaned = _VERSION_RE.sub("", raw).strip().lower()
    return cleaned if cleaned else None


# email -> lowercase + trimmed

def normalize_email(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()
    return cleaned if "@" in cleaned else None


# country -> ISO-3166 alpha-2

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

# city fallback for bare city strings
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
    if not raw or not isinstance(raw, str):
        return None

    parts = [p.strip().lower() for p in raw.split(",")]

    for part in reversed(parts):
        if part in _COUNTRY_MAP:
            return _COUNTRY_MAP[part]

    for part in parts:
        if part in _CITY_COUNTRY_MAP:
            return _CITY_COUNTRY_MAP[part]

    return None