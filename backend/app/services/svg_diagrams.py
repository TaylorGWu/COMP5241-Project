"""Render course diagrams as safe, deterministic SVG teaching graphics.

Mermaid is accepted only as a compact relationship description. It is never
executed in the browser: this module extracts labels and draws a finite set of
course-oriented layouts with ordinary SVG primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

_NODE = re.compile(r"(?P<id>[A-Za-z][\w-]*)\s*(?P<shape>[\[{])(?P<label>[^\]}]+)[\]}]")
_EDGE = re.compile(
    r"(?P<source>[A-Za-z][\w-]*)(?:[\[{][^\]}]+[\]}])?\s*"
    r"(?:(?:--\s*(?P<branch>[^>\n]+?)\s*-->)|-->)\s*"
    r"(?:\|(?P<pipe>[^|\n]+)\|\s*)?"
    r"(?P<target>[A-Za-z][\w-]*)(?:[\[{][^\]}]+[\]}])?"
)
_BRANCH_WORDS = ("branch", "main", "分支", "主幹", "主干")
_PR_WORDS = ("pull request", "拉取请求", "拉取請求")
_EXCHANGE_WORDS = ("push", "pull", "本地", "遠端", "远端", "远程", "remote", "server", "client")


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""


def _short(value: str, limit: int = 18) -> str:
    value = " ".join(value.replace("`", "").split()).strip("\"'")
    return value if len(value) <= limit else f"{value[:limit - 1]}…"


def _graph(code: str) -> tuple[list[str], list[Edge]]:
    labels: list[str] = []
    seen: set[str] = set()
    for match in _NODE.finditer(code):
        if match.group("id") not in seen:
            labels.append(_short(match.group("label")))
            seen.add(match.group("id"))
    edges: list[Edge] = []
    for match in _EDGE.finditer(code):
        source, target = match.group("source"), match.group("target")
        label = (match.group("branch") or match.group("pipe") or "").strip()
        edges.append(Edge(source=source, target=target, label=_short(label)))
        for node_id in (source, target):
            if node_id not in seen:
                labels.append(_short(node_id.replace("_", " ")))
                seen.add(node_id)
    return labels[:4], edges


def _text(x: int, y: int, label: str, *, size: int = 18, fill: str = "#172033", weight: int = 600) -> str:
    return f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, Hiragino Sans GB, sans-serif" font-size="{size}" font-weight="{weight}">{escape(label)}</text>'


def _card(x: int, y: int, width: int, label: str, fill: str, stroke: str) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="72" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="2"/>{_text(x + 16, y + 43, label, size=17)}'


def _arrow(x1: int, x2: int, y: int, color: str = "#315FC6") -> str:
    return f'<path d="M{x1} {y} H{x2}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" marker-end="url(#arrow)"/>'


def _curve(path: str, color: str = "#315FC6") -> str:
    return f'<path d="{path}" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" marker-end="url(#arrow)"/>'


def _branch_lane(labels: list[str]) -> str:
    labels = (labels + ["main", "Feature branch", "Review", "Merge"])[:4]
    return "".join((
        '<path d="M88 355 H872" stroke="#315FC6" stroke-width="8" stroke-linecap="round"/>',
        '<path d="M210 355 C260 355 252 190 340 190 H640 C714 190 708 355 772 355" fill="none" stroke="#16806A" stroke-width="8" stroke-linecap="round"/>',
        '<circle cx="210" cy="355" r="14" fill="#315FC6"/><circle cx="772" cy="355" r="14" fill="#16806A"/>',
        _card(82, 398, 186, labels[0], "#E7EEFF", "#B6C9F5"),
        _card(264, 130, 186, labels[1], "#DDF4EC", "#9BD8C8"),
        _card(520, 130, 186, labels[2], "#DDF4EC", "#9BD8C8"),
        _card(696, 398, 186, labels[3], "#E7EEFF", "#B6C9F5"),
        _text(82, 326, "main", size=15, fill="#66758D", weight=700),
        _text(264, 106, "feature branch", size=15, fill="#16806A", weight=700),
    ))


def _pull_request_flow(labels: list[str]) -> str:
    labels = (labels + ["Feature branch", "Pull request", "Review", "Merge"])[:4]
    xs = [72, 290, 508, 726]
    colors = (("#E7EEFF", "#B6C9F5"), ("#FFFFFF", "#AFC5F7"), ("#DDF4EC", "#9BD8C8"), ("#E7EEFF", "#B6C9F5"))
    parts = ['<rect x="276" y="118" width="234" height="212" rx="24" fill="#F5F8FF"/>']
    for index, (x, label) in enumerate(zip(xs, labels, strict=False)):
        parts.append(_card(x, 196, 158, label, *colors[index]))
        if index < len(labels) - 1:
            parts.append(_arrow(x + 158, xs[index + 1] - 18, 232, "#16806A" if index == 2 else "#315FC6"))
    parts.extend((_text(316, 158, "review gate", size=14, fill="#315FC6", weight=700), '<circle cx="625" cy="142" r="10" fill="#16806A"/>', _text(646, 148, "checks passed", size=14, fill="#16806A", weight=700)))
    return "".join(parts)


def _step_sequence(labels: list[str]) -> str:
    # A renderer must not fabricate learning content.  A short Mermaid graph is
    # still a short relationship: show the nodes it contains rather than adding
    # misleading "Step 1/2" cards merely to fill the canvas.
    labels = labels[:4] or ["未提供關係"]
    width, gap = 170, 46
    start = int((960 - (len(labels) * width + (len(labels) - 1) * gap)) / 2)
    parts: list[str] = []
    for index, label in enumerate(labels):
        x = start + index * (width + gap)
        parts.extend((f'<circle cx="{x + 28}" cy="178" r="28" fill="#315FC6"/>', _text(x + 18, 185, str(index + 1), size=18, fill="#FFFFFF", weight=700), _card(x, 230, width, label, "#FFFFFF", "#DCE2EA")))
        if index < len(labels) - 1:
            parts.append(_arrow(x + width, x + width + gap - 12, 266))
    return "".join(parts)


def _exchange_lane(labels: list[str], edges: list[Edge]) -> str:
    """Show named transfers between two workspaces and a shared service."""
    labels = (labels + ["Local workspace", "Shared service", "Teammate workspace"])[:3]
    transfers = [edge.label for edge in edges if edge.label]
    outgoing = transfers[0] if transfers else "send"
    incoming = transfers[1] if len(transfers) > 1 else "receive"
    return "".join((
        '<rect x="326" y="90" width="308" height="126" rx="24" fill="#E7EEFF" stroke="#B6C9F5" stroke-width="2"/>',
        _text(350, 130, "共用版本紀錄", size=14, fill="#315FC6", weight=700),
        _text(350, 174, labels[1], size=19),
        _card(76, 352, 238, labels[0], "#FFFFFF", "#DCE2EA"),
        _card(646, 352, 238, labels[2], "#FFFFFF", "#DCE2EA"),
        _curve("M195 352 C220 285 318 246 406 218"),
        _curve("M554 218 C640 246 740 285 765 352", "#16806A"),
        _text(238, 270, outgoing, size=15, fill="#315FC6", weight=700),
        _text(660, 270, incoming, size=15, fill="#16806A", weight=700),
        '<circle cx="208" cy="316" r="7" fill="#315FC6"/><circle cx="752" cy="316" r="7" fill="#16806A"/>',
    ))


def _decision_branch(labels: list[str], edges: list[Edge]) -> str:
    """Keep a decision point and its alternatives visible on a projected slide."""
    labels = (labels + ["Check state", "Decision", "Continue", "Resolve"])[:4]
    outcome_edges = [edge for edge in edges if edge.label]
    first_label = outcome_edges[0].label if outcome_edges else "option A"
    second_label = outcome_edges[1].label if len(outcome_edges) > 1 else "option B"
    return "".join((
        _card(60, 234, 210, labels[0], "#E7EEFF", "#B6C9F5"),
        _curve("M270 270 C320 270 344 270 380 270"),
        '<path d="M480 144 L580 270 L480 396 L380 270 Z" fill="#F5F8FF" stroke="#5472A6" stroke-width="3"/>',
        _text(414, 276, labels[1], size=17),
        _curve("M568 230 C626 188 648 162 690 162", "#16806A"),
        _curve("M568 310 C626 352 648 378 690 378", "#C46B1B"),
        _card(694, 126, 208, labels[2], "#DDF4EC", "#9BD8C8"),
        _card(694, 342, 208, labels[3], "#FFF4E5", "#F2C980"),
        _text(606, 198, first_label, size=15, fill="#16806A", weight=700),
        _text(606, 350, second_label, size=15, fill="#C46B1B", weight=700),
    ))


def _is_decision(code: str, edges: list[Edge]) -> bool:
    return "{" in code or sum(bool(edge.label) for edge in edges) >= 2 and any(
        edge.label.lower() in {"yes", "no", "是", "否", "true", "false"} for edge in edges
    )


def _is_exchange(labels: list[str], edges: list[Edge]) -> bool:
    haystack = " ".join((*labels, *(edge.label for edge in edges))).lower()
    return len(edges) >= 2 and any(word in haystack for word in _EXCHANGE_WORDS)


def course_diagram_template(code: str) -> str:
    """Classify compact Mermaid IR into one bounded teaching visual treatment."""
    labels, edges = _graph(code)
    haystack = f"{' '.join(labels)} {code}".lower()
    if _is_decision(code, edges):
        return "decision-branch"
    if _is_exchange(labels, edges):
        return "exchange-lane"
    if any(word in haystack for word in _PR_WORDS):
        return "pull-request-flow"
    if any(word in haystack for word in _BRANCH_WORDS):
        return "branch-lane"
    return "step-sequence"


def render_course_svg(code: str) -> str:
    """Produce a safe SVG from diagram IR without evaluating Mermaid or model code."""
    labels, edges = _graph(code)
    template = course_diagram_template(code)
    if template == "decision-branch":
        template, body = "decision-branch", _decision_branch(labels, edges)
    elif template == "exchange-lane":
        template, body = "exchange-lane", _exchange_lane(labels, edges)
    elif template == "pull-request-flow":
        template, body = "pull-request-flow", _pull_request_flow(labels)
    elif template == "branch-lane":
        template, body = "branch-lane", _branch_lane(labels)
    else:
        template, body = "step-sequence", _step_sequence(labels)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" role="img" aria-label="Course diagram" data-template="{template}">'
        '<rect width="960" height="540" rx="28" fill="#F7F9FD"/>'
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#315FC6"/></marker></defs>'
        f"{body}</svg>"
    )
