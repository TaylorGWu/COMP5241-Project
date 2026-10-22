"""Validation and graceful degradation for optional slide-preview animations.

Animations are metadata over the existing courseware IR.  A malformed plan must
never drop otherwise valid teaching content, so this module strips only that
metadata and returns a stable warning code for the job record.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from app.schemas.ir import Slide, SlideAnimation, slide_animation_validation_error


def normalize_slide_animation(raw_slide: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Keep a valid base slide when optional animation metadata is malformed."""

    candidate = deepcopy(raw_slide)
    raw_animation = candidate.pop("animation", None)
    if raw_animation is None:
        return candidate, None

    # The normal generation validator owns errors in the base slide itself.
    try:
        base_slide = Slide.model_validate(candidate)
    except ValidationError:
        return candidate, None

    try:
        animation = SlideAnimation.model_validate(raw_animation)
    except ValidationError:
        return candidate, "animation_invalid_shape"

    warning = slide_animation_validation_error(base_slide, animation)
    if warning:
        return candidate, warning

    normalized = Slide.model_validate({**candidate, "animation": raw_animation})
    return normalized.model_dump(by_alias=True), None
