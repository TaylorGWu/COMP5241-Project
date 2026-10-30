"""Visual polish must not replace the teacher's actual relationship graph."""
import xml.etree.ElementTree as ET

import pytest

from app.services.svg_diagrams import render_course_svg
from app.services.diagram_layout import layout_graph, wrap_label
from app.services.mermaid_assets import _fallback_font


def test_complete_labels_and_all_nodes_survive_rendering():
    labels = ["Global feature [0.9, 0.8]", "Linear projection from two to four dimensions", "ReLU activation", "Linear projection from four to three dimensions", "Three classification logits", "Softmax probabilities"]
    code = "graph LR; " + "; ".join(f'n{i}["{label}"]' for i, label in enumerate(labels))
    code += "; " + "; ".join(f"n{i} --> n{i+1}" for i in range(5))
    root = ET.fromstring(render_course_svg(code))
    text = "".join(root.itertext())
    assert all(label in text for label in labels)
    assert len(root.findall(".//*[@data-node-id]")) == 6


def test_branch_edges_and_conditions_are_not_replaced_with_a_linear_sequence():
    root = ET.fromstring(render_course_svg("graph LR; A[Input] --> B{Accepted?}; B -->|yes| C[Continue]; B -->|no| D[Revise]; D --> B"))
    edges = {(e.attrib["data-source"], e.attrib["data-target"]) for e in root.findall(".//*[@data-source]")}
    assert edges == {("A", "B"), ("B", "C"), ("B", "D"), ("D", "B")}
    assert "yes" in "".join(root.itertext()) and "no" in "".join(root.itertext())
    assert "checks passed" not in "".join(root.itertext())


def test_labels_are_safe_text_and_svg_is_accessible():
    root = ET.fromstring(render_course_svg('graph TD; A["<script>alert(1)</script>"] -->|review & verify| B["Result"]'))
    assert root.attrib["role"] == "img"
    assert root.find("{http://www.w3.org/2000/svg}title") is not None
    assert not root.findall(".//{http://www.w3.org/2000/svg}script")
    assert not root.findall(".//{http://www.w3.org/2000/svg}foreignObject")


def test_chained_arrows_preserve_every_connection():
    root = ET.fromstring(render_course_svg("flowchart LR; A[需求] --> B[設計] --> C[實作] --> D[驗證]"))
    edges = {(e.attrib["data-source"], e.attrib["data-target"]) for e in root.findall(".//*[@data-source]")}
    assert edges == {("A", "B"), ("B", "C"), ("C", "D")}


def test_wide_glyph_labels_fit_inside_the_node_padding():
    scene = layout_graph('graph LR; A["' + 'W' * 52 + '"] --> B[End]')
    font = _fallback_font(26)
    assert all(font.getlength(line) <= 208 for line in scene.nodes[0].lines)


def test_long_condition_captions_fit_the_canvas_without_covering_nodes():
    scene = layout_graph('graph LR; A[Source] -->|' + 'a long condition for checking the result ' * 8 + '| B[Target]')
    edge = scene.edges[0]
    x, y, width, height = edge.caption
    assert x >= 0 and y >= 0 and x + width <= scene.width and y + height <= scene.height
    for node in scene.nodes:
        assert x + width <= node.x or x >= node.x + node.width or y + height <= node.y or y >= node.y + node.height


def test_sibling_branch_captions_do_not_erase_each_other():
    label = 'long branch condition ' * 6
    scene = layout_graph(f'graph LR; A{{Decision}} -->|{label}| B[Yes]; A -->|{label}| C[No]')
    a, b = [edge.caption for edge in scene.edges]
    assert a[0]+a[2] <= b[0] or b[0]+b[2] <= a[0] or a[1]+a[3] <= b[1] or b[1]+b[3] <= a[1]


@pytest.mark.parametrize('direction', ['LR', 'RL', 'TD', 'BT'])
def test_long_flows_remain_readable_in_a_slide_figure(direction):
    # At a 600x420 preview, labels must not become six-pixel text in a strip.
    code = f'graph {direction}; A[Ingest materials] --> B[Plan outline] --> C[Section agents] --> D[Inspect visuals] --> E[Collect assets] --> F[Validate IR]'
    scene = layout_graph(code)
    root = ET.fromstring(render_course_svg(code))
    font_size = float(root.find('.//{http://www.w3.org/2000/svg}text').attrib['font-size'])
    assert font_size * min(600 / scene.width, 420 / scene.height) >= 12
    assert len({node.y for node in scene.nodes}) > 1
    assert len({node.x for node in scene.nodes}) > 1
    assert {(edge.source, edge.target) for edge in scene.edges} == {('A', 'B'), ('B', 'C'), ('C', 'D'), ('D', 'E'), ('E', 'F')}
    for node in scene.nodes:
        assert 0 <= node.x < node.x + node.width <= scene.width
        assert 0 <= node.y < node.y + node.height <= scene.height


def test_folded_architecture_keeps_both_outputs_and_their_edge_captions():
    scene = layout_graph('graph LR; A[Browser] --> B[API] --> C[Service] --> D[IR]; D -->|persist| E[SQLite]; D -->|render| F[Preview and export]')
    assert scene.width / scene.height <= 3
    assert len(scene.nodes) == 6 and len(scene.edges) == 5
    for edge in scene.edges:
        if edge.label:
            x, y, w, h = edge.caption
            assert all(x+w <= n.x or x >= n.x+n.width or y+h <= n.y or y >= n.y+n.height for n in scene.nodes)


def test_larger_english_labels_wrap_at_words_when_the_words_fit():
    scene = layout_graph('graph LR; A[Teacher browser] --> B[L1 or L2 service] --> C[CoursePackage IR]')
    assert scene.nodes[0].lines == ['Teacher', 'browser']
    assert scene.nodes[1].lines == ['L1 or L2', 'service']
    assert scene.nodes[2].lines == ['CoursePackage', 'IR']
    assert wrap_label('preview and export', 8) == ['preview', 'and', 'export']


def test_semantic_focus_classes_emphasize_review_without_changing_the_graph():
    code = 'graph LR; P[Proposed changes] --> R[Teacher review] --> A[Apply to IR]; class P primary; class R review; class A accepted'
    scene = layout_graph(code)
    assert [node.tone for node in scene.nodes] == ['primary', 'review', 'accepted']
    root = ET.fromstring(render_course_svg(code))
    ns = '{http://www.w3.org/2000/svg}'
    nodes = root.findall('.//*[@data-node-id]')
    assert [node.find(ns+'rect').attrib['fill'] for node in nodes] == ['#315fc6', '#fdf5e9', '#f0f8f3']
    assert {(edge.source, edge.target) for edge in scene.edges} == {('P','R'), ('R','A')}


def test_unknown_diagram_classes_cannot_inject_svg_styles():
    svg = render_course_svg('graph LR; A[Input] --> B[Result]; class A external; classDef external fill:url(https://example.test/x)')
    assert 'https://' not in svg and 'fill="url(' not in svg
    assert layout_graph('graph LR; A[Input]; class A external').nodes[0].tone == 'default'
