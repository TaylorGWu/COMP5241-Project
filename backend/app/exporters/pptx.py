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
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_SHAPE_TYPE
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

# Git 协作课件的视觉语言: 深墨色是「稳定的主干」,青绿是「安全合并/前进」,
# 砂白内容底避免每一页都像同一张后台表单。这里是纯渲染 token,不写回 IR。
INK = "172033"
CANVAS = "F6F7F3"
SURFACE = "FFFFFF"
BLUE = "2D5BC4"
TEAL = "16806A"
TEAL_SOFT = "DDF4EC"
BLUE_SOFT = "E7EEFF"
MUTED = "66758D"
LINE = "DCE2EA"

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


def _fill(shape, color: str) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.fill.background()


def _panel(
    slide,
    *,
    left: int,
    top: int,
    width: int,
    height: int,
    color: str = SURFACE,
    rounded: bool = True,
):
    """加一个无边框的内容面板。所有卡片都通过这一处生成,间距才会稳定。"""
    shape_type = MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE if rounded else MSO_AUTO_SHAPE_TYPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Emu(left), Emu(top), Emu(width), Emu(height))
    _fill(shape, color)
    return shape


def _background(slide, color: str) -> None:
    _panel(
        slide,
        left=0,
        top=0,
        width=SLIDE_WIDTH,
        height=SLIDE_HEIGHT,
        color=color,
        rounded=False,
    )


def _line(
    frame,
    text: str,
    *,
    size,
    bold: bool = False,
    color: str = INK,
    space_after: int = 0,
) -> None:
    """往文本框追加一行。

    python-pptx 的 text_frame 永远自带一个空段落,所以第一行要**复用**它,
    否则页面上会多出一个空行(而且是行首的空行,最显眼的位置)。
    """
    paragraph = frame.paragraphs[0] if not frame.paragraphs[0].text else frame.add_paragraph()
    paragraph.text = text
    # 不能只设 `font.name`: PowerPoint 把 CJK 当 East Asian 字体处理。缺这项时
    # LibreOffice 的回退会吞掉中文,导出结果就只剩冒号或英文。
    paragraph.font.name = "Arial"
    paragraph._p.get_or_add_pPr().get_or_add_defRPr().set("ea", "Heiti TC")  # noqa: SLF001
    # `paragraph.text` creates a run with its own properties, so set the East Asian
    # typeface there too; otherwise the paragraph default is ignored by some renderers.
    if paragraph.runs:
        run = paragraph.runs[0]
        run.font.name = "Arial"
        run._r.get_or_add_rPr().set("ea", "Apple LiGothic")  # noqa: SLF001
        run._r.get_or_add_rPr().set("cs", "Apple LiGothic")  # noqa: SLF001
    paragraph.font.size = size
    paragraph.font.bold = bold
    paragraph.font.color.rgb = RGBColor.from_string(color)
    paragraph.space_after = Pt(space_after)


def _label(slide, text: str, *, left: int, top: int, width: int, color: str, text_color: str) -> None:
    """简短的版式标签,替代机械的标题下划线。"""
    _panel(slide, left=left, top=top, width=width, height=304800, color=color)
    frame = _textbox(slide, left=left + 127000, top=top + 25400, width=width - 254000, height=254000)
    _line(frame, text.upper(), size=Pt(9), bold=True, color=text_color)


def _visual_placeholder(visual: Visual) -> str:
    """图插不进去时显示的文字。

    Mermaid 的源码对教师也有用 —— 至少能看出这里该有张什么图。
    """
    kind = {"diagram": "示意图", "chart": "图表", "icon": "图标", "illustration": "插画"}.get(
        visual.kind, visual.kind
    )
    # 英文说明让没有 CJK 字体的阅览器也不会呈现为空框; 中文保留给教师端和测试。
    return f"Diagram / {kind} pending render\nThe rendered visual will appear here. {PLACEHOLDER_PREFIX}{kind}尚未渲染"


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
    _line(frame, _visual_placeholder(visual), size=FONT_META, bold=True, color=MUTED, space_after=8)


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
        _background(slide, INK)
        _label(
            slide,
            "Course note",
            left=MARGIN,
            top=685800,
            width=1524000,
            color=BLUE,
            text_color="FFFFFF",
        )
        frame = _textbox(
            slide,
            left=MARGIN,
            top=1828800,
            width=int((SLIDE_WIDTH - 2 * MARGIN) * 0.78),
            height=1981200,
        )
        _line(frame, slide_ir.title, size=FONT_TITLE, bold=True, color="FFFFFF", space_after=12)
        for bullet in slide_ir.bullets:
            _line(frame, bullet, size=FONT_BODY, color="D7E1F7", space_after=8)
        if is_first and meta_line:
            # 封面信息挂在这一页上,不单独占一页 —— 否则教师改完课件重新导出,
            # 页数就对不上了,而「课件第 3 页」这句话在两个地方会指不同的页。
            _line(frame, meta_line, size=FONT_META, color="AFC5F7", space_after=8)
        slide.notes_slide.notes_text_frame.text = slide_ir.speaker_notes
        return

    _background(slide, CANVAS)
    _label(
        slide,
        slide_ir.layout,
        left=MARGIN,
        top=431800,
        width=1219200,
        color=TEAL_SOFT if slide_ir.layout == "diagram" else BLUE_SOFT,
        text_color=TEAL if slide_ir.layout == "diagram" else BLUE,
    )

    # 除封面外,第一行都是标题。标题不靠装饰线,而是靠卡片和留白分层。
    title_frame = _textbox(
        slide, left=MARGIN, top=1016000, width=SLIDE_WIDTH - 2 * MARGIN, height=787400
    )
    _line(title_frame, slide_ir.title, size=FONT_SLIDE_TITLE, bold=True, color=INK)

    if is_first and meta_line:
        meta_frame = _textbox(
            slide, left=MARGIN, top=1778000, width=SLIDE_WIDTH - 2 * MARGIN, height=304800
        )
        _line(meta_frame, meta_line, size=FONT_META, color=MUTED)

    has_visual = bool(slide_ir.visuals)
    content_top = 2387600 if is_first and meta_line else 2159000
    content_height = SLIDE_HEIGHT - content_top - MARGIN
    full_width = SLIDE_WIDTH - 2 * MARGIN

    if has_visual:
        # 带图页面让图占更大比重。图不是在正文旁边随手塞一个缩略图。
        text_width = int(full_width * 0.38)
        gap = 254000
        visual_width = full_width - text_width - gap
        _panel(slide, left=MARGIN, top=content_top, width=text_width, height=content_height)
        _panel(
            slide,
            left=MARGIN + text_width + gap,
            top=content_top,
            width=visual_width,
            height=content_height,
            color="F0F4F8" if slide_ir.layout == "diagram" else SURFACE,
        )
    elif slide_ir.layout != "twoCol":
        _panel(slide, left=MARGIN, top=content_top, width=full_width, height=content_height)

    if slide_ir.layout == "twoCol":
        # 左右分栏:奇数条左边,偶数条右边; 两块卡片让比较关系一眼可读。
        left_items = slide_ir.bullets[::2]
        right_items = slide_ir.bullets[1::2]
        gap = 304800
        half = int((full_width - gap) / 2)
        _panel(
            slide,
            left=MARGIN,
            top=content_top,
            width=half,
            height=content_height,
            color="F7FAFF",
        )
        _panel(
            slide,
            left=MARGIN + half + gap,
            top=content_top,
            width=half,
            height=content_height,
            color="F3FBF8",
        )
        _label(
            slide,
            "01",
            left=MARGIN + 254000,
            top=content_top + 254000,
            width=838200,
            color=BLUE_SOFT,
            text_color=BLUE,
        )
        _label(
            slide,
            "02",
            left=MARGIN + half + gap + 254000,
            top=content_top + 254000,
            width=838200,
            color=TEAL_SOFT,
            text_color=TEAL,
        )
        left_frame = _textbox(
            slide,
            left=MARGIN + 254000,
            top=content_top + 660400,
            width=half - 508000,
            height=content_height - 914400,
        )
        for item in left_items:
            _line(left_frame, item, size=FONT_BODY, space_after=14)
        right_frame = _textbox(
            slide,
            left=MARGIN + half + gap + 254000,
            top=content_top + 660400,
            width=half - 508000,
            height=content_height - 914400,
        )
        for item in right_items:
            _line(right_frame, item, size=FONT_BODY, space_after=14)
    elif slide_ir.bullets:
        body_left = MARGIN + 254000
        body_width = (text_width - 508000) if has_visual else (full_width - 508000)
        body_frame = _textbox(
            slide,
            left=body_left,
            top=content_top + 254000,
            width=body_width,
            height=content_height - 508000,
        )
        size = FONT_CODE if slide_ir.layout == "code" else FONT_BODY
        for bullet in slide_ir.bullets:
            prefix = "• " if slide_ir.layout not in {"code", "quiz"} else ""
            _line(
                body_frame,
                f"{prefix}{bullet}",
                size=size,
                color=INK if slide_ir.layout != "code" else "22304A",
                space_after=14,
            )

    if has_visual:
        visual = slide_ir.visuals[0]
        _add_visual(
            slide,
            visual,
            left=MARGIN + text_width + gap + 254000,
            top=content_top + 254000,
            width=visual_width - 508000,
            height=content_height - 508000,
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

    meta_line = f"Audience · {project.meta.audience}    Duration · {project.meta.duration_min} min"

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
