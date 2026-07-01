"""
schema.py
Canonical Golden Record schema.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, EmailStr, field_validator
import re


# Sub-models
class Location(BaseModel):
    city:    Optional[str] = None
    region:  Optional[str] = None
    country: Optional[str] = None          # ISO-3166 alpha-2, e.g. "US"


class Links(BaseModel):
    linkedin:  Optional[str] = None
    github:    Optional[str] = None
    portfolio: Optional[str] = None
    other:     List[str]     = []


class Skill(BaseModel):
    name:       str                        # canonical (lowercase, no version)
    confidence: float                      # 0.0 – 1.0
    sources:    List[str]                  # e.g. ["ats_json", "github_api"]


class Experience(BaseModel):
    company: Optional[str] = None
    title:   Optional[str] = None
    start:   Optional[str] = None          # YYYY-MM
    end:     Optional[str] = None          # YYYY-MM or null if current
    summary: Optional[str] = None


class Education(BaseModel):
    institution: Optional[str] = None
    degree:      Optional[str] = None
    field:       Optional[str] = None
    end_year:    Optional[int] = None


class ProvenanceEntry(BaseModel):
    field:            str                  # canonical field name
    source:           str                  # e.g. "ats_json", "github_api"
    method:           str                  # e.g. "normalized_E164", "mapped_from_bio"
    confidence_score: float                # 0.0 – 1.0


# Top-level Golden Record
class GoldenRecord(BaseModel):
    candidate_id:       str
    full_name:          Optional[str]           = None
    emails:             List[str]               = []   # normalized: lowercase
    phones:             List[str]               = []   # normalized: E.164
    location:           Location                = Location()
    links:              Links                   = Links()
    headline:           Optional[str]           = None
    years_experience:   Optional[float]         = None
    skills:             List[Skill]             = []
    experience:         List[Experience]        = []
    education:          List[Education]         = []
    provenance:         List[ProvenanceEntry]   = []
    overall_confidence: float                   = 0.0


    @field_validator("emails", mode="before")
    @classmethod
    def normalize_emails(cls, v):
        """Lowercase and strip all emails."""
        return [e.lower().strip() for e in v if isinstance(e, str) and e.strip()]

    @field_validator("phones", mode="before")
    @classmethod
    def validate_phones(cls, v):
        """Accept only E.164 format: +[country code][number]."""
        e164 = re.compile(r"^\+[1-9]\d{6,14}$")
        return [p for p in v if isinstance(p, str) and e164.match(p)]

    @field_validator("overall_confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v):
        """Keep overall_confidence between 0.0 and 1.0."""
        return max(0.0, min(1.0, float(v)))