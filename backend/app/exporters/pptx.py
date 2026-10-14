"""课件 → pptx —— 设计规格 §12.2。

═══════════════════════════════════════════════════════════════════
版式:一页 IR 幻灯片 = 一页 pptx,不做别的
═══════════════════════════════════════════════════════════════════
不额外加封面页、不加结束页。原因很实在:教师改课件之后重新导出,
页数必须还对得上,否则「课件第 3 页」这句话在两个地方指的是不同的页。

封面信息(受众、课时)挂在**第一页**上,而不是单独占一页。

═══════════════════════════════════════════════════════════════════
版面:固定 6 种,不追求任意排版
═══════════════════════════════════════════════════════════════════
title / bullets / diagram / twoCol / code / quiz —— 与 IR 的 `SlideLayout`
一一对应。规格里写明了不追求任意排版:占位符 + 自适应文本框极易溢出,
而溢出的表现是文字跑到页面外,教师拿到手才发现。

═══════════════════════════════════════════════════════════════════
图:插不进去也要留占位
═══════════════════════════════════════════════════════════════════
规格要求图用后端渲染的 PNG(§8.2 走 Kroki)。渲染服务还没接,
所以调 `slide_deck_to_pptx(..., asset_paths=...)` 时:
  有图 → 真的插进去
  没图 → 放一个占位框,写明这是什么图

**绝不留空白。** 一个空框会让教师以为导出坏了,而实际上是渲染还没接上 ——
这两种情况的处理方式完全不同。
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Emu, Pt

from app.schemas.ir import Project, Slide, SlideDeck, Visual

#: 16:9。和网页预览的画布比例一致 —— 不然教师会以为放错了。
SLIDE_WIDTH = 12192000
SLIDE_HEIGHT = 6858000

#: 页面边距(EMU)
MARGIN = 685800

#: 各版面里正文区的位置(precise 一点比用 layout placeholder 稳)
TITLE_TOP = 2286000
BODY_TOP = 1828800
BODY_HEIGHT = 4114800

FONT_TITLE = Pt(40)
FONT_SLIDE_TITLE = Pt(28)
FONT_BODY = Pt(18)
FONT_META = Pt(12)
FONT_CODE = Pt(14)

#: 图的占位框。**一定要带「图」字** —— 界面上和测试里都靠它区分「有图」和「没接渲染」。
PLACEHOLDER_PREFIX = "【图】"


def _blank_slide(prs: Presentation):
    """空白版面 —— 所有内容都由我们自己摆位置。"""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _textbox(slide, *, left: int, top: int, width: int, height: int):
    box = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    frame = box.text_frame
    frame.word_wrap = True
    return frame


def _line(frame, text: str, *, size, bold: bool = False) -> None:
    """往文本框追加一行。

    python-pptx 的 text_frame 永远自带一个空段落,所以第一行要**复用**它,
    否则页面上会多出一个空行(而且是行首的空行,最显眼的位置)。
    """
    paragraph = frame.paragraphs[0] if not frame.paragraphs[0].text else frame.add_paragraph()
    paragraph.text = text
    paragraph.font.size = size
    paragraph.font.bold = bold


def _visual_placeholder(visual: Visual) -> str:
    """图插不进去时显示的文字。

    Mermaid 的源码对教师也有用 —— 至少能看出这里该有张什么图。
    """
    kind = {"diagram": "示意图", "chart": "图表", "icon": "图标", "illustration": "插画"}.get(
        visual.kind, visual.kind
    )
    code = (visual.spec or {}).get("code") or (visual.spec or {}).get("prompt") or ""
    hint = str(code).strip().replace("\n", " ")[:120]
    return f"{PLACEHOLDER_PREFIX}{kind}(尚未渲染){(':' + hint) if hint else ''}"


def _add_visual(
    slide,
    visual: Visual,
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    asset_paths: Mapping[str, Path] | None,
) -> None:
    """把一处视觉需求落到页面上:能插图就插,不能就留占位。"""
    path = asset_paths.get(visual.asset_id) if (asset_paths and visual.asset_id) else None
    if path is not None and Path(path).exists():
        slide.shapes.add_picture(str(path), Emu(left), Emu(top), width=Emu(width))
        return

    frame = _textbox(slide, left=left, top=top, width=width, height=min(height, 914400))
    frame.paragraphs[0].text = _visual_placeholder(visual)
    frame.paragraphs[0].font.size = FONT_META


def _render_slide(
    prs: Presentation,
    slide_ir: Slide,
    *,
    is_first: bool,
    meta_line: str,
    asset_paths: Mapping[str, Path] | None,
) -> None:
    """把一页 IR 渲染成一页 pptx。"""
    slide = _blank_slide(prs)

    if slide_ir.layout == "title":
        frame = _textbox(
            slide,
            left=MARGIN,
            top=TITLE_TOP,
            width=SLIDE_WIDTH - 2 * MARGIN,
            height=1600200,
        )
        _line(frame, slide_ir.title, size=FONT_TITLE, bold=True)
        for bullet in slide_ir.bullets:
            _line(frame, bullet, size=FONT_BODY)
        if is_first and meta_line:
            # 封面信息挂在这一页上,不单独占一页 —— 否则教师改完课件重新导出,
            # 页数就对不上了,而「课件第 3 页」这句话在两个地方会指不同的页。
            _line(frame, meta_line, size=FONT_META)
        slide.notes_slide.notes_text_frame.text = slide_ir.speaker_notes
        return

    # 除封面外,第一行都是标题
    title_frame = _textbox(
        slide, left=MARGIN, top=MARGIN, width=SLIDE_WIDTH - 2 * MARGIN, height=914400
    )
    _line(title_frame, slide_ir.title, size=FONT_SLIDE_TITLE, bold=True)

    if is_first and meta_line:
        meta_frame = _textbox(
            slide, left=MARGIN, top=MARGIN + 800100, width=SLIDE_WIDTH - 2 * MARGIN, height=365760
        )
        _line(meta_frame, meta_line, size=FONT_META)

    has_visual = bool(slide_ir.visuals)
    body_width = SLIDE_WIDTH - 2 * MARGIN
    if has_visual:
        # 左文右图
        body_width = int((SLIDE_WIDTH - 2 * MARGIN) * 0.52)

    if slide_ir.layout == "twoCol":
        # 左右分栏:奇数条左边,偶数条右边
        left_items = slide_ir.bullets[::2]
        right_items = slide_ir.bullets[1::2]
        half = int((SLIDE_WIDTH - 3 * MARGIN) / 2)
        left_frame = _textbox(slide, left=MARGIN, top=BODY_TOP, width=half, height=BODY_HEIGHT)
        for item in left_items:
            _line(left_frame, item, size=FONT_BODY)
        right_frame = _textbox(
            slide, left=MARGIN * 2 + half, top=BODY_TOP, width=half, height=BODY_HEIGHT
        )
        for item in right_items:
            _line(right_frame, item, size=FONT_BODY)
    elif slide_ir.bullets:
        body_frame = _textbox(
            slide, left=MARGIN, top=BODY_TOP, width=body_width, height=BODY_HEIGHT
        )
        size = FONT_CODE if slide_ir.layout == "code" else FONT_BODY
        for bullet in slide_ir.bullets:
            _line(body_frame, bullet, size=size)

    if has_visual:
        visual = slide_ir.visuals[0]
        _add_visual(
            slide,
            visual,
            left=MARGIN + body_width + MARGIN // 2,
            top=BODY_TOP,
            width=SLIDE_WIDTH - 2 * MARGIN - body_width - MARGIN // 2,
            height=BODY_HEIGHT,
            asset_paths=asset_paths,
        )

    slide.notes_slide.notes_text_frame.text = slide_ir.speaker_notes


def slide_deck_to_pptx(
    project: Project,
    deck: SlideDeck,
    *,
    asset_paths: Mapping[str, Path] | None = None,
) -> bytes:
    """把课件导出成 pptx,返回文件字节。

    `asset_paths` 是 `assetId → 本地 PNG 路径`。给不出来就走占位 ——
    见模块文档字符串里关于「绝不留空白」的说明。
    """
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_WIDTH)
    prs.slide_height = Emu(SLIDE_HEIGHT)

    meta_line = f"受众:{project.meta.audience}　课时:{project.meta.duration_min} 分钟"

    for index, slide_ir in enumerate(deck.slides):
        _render_slide(
            prs,
            slide_ir,
            is_first=(index == 0),
            meta_line=meta_line,
            asset_paths=asset_paths,
        )

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()
