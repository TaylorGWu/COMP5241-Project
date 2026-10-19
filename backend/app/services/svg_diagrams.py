"""把课程 IR 里的 Mermaid 结构渲染成可读的教学 SVG。

这里没有模型调用，也不执行 Mermaid。Mermaid 源码只是 agent 已经产出的
"节点 + 关系" 数据；本模块用有限、可测试的版式把它画成适合课件的图。
这让中文标签保持可控，网页与导出器也能复用同一份视觉资产。
"""

from __future__ import annotations

from html import escape
import re

_NODE = re.compile(r"(?P<id>[A-Za-z][\w-]*)\s*\[(?P<label>[^\]]+)]")
_EDGE = re.compile(r"(?P<from>[A-Za-z][\w-]*)\s*--+>\s*(?P<to>[A-Za-z][\w-]*)")
_BRANCH_WORDS = ("branch", "main", "分支", "主幹", "主干")
_PR_WORDS = ("pull request", "拉取请求", "拉取請求")


def _short(text: str, limit: int = 18) -> str:
    """避免一条 AI 标签撑爆节点；完整内容仍留在幻灯片要点和讲稿。"""
    clean = " ".join(text.replace("`", "").split()).strip("\"'")
    return clean if len(clean) <= limit else f"{clean[: limit - 1]}…"


def _nodes(code: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    known: set[str] = set()
    for match in _NODE.finditer(code):
        node_id, label = match.group("id"), _short(match.group("label"))
        if node_id not in known:
            found.append((node_id, label))
            known.add(node_id)
    if found:
        return found[:5]

    # 生成器偶尔会写 A --> B 而不写方括号标签。保留节点而不是整张图空白。
    ids: list[str] = []
    for match in _EDGE.finditer(code):
        for node_id in (match.group("from"), match.group("to")):
            if node_id not in ids:
                ids.append(node_id)
    return [(node_id, _short(node_id.replace("_", " "))) for node_id in ids[:5]]


def _template(labels: list[str], code: str) -> str:
    haystack = f"{' '.join(labels)} {code}".lower()
    # 单独出现 review / merge 时通常仍是分支概念图; 有明确 PR 语义才画审查流。
    if any(word in haystack for word in _PR_WORDS):
        return "pull-request-flow"
    if any(word in haystack for word in _BRANCH_WORDS):
        return "branch-lane"
    return "step-sequence"


def _text(x: int, y: int, value: str, *, size: int = 18, fill: str = "#172033", weight: int = 600) -> str:
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="Arial, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">{escape(value)}</text>'
    )


def _card(x: int, y: int, width: int, label: str, *, fill: str, stroke: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="72" rx="16" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="2"/>'
        + _text(x + 18, y + 43, label, size=17)
    )


def _arrow(x1: int, y1: int, x2: int, y2: int, *, color: str = "#315FC6") -> str:
    return (
        f'<path d="M{x1} {y1} H{x2}" fill="none" stroke="{color}" stroke-width="5" '
        'stroke-linecap="round" marker-end="url(#arrow)"/>'
    )


def _defs() -> str:
    return """
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" fill="#315FC6"/>
        </marker>
      </defs>
    """


def _branch_lane(labels: list[str]) -> str:
    labels = (labels + ["Feature branch", "Review", "Merge", "main"])[:4]
    return "".join(
        [
            '<path d="M88 355 H862" stroke="#315FC6" stroke-width="8" stroke-linecap="round"/>',
            '<path d="M212 355 C260 355 255 192 338 192 H650 C710 192 705 355 766 355" '
            'fill="none" stroke="#16806A" stroke-width="8" stroke-linecap="round"/>',
            '<circle cx="212" cy="355" r="14" fill="#315FC6"/>',
            '<circle cx="766" cy="355" r="14" fill="#16806A"/>',
            _card(88, 398, 184, labels[0], fill="#E7EEFF", stroke="#B6C9F5"),
            _card(266, 132, 184, labels[1], fill="#DDF4EC", stroke="#9BD8C8"),
            _card(524, 132, 184, labels[2], fill="#DDF4EC", stroke="#9BD8C8"),
            _card(704, 398, 184, labels[3], fill="#E7EEFF", stroke="#B6C9F5"),
            _text(88, 326, "main", size=15, fill="#66758D", weight=700),
            _text(266, 108, "feature branch", size=15, fill="#16806A", weight=700),
        ]
    )


def _pull_request_flow(labels: list[str]) -> str:
    labels = (labels + ["Feature branch", "Pull request", "Review", "Merge"])[:4]
    xs = [74, 292, 510, 728]
    colors = [("#E7EEFF", "#B6C9F5"), ("#FFFFFF", "#AFC5F7"), ("#DDF4EC", "#9BD8C8"), ("#E7EEFF", "#B6C9F5")]
    parts = ['<rect x="278" y="118" width="232" height="212" rx="24" fill="#F5F8FF"/>']
    for index, (x, label) in enumerate(zip(xs, labels, strict=False)):
        fill, stroke = colors[index]
        parts.append(_card(x, 196, 158, label, fill=fill, stroke=stroke))
        if index < len(labels) - 1:
            parts.append(_arrow(x + 158, 232, xs[index + 1] - 18, 232, color="#16806A" if index == 2 else "#315FC6"))
    parts += [
        _text(318, 158, "review gate", size=14, fill="#315FC6", weight=700),
        '<circle cx="625" cy="142" r="10" fill="#16806A"/>',
        _text(646, 148, "checks passed", size=14, fill="#16806A", weight=700),
    ]
    return "".join(parts)


def _step_sequence(labels: list[str]) -> str:
    labels = (labels + ["Step 1", "Step 2", "Step 3"])[:4]
    count = len(labels)
    width = 170
    gap = 46
    start = int((960 - (count * width + (count - 1) * gap)) / 2)
    parts: list[str] = []
    for index, label in enumerate(labels):
        x = start + index * (width + gap)
        parts.append(f'<circle cx="{x + 28}" cy="178" r="28" fill="#315FC6"/>')
        parts.append(_text(x + 18, 185, str(index + 1), size=18, fill="#FFFFFF", weight=700))
        parts.append(_card(x, 230, width, label, fill="#FFFFFF", stroke="#DCE2EA"))
        if index < count - 1:
            parts.append(_arrow(x + width, 266, x + width + gap - 12, 266))
    return "".join(parts)


def render_diagram_svg(mermaid: str) -> str:
    """IR 中的 Mermaid 关系 → 安全、固定尺寸的教学 SVG。

    文本统一经 escape，不把 Mermaid 当代码执行。未知的图仍会落到步骤序列，
    保证单张视觉资产失败不会让整页或整包崩掉。
    """
    nodes = _nodes(mermaid)
    labels = [label for _, label in nodes]
    template = _template(labels, mermaid)
    if template == "pull-request-flow":
        body = _pull_request_flow(labels)
    elif template == "branch-lane":
        body = _branch_lane(labels)
    else:
        body = _step_sequence(labels)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 540" role="img" '
        f'aria-label="Course diagram" data-template="{template}">'
        '<rect width="960" height="540" rx="28" fill="#F7F9FD"/>'
        + _defs()
        + body
        + "</svg>"
    )
