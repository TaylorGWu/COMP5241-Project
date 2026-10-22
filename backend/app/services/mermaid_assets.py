"""Render Mermaid IR to PNG bytes without involving a model or network service."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from io import BytesIO
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.svg_diagrams import _graph, course_diagram_template


class MermaidRenderError(RuntimeError):
    """A diagram could not be rendered; callers may keep a text fallback."""


_NODE = re.compile(r"(?P<id>[A-Za-z][\w-]*)\s*\[(?P<label>[^\]]+)]")


def _fallback_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Use a local CJK-capable font when present, otherwise Pillow's default."""
    for candidate in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fallback_labels(code: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for match in _NODE.finditer(code):
        node_id = match.group("id")
        if node_id in seen:
            continue
        label = " ".join(match.group("label").replace("`", "").split())
        labels.append(label[:28] + ("…" if len(label) > 28 else ""))
        seen.add(node_id)
    return (labels + ["Change", "Review", "Verified result"])[:4]


def _draw_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (text_box[2] - text_box[0])) / 2
    y = top + (bottom - top - (text_box[3] - text_box[1])) / 2 - text_box[1]
    draw.text((x, y), text, font=font, fill=fill)


def fallback_template_for(code: str) -> str:
    """Keep exported PNGs on the same semantic template as browser SVG previews."""
    return course_diagram_template(code)


def _draw_card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    font: ImageFont.ImageFont,
    *,
    fill: str = "#FFFFFF",
    outline: str = "#DCE2EA",
) -> None:
    draw.rounded_rectangle(box, radius=24, fill=fill, outline=outline, width=4)
    _draw_centered(draw, box, label, font, "#172033")


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str) -> None:
    draw.line((*start, *end), fill=color, width=10)
    x, y = end
    arrow = 26
    if abs(end[0] - start[0]) >= abs(end[1] - start[1]):
        direction = 1 if end[0] >= start[0] else -1
        draw.polygon(((x, y), (x - direction * arrow, y - arrow // 2), (x - direction * arrow, y + arrow // 2)), fill=color)
    else:
        direction = 1 if end[1] >= start[1] else -1
        draw.polygon(((x, y), (x - arrow // 2, y - direction * arrow), (x + arrow // 2, y - direction * arrow)), fill=color)


def _draw_exchange_png(draw: ImageDraw.ImageDraw, labels: list[str], edge_labels: list[str]) -> None:
    labels = (labels + ["Local workspace", "Shared source", "Teammate workspace"])[:3]
    label_font = _fallback_font(32)
    hint_font = _fallback_font(27)
    _draw_card(draw, (650, 166, 1270, 350), labels[1], label_font, fill="#E7EEFF", outline="#B6C9F5")
    _draw_card(draw, (130, 676, 650, 858), labels[0], label_font)
    _draw_card(draw, (1270, 676, 1790, 858), labels[2], label_font)
    _draw_arrow(draw, (650, 676), (815, 350), "#315FC6")
    _draw_arrow(draw, (1105, 350), (1270, 676), "#16806A")
    _draw_centered(draw, (530, 428, 750, 480), edge_labels[0] if edge_labels else "send", hint_font, "#315FC6")
    _draw_centered(draw, (1170, 428, 1390, 480), edge_labels[1] if len(edge_labels) > 1 else "receive", hint_font, "#16806A")


def _draw_decision_png(draw: ImageDraw.ImageDraw, labels: list[str], edge_labels: list[str]) -> None:
    labels = (labels + ["Check state", "Decision", "Continue", "Resolve"])[:4]
    label_font = _fallback_font(31)
    hint_font = _fallback_font(27)
    _draw_card(draw, (112, 470, 530, 650), labels[0], label_font, fill="#E7EEFF", outline="#B6C9F5")
    _draw_arrow(draw, (530, 560), (720, 560), "#315FC6")
    diamond = ((960, 330), (1160, 560), (960, 790), (760, 560))
    draw.polygon(diamond, fill="#F5F8FF", outline="#5472A6", width=5)
    _draw_centered(draw, (805, 500, 1115, 620), labels[1], label_font, "#172033")
    _draw_card(draw, (1370, 222, 1808, 402), labels[2], label_font, fill="#DDF4EC", outline="#9BD8C8")
    _draw_card(draw, (1370, 720, 1808, 900), labels[3], label_font, fill="#FFF4E5", outline="#F2C980")
    _draw_arrow(draw, (1108, 500), (1370, 316), "#16806A")
    _draw_arrow(draw, (1108, 620), (1370, 810), "#C46B1B")
    _draw_centered(draw, (1120, 385, 1320, 435), edge_labels[0] if edge_labels else "option A", hint_font, "#16806A")
    _draw_centered(draw, (1120, 690, 1320, 740), edge_labels[1] if len(edge_labels) > 1 else "option B", hint_font, "#C46B1B")


def _render_local_png(code: str) -> bytes:
    """Draw the same compact teaching-flow fallback without a browser process.

    Mermaid remains the stored structural language. This renderer only makes the
    export resilient when mmdc/Puppeteer is unavailable (for example, a locked
    down deployment or test runner).
    """
    canvas = Image.new("RGB", (1920, 1080), "#F7F9FD")
    draw = ImageDraw.Draw(canvas)
    labels = _fallback_labels(code)
    graph_labels, edges = _graph(code)
    if graph_labels:
        labels = graph_labels
    template = fallback_template_for(code)
    title_font = _fallback_font(34)
    label_font = _fallback_font(32)
    number_font = _fallback_font(30)
    card_width, card_height, gap = 390, 166, 62
    total_width = len(labels) * card_width + (len(labels) - 1) * gap
    start_x = (1920 - total_width) // 2
    card_top = 460

    draw.rounded_rectangle((72, 70, 1848, 1010), radius=48, fill="#FFFFFF", outline="#DCE2EA", width=4)
    draw.text((130, 150), "工程決策流程", font=title_font, fill="#172033")
    draw.text((130, 208), "從改動追蹤到可驗證結果。", font=label_font, fill="#66758D")
    edge_labels = [edge.label for edge in edges if edge.label]
    if template == "exchange-lane":
        _draw_exchange_png(draw, labels, edge_labels)
    elif template == "decision-branch":
        _draw_decision_png(draw, labels, edge_labels)
    else:
        for index, label in enumerate(labels):
            x = start_x + index * (card_width + gap)
            draw.ellipse((x + 18, 350, x + 78, 410), fill="#315FC6")
            _draw_centered(draw, (x + 18, 350, x + 78, 410), str(index + 1), number_font, "#FFFFFF")
            draw.rounded_rectangle((x, card_top, x + card_width, card_top + card_height), radius=26, fill="#EEF4FF", outline="#B6C9F5", width=4)
            _draw_centered(draw, (x + 28, card_top + 30, x + card_width - 28, card_top + card_height - 30), label, label_font, "#172033")
            if index < len(labels) - 1:
                line_start = x + card_width + 12
                line_end = x + card_width + gap - 20
                mid_y = card_top + card_height // 2
                draw.line((line_start, mid_y, line_end, mid_y), fill="#315FC6", width=10)
                draw.polygon(((line_end, mid_y), (line_end - 24, mid_y - 16), (line_end - 24, mid_y + 16)), fill="#315FC6")

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _cli() -> str:
    configured = os.environ.get("MERMAID_CLI_PATH")
    if configured:
        return configured
    local = Path(__file__).resolve().parents[2] / "node_modules" / ".bin" / "mmdc"
    if local.is_file():
        return str(local)
    installed = shutil.which("mmdc")
    if installed:
        return installed
    raise MermaidRenderError("Mermaid CLI is not installed for the backend")


def _browser_env() -> dict[str, str]:
    env = os.environ.copy()
    if "PUPPETEER_EXECUTABLE_PATH" not in env:
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
        ):
            if Path(candidate).is_file():
                env["PUPPETEER_EXECUTABLE_PATH"] = candidate
                break
    return env


def mermaid_render_config() -> dict[str, object]:
    """Keep deterministic diagrams readable on a projected teaching slide."""
    return {
        "securityLevel": "strict",
        "theme": "base",
        "themeVariables": {
            "fontFamily": "Arial, 'Hiragino Sans GB', sans-serif",
            "fontSize": "18px",
            "primaryColor": "#eef4ff",
            "primaryTextColor": "#172033",
            "primaryBorderColor": "#5472a6",
            "lineColor": "#5472a6",
            "secondaryColor": "#f7f9fd",
            "tertiaryColor": "#dce8ff",
            "clusterBkg": "#f7f9fd",
            "clusterBorder": "#a8b9d4",
            "edgeLabelBackground": "#ffffff",
        },
        "flowchart": {
            "htmlLabels": False,
            "curve": "basis",
            "nodeSpacing": 54,
            "rankSpacing": 64,
            "padding": 16,
            "useMaxWidth": True,
        },
    }


@lru_cache(maxsize=64)
def render_mermaid_png(code: str) -> bytes:
    """Convert one Mermaid diagram to PNG; identical diagrams reuse cached bytes."""
    if not code.strip() or len(code) > 20_000:
        raise MermaidRenderError("Diagram source is empty or too large")
    with tempfile.TemporaryDirectory(prefix="course-mermaid-") as directory:
        root = Path(directory)
        source = root / "diagram.mmd"
        output = root / "diagram.png"
        config = root / "config.json"
        source.write_text(code, encoding="utf-8")
        config.write_text(json.dumps(mermaid_render_config()), encoding="utf-8")
        try:
            result = subprocess.run(
                [_cli(), "-i", str(source), "-o", str(output), "-b", "white", "-s", "2", "-c", str(config), "-q"],
                capture_output=True,
                text=True,
                env=_browser_env(),
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _render_local_png(code)
        if result.returncode != 0 or not output.is_file():
            return _render_local_png(code)
        data = output.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return _render_local_png(code)
        return data
