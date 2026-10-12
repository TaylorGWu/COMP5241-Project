"""材料摄取测试 —— 对应设计规格 §6.1 阶段 1 与 §14(失败隔离)。

两条最重要的:
  · **扫描件必须被识别出来并转 OCR**,不能静默抽到 0 字还说成功
  · **单个文件失败不影响整批**
"""

from __future__ import annotations

import pytest

try:
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

from app.services.ingest import (
    IngestDeps,
    chunk_text,
    detect_form,
    ingest_file,
    ingest_many,
    sniff_head,
)


# ═══════════════════════════════════════════════════════════
# 探测:看文件头,不看扩展名
# ═══════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"%PDF-1.7\n...", "pdf"),
        (b"PK\x03\x04\x14\x00", "zip"),
        (b"\xff\xd8\xff\xe0", "jpeg"),
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
        (b"GIF89a...", "gif"),
        (b"\x00\x01\x02\x03", "unknown"),
    ],
)
def test_sniff_head(head, expected):
    assert sniff_head(head) == expected


# ═══════════════════════════════════════════════════════════
# 夹具:造材料
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def text_pdf(tmp_path):
    """有文字层的 PDF。"""
    p = tmp_path / "text.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((60, 90), "Git branching keeps the trunk usable. " * 8, fontsize=12)
    doc.save(str(p))
    doc.close()
    return p


@pytest.fixture
def scanned_pdf(tmp_path, text_pdf):
    """扫描版 PDF:把文字页渲染成图,再塞进新 PDF —— 没有文字层。"""
    p = tmp_path / "scanned.pdf"
    with pymupdf.open(str(text_pdf)) as doc:
        src = doc[0]
        pix = src.get_pixmap(dpi=120)
        out = pymupdf.open()
        pg = out.new_page(width=src.rect.width, height=src.rect.height)
        pg.insert_image(pg.rect, pixmap=pix)
        out.save(str(p))
        out.close()
    return p


async def fake_ocr(image_bytes: bytes) -> str:
    """假 OCR:回显图片大小,便于断言它真的收到了图。"""
    return f"OCR 读到 {len(image_bytes)} 字节的图,内容是 Git 分支说明。"


def deps() -> IngestDeps:
    return IngestDeps(ocr_image=fake_ocr)


# ═══════════════════════════════════════════════════════════
# ★ 核心:扫描件必须被识别出来
# ═══════════════════════════════════════════════════════════


def test_text_pdf_is_detected_as_text_pdf(text_pdf):
    assert detect_form(text_pdf) == "text_pdf"


def test_scanned_pdf_is_detected_as_scanned(scanned_pdf):
    """扩展名一样,但内容探测必须把它判成扫描件。"""
    assert detect_form(scanned_pdf) == "scanned_pdf"


async def test_text_pdf_is_extracted_without_ocr(text_pdf):
    report = await ingest_file(text_pdf, deps=deps())
    assert report.status == "ok"
    assert report.ocr_used is False
    assert report.extracted_chars > 0
    assert all(c.kind == "text" for c in report.chunks)


async def test_scanned_pdf_falls_back_to_ocr(scanned_pdf):
    """扫描件抽不到字 → 必须转 OCR,并标为 degraded 提醒教师抽查。"""
    report = await ingest_file(scanned_pdf, deps=deps())
    assert report.detected_form == "scanned_pdf"
    assert report.ocr_used is True
    assert report.status == "degraded"
    assert report.extracted_chars > 0
    assert all(c.kind == "ocr" for c in report.chunks)


async def test_ocr_failure_reports_zero_chars_loudly(tmp_path, scanned_pdf):
    """OCR 也读不出来时,状态必须是 failed 且说明原因 —— 不能静默成功。"""

    async def empty_ocr(_: bytes) -> str:
        return ""

    report = await ingest_file(scanned_pdf, deps=IngestDeps(ocr_image=empty_ocr))
    assert report.status == "failed"
    assert report.extracted_chars == 0
    assert "没读到任何文字" in report.message


# ═══════════════════════════════════════════════════════════
# 格式支持与拒绝
# ═══════════════════════════════════════════════════════════


async def test_markdown_is_read(tmp_path):
    p = tmp_path / "notes.md"
    p.write_text("# 标题\n\n这是一段笔记内容。", encoding="utf-8")
    report = await ingest_file(p, deps=deps())
    assert report.detected_form == "text"
    assert report.status == "ok"
    assert report.extracted_chars > 0


async def test_image_goes_through_ocr(tmp_path):
    from PIL import Image

    p = tmp_path / "shot.png"
    Image.new("RGB", (200, 100), "white").save(str(p))
    report = await ingest_file(p, deps=deps())
    assert report.detected_form == "image"
    assert report.ocr_used is True
    assert report.status == "degraded"


async def test_unsupported_format_is_rejected_with_a_helpful_message(tmp_path):
    p = tmp_path / "book.xlsx"
    p.write_bytes(b"PK\x03\x04" + b"\x00" * 100 + b"xl/worksheets/sheet1.xml")
    report = await ingest_file(p, deps=deps())
    assert report.status == "failed"
    assert "不支持的格式" in report.message
    assert ".pdf" in report.message          # 要告诉教师支持什么


async def test_renamed_file_is_caught_by_content_not_extension(tmp_path):
    """把一个假文件改名成 .pdf —— 靠扩展名会误判,靠文件头不会。"""
    p = tmp_path / "fake.pdf"
    p.write_bytes(b"\x00\x01\x02\x03" * 50)
    report = await ingest_file(p, deps=deps())
    assert report.status == "failed"


# ═══════════════════════════════════════════════════════════
# ★ 失败隔离(§14)
# ═══════════════════════════════════════════════════════════


async def test_one_bad_file_does_not_break_the_batch(tmp_path, text_pdf):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.7\nbut this is not a real pdf")
    good = tmp_path / "ok.md"
    good.write_text("正常内容" * 50, encoding="utf-8")

    reports = await ingest_many([bad, text_pdf, good], deps=deps())

    assert len(reports) == 3
    assert reports[1].status == "ok"      # 中间那个好的没受影响
    assert reports[2].status == "ok"
    assert reports[0].status == "failed"  # 坏的如实报告
    assert reports[0].message             # 且带原因


# ═══════════════════════════════════════════════════════════
# 分块与页码
# ═══════════════════════════════════════════════════════════


def test_chunk_text_keeps_page_number():
    chunks = chunk_text("内容" * 900, page=7)
    assert chunks and all(c.page == 7 for c in chunks)


def test_short_text_is_one_chunk():
    assert len(chunk_text("短", page=1)) == 1


def test_long_text_is_split_with_overlap():
    text = "句子。" * 500
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # 相邻块必须有重叠,否则跨块的句子会被切断
    assert chunks[0].text[-20:] in chunks[1].text


def test_empty_text_yields_no_chunks():
    assert chunk_text("   \n\n  ") == []


async def test_pdf_chunks_carry_page_numbers(text_pdf):
    report = await ingest_file(text_pdf, deps=deps())
    assert report.pages >= 1
    assert all(c.page is not None and c.page >= 1 for c in report.chunks)


# ═══════════════════════════════════════════════════════════
# 报告本身
# ═══════════════════════════════════════════════════════════


def test_summary_shows_extracted_chars():
    """报告必须显示抽到多少字 —— 这是「没读到」可见的前提。"""
    from app.services.ingest import IngestReport

    r = IngestReport(
        filename="a.pdf", detected_form="text_pdf", status="ok",
        pages=2, extracted_chars=1234,
    )
    text = r.summary()
    assert "1234" in text and "2 页" in text
