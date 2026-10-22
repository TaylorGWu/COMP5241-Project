from __future__ import annotations

from app.schemas.ir import Slide
from app.services.animation import normalize_slide_animation


def _slide_payload() -> dict[str, object]:
    return {
        "id": "s1",
        "order": 1,
        "layout": "diagram",
        "title": "Why record changes?",
        "bullets": ["A commit keeps a recoverable checkpoint."],
        "visuals": [
            {
                "id": "v1",
                "kind": "diagram",
                "spec": {"engine": "mermaid", "code": "flowchart LR\nA --> B"},
            }
        ],
    }


def test_legacy_slide_has_no_animation_by_default() -> None:
    slide = Slide.model_validate(_slide_payload())

    assert slide.animation is None
    assert slide.model_dump(by_alias=True).get("animation") is None


def test_slide_serializes_a_valid_animation_with_camel_case_fields() -> None:
    slide = Slide.model_validate(
        {
            **_slide_payload(),
            "animation": {
                "autoplay": True,
                "steps": [
                    {"kind": "reveal", "target": "title", "atMs": 0},
                    {
                        "kind": "reveal",
                        "target": "bullet:0",
                        "atMs": 700,
                        "durationMs": 850,
                    },
                    {"kind": "sequence", "target": "visual:v1", "atMs": 1700},
                ],
            },
        }
    )

    assert slide.model_dump(by_alias=True)["animation"] == {
        "autoplay": True,
        "steps": [
            {"kind": "reveal", "target": "title", "atMs": 0, "durationMs": 700},
            {
                "kind": "reveal",
                "target": "bullet:0",
                "atMs": 700,
                "durationMs": 850,
            },
            {"kind": "sequence", "target": "visual:v1", "atMs": 1700, "durationMs": 700},
        ],
    }


def test_legacy_animation_steps_migrate_to_the_current_contract() -> None:
    """Older agent replies used ``action`` and omitted their playback times."""
    slide = Slide.model_validate(
        {
            **_slide_payload(),
            "bullets": ["First point.", "Second point."],
            "animation": {
                "steps": [
                    {"action": "reveal", "target": "title"},
                    {"action": "reveal", "target": "bullet:0"},
                    {"action": "emphasize", "target": "bullet:1"},
                ]
            },
        }
    )

    assert slide.model_dump(by_alias=True)["animation"]["steps"] == [
        {"kind": "reveal", "target": "title", "atMs": 0, "durationMs": 700},
        {"kind": "reveal", "target": "bullet:0", "atMs": 700, "durationMs": 700},
        {"kind": "emphasis", "target": "bullet:1", "atMs": 1400, "durationMs": 700},
    ]


def test_invalid_animation_is_dropped_but_base_slide_is_retained() -> None:
    raw = {
        **_slide_payload(),
        "animation": {
            "steps": [
                {"kind": "reveal", "target": "bullet:99", "atMs": 0},
            ]
        },
    }

    normalized, warning = normalize_slide_animation(raw)

    assert normalized["id"] == "s1"
    assert normalized["title"] == "Why record changes?"
    assert "animation" not in normalized
    assert warning == "animation_unknown_target"
