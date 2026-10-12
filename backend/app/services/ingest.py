"""材料摄取 —— 设计规格 §6.1 阶段 1 的真实实现。

═══════════════════════════════════════════════════════════════════
核心原则:靠「探测」,不靠「猜扩展名」
═══════════════════════════════════════════════════════════════════
同一个扩展名,内容可能完全不同:

    讲义.pdf   ← Word 导出的,有文字层     → PyMuPDF 直接抽
    讲义.pdf   ← 扫描仪扫的,全是图        → 抽到 0 字!必须转 OCR

`课件.pptx` 每页是一张截图时,也一样抽不到字。

所以流程是三步:

    ① 读文件头(magic bytes)→ 知道真实格式,扩展名可以是骗人的
    ② 抽样看内容有没有文字  → 决定走「抽文字」还是「转 OCR」
    ③ 抽不到就如实报告      → **绝不静默成功**

最后一条最重要:抽到 0 字还显示「解析成功」,教师会以为是模型不行,
而实际是这份文件根本没读到。所以报告里必须带 `extracted_chars`。

═══════════════════════════════════════════════════════════════════
失败隔离(§14)
═══════════════════════════════════════════════════════════════════
单个文件失败**不影响整批**。`ingest_many()` 永远返回每个文件的报告,
失败的标 `status="failed"` 并带上原因,而不是抛异常中断。
"""

from __future__ import annotations

import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

# PyMuPDF 1.24+ 推荐 `import pymupdf`;老版本叫 `fitz`
try:
    import pymupdf  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore[no-redef]

# ═══════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════

Form = Literal[
    "text_pdf", "scanned_pdf", "pptx", "docx", "text", "image", "unsupported"
]
Status = Literal["ok", "degraded", "failed"]

#: 一份文件被判定为「有文字层」的最低密度(每页至少这么多字)
MIN_CHARS_PER_PAGE = 50

#: 抽样探测的页数。全扫一遍太慢,前几页足够判断。
SAMPLE_PAGES = 3

#: 分块大小与重叠(字符数)。重叠是为了不让跨块的句子被切断。
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

#: 渲染扫描页给 OCR 时的分辨率。太高会撑爆请求体,太低 OCR 认不出。
RENDER_DPI = 150

SUPPORTED_SUFFIXES = {
    ".pdf", ".pptx", ".docx", ".md", ".txt", ".markdown",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}


# ═══════════════════════════════════════════════════════════════
# ① 探测:这个文件到底是什么
# ═══════════════════════════════════════════════════════════════


def sniff_head(head: bytes) -> str:
    """只看文件头几个字节判断真实格式 —— 扩展名是可以改的,文件头不能。

    返回 "pdf" / "zip" / "jpeg" / "png" / "webp" / "gif" / "unknown"。
    """
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "zip"  # pptx / docx / xlsx 都是 zip 容器
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return "unknown"


def _zip_kind(path: Path) -> str:
    """zip 容器再看里面装的是什么 —— pptx 有 `ppt/`,docx 有 `word/`。

    注意:xlsx 和「伪装成 zip 的二进制」都以 `PK\x03\x04` 开头。
    打不开就返回 "unknown",由 `detect_form` 归为不支持 ——
    **不能让 BadZipFile 冒到外层**,否则教师看到的是「探测失败」而不是
    「不支持的格式」,前者完全没法排查。
    """
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
    except (zipfile.BadZipFile, OSError):
        return "unknown"
    if any(n.startswith("ppt/") for n in names):
        return "pptx"
    if any(n.startswith("word/") for n in names):
        return "docx"
    return "unknown"


def _pdf_text_density(path: Path) -> tuple[int, int]:
    """抽样统计 PDF 的文字密度,返回 (总字数, 抽样页数)。

    这是「扫描件判定」的依据:扫描件的文字都在图里,get_text() 返回空。
    """
    with pymupdf.open(path) as doc:
        pages = [doc[i] for i in range(min(SAMPLE_PAGES, doc.page_count))]
        chars = sum(len(page.get_text().strip()) for page in pages)
    return chars, len(pages)


#: 控制字符占比超过这个值,就当成二进制,不当文本
MAX_CONTROL_RATIO = 0.05


def _looks_like_text(path: Path, sample: int = 4096) -> bool:
    """判断一个「没有 magic」的文件是不是纯文本。

    **光靠 `decode("utf-8")` 不够** —— 像 `\x00\x01\x02\x03` 这种二进制
    在 UTF-8 下是合法的,会被误判成文本文件,然后「解析成功但抽到一堆乱码」。
    所以再加两条:不能有 NUL 字节,控制字符比例要低。
    """
    data = path.open("rb").read(sample)
    if not data:
        return False
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    control = sum(1 for b in data if b < 32 and b not in (9, 10, 13))
    return control / len(data) < MAX_CONTROL_RATIO


def detect_form(path: Path) -> Form:
    """综合文件头 + 内容探测,判断这份材料该走哪条解析路。

    注意:返回的是「处理方式」而不是「文件类型」——
    `text_pdf` 和 `scanned_pdf` 扩展名一样,但走的路完全不同。
    """
    head = path.open("rb").read(16)
    kind = sniff_head(head)

    if kind == "pdf":
        chars, pages = _pdf_text_density(path)
        dense = chars >= MIN_CHARS_PER_PAGE * pages
        return "text_pdf" if dense else "scanned_pdf"

    if kind == "zip":
        inner = _zip_kind(path)
        return inner if inner in ("pptx", "docx") else "unsupported"

    if kind in ("jpeg", "png", "webp", "gif"):
        return "image"

    if kind == "unknown":
        # 没有 magic —— 可能是纯文本。
        return "text" if _looks_like_text(path) else "unsupported"

    return "unsupported"


# ═══════════════════════════════════════════════════════════════
# ② 分块:保留页码,这是溯源的基础(§9.2)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Chunk:
    """一个检索单元。**page 是必须的** —— 没有它就没法标注「来源 p.14」。"""

    text: str
    page: int | None = None
    kind: Literal["text", "ocr"] = "text"


def chunk_text(text: str, *, page: int | None = None, kind: str = "text") -> list[Chunk]:
    """把一段文字切成带重叠的块。短文本原样返回一块。"""
    text = text.strip()
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [Chunk(text=text, page=page, kind=kind)]  # type: ignore[arg-type]

    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        # 尽量在句子边界切,别把话切一半
        if end < len(text):
            for sep in ("\n\n", "\n", "。", ". "):
                cut = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        chunks.append(Chunk(text=text[start:end].strip(), page=page, kind=kind))  # type: ignore[arg-type]
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return [c for c in chunks if c.text]


# ═══════════════════════════════════════════════════════════════
# ③ 各格式的抽取
# ═══════════════════════════════════════════════════════════════


@dataclass
class IngestReport:
    """一份材料的摄取结果。

    `extracted_chars == 0` 就是「没读到」,必须让教师看见 ——
    这是这份报告存在的意义。
    """

    filename: str
    detected_form: Form
    status: Status
    message: str = ""
    pages: int = 0
    extracted_chars: int = 0
    ocr_used: bool = False
    chunks: list[Chunk] = field(default_factory=list)
    images: list[str] = field(default_factory=list)

    def summary(self) -> str:
        icon = {"ok": "✅", "degraded": "⚠️ ", "failed": "❌"}[self.status]
        bits = [f"{self.detected_form}", f"{self.pages} 页" if self.pages else "",
                f"{self.extracted_chars} 字"]
        if self.ocr_used:
            bits.append("已 OCR")
        return f"{icon} {self.filename:<24} " + " · ".join(b for b in bits if b) + (
            f"  ← {self.message}" if self.message else ""
        )


#: OCR 函数签名:图片字节 → 文字。抽成可替换的,是为了 demo 不需要 key 就能跑。
OcrFn = Callable[[bytes], Awaitable[str]]


@dataclass
class IngestDeps:
    """摄取需要的外部能力。"""

    #: 图片 → 文字。生产环境接 DeepSeek Flash;demo / 测试传假实现。
    ocr_image: OcrFn
    #: 从 PDF / PPTX 里抽出来的图存到哪(相对路径会进 assets 池)
    image_dir: Path | None = None


async def _extract_pdf(path: Path, deps: IngestDeps, report: IngestReport) -> None:
    """抽 PDF。有文字层就直接抽;没有就渲染成图走 OCR。"""
    with pymupdf.open(path) as doc:
        report.pages = doc.page_count

        if report.detected_form == "text_pdf":
            for i, page in enumerate(doc, start=1):
                report.chunks.extend(chunk_text(page.get_text(), page=i))
            return

        # ── 扫描件:没有文字层,只能渲染成图让多模态模型读 ──
        report.ocr_used = True
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=RENDER_DPI)
            text = await deps.ocr_image(pix.tobytes("png"))
            report.chunks.extend(chunk_text(text, page=i, kind="ocr"))


async def _extract_image(path: Path, deps: IngestDeps, report: IngestReport) -> None:
    """图片直接走 OCR / 多模态理解。"""
    report.pages = 1
    report.ocr_used = True
    text = await deps.ocr_image(path.read_bytes())
    report.chunks.extend(chunk_text(text, page=1, kind="ocr"))


def _extract_pptx(path: Path, report: IngestReport) -> None:
    """抽 PPTX。文字 + 备注,按页编号 —— 溯源要用。"""
    from pptx import Presentation

    prs = Presentation(str(path))
    report.pages = len(prs.slides)
    for i, slide in enumerate(prs.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            if shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
        # 备注也算内容 —— 教师常把讲解写在备注里
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            parts.append(slide.notes_slide.notes_text_frame.text.strip())
        report.chunks.extend(chunk_text("\n".join(parts), page=i))


def _extract_docx(path: Path, report: IngestReport) -> None:
    """抽 DOCX。段落 + 表格。DOCX 没有真实页码,用段落序号当锚点。"""
    import docx

    document = docx.Document(str(path))
    parts: list[str] = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    text = "\n".join(parts)
    report.pages = 1
    report.chunks.extend(chunk_text(text, page=1))


def _extract_text(path: Path, report: IngestReport) -> None:
    """纯文本 / Markdown 直接读。"""
    text = path.read_text(encoding="utf-8", errors="replace")
    report.pages = 1
    report.chunks.extend(chunk_text(text, page=1))


_EXTRACTORS = {
    "text_pdf": _extract_pdf,
    "scanned_pdf": _extract_pdf,
    "pptx": _extract_pptx,
    "docx": _extract_docx,
    "text": _extract_text,
    "image": _extract_image,
}


# ═══════════════════════════════════════════════════════════════
# ④ 对外入口
# ═══════════════════════════════════════════════════════════════


async def ingest_file(path: Path, *, deps: IngestDeps) -> IngestReport:
    """摄取一份材料。**不抛异常** —— 失败会体现在返回的报告里。"""
    report = IngestReport(filename=path.name, detected_form="unsupported", status="failed")

    if not path.exists():
        report.message = "文件不存在"
        return report

    try:
        form = detect_form(path)
    except Exception as exc:  # noqa: BLE001
        report.message = f"探测失败:{type(exc).__name__}: {exc}"
        return report

    report.detected_form = form

    if form == "unsupported":
        report.message = (
            "不支持的格式。支持:" + " / ".join(sorted(SUPPORTED_SUFFIXES))
        )
        return report

    extractor = _EXTRACTORS[form]
    try:
        result = extractor(path, deps, report) if form in ("text_pdf", "scanned_pdf", "image") \
            else extractor(path, report)
        if result is not None:
            await result
    except Exception as exc:  # noqa: BLE001
        # §14:单个文件失败不影响整批。如实报告,继续处理下一个。
        report.message = f"解析失败:{type(exc).__name__}: {exc}"
        return report

    report.extracted_chars = sum(len(c.text) for c in report.chunks)

    # ── 最关键的判定:抽到 0 字必须说出来 ──────────────────
    if report.extracted_chars == 0:
        report.status = "failed"
        report.message = (
            "没读到任何文字。若是扫描件或纯截图,OCR 也没识别出来 —— "
            "建议换文字版文件,或先自行确认内容是否可读。"
        )
    elif report.ocr_used:
        report.status = "degraded"   # 能用,但经过 OCR,质量需要教师抽查
        report.message = "扫描件 / 图片,已用 OCR 提取,建议抽查识别准确性"
    else:
        report.status = "ok"

    return report


async def ingest_many(paths: list[Path], *, deps: IngestDeps) -> list[IngestReport]:
    """摄取一批材料。**逐个处理,一个失败不影响其他。**

    这里故意不用 `asyncio.gather` —— OCR 调用是外部 API,
    一批文件同时打过去容易被限流。材料摄取不是瓶颈,顺序跑更稳。
    """
    return [await ingest_file(p, deps=deps) for p in paths]


def total_chunks(reports: list[IngestReport]) -> int:
    """汇总统计,给流水线的进度回报用。"""
    return sum(len(r.chunks) for r in reports)
