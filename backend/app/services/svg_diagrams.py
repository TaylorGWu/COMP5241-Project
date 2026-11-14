"""Safe course diagrams: preserve the IR graph and use a shared teaching layout."""
from __future__ import annotations

from app.services.diagram_layout import Connection as Edge, parse_graph, render_scene_svg

_BRANCH_WORDS = ("branch", "main", "分支", "主幹", "主干")
_PR_WORDS = ("pull request", "拉取请求", "拉取請求")
_EXCHANGE_WORDS = ("push", "pull", "本地", "遠端", "远端", "远程", "remote", "server", "client")


def _graph(code: str) -> tuple[list[str], list[Edge]]:
    nodes, edges = parse_graph(code)
    return [node.label for node in nodes], edges


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
    if any(word in haystack for word in _PR_WORDS):
        return "pull-request-flow"
    if _is_decision(code, edges):
        return "decision-branch"
    if _is_exchange(labels, edges):
        return "exchange-lane"
    if any(word in haystack for word in _BRANCH_WORDS):
        return "branch-lane"
    return "step-sequence"


def render_course_svg(code: str) -> str:
    """Render complete graph semantics; classification never replaces edges."""
    return render_scene_svg(code, course_diagram_template(code))
