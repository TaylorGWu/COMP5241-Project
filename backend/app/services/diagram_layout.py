"""Deterministic layout shared by SVG previews and offline PNG exports.

Accept the compact flowchart subset used by the generation tools. Preserve node
identity, edge direction and complete labels; never infer extra teaching claims.
"""
from collections import defaultdict, deque
from dataclasses import dataclass
from html import escape, unescape
import re
import unicodedata

_ID = r"[A-Za-z_][\w-]*"
_SHAPE = r'(?:\["[^"]*"\]|\[[^\]]*\]|\{"[^"]*"\}|\{[^}]*\}|\("[^"]*"\)|\([^()]*\))'
_NODE = re.compile(rf'(?P<id>{_ID})\s*(?P<shape>{_SHAPE})')
_EDGE = re.compile(rf'(?P<source>{_ID})(?:\s*{_SHAPE})?\s*(?:--\s*(?P<branch>[^>\n;]+?)\s*-->|-->)\s*(?:\|(?P<pipe>[^|\n]+)\|\s*)?(?P<target>{_ID})(?:\s*{_SHAPE})?')
FONT = "Manrope, Noto Sans CJK TC, Noto Sans CJK SC, PingFang TC, Hiragino Sans GB, sans-serif"
NODE_FONT_SIZE = 26
NODE_LINE_HEIGHT = 34
EDGE_FONT_SIZE = 18
EDGE_LINE_HEIGHT = 24


@dataclass
class Node:
    id: str
    label: str
    lines: list[str]
    decision: bool
    x: float = 0
    y: float = 0
    width: float = 240
    height: float = 88
    tone: str = 'default'


def node_colors(node: Node) -> tuple[str, str, str]:
    """A bounded semantic palette, never arbitrary Mermaid CSS or URLs."""
    return {
        'primary': ('#315fc6', '#315fc6', '#ffffff'),
        'review': ('#fdf5e9', '#96601a', '#714710'),
        'accepted': ('#f0f8f3', '#2a7755', '#245f44'),
    }.get(node.tone, ('#fff8eb', '#b78131', '#172033') if node.decision else ('#f3f6fc', '#a9b9d4', '#172033'))


@dataclass
class Connection:
    source: str
    target: str
    label: str
    points: tuple[tuple[float, float], ...] = ()
    caption: tuple[float, float, float, float] = (0, 0, 0, 0)
    caption_anchor: tuple[float, float] | None = None


@dataclass
class Scene:
    nodes: list[Node]
    edges: list[Connection]
    width: float
    height: float


def _label(value: str) -> str:
    return unescape(re.sub(r"<br\s*/?>", "\n", value.strip().strip('"'), flags=re.I))


def wrap_label(label: str, limit: int = 20) -> list[str]:
    """Keep every character; CJK glyphs receive twice a Latin glyph's budget."""
    def weight(char: str) -> float:
        return 2 if unicodedata.east_asian_width(char) in "WF" or char in "MWmw@#%&" else 1.5 if char.isupper() else 1

    lines, line, used = [], "", 0
    for char in label:
        size = weight(char)
        if char == "\n" or used + size > limit:
            if char != "\n" and not char.isspace() and " " in line.rstrip():
                head, _, tail = line.rpartition(" ")
                lines.append(head)
                line, used = tail, sum(weight(c) for c in tail)
            else:
                lines.append(line.rstrip())
                line, used = "", 0
            if char == "\n":
                continue
        if not line and char.isspace():
            continue
        line += char
        used += size
    return lines + ([line] if line else []) or [""]


def parse_graph(code: str) -> tuple[list[Node], list[Connection]]:
    classes = re.findall(r'(?:^|[;\n])\s*class\s+([\w,-]+)\s+(primary|review|accepted)\b', code)
    # Style directives are not graph nodes (e.g. url(...) is not a shape).
    # Unknown CSS is ignored by this safe subset rather than copied into SVG.
    code = re.sub(r'(?:^|(?<=[;\n]))\s*(?:classDef|class|style|linkStyle)\s+[^;\n]*', '', code)
    nodes: dict[str, Node] = {}
    for match in _NODE.finditer(code):
        shape = match["shape"]
        label = _label(shape[1:-1])
        lines = wrap_label(label, 14)
        nodes[match["id"]] = Node(match["id"], label, lines, shape.startswith("{"), height=max(96, 32 + len(lines) * NODE_LINE_HEIGHT))
    edges = []
    cursor = 0
    while match := _EDGE.search(code, cursor):
        cursor = match.start("target")
        source, target = match["source"], match["target"]
        edges.append(Connection(source, target, _label(match["branch"] or match["pipe"] or "")))
        for node_id in (source, target):
            if node_id not in nodes:
                lines = wrap_label(node_id, 14)
                nodes[node_id] = Node(node_id, node_id, lines, False, height=max(96, 32 + len(lines) * NODE_LINE_HEIGHT))
    for ids, tone in classes:
        for node_id in ids.split(','):
            if node_id in nodes:
                nodes[node_id].tone = tone
    return list(nodes.values()), edges


def layout_graph(code: str) -> Scene:
    nodes, edges = parse_graph(code)
    if not nodes:
        return Scene([], [], 640, 180)
    by_id = {node.id: node for node in nodes}
    incoming, children = defaultdict(int), defaultdict(list)
    for edge in edges:
        incoming[edge.target] += 1
        children[edge.source].append(edge.target)
    roots = [node.id for node in nodes if not incoming[node.id]] or [nodes[0].id]
    rank = {node_id: 0 for node_id in roots}
    queue = deque(roots)
    # Breadth-first layering also terminates for feedback loops. Back-edges are
    # routed separately rather than changing their direction or deleting them.
    while len(rank) < len(nodes) or queue:
        if not queue:
            node_id = next(node.id for node in nodes if node.id not in rank)
            rank[node_id] = 0
            queue.append(node_id)
        source = queue.popleft()
        for target in children[source]:
            if target not in rank:
                rank[target] = rank[source] + 1
                queue.append(target)
    layers = defaultdict(list)
    for node in nodes:
        layers[rank[node.id]].append(node)
    horizontal = not re.search(r"(?:graph|flowchart)\s+(?:TD|TB|BT)\b", code)
    semantic_rank = rank.copy()
    if re.search(r"(?:graph|flowchart)\s+BT\b", code):
        # Reverse only positioning; the source/target relationship is unchanged.
        rank = {key: max(rank.values()) - value for key, value in rank.items()}
        layers = defaultdict(list)
        for node in nodes:
            layers[rank[node.id]].append(node)
    caption_height = max((len(wrap_label(edge.label, 8)) * EDGE_LINE_HEIGHT + 14 for edge in edges if edge.label), default=0)
    row_height = max(max(node.height for node in nodes), caption_height if horizontal else 0)
    rank_gap = max(96, caption_height + 32)
    largest = max(len(layer) for layer in layers.values())
    width = 144 + ((max(rank.values()) + 1) * 240 + max(rank.values()) * 120 if horizontal else largest * 240 + (largest - 1) * 64)
    content_height = largest * row_height + (largest - 1) * 64 if horizontal else (max(rank.values()) + 1) * row_height + max(rank.values()) * rank_gap
    has_feedback = any(semantic_rank[edge.target] <= semantic_rank[edge.source] for edge in edges)
    height = 144 + content_height + (caption_height + 48 if has_feedback else 0)
    for level, layer in layers.items():
        for index, node in enumerate(layer):
            if horizontal:
                node.x = 72 + level * 360
                node.y = 72 + (content_height - (len(layer) * row_height + (len(layer) - 1) * 64)) / 2 + index * (row_height + 64) + (row_height - node.height) / 2
            else:
                node.x = (width - (len(layer) * 240 + (len(layer) - 1) * 64)) / 2 + index * 304
                node.y = 72 + level * (row_height + rank_gap)
    # Long strips shrink every glyph when fitted to a slide. Fold ranks, not
    # individual nodes: siblings retain their branch relationship and no edge
    # or label is dropped. Short diagrams keep their authored orientation.
    folded = max(rank.values()) >= 3 and largest <= 2
    if folded:
        columns = 3
        bands = (max(rank.values()) + columns) // columns
        band_height = largest * row_height + (largest - 1) * 64
        band_gap = max(112, caption_height + 40)
        width = 112 + columns * 240 + (columns - 1) * 120
        content_height = bands * band_height + (bands - 1) * band_gap
        height = 112 + content_height + (caption_height + 48 if has_feedback else 0)
        for level, layer in layers.items():
            band, column = divmod(level, columns)
            if band % 2:
                column = columns - 1 - column
            for index, node in enumerate(layer):
                node.x = 56 + column * 360
                node.y = 56 + band * (band_height + band_gap) + (band_height - (len(layer) * row_height + (len(layer) - 1) * 64)) / 2 + index * (row_height + 64) + (row_height - node.height) / 2
    for index, edge in enumerate(edges):
        start, end = by_id[edge.source], by_id[edge.target]
        forward = semantic_rank[edge.target] > semantic_rank[edge.source]
        if folded and forward:
            if rank[edge.source] // 3 == rank[edge.target] // 3:
                right = end.x > start.x
                a = (start.x + (start.width if right else 0), start.y + start.height / 2)
                b = (end.x + (0 if right else end.width), end.y + end.height / 2)
                mid = (a[0] + b[0]) / 2
                edge.points = (a, (mid, a[1]), (mid, b[1]), b)
            else:
                down = end.y > start.y
                a = (start.x + 120, start.y + (start.height if down else 0))
                b = (end.x + 120, end.y + (0 if down else end.height))
                mid = (a[1] + b[1]) / 2
                edge.points = (a, (a[0], mid), (b[0], mid), b)
        elif horizontal and end.x > start.x:
            a, b = (start.x + start.width, start.y + start.height / 2), (end.x, end.y + end.height / 2)
            mid = (a[0] + b[0]) / 2
            edge.points = (a, (mid, a[1]), (mid, b[1]), b)
        elif not horizontal and semantic_rank[edge.target] > semantic_rank[edge.source]:
            a, b = ((start.x + 120, start.y + start.height), (end.x + 120, end.y)) if end.y > start.y else ((start.x + 120, start.y), (end.x + 120, end.y + end.height))
            mid = (a[1] + b[1]) / 2
            edge.points = (a, (a[0], mid), (b[0], mid), b)
        else:
            bottom = 72 + content_height + 32 + caption_height / 2 + (index % 3) * 8
            a, b = (start.x + 170, start.y + start.height), (end.x + 70, end.y + end.height)
            edge.points = (a, (a[0], bottom), (b[0], bottom), b)
    if re.search(r"(?:graph|flowchart)\s+RL\b", code):
        for node in nodes:
            node.x = width - node.x - node.width
        for edge in edges:
            edge.points = tuple((width - x, y) for x, y in edge.points)
    for edge in edges:
        if edge.label:
            a, b = edge.points[1:3]
            caption_h = len(wrap_label(edge.label, 8)) * EDGE_LINE_HEIGHT + 14
            center_x = (a[0] + b[0]) / 2
            center_y = edge.points[-1][1] if horizontal and not folded and semantic_rank[edge.target] > semantic_rank[edge.source] else (a[1] + b[1]) / 2
            edge.caption_anchor = (center_x, center_y)
            edge.caption = (center_x - 52, center_y - caption_h / 2, 104, caption_h)
    placed: list[tuple[float, float, float, float]] = []
    for edge in edges:
        if not edge.label:
            continue
        x, y, w, h = edge.caption
        # Converging edges and feedback loops can share a caption anchor.
        # Resolve collisions in the clear inter-rank channel, not over nodes.
        for px, py, pw, ph in placed:
            if x < px+pw+8 and x+w+8 > px and y < py+ph+8 and y+h+8 > py:
                if not horizontal and semantic_rank[edge.target] > semantic_rank[edge.source]:
                    x = px + pw + 16
                else:
                    y = py + ph + 16
        edge.caption = (x, y, w, h)
        placed.append(edge.caption)
        width = max(width, x+w+32)
        height = max(height, y+h+32)
    return Scene(nodes, edges, width, height)


def render_scene_svg(code: str, template: str) -> str:
    scene = layout_graph(code)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {scene.width:g} {scene.height:g}" role="img" aria-labelledby="diagram-title diagram-description" data-template="{escape(template)}">',
        '<title id="diagram-title">Course relationship diagram</title>',
        f'<desc id="diagram-description">{escape("; ".join(n.label for n in scene.nodes))}</desc>',
        f'<rect width="{scene.width:g}" height="{scene.height:g}" fill="#ffffff"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M1 1L9 5L1 9" fill="none" stroke="#64748b" stroke-width="1.5"/></marker></defs>']
    for edge in scene.edges:
        path = "M" + " L".join(f"{x:g},{y:g}" for x, y in edge.points)
        parts.append(f'<path data-source="{escape(edge.source)}" data-target="{escape(edge.target)}" d="{path}" fill="none" stroke="#64748b" stroke-width="1.75" stroke-linejoin="round" marker-end="url(#arrow)"/>')
    for node in scene.nodes:
        fill, stroke, ink = node_colors(node)
        parts.append(f'<g data-node-id="{escape(node.id)}"><rect x="{node.x:g}" y="{node.y:g}" width="240" height="{node.height:g}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="1.25"/>')
        y = node.y + (node.height - (len(node.lines) - 1) * NODE_LINE_HEIGHT) / 2 + 8
        parts.append(f'<text x="{node.x + 120:g}" text-anchor="middle" fill="{ink}" font-family="{FONT}" font-size="{NODE_FONT_SIZE}" font-weight="550" aria-label="{escape(node.label)}" xml:space="preserve">')
        for index, line in enumerate(node.lines):
            parts.append(f'<tspan x="{node.x + 120:g}" y="{y + index * NODE_LINE_HEIGHT:g}">{escape(line)}</tspan>')
        parts.append('</text></g>')
    # Edge captions are drawn last on a clean backing so crossings stay legible.
    for edge in scene.edges:
        if edge.label:
            x, y, width, height = edge.caption
            if edge.caption_anchor != (x+width/2, y+height/2):
                ax, ay = edge.caption_anchor
                parts.append(f'<path d="M{ax:g},{ay:g} L{x+width/2:g},{y+height/2:g}" fill="none" stroke="#a9b9d4" stroke-width="1" stroke-dasharray="3 3"/>')
            parts.append(f'<rect x="{x:g}" y="{y:g}" width="{width:g}" height="{height:g}" rx="5" fill="#ffffff"/><text text-anchor="middle" fill="#475569" font-family="{FONT}" font-size="{EDGE_FONT_SIZE}" aria-label="{escape(edge.label)}" xml:space="preserve">')
            for index, line in enumerate(wrap_label(edge.label, 8)):
                parts.append(f'<tspan x="{x+width/2:g}" y="{y+23+index*EDGE_LINE_HEIGHT:g}">{escape(line)}</tspan>')
            parts.append('</text>')
    if not scene.nodes:
        parts.append('<text x="320" y="90" text-anchor="middle" font-family="sans-serif" font-size="18">No supported graph nodes</text>')
    return "".join(parts) + '</svg>'
