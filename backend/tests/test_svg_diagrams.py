"""确定性课程图解 —— Mermaid 只是结构输入,不是最终视觉语言。"""

from app.services.svg_diagrams import render_diagram_svg


def test_branch_diagram_becomes_a_git_branch_lane_svg():
    svg = render_diagram_svg(
        "flowchart LR\nmain[主幹] --> branch[建立分支] --> review[程式碼審查] --> merge[合併]"
    )

    assert svg.startswith("<svg")
    assert 'data-template="branch-lane"' in svg
    assert "建立分支" in svg
    assert "主幹" in svg
    assert "<!--" not in svg


def test_pull_request_diagram_becomes_a_review_flow_svg():
    svg = render_diagram_svg(
        "flowchart LR\nbranch[Feature branch] --> pr[Pull request] --> review[Review] --> merge[Merge]"
    )

    assert 'data-template="pull-request-flow"' in svg
    assert "Pull request" in svg
    assert "Review" in svg


def test_diagram_labels_are_escaped_before_entering_svg():
    svg = render_diagram_svg('flowchart LR\na[<script>alert(1)</script>] --> b[Safe]')

    assert "<script>" not in svg
    assert "&lt;script&gt;" in svg
