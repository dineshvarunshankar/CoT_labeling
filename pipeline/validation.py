"""Shared validation for model responses and saved annotations."""

from __future__ import annotations

import math


BBox = tuple[float, float, float, float]


def validate_bbox(value: object) -> BBox:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError("subject_bbox must be an array of 4 numbers")
    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
        raise ValueError("subject_bbox must contain only numbers")
    try:
        left, top, right, bottom = (float(coord) for coord in value)
    except OverflowError as exc:
        raise ValueError("subject_bbox coordinates must be finite") from exc
    coords = (left, top, right, bottom)
    if not all(math.isfinite(coord) for coord in coords):
        raise ValueError("subject_bbox coordinates must be finite")
    if any(coord < 0 for coord in coords):
        raise ValueError("subject_bbox coordinates must be nonnegative")
    if left >= right or top >= bottom:
        raise ValueError("subject_bbox coordinates are not ordered")
    return coords


def validate_cot(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("cot must be a nonempty string")
    return value.strip()


def is_complete_annotation(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("modality") not in ("rgb", "thermal"):
        return False
    if payload.get("difficulty") not in ("easy", "hard"):
        return False
    try:
        validate_bbox(payload.get("subject_bbox"))
        validate_cot(payload.get("cot"))
    except ValueError:
        return False
    return True
