"""教师端四个增量的接口测试 —— 出题 / 组卷 / 白话化 / 导出。

═══════════════════════════════════════════════════════════════════
这组测试和单元测试的分工
═══════════════════════════════════════════════════════════════════
`test_questions.py` / `test_paper.py` / `test_exporters.py` / `test_glossary.py`
测的是**服务层本身**,喂的是构造好的输入。

这个文件测的是**接线**:接口有没有把参数传对、有没有把结果挂到产物上、
导出的下载响应头对不对。这类 bug 服务层测试一条都抓不到 ——
服务层全绿而接口传错参数,是最常见的一种。

═══════════════════════════════════════════════════════════════════
为什么用假模型
═══════════════════════════════════════════════════════════════════
`use_real_model: false` 会走到 `app/demo_teacher.py` 的假模型。
它们从 prompt 里 parse 学习目标(而不是写死返回值),所以
「目标 id 没传下去」这类 bug 在这里也会暴露。

但**假模型本身也需要测试** —— 它坏了的话,离线 demo 会静默降级成空结果。
文件末尾那几条测的就是它。
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.api.routes import demo
from app.main import app

GENERATE_BODY = {
    "topic": "Git 分支管理",
    "audience": "非计算机专业初学者",
    "duration_min": 45,
    "objectives": [],
    "material_text": "",
    "use_real_model": False,
    "language": "zh-HK",
}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch):
    """每个测试都从干净状态开始,并把演示延迟归零。"""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.result = None
    yield
    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.result = None


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _post(path: str, body: dict | None = None):
    async with _client() as client:
        return await client.post(path, json=body or {})


async def _get(path: str):
    async with _client() as client:
        return await client.get(path)


async def _generated():
    """先跑一次 L1 —— 后面所有端点都要有产物才能用。"""
    response = await _post("/api/demo/generate", GENERATE_BODY)
    assert response.status_code == 200, response.text
    return response.json()


# ═══════════════════════════════════════════════════════════════
# 前置条件:没有产物时必须 409,而不是 500
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "path",
    ["/api/demo/questions", "/api/demo/paper", "/api/demo/glossary"],
)
async def test_endpoints_require_a_package_first(path: str):
    """还没生成就来用这些端点 → 409 加一句人话。

    500 的话前端只能显示「服务器错误」,而真正的原因是「你还没生成」。
    """
    response = await _post(path)

    assert response.status_code == 409
    assert "生成" in response.json()["detail"]


async def test_paper_requires_questions_first():
    """组卷要有题库 —— 没有的话说清楚缺哪一步。"""
    await _generated()
    response = await _post("/api/demo/paper", {"total_points": 20})

    assert response.status_code == 409
    assert "出题" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════
# 出题
# ═══════════════════════════════════════════════════════════════


async def test_questions_endpoint_returns_a_question_set():
    await _generated()
    response = await _post(
        "/api/demo/questions",
        {"use_real_model": False, "count_per_objective": 2, "language": "zh-HK"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_fallback"] is False
    assert len(body["question_set"]["questions"]) >= 2


async def test_questions_cover_the_objectives_from_the_outline():
    """出题的输入必须是**大纲里的**学习目标,不是接口另传一套。

    这是接线最容易错的地方:服务层测试喂的是构造好的目标,
    接口要是传错了(比如传空列表),服务层测试照样全绿。
    """
    generated = await _generated()
    objective_ids = {
        o["id"] for o in generated["package"]["project"]["learningObjectives"]
    }

    response = await _post("/api/demo/questions", {"use_real_model": False})
    questions = response.json()["question_set"]["questions"]
    covered = {oid for q in questions for oid in q.get("objectiveIds", [])}

    assert covered == objective_ids, f"覆盖 {covered},大纲是 {objective_ids}"


async def test_questions_are_attached_to_the_package():
    """出完题要挂到产物上 —— 不挂的话前端拿不到,后面组卷也用不了。"""
    await _generated()
    response = await _post("/api/demo/questions", {"use_real_model": False})

    package = response.json()["package"]
    assert package["questionSet"] is not None
    assert package["questionSet"]["questions"]


async def test_regenerating_questions_clears_the_stale_paper():
    """换了题库,旧卷子必然对不上 —— 留着会让 §6.4 报「引用了不存在的题目」。

    主动清掉比留一个坏卷子好:教师看到「还没组卷」是清楚的,
    看到一个报错的卷子则要自己去猜为什么。
    """
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False})
    await _post("/api/demo/paper", {"total_points": 20})

    again = await _post("/api/demo/questions", {"use_real_model": False})

    assert again.json()["package"]["examPaper"] is None


async def test_the_count_per_objective_reaches_the_model():
    """接口上的数要真的传下去。"""
    await _generated()
    body = {"use_real_model": False, "count_per_objective": 1}
    few = await _post("/api/demo/questions", body)
    body["count_per_objective"] = 3
    many = await _post("/api/demo/questions", body)

    assert len(many.json()["question_set"]["questions"]) > len(
        few.json()["question_set"]["questions"]
    )


# ═══════════════════════════════════════════════════════════════
# 组卷
# ═══════════════════════════════════════════════════════════════


async def test_the_paper_endpoint_hits_the_exact_total():
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False, "count_per_objective": 3})

    response = await _post(
        "/api/demo/paper", {"total_points": 20, "duration_min": 30, "coverage": []}
    )

    body = response.json()
    assert response.status_code == 200
    if body["ok"]:
        assert body["actual_points"] == 20


async def test_the_paper_is_attached_to_the_package():
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False, "count_per_objective": 3})
    response = await _post("/api/demo/paper", {"total_points": 20, "coverage": []})

    package = response.json()["package"]
    assert package["examPaper"] is not None


async def test_an_unreachable_total_is_reported_with_ok_false():
    """凑不出的总分要如实说 —— 前端据此显示提示而不是假装成功。"""
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False, "count_per_objective": 1})

    response = await _post(
        "/api/demo/paper", {"total_points": 3, "duration_min": 30, "coverage": []}
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["reason"]


async def test_a_successful_paper_passes_the_package_integrity_check():
    """最终验收:组完卷之后整包必须过 §6.4 的交叉引用校验。"""
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False, "count_per_objective": 3})
    await _post("/api/demo/paper", {"total_points": 20, "duration_min": 30, "coverage": []})

    state = (await _get("/api/demo/state")).json()
    package = state["package"]

    # 卷子里引用的题必须都在题库里
    bank = {q["id"] for q in package["questionSet"]["questions"]}
    referenced = {
        qid for section in package["examPaper"]["sections"] for qid in section["questionIds"]
    }
    assert referenced <= bank


# ═══════════════════════════════════════════════════════════════
# 术语白话化与无障碍
# ═══════════════════════════════════════════════════════════════


async def test_the_glossary_endpoint_returns_terms_and_alt_texts():
    await _generated()
    response = await _post("/api/demo/glossary", {"use_real_model": False})

    body = response.json()
    assert response.status_code == 200
    assert body["glossary"]
    assert isinstance(body["alt_texts"], dict)


async def test_the_glossary_is_attached_to_the_project():
    await _generated()
    response = await _post("/api/demo/glossary", {"use_real_model": False})

    package = response.json()["package"]
    assert package["project"]["glossary"]


async def test_alt_text_lands_on_the_assets():
    """替代文本要写进资产里,不是只回一个映射 —— 否则导出和读屏都用不上。"""
    await _generated()
    response = await _post("/api/demo/glossary", {"use_real_model": False})

    package = response.json()["package"]
    assets = package["assets"]
    assert assets, "没有资产,这条测不了"
    assert all(a.get("altText") for a in assets), "有资产没拿到替代文本"


async def test_a_generated_diagram_is_available_as_a_safe_svg_asset():
    """课件画布不应展示 Mermaid 源码; 它应拿到可直接显示的确定性 SVG。"""
    generated = await _generated()
    asset = next(a for a in generated["package"]["assets"] if a["kind"] == "diagram")

    response = await _get(f"/api/demo/assets/{asset['id']}.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert 'data-template="' in response.text
    assert "<script>" not in response.text


# ═══════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("path", "prefix"),
    [
        ("/api/demo/export/deck.pptx", b"PK\x03\x04"),
        ("/api/demo/export/lesson-plan.docx", b"PK\x03\x04"),
    ],
)
async def test_exports_download_as_real_office_files(path: str, prefix: bytes):
    await _generated()
    response = await _get(path)

    assert response.status_code == 200
    assert response.content[:4] == prefix, "不是合法的 Office 文件"
    assert "attachment" in response.headers["content-disposition"]


async def test_the_download_filename_is_utf8_encoded():
    """中文文件名只写 filename= 的话 Chrome 会给出乱码。

    要按 RFC 5987 再给一个 `filename*=UTF-8''...`。
    """
    await _generated()
    response = await _get("/api/demo/export/deck.pptx")

    disposition = response.headers["content-disposition"]
    assert "filename*=UTF-8''" in disposition


async def test_the_exam_paper_export_needs_both_steps():
    """没出题就导出考卷 → 409,并说清缺哪一步。"""
    await _generated()
    response = await _get("/api/demo/export/exam-paper.docx")

    assert response.status_code == 409
    assert "出题" in response.json()["detail"]


async def test_the_student_version_leaves_out_the_answers():
    """学生版不能带解析 —— 这是这个开关存在的唯一理由。"""
    await _generated()
    await _post("/api/demo/questions", {"use_real_model": False})
    await _post("/api/demo/paper", {"total_points": 20, "coverage": []})

    teacher = await _get("/api/demo/export/exam-paper.docx?answers=true")
    student = await _get("/api/demo/export/exam-paper.docx?answers=false")

    from io import BytesIO

    from docx import Document

    def text_of(data: bytes) -> str:
        doc = Document(BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    assert "参考答案" in text_of(teacher.content)
    assert "参考答案" not in text_of(student.content)


# ═══════════════════════════════════════════════════════════════
# 假模型本身也要测
#
# 它坏了的话,离线 demo 会**静默降级成空结果** —— 教师看到的是
# 「一道题都没出出来」,而真正的原因在这里。
# ═══════════════════════════════════════════════════════════════


async def test_the_fake_question_model_reads_the_objectives_from_the_prompt():
    """假模型是从 prompt 里 parse 目标的,不是写死返回值。

    写死的话,「目标 id 没传下去」这类 bug 在离线 demo 里永远看不见。
    """
    from app.demo_teacher import FakeQuestionModel

    prompt = (
        "学习者:初学者\n每个学习目标出 2 道题。\n"
        "**题干、选项和解析全部用 zh-HK 书写。**\n\n"
        "要覆盖的学习目标:\n  LO7  某个目标\n  LO9  另一个目标"
    )
    reply = await FakeQuestionModel().complete(
        model="fake",
        messages=[
            {"role": "system", "content": "你在为一份软件工程迷你课程出题"},
            {"role": "user", "content": prompt},
        ],
    )

    payload = json.loads(reply.content)
    covered = {o for q in payload["questions"] for o in q["objectiveIds"]}
    assert covered == {"LO7", "LO9"}
    assert len(payload["questions"]) == 4


async def test_the_fake_glossary_model_answers_the_asset_ids_it_was_given():
    from app.demo_teacher import FakeGlossaryModel

    prompt = (
        "**全部用 zh-HK 书写。**\n\n需要描述的图:\n"
        "  assetId=as-aaa  kind=diagram  内容:graph LR\n"
        "  assetId=as-bbb  kind=diagram  内容:graph TD"
    )
    reply = await FakeGlossaryModel().complete(
        model="fake",
        messages=[
            {"role": "system", "content": "你在为课程材料里的图写替代文本"},
            {"role": "user", "content": prompt},
        ],
    )

    ids = {d["assetId"] for d in json.loads(reply.content)["descriptions"]}
    assert ids == {"as-aaa", "as-bbb"}


async def test_the_fake_glossary_model_tells_the_two_prompts_apart():
    """同一个假模型要同时应付术语表和替代文本两段 prompt。"""
    from app.demo_teacher import FakeGlossaryModel

    model = FakeGlossaryModel()
    glossary = await model.complete(
        model="fake",
        messages=[
            {"role": "system", "content": "你在替一份课程材料做术语表"},
            {"role": "user", "content": "**全部用 zh-HK 书写。**"},
        ],
    )
    assert "glossary" in json.loads(glossary.content)
