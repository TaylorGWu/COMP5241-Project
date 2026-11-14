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

from app.services.svg_diagrams import course_diagram_template


class MermaidRenderError(RuntimeError):
    """A diagram could not be rendered; callers may keep a text fallback."""


def _fallback_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A CJK-capable font for the diagram text. macOS and Linux both ship one;
    without any, Pillow's default would draw tofu, so fontconfig discovery is
    preferred over a fixed path list."""
    import shutil
    import subprocess

    for candidate in (
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    fc_match = shutil.which("fc-match")
    if fc_match:
        result = subprocess.run(
            [fc_match, "-f", "%{file}", ":lang=zh-cn"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0:
            path = result.stdout.strip()
            if path and Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    pass
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    left, top, right, bottom = box
    text_box = draw.textbbox((0, 0), text, font=font)
    x = left + (right - left - (text_box[2] - text_box[0])) / 2
    y = top + (bottom - top - (text_box[3] - text_box[1])) / 2 - text_box[1]
    draw.text((x, y), text, font=font, fill=fill)


def fallback_template_for(code: str) -> str:
    """Keep exported PNGs on the same semantic template as browser SVG previews."""
    return course_diagram_template(code)


def _render_local_png(code: str) -> bytes:
    """Offline export uses the exact same node/edge layout as SVG previews."""
    from app.services.diagram_layout import EDGE_FONT_SIZE, EDGE_LINE_HEIGHT, NODE_FONT_SIZE, NODE_LINE_HEIGHT, layout_graph, node_colors, wrap_label

    scene = layout_graph(code)
    # Preserve the scene's aspect ratio, not a second slide-shaped white mat.
    # Exporters already fit the image inside their own bounded placeholders.
    scale = min(1856 / scene.width, 1016 / scene.height)
    canvas = Image.new("RGB", (round(scene.width * scale) + 64, round(scene.height * scale) + 64), "#FFFFFF")
    draw = ImageDraw.Draw(canvas)
    offset_x = offset_y = 32

    def point(x: float, y: float) -> tuple[float, float]:
        return offset_x + x * scale, offset_y + y * scale

    for edge in scene.edges:
        points = [point(x, y) for x, y in edge.points]
        draw.line(points, fill="#64748B", width=max(2, round(1.75 * scale)), joint="curve")
        (ax, ay), (bx, by) = points[-2:]
        size = 8 * scale
        if abs(bx - ax) > abs(by - ay):
            direction = 1 if bx > ax else -1
            triangle = [(bx, by), (bx - direction * size, by - size / 2), (bx - direction * size, by + size / 2)]
        else:
            direction = 1 if by > ay else -1
            triangle = [(bx, by), (bx - size / 2, by - direction * size), (bx + size / 2, by - direction * size)]
        draw.polygon(triangle, fill="#64748B")
    font = _fallback_font(max(12, round(NODE_FONT_SIZE * scale)))
    for node in scene.nodes:
        fill, stroke, ink = node_colors(node)
        draw.rounded_rectangle((*point(node.x, node.y), *point(node.x + node.width, node.y + node.height)),
            radius=round(12 * scale), fill=fill, outline=stroke, width=max(1, round(1.25 * scale)))
        top = node.y + (node.height - len(node.lines) * NODE_LINE_HEIGHT) / 2
        for index, line in enumerate(node.lines):
            left, y = point(node.x, top + index * NODE_LINE_HEIGHT)
            right, bottom = point(node.x + node.width, top + (index + 1) * NODE_LINE_HEIGHT)
            _draw_centered(draw, (left, y, right, bottom), line, font, ink)
    hint_font = _fallback_font(max(11, round(EDGE_FONT_SIZE * scale)))
    for edge in scene.edges:
        if not edge.label:
            continue
        x, y, width, height = edge.caption
        if edge.caption_anchor != (x+width/2, y+height/2):
            draw.line((point(*edge.caption_anchor), point(x+width/2, y+height/2)), fill="#A9B9D4", width=max(1, round(scale)))
        draw.rectangle((*point(x, y), *point(x+width, y+height)), fill="#FFFFFF")
        for index, line in enumerate(wrap_label(edge.label, 8)):
            left, top = point(x, y + 6 + index * EDGE_LINE_HEIGHT)
            right, bottom = point(x+width, y + 6 + (index + 1) * EDGE_LINE_HEIGHT)
            _draw_centered(draw, (left, top, right, bottom), line, hint_font, "#475569")
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
            "fontSize": "26px",
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
    # The compact subset shown by the web preview must not acquire a different
    # CLI layout during export. Rich Mermaid syntax still uses its full engine.
    if re.match(r"\s*(?:graph|flowchart)\s+(?:LR|RL|TD|TB|BT)\b", code) and not re.search(
        r"(?:^|[;\n])\s*(?:subgraph|end|classDef|style|linkStyle)\b|---|==>|-\.->|:::|\[\[|\(\(", code
    ):
        return _render_local_png(code)
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
