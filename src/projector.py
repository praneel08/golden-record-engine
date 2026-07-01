"""
projector.py
"""

from __future__ import annotations
import jmespath
from typing import Any
from src.normalizers import normalize_phone, normalize_skill, normalize_email, normalize_date


# Normalization registry — maps config "normalize" values to functions

_NORMALIZERS = {
    "E164":      lambda v: normalize_phone(v) if isinstance(v, str) else v,
    "canonical": lambda v: normalize_skill(v) if isinstance(v, str) else v,
    "email":     lambda v: normalize_email(v) if isinstance(v, str) else v,
    "date":      lambda v: normalize_date(v)  if isinstance(v, str) else v,
}


def _apply_normalize(value: Any, normalize: str | None) -> Any:
    """Route value through the requested normalizer. Fail fast on unknown key."""
    if normalize is None:
        return value
    if normalize not in _NORMALIZERS:
        raise ValueError(f"Unknown normalize type: '{normalize}'")

    fn = _NORMALIZERS[normalize]
    if isinstance(value, list):
        return [fn(v) for v in value]
    return fn(value)


def _is_empty(value: Any) -> bool:
    """Treat None, empty string, empty list as 'missing'."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False



# Confidence lookup

def _find_confidence(record_dict: dict, field_path: str) -> float | None:
    """Look up a field's confidence score from the provenance array."""
    base_field = field_path.split(".")[0].split("[")[0]
    for entry in record_dict.get("provenance", []):
        if entry["field"] == base_field or entry["field"].startswith(base_field):
            return entry["confidence_score"]
    return None


def _find_provenance(record_dict: dict, field_path: str) -> dict | None:
    """Look up a field's full provenance entry (source + method) from the array."""
    base_field = field_path.split(".")[0].split("[")[0]
    for entry in record_dict.get("provenance", []):
        if entry["field"] == base_field or entry["field"].startswith(base_field):
            return {"source": entry["source"], "method": entry["method"]}
    return None


# Lightweight output validation

_TYPE_CHECKS = {
    "string":   lambda v: isinstance(v, str),
    "number":   lambda v: isinstance(v, (int, float)),
    "boolean":  lambda v: isinstance(v, bool),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "object":   lambda v: isinstance(v, dict),
}


def _validate_field(out_path, value, declared_type):
    """Check a projected value matches its declared config type. None always passes."""
    if declared_type is None or value is None:
        return
    check = _TYPE_CHECKS.get(declared_type)
    if check is None:
        raise ValueError(f"Unknown type '{declared_type}' for field '{out_path}'.")
    if not check(value):
        raise ValueError(
            f"Field '{out_path}' failed validation: expected '{declared_type}', got {type(value).__name__}."
        )


# Main projection function

def project(record_dict: dict, config: dict) -> dict:

    on_missing = config.get("on_missing", "null")
    include_confidence = config.get("include_confidence", False)
    include_provenance = config.get("include_provenance", False)

    output: dict = {}
    confidence_block: dict = {}
    provenance_block: dict = {}

    for field_cfg in config.get("fields", []):
        out_path  = field_cfg["path"]
        from_path = field_cfg.get("from", out_path)
        required  = field_cfg.get("required", False)
        normalize = field_cfg.get("normalize")

        value = jmespath.search(from_path, record_dict)
        value = _apply_normalize(value, normalize)

        if _is_empty(value):
            if required:
                raise ValueError(f"Required field '{out_path}' is missing.")
            if on_missing == "error":
                raise ValueError(f"Field '{out_path}' is missing and on_missing='error'.")
            if on_missing == "omit":
                continue
            output[out_path] = None  # on_missing == "null"
        else:
            declared_type = field_cfg.get("type")
            _validate_field(out_path, value, declared_type)
            output[out_path] = value

        if include_confidence:
            conf = _find_confidence(record_dict, from_path)
            if conf is not None:
                confidence_block[out_path] = conf

        if include_provenance:
            prov = _find_provenance(record_dict, from_path)
            if prov is not None:
                provenance_block[out_path] = prov

    if include_confidence:
        output["_confidence"] = confidence_block

    if include_provenance:
        output["_provenance"] = provenance_block

    return output