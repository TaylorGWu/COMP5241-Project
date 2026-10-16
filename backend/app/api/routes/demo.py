"""仅供本地演示的接口 —— **不是设计规格 §13 定义的正式 API。**

═══════════════════════════════════════════════════════════════════
为什么单独开一套
═══════════════════════════════════════════════════════════════════
正式 API 要的东西现在都还没有:

    正式 API(§13)             这个 demo 路由
    ─────────────────────     ─────────────────────
    JWT + RBAC 鉴权            无认证
    PostgreSQL 持久化          进程内存,重启即丢
    异步作业 + SSE 进度         请求内直接跑(但**有** SSE 了,见 §13.4)
    /api/artifacts/...         /api/demo/...
    需要 patches 表            内存 PatchStore

**目的是让你能在浏览器里点着看 L1/L2 跑起来**,验证产品流程,
而不是替代正式接口。接数据库和认证时,这套路由整份删掉即可。

═══════════════════════════════════════════════════════════════════
★ 一处与 AGENTS.md 硬规则的正面冲突(有意为之,已记录)
═══════════════════════════════════════════════════════════════════
硬规则第 10 条:「生成是异步作业。用任务队列(ARQ)。**不要在请求处理函数里
跑生成**,也不要用 `BackgroundTasks`。」

`/generate/stream` 和 `/edit/stream` 用 `StreamingResponse`,**确实是在请求
处理函数里跑生成**。它只解决了那条规则想防的一半问题:

    同步请求 30–120 秒后超时 → 解决了(首字节立刻返回)
    长时间占用 API worker    → 没解决(协程仍挂满整个生成期间)

这是**有意的、有记录的偏离**,理由见设计规格 §13.4。它只允许存在于
`/api/demo/*` 这套内存演示路由里。**若被带进 `/api/` 正式路由,PR 应当被驳回。**
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tempfile
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from app.config import settings
from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.llm.client import ChatClient, build_deepseek_client
from app.llm.ocr import make_ocr
from app.services.agent import AgentStep
from app.services.edit import EditResult, edit_artifact
from app.services.ingest import IngestDeps, SUPPORTED_SUFFIXES, ingest_file
from app.services.patches import (
    InMemoryPatchStore,
    apply_patch,
    artifact_id_of,
    manual_edit,
    reject_patch,
)
from app.services.pipeline import (
    GenerationRequest,
    PipelineDeps,
    PipelineResult,
    ProgressEvent,
    generate_course,
)
from app.services.planner import PlannerRequest, plan_outline
from app.services.course_repository import InMemoryCourseRepository
from app.services.teacher_courses import TeacherCourseService
from app.services.paper import PaperRequest, compose_paper
from app.services.glossary import (
    GlossaryRequest,
    VisualRequest,
    build_glossary,
    describe_visuals,
)
from app.services.questions import QuestionRequest, generate_questions
from app.exporters import exam_paper_to_docx, lesson_plan_to_docx, slide_deck_to_pptx

router = APIRouter(prefix="/demo", tags=["demo"])

#: 假模型每一步的人为延迟(秒)。**只在这个演示路由里用。**
#:
#: 假模型是瞬间跑完的:不延迟的话六段进度条和动作流会在一帧之内全部闪过去,
#: 于是「生成过程看得见」这件事根本没法验收 —— 界面看起来跟没有进度一样。
#: 测试里这个值是 0(`FakeSectionModel()`),所以测试套件不受影响。
FAKE_MODEL_DELAY = 0.6


# ═══════════════════════════════════════════════════════════════
# 进程内存状态。单用户、单次会话 —— 够用来测流程。
# ═══════════════════════════════════════════════════════════════


class _State:
    package: Any = None
    store: InMemoryPatchStore | None = None
    result: Any = None
    model_mode: str = ""


STATE = _State()
COURSE_WORKSPACE = TeacherCourseService(InMemoryCourseRepository())


def reset_course_workspace() -> None:
    """Test hook: reset only the course-first demo state."""
    global COURSE_WORKSPACE
    COURSE_WORKSPACE = TeacherCourseService(InMemoryCourseRepository())


async def _fake_ocr(image_bytes: bytes) -> str:
    """假 OCR —— 让 demo 不需要 key 也能跑通扫描件那条路。"""
    return f"OCR 识别结果(输入图 {len(image_bytes) // 1024} KB):分支隔离改动,主干保持可用。"


def _build_model(
    use_real: bool, role: str = "generate"
) -> tuple[ChatClient, str, Any, str]:
    """选真模型还是假模型。

    只有配了 key 且用户勾选「真实模型」才走真调用 ——
    否则一律假模型,保证 demo 永远能跑。

    `role` 决定用哪个假模型:L1 生成和 L2 编辑的假模型不一样 ——
    **L1 的假模型不认识编辑工具**,拿它跑编辑会得到 0 个 patch。
    """
    if use_real:
        if not settings.deepseek_api_key:
            raise HTTPException(
                status_code=503,
                detail="未配置模型密钥。请在后端 env.yaml 或环境变量中配置 DEEPSEEK_API_KEY。",
            )
        client = build_deepseek_client()
        return (
            client,
            settings.deepseek_model,
            make_ocr(client, settings.deepseek_vision_model),
            "deepseek",
        )

    if role == "edit":
        from app.demo_edit import FakeEditModel

        return FakeEditModel(delay=FAKE_MODEL_DELAY), "fake-edit", _fake_ocr, "fake"

    if role == "questions":
        # 每个流程都要自己的假模型 —— FakeSectionModel 不认识出题的 prompt,
        # 拿它跑出题会直接降级成 0 道题(这个坑真踩过)。
        from app.demo_teacher import FakeQuestionModel

        return FakeQuestionModel(delay=FAKE_MODEL_DELAY), "fake-questions", _fake_ocr, "fake"

    if role == "glossary":
        from app.demo_teacher import FakeGlossaryModel

        return FakeGlossaryModel(delay=FAKE_MODEL_DELAY), "fake-glossary", _fake_ocr, "fake"

    return FakeSectionModel(delay=FAKE_MODEL_DELAY), "fake-model", _fake_ocr, "fake"


# ═══════════════════════════════════════════════════════════════
# 请求体
# ═══════════════════════════════════════════════════════════════


class GenerateBody(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    audience: str = "非计算机专业初学者"
    duration_min: int = Field(default=45, ge=10, le=180)
    objectives: list[str] = Field(default_factory=list)
    material_text: str = ""          # 直接贴一段讲义文本(比上传文件更快)
    use_real_model: bool = False
    #: 教材用什么语言写。与界面语言无关 —— 中文界面完全可以出英文教材。
    language: str = "zh-HK"


class EditBody(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    use_real_model: bool = False


class PatchBody(BaseModel):
    patch_id: str


class QuestionsBody(BaseModel):
    """出题。学习目标取自当前产物的大纲,不用前端再传一遍。"""

    use_real_model: bool = False
    #: 每个学习目标出几道题。
    count_per_objective: int = Field(default=2, ge=1, le=5)
    language: str = "zh-HK"


class PaperBody(BaseModel):
    """组卷。约束都在这。"""

    total_points: int = Field(default=100, gt=0, le=500)
    duration_min: int = Field(default=90, gt=0, le=600)
    #: 必须覆盖的学习目标 id。留空表示不强制。
    coverage: list[str] = Field(default_factory=list)
    easy: float = Field(default=0.0, ge=0, le=1)
    medium: float = Field(default=0.0, ge=0, le=1)
    hard: float = Field(default=0.0, ge=0, le=1)


class GlossaryBody(BaseModel):
    """术语白话化与图片替代文本。"""

    use_real_model: bool = False
    language: str = "zh-HK"


class ManualEditBody(BaseModel):
    """教师手动改内容。**保存即确认**,但仍会留下 patch 记录。"""

    kind: Literal["slide", "timeline"]
    target_id: str
    payload: dict[str, Any]
    note: str = "教师手动修改"


class CourseCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = ""
    audience: str = "非计算机专业初学者"
    duration_min: int = Field(default=45, ge=10, le=180, alias="durationMin")
    language: str = "zh-HK"


class CoursePatchBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    audience: str | None = None
    duration_min: int | None = Field(default=None, ge=10, le=180, alias="durationMin")
    language: str | None = None


class ChapterCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str = ""


class ChapterPatchBody(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = None
    status: Literal["empty", "generating", "draft", "ready", "failed"] | None = None
    package: dict[str, Any] | None = None


class ReorderChaptersBody(BaseModel):
    chapter_ids: list[str] = Field(alias="chapterIds")


class StudentImportBody(BaseModel):
    """A small CSV-shaped roster payload from the teacher workspace."""

    rows: list[dict[str, Any]] = Field(default_factory=list, max_length=200)


def _camel_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {to_camel(str(key)): _camel_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_camel_json(item) for item in value]
    return value


def _course_json(course: Any) -> dict[str, Any]:
    # Keep the parsed syllabus server-side: it is generation context, not UI
    # state.  The UI only needs its filename, parse status and character count.
    payload = dataclasses.asdict(course)
    payload.pop("syllabus_text", None)
    return _camel_json(payload)


def _chapter_json(chapter: Any) -> dict[str, Any]:
    return _camel_json(dataclasses.asdict(chapter))


def _course_or_404(course_id: str) -> Any:
    try:
        return COURSE_WORKSPACE.repository.get_course(course_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="课程不存在") from error


def _chapter_or_404(course_id: str, chapter_id: str) -> Any:
    try:
        return COURSE_WORKSPACE.repository.get_chapter(course_id, chapter_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="章节不存在或不属于该课程") from error


# ═══════════════════════════════════════════════════════════════
# 序列化辅助
# ═══════════════════════════════════════════════════════════════


def _package_json(pkg: Any) -> dict[str, Any] | None:
    return pkg.model_dump(by_alias=True) if pkg is not None else None


def _patch_json(p: Any) -> dict[str, Any]:
    return dataclasses.asdict(p)


def _outline_json(outline: Any) -> dict[str, Any] | None:
    return outline.model_dump(by_alias=True) if outline is not None else None


# ═══════════════════════════════════════════════════════════════
# Course-first teacher workspace.  Legacy singleton endpoints below remain
# temporarily for the existing page while it is migrated to these routes.
# ═══════════════════════════════════════════════════════════════


@router.get("/courses")
async def list_courses() -> dict[str, Any]:
    return {"courses": [_course_json(course) for course in COURSE_WORKSPACE.repository.list_courses()]}


@router.post("/courses", status_code=201)
async def create_course(body: CourseCreateBody) -> dict[str, Any]:
    course = COURSE_WORKSPACE.create_course(
        title=body.title,
        description=body.description,
        audience=body.audience,
        duration_min=body.duration_min,
        language=body.language,
    )
    return _course_json(course)


@router.get("/courses/{course_id}")
async def get_course(course_id: str) -> dict[str, Any]:
    return _course_json(_course_or_404(course_id))


@router.patch("/courses/{course_id}")
async def update_course(course_id: str, body: CoursePatchBody) -> dict[str, Any]:
    _course_or_404(course_id)
    changes = body.model_dump(exclude_none=True)
    try:
        return _course_json(COURSE_WORKSPACE.repository.update_course(course_id, **changes))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/courses/{course_id}/publish")
async def publish_course(course_id: str) -> dict[str, Any]:
    _course_or_404(course_id)
    try:
        return _course_json(COURSE_WORKSPACE.publish(course_id))
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/courses/{course_id}/unpublish")
async def unpublish_course(course_id: str) -> dict[str, Any]:
    _course_or_404(course_id)
    return _course_json(COURSE_WORKSPACE.unpublish(course_id))


@router.post("/courses/{course_id}/syllabus")
async def attach_course_syllabus(course_id: str, request: Request) -> dict[str, Any]:
    """Attach one teacher-owned syllabus and retain its extracted text in memory.

    This demo accepts a raw upload body instead of multipart so it has no
    hidden dependency on ``python-multipart``.  The browser sends the safe
    filename in a header; the file itself is parsed by the existing material
    ingestion pipeline and only the extracted reference text is retained.
    """
    _course_or_404(course_id)
    filename = Path(request.headers.get("x-filename", "syllabus")).name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail="不支持的 syllabus 格式。支持 PDF、PPTX、DOCX、Markdown 和 TXT。",
        )
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=422, detail="上传的 syllabus 是空文件。")
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="syllabus 不能超过 10 MB。")

    with tempfile.TemporaryDirectory(prefix="pathpilot-syllabus-") as directory:
        path = Path(directory) / filename
        path.write_bytes(payload)
        report = await ingest_file(path, deps=IngestDeps(ocr_image=_fake_ocr))

    text = "\n\n".join(chunk.text for chunk in report.chunks).strip()
    if not text:
        raise HTTPException(status_code=422, detail=report.message or "无法从 syllabus 中读取文字。")
    course = COURSE_WORKSPACE.repository.update_course(
        course_id,
        syllabus_filename=filename,
        syllabus_text=text,
        syllabus_status=report.status,
        syllabus_chars=report.extracted_chars,
    )
    return _course_json(course)


@router.post("/courses/{course_id}/students/import")
async def import_students(course_id: str, body: StudentImportBody) -> dict[str, Any]:
    _course_or_404(course_id)
    result = COURSE_WORKSPACE.import_students(course_id, body.rows)
    return {
        "imported": result["imported"],
        "errors": result["errors"],
        "students": [_camel_json(dataclasses.asdict(student)) for student in result["students"]],
    }


@router.post("/courses/{course_id}/invites", status_code=201)
async def create_course_invite(course_id: str) -> dict[str, str]:
    _course_or_404(course_id)
    return {"code": COURSE_WORKSPACE.create_invite(course_id)}


@router.get("/courses/{course_id}/analytics")
async def course_analytics(course_id: str) -> dict[str, Any]:
    _course_or_404(course_id)
    analytics = COURSE_WORKSPACE.analytics(course_id)
    latest_attempts = {item["studentId"]: item for item in analytics["students"]}
    students = []
    for student in COURSE_WORKSPACE.students(course_id):
        payload = _camel_json(dataclasses.asdict(student))
        payload.update(latest_attempts.get(student.id, {"completionPercent": 0, "score": 0}))
        students.append(payload)
    return {
        "enrolledCount": len(students),
        "averageScore": analytics["averageScore"],
        "mostMissed": analytics["mostMissed"],
        "students": students,
    }


@router.post("/courses/{course_id}/chapters", status_code=201)
async def create_chapter(course_id: str, body: ChapterCreateBody) -> dict[str, Any]:
    _course_or_404(course_id)
    try:
        return _chapter_json(COURSE_WORKSPACE.repository.create_chapter(course_id, title=body.title, summary=body.summary))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/courses/{course_id}/chapters/reorder")
async def reorder_chapters(course_id: str, body: ReorderChaptersBody) -> dict[str, Any]:
    _course_or_404(course_id)
    try:
        chapters = COURSE_WORKSPACE.repository.reorder_chapters(course_id, body.chapter_ids)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"chapters": [_chapter_json(chapter) for chapter in chapters]}


@router.get("/courses/{course_id}/chapters/{chapter_id}")
async def get_chapter(course_id: str, chapter_id: str) -> dict[str, Any]:
    return _chapter_json(_chapter_or_404(course_id, chapter_id))


@router.post("/courses/{course_id}/chapters/{chapter_id}/activate")
async def activate_chapter(course_id: str, chapter_id: str) -> dict[str, Any]:
    """Make one selected chapter the legacy tool adapter's active IR package.

    Question generation, paper composition and edit patches are shared IR tools
    during this in-memory migration. Activating first prevents a teacher from
    accidentally applying them to whichever chapter was generated most recently.
    """
    chapter = _chapter_or_404(course_id, chapter_id)
    if chapter.package is None:
        raise HTTPException(status_code=409, detail="先为这个章节生成课件")
    STATE.package = chapter.package
    STATE.store = InMemoryPatchStore()
    return _chapter_json(chapter)


@router.patch("/courses/{course_id}/chapters/{chapter_id}")
async def update_chapter(course_id: str, chapter_id: str, body: ChapterPatchBody) -> dict[str, Any]:
    _chapter_or_404(course_id, chapter_id)
    try:
        return _chapter_json(COURSE_WORKSPACE.repository.update_chapter(course_id, chapter_id, **body.model_dump(exclude_none=True)))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete("/courses/{course_id}/chapters/{chapter_id}", status_code=204)
async def delete_chapter(course_id: str, chapter_id: str) -> None:
    _chapter_or_404(course_id, chapter_id)
    try:
        COURSE_WORKSPACE.repository.delete_chapter(course_id, chapter_id)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


async def _run_chapter_generation(
    course_id: str,
    chapter_id: str,
    body: GenerateBody,
    on_event: Callable[[ProgressEvent], None] | None = None,
) -> tuple[Any, PipelineResult, str]:
    """Run one chapter-owned generation without leaking through the singleton flow."""
    course = _course_or_404(course_id)
    chapter = _chapter_or_404(course_id, chapter_id)
    before = {"package": _package_json(chapter.package), "status": chapter.status}
    COURSE_WORKSPACE.repository.update_chapter(course_id, chapter_id, status="generating")
    try:
        material_text = "\n\n".join(
            part for part in (course.syllabus_text, body.material_text) if part.strip()
        )
        result, mode = await _run_generation(
            body.model_copy(update={"material_text": material_text}),
            on_event=on_event,
        )
    except Exception:
        COURSE_WORKSPACE.repository.update_chapter(course_id, chapter_id, status="failed")
        raise
    chapter = COURSE_WORKSPACE.repository.update_chapter(
        course_id,
        chapter_id,
        package=result.package,
        materials=result.materials,
        status="ready",
    )
    COURSE_WORKSPACE.record_version(
        course_id,
        chapter_id,
        kind="generation",
        reason="AI generated chapter draft",
        changed_fields=["package", "materials", "status"],
        before=before,
        after={"package": _package_json(result.package), "status": "ready"},
    )
    return chapter, result, mode


@router.post("/courses/{course_id}/chapters/{chapter_id}/generate")
async def generate_chapter(course_id: str, chapter_id: str, body: GenerateBody) -> dict[str, Any]:
    """Generate structured draft material into exactly one owned chapter."""
    events: list[dict[str, Any]] = []
    chapter, result, mode = await _run_chapter_generation(
        course_id, chapter_id, body, on_event=_collector(events)
    )
    return {
        "chapter": _chapter_json(chapter),
        **_generation_payload(result, mode, events),
    }


# ═══════════════════════════════════════════════════════════════
# SSE 传输层 —— 设计规格 §13.4
# ═══════════════════════════════════════════════════════════════


def _sse(event: str, data: Any) -> str:
    """拼一帧 SSE。

    `json.dumps` 出来的字符串**不会有裸换行**(会转义成 \\n),
    所以这里可以直接把整段放在一行 `data:` 后面。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _sse_stream(
    request: Request,
    job: Callable[[Callable[[str, Any], None]], Awaitable[Any]],
) -> AsyncIterator[str]:
    """把一个后台协程的进度队列转成 SSE 帧。

    ═══════════════════════════════════════════════════════════════
    为什么要开一个后台 task,而不是直接 await
    ═══════════════════════════════════════════════════════════════
    生成过程中要**边跑边发**。如果直接 `await job()`,`job` 跑完之前
    一个字节都发不出去 —— 那就退化回同步接口了。

    所以:生成跑在 task 里,进度通过队列传出来,这里负责边收边发。

    ═══════════════════════════════════════════════════════════════
    三条约束(§13.4)
    ═══════════════════════════════════════════════════════════════
    1. `result` 至多一次,且必在 `done` 之前;中途出错发 `error`。
    2. 与同步端点产出**逐字段相同**的结果 —— 靠两条路共用一个 payload 构造函数保证。
    3. **客户端断开即取消** —— 不留还在烧 token 的孤儿协程。
    """
    queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()

    async def runner() -> Any:
        try:
            return await job(lambda name, data: queue.put_nowait((name, data)))
        finally:
            # 哨兵:告诉消费者「生产者已经结束了」。
            # 放在 finally 里,所以**出错也会发** —— 否则消费者会一直等下去。
            queue.put_nowait(None)

    task = asyncio.create_task(runner())

    try:
        while True:
            # 约束 3:断开就停。否则教师关掉页面,后端还在烧 token。
            if await request.is_disconnected():
                return

            getter: asyncio.Future[tuple[str, Any] | None] = asyncio.ensure_future(
                queue.get()
            )
            done, _ = await asyncio.wait(
                {getter, task}, return_when=asyncio.FIRST_COMPLETED
            )

            if getter in done:
                item = getter.result()
                if item is None:      # 哨兵 —— 生成结束
                    break
                yield _sse(item[0], item[1])
                continue

            # 生成结束了,但队列里可能还有没发完的进度
            getter.cancel()
            while not queue.empty():
                leftover = queue.get_nowait()
                if leftover is not None:
                    yield _sse(leftover[0], leftover[1])
            break

        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            # 结构见 §13.1
            yield _sse("error", {
                "error": {
                    "code": type(error).__name__,
                    "message": str(error)[:300],
                    "retryable": False,
                }
            })
            return
        yield _sse("result", task.result())
        yield _sse("done", {"ok": True})
    finally:
        if not task.done():
            task.cancel()


def _sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    """包一层 SSE 响应。禁用中间层缓冲,否则帧会攒着一起发。"""
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx 之类的反代会缓冲 SSE,加这个才真的流式
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════
# 生成:同步与流式**共用同一个实现**
# ═══════════════════════════════════════════════════════════════


async def _run_generation(
    body: GenerateBody,
    on_event: Callable[[ProgressEvent], None] | None = None,
) -> tuple[PipelineResult, str]:
    """跑一次 L1,并更新进程内状态。

    ═══════════════════════════════════════════════════════════════
    为什么两条路必须共用这一个函数
    ═══════════════════════════════════════════════════════════════
    §13.4 的约束 2:流式端点与同步端点对同一输入必须产出逐字段相同的包。
    最省事的保证方式不是「写两遍然后祈祷」,而是**只有一份实现**。
    """
    client, model, ocr, mode = _build_model(body.use_real_model)

    material_paths: list[Any] = []
    if body.material_text.strip():
        import tempfile
        from pathlib import Path

        path = Path(tempfile.mkdtemp()) / "教师讲义.md"
        path.write_text(body.material_text, encoding="utf-8")
        material_paths.append(path)

    result = await generate_course(
        GenerationRequest(
            topic=body.topic,
            audience=body.audience,
            duration_min=body.duration_min,
            objectives=body.objectives,
            language=body.language,
            material_paths=material_paths,
        ),
        PipelineDeps(
            client=client,
            model=model,
            search_materials=fake_search,
            make_diagram=fake_make_diagram,
            request_illustration=fake_illustration,
            section_concurrency=3,
            ingest_deps=IngestDeps(ocr_image=ocr),
        ),
        on_event=on_event,
    )

    STATE.package = result.package
    STATE.store = InMemoryPatchStore()
    STATE.result = result
    STATE.model_mode = mode
    return result, mode


def _generation_payload(result: PipelineResult, mode: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """组装生成结果。**同步与流式两条路都走这里** —— 这是约束 2 的落点。"""
    return {
        "model_mode": mode,
        "events": events,
        "materials": [dataclasses.asdict(m) for m in result.materials],
        "outline": _outline_json(result.outline),
        "package": _package_json(result.package),
        "integrity_issues": result.integrity_issues,
        "agents": [
            {
                "call_names": a.call_names,
                "turns": a.turns,
                "stopped_by": a.stopped_by,
                "errors": [c.error for c in a.calls if c.error],
            }
            for a in result.agents
        ],
    }


def _collector(events: list[dict[str, Any]]) -> Callable[[ProgressEvent], None]:
    """把事件收进列表 —— 同步端点用。"""
    def sink(ev: ProgressEvent) -> None:
        events.append(ev.to_dict())

    return sink


# ═══════════════════════════════════════════════════════════════
# 接口
# ═══════════════════════════════════════════════════════════════


@router.post("/outline")
async def preview_outline(body: GenerateBody) -> dict[str, Any]:
    """只跑阶段 2:看看模型会给出什么章节骨架。**不生成内容,几秒就回。**"""
    client, model, _, mode = _build_model(body.use_real_model)
    outline = await plan_outline(
        PlannerRequest(
            topic=body.topic,
            audience=body.audience,
            duration_min=body.duration_min,
            requested_objectives=body.objectives,
            language=body.language,
        ),
        client=client,
        model=model,
    )
    return {"model_mode": mode, "outline": _outline_json(outline)}


@router.post("/generate")
async def generate(body: GenerateBody) -> dict[str, Any]:
    """跑完整 L1。**同步返回** —— 会卡几秒,看不到过程。

    要看见过程请用 `POST /api/demo/generate/stream`。
    这个端点保留是为了向后兼容(以及给不想处理 SSE 的调用方用)。
    """
    events: list[dict[str, Any]] = []
    result, mode = await _run_generation(body, on_event=_collector(events))
    return _generation_payload(result, mode, events)


@router.post("/generate/stream")
async def generate_stream(body: GenerateBody, request: Request) -> StreamingResponse:
    """跑完整 L1,**边跑边推进度**(SSE)—— 设计规格 §13.4。

    事件名:`progress` / `result` / `error` / `done`;
    `progress` 的子类型看 `data.kind`(§6.1.1)。

    ⚠️ 这是在请求处理函数里跑生成,与 AGENTS.md 硬规则冲突。
    偏离的理由和边界见本模块的文档字符串。
    """
    async def job(emit: Callable[[str, Any], None]) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def on_event(ev: ProgressEvent) -> None:
            events.append(ev.to_dict())
            emit("progress", ev.to_dict())

        result, mode = await _run_generation(body, on_event=on_event)
        # 最终结果里带上完整事件列表,和同步端点保持一致
        return _generation_payload(result, mode, events)

    return _sse_response(_sse_stream(request, job))


@router.post("/courses/{course_id}/chapters/{chapter_id}/generate/stream")
async def generate_chapter_stream(
    course_id: str,
    chapter_id: str,
    body: GenerateBody,
    request: Request,
) -> StreamingResponse:
    """Stream a generation job while keeping its result owned by one chapter."""
    # Report a bad course/chapter immediately, rather than opening a stream
    # that only later produces an error frame.
    _chapter_or_404(course_id, chapter_id)

    async def job(emit: Callable[[str, Any], None]) -> dict[str, Any]:
        events: list[dict[str, Any]] = []

        def on_event(event: ProgressEvent) -> None:
            payload = event.to_dict()
            events.append(payload)
            emit("progress", payload)

        chapter, result, mode = await _run_chapter_generation(
            course_id, chapter_id, body, on_event=on_event
        )
        return {
            "chapter": _chapter_json(chapter),
            **_generation_payload(result, mode, events),
        }

    return _sse_response(_sse_stream(request, job))


def _edit_payload(result: EditResult, mode: str) -> dict[str, Any]:
    """组装 L2 结果。**同步与流式两条路都走这里**(§13.4 约束 2)。"""
    return {
        "model_mode": mode,
        "reply": result.reply,
        "call_names": result.call_names,
        "patches": [_patch_json(p) for p in result.proposed],
        # 让前端能自己确认「产物确实没变」
        "package": _package_json(STATE.package),
    }


async def _run_edit(
    body: EditBody,
    on_step: Callable[[AgentStep], None] | None = None,
) -> tuple[EditResult, str]:
    """跑一次 L2。同样只有一份实现,两条传输共用。"""
    if STATE.package is None or STATE.store is None:
        raise HTTPException(status_code=409, detail="先点「生成」")

    client, model, _, mode = _build_model(body.use_real_model, "edit")
    result = await edit_artifact(
        client=client,
        model=model,
        package=STATE.package,
        message=body.message,
        store=STATE.store,
        on_step=on_step,
    )
    return result, mode


@router.post("/edit")
async def edit(body: EditBody) -> dict[str, Any]:
    """跑 L2:让 agent 提议改动。**产物不变**,只产生待确认的 patch。"""
    result, mode = await _run_edit(body)
    return _edit_payload(result, mode)


@router.post("/edit/stream")
async def edit_stream(body: EditBody, request: Request) -> StreamingResponse:
    """跑 L2,**边跑边推 agent 的每一步**(SSE)。

    L2 比 L1 更值得看过程:教师能看见 agent 先读了哪一页、为什么这么改。
    """
    # 先做一次前置检查,这样「还没生成」能立刻返回 409,
    # 而不是开了一个流再在里面报错 —— 前端处理 409 比处理流内 error 简单。
    if STATE.package is None or STATE.store is None:
        raise HTTPException(status_code=409, detail="先点「生成」")

    async def job(emit: Callable[[str, Any], None]) -> dict[str, Any]:
        def on_step(step: AgentStep) -> None:
            # L2 的进度不是百分比,是「第几轮 · 调了什么工具」。
            # 形状故意与 L1 的 progress 帧保持一致(kind / tool / detail),
            # 这样前端只用一套渲染逻辑。
            emit("progress", {
                "kind": "tool" if step.kind.startswith("tool") else step.kind,
                "tool": step.tool,
                "status": step.status,
                "detail": step.summary,
                "turn": step.turn,
            })

        result, mode = await _run_edit(body, on_step=on_step)
        return _edit_payload(result, mode)

    return _sse_response(_sse_stream(request, job))


@router.post("/apply")
async def apply(body: PatchBody) -> dict[str, Any]:
    """教师确认。**这是唯一真正改产物的入口。**"""
    if STATE.package is None or STATE.store is None:
        raise HTTPException(status_code=409, detail="先点「生成」")
    try:
        apply_patch(STATE.package, STATE.store, body.patch_id)
    except (KeyError, Exception) as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"package": _package_json(STATE.package)}


@router.post("/reject")
async def reject(body: PatchBody) -> dict[str, Any]:
    """驳回。产物本来就没动过,只需改 patch 状态。"""
    if STATE.store is None:
        raise HTTPException(status_code=409, detail="先点「生成」")
    reject_patch(STATE.store, body.patch_id)
    return {"package": _package_json(STATE.package)}


@router.post("/manual-edit")
async def manual(body: ManualEditBody) -> dict[str, Any]:
    """教师**直接改内容** —— 不走 AI,但仍走 patch 机制。

    ═══════════════════════════════════════════════════════════════
    为什么手动改还要走 patch
    ═══════════════════════════════════════════════════════════════
    如果它直接写产物,`apply_patch()` 就不再是唯一能改产物的函数 ——
    所有断言这条不变式的测试和文档立刻变成假话,而且改动没有记录、
    没法撤销。

    所以这里生成一条 `author="teacher"` 的 patch 并**立刻 apply**:
    教师点「保存」就是确认,不用再点一次。对用户是一次点击,
    对系统产物仍然只被 `apply_patch()` 改过。
    """
    if STATE.package is None or STATE.store is None:
        raise HTTPException(status_code=409, detail="先点「生成」")

    try:
        patch, _ = manual_edit(
            STATE.package,
            STATE.store,
            kind=body.kind,
            target_id=body.target_id,
            payload=body.payload,
            note=body.note,
        )
    except ValueError as exc:                       # 没有字段变化
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:                         # 找不到目标
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:                        # 校验没过
        raise HTTPException(
            status_code=400, detail=f"改动不合规:{exc}"
        ) from exc

    return {
        "patch": _patch_json(patch),
        "package": _package_json(STATE.package),
    }


# ===============================================================
# 教师端的四个增量:出题 / 组卷 / 白话化 / 导出
#
# 这几个端点**直接写产物**,和 `/generate` 是同一类 ——
# 「生成一个新产物」,不是「修改已有内容」。
#
# 那条不变式(未确认的 patch 不得改变产物 / apply_patch 是唯一的写路径)
# 管的是**对已有内容的改动**。出题、组卷、生成术语表都是产出新东西,
# 和 L1 生成课件同一性质。教师想改某一页的内容,仍然只能走 patch。
# ===============================================================


def _require_package() -> Any:
    if STATE.package is None:
        raise HTTPException(status_code=409, detail="先点「生成」")
    return STATE.package


def _deck_context(package: Any) -> str:
    """把课件正文拼成一段文字,给出题和术语表当依据。

    关键:**出题不能凭空出。** 题目该考的是这份课件讲过的东西,
    所以上下文直接取已生成的课件 —— 教师改完课件再出题,题目跟着变。
    """
    deck = package.slide_deck
    if deck is None:
        return ""
    lines: list[str] = []
    for slide in deck.slides:
        lines.append(f"# {slide.title}")
        lines.extend(f"- {b}" for b in slide.bullets)
        if slide.speaker_notes:
            lines.append(slide.speaker_notes)
    return "\n".join(lines)


@router.post("/questions")
async def make_questions(body: QuestionsBody) -> dict[str, Any]:
    """按大纲里的学习目标出题,结果挂到产物上。"""
    package = _require_package()
    client, model, _, mode = _build_model(body.use_real_model, "questions")

    result = await generate_questions(
        QuestionRequest(
            objectives=list(package.project.learning_objectives),
            audience=package.project.meta.audience,
            language=body.language,
            count_per_objective=body.count_per_objective,
            material_context=_deck_context(package),
        ),
        client=client,
        model=model,
    )

    package.question_set = result.question_set
    # 换了题库之后旧卷子必然对不上(§6.4 会报「引用了不存在的题目」)
    package.exam_paper = None

    return {
        "model_mode": mode,
        "question_set": _package_json(result.question_set),
        "used_fallback": result.used_fallback,
        "reason": result.reason,
        "package": _package_json(package),
    }


@router.post("/paper")
async def make_paper(body: PaperBody) -> dict[str, Any]:
    """按约束从题库组卷。**纯算法,不调用模型。**"""
    package = _require_package()
    if package.question_set is None or not package.question_set.questions:
        raise HTTPException(status_code=409, detail="先出题,题库还是空的")

    from app.schemas.ir import ExamConstraints, PaperDifficulty

    coverage = body.coverage or [o.id for o in package.project.learning_objectives]
    result = compose_paper(
        PaperRequest(
            question_set=package.question_set,
            constraints=ExamConstraints(
                total_points=body.total_points,
                duration_min=body.duration_min,
                coverage=coverage,
                difficulty=PaperDifficulty(
                    easy=body.easy, medium=body.medium, hard=body.hard
                ),
            ),
        )
    )

    package.exam_paper = result.paper

    return {
        "ok": result.ok,
        "reason": result.reason,
        "actual_points": result.actual_points,
        "missing": sorted(result.missing),
        "actual_difficulty": result.actual_difficulty.model_dump(),
        "paper": _package_json(result.paper),
        "package": _package_json(package),
    }


@router.post("/glossary")
async def make_glossary(body: GlossaryBody) -> dict[str, Any]:
    """生成术语白话解释,并给每张已渲染的图配替代文本。"""
    package = _require_package()
    client, model, _, mode = _build_model(body.use_real_model, "glossary")

    glossary_result = await build_glossary(
        GlossaryRequest(
            content=_deck_context(package),
            objectives=list(package.project.learning_objectives),
            language=body.language,
        ),
        client=client,
        model=model,
    )

    visuals = [
        visual
        for slide in (package.slide_deck.slides if package.slide_deck else [])
        for visual in slide.visuals
    ]
    alt_result = await describe_visuals(
        VisualRequest(visuals=visuals, language=body.language),
        client=client,
        model=model,
    )

    package.project.glossary = glossary_result.glossary
    for asset in package.assets:
        if asset.id in alt_result.alt_texts:
            asset.alt_text = alt_result.alt_texts[asset.id]

    return {
        "model_mode": mode,
        "glossary": [g.model_dump(by_alias=True) for g in glossary_result.glossary],
        "alt_texts": alt_result.alt_texts,
        "used_fallback": glossary_result.used_fallback or alt_result.used_fallback,
        "reason": ";".join(r for r in (glossary_result.reason, alt_result.reason) if r),
        "package": _package_json(package),
    }


def _attachment(data: bytes, filename: str, media_type: str) -> Response:
    """下载响应。

    中文文件名要用 RFC 5987 的 `filename*=UTF-8''...` 形式,
    只写 `filename=` 的话 Chrome 会给出乱码文件名。
    """
    from urllib.parse import quote

    disposition = (
        f'attachment; filename="course-export"'
        f"; filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


_DOCX_MEDIA = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_PPTX_MEDIA = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


@router.get("/export/deck.pptx")
async def export_deck() -> Response:
    """课件导出成 pptx。**纯转换,不调用模型。**"""
    package = _require_package()
    if package.slide_deck is None:
        raise HTTPException(status_code=409, detail="还没有课件")
    data = slide_deck_to_pptx(package.project, package.slide_deck)
    return _attachment(data, f"{package.project.meta.title}.pptx", _PPTX_MEDIA)


@router.get("/export/lesson-plan.docx")
async def export_lesson_plan() -> Response:
    """教案导出成 docx。"""
    package = _require_package()
    if package.lesson_plan is None:
        raise HTTPException(status_code=409, detail="还没有教案")
    data = lesson_plan_to_docx(package.project, package.lesson_plan)
    return _attachment(data, f"{package.project.meta.title}-教案.docx", _DOCX_MEDIA)


@router.get("/export/exam-paper.docx")
async def export_exam_paper(answers: bool = True) -> Response:
    """考卷导出成 docx。`?answers=false` 得到学生版(不含答案与解析)。"""
    package = _require_package()
    if package.exam_paper is None or package.question_set is None:
        raise HTTPException(status_code=409, detail="先出题并组卷")
    data = exam_paper_to_docx(
        package.project,
        package.question_set,
        package.exam_paper,
        include_answer_key=answers,
    )
    suffix = "教师版" if answers else "学生版"
    return _attachment(
        data, f"{package.project.meta.title}-试卷-{suffix}.docx", _DOCX_MEDIA
    )


@router.get("/state")
async def state() -> dict[str, Any]:
    """当前状态。刷新页面后前端用它恢复。"""
    if STATE.package is None:
        return {"has_package": False}
    return {
        "has_package": True,
        "model_mode": STATE.model_mode,
        "package": _package_json(STATE.package),
        # 交叉引用校验结果也要给 —— 不然刷新之后那条「校验通过」的横条会消失,
        # 界面和刚生成时不一致。教师会以为是自己改坏了什么。
        "integrity_issues": STATE.package.validate_integrity(),
        # 全部历史,不只是待确认的 —— 教师改了什么也要看得见(可审计)
        "patches": [
            _patch_json(p) for p in STATE.store.list(artifact_id_of(STATE.package))  # type: ignore[union-attr]
        ],
    }


@router.post("/reset")
async def reset() -> dict[str, str]:
    """清空状态,从头再测一次。"""
    STATE.package = None
    STATE.store = None
    STATE.result = None
    return {"status": "cleared"}
