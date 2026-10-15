"""SSE 进度流 —— 设计规格 §13.4。

═══════════════════════════════════════════════════════════════════
这组测试守的三条
═══════════════════════════════════════════════════════════════════
1. **事件顺序**:`result` 至多一次、必在 `done` 之前;出错发 `error`。
   顺序错了前端就会卡在「生成中」永远不出来。

2. **传输等价**(最重要)。同一个输入,流式端点和同步端点产出的 `package`
   必须逐字段相同。这不是杞人忧天:两条路要分别组装响应、分别跑一遍流水线,
   任何一处分支写歪了都会让「预览看到的」和「流式拿到的」不一样,
   而且**只会在教师真的用那条路时才发现**。

   这里的做法不是「写两遍再祈祷」,而是让两条路共用 `_run_generation` 和
   `_generation_payload` —— 这个测试守的就是「别哪天有人把它们拆开」。

3. **思考流只在流式上有意义**。同步响应里塞上千个 chunk 只会把包撑大。

═══════════════════════════════════════════════════════════════════
为什么用 ASGITransport 而不是起服务器
═══════════════════════════════════════════════════════════════════
起真服务器测不出「两条传输是否等价」—— 它只能测一条。
`httpx.ASGITransport` 能直接调 app,而且支持流式读取响应体。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.api.routes import demo
from app.main import app

PAYLOAD: dict[str, Any] = {
    "topic": "Git 分支管理",
    "audience": "非计算机专业初学者",
    "duration_min": 45,
    "objectives": ["解释分支与主干的关系"],
    "material_text": "",
    "use_real_model": False,     # ← 假模型,不花钱、可复现
    "language": "zh-HK",
}


def _frames(text: str) -> list[tuple[str, Any]]:
    """把 SSE 文本拆成 (事件名, 数据) 列表。"""
    out: list[tuple[str, Any]] = []
    for block in text.split("\n\n"):
        name = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if name is not None:
            out.append((name, data))
    return out


async def _stream(body: dict[str, Any], path: str = "/api/demo/generate/stream") -> list[tuple[str, Any]]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("POST", path, json=body) as resp:
            assert resp.status_code == 200, resp.status_code
            assert resp.headers["content-type"].startswith("text/event-stream")
            text = "".join([chunk async for chunk in resp.aiter_text()])
    return _frames(text)


async def _sync(body: dict[str, Any], path: str = "/api/demo/generate") -> dict[str, Any]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(path, json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch):
    """每个测试都从干净状态开始 —— demo 路由的状态是进程级全局的。

    同时把**演示用**的假模型延迟归零。那个延迟是为了让人在浏览器里
    看得见进度(假模型本来是瞬间跑完的),但它会让每次生成多花约两秒,
    14 个测试叠起来就是半分钟 —— 没人愿意跑那种套件。
    """
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.result = None
    yield
    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.result = None


# ═══════════════════════════════════════════════════════════════
# 1. 帧的顺序与形状
# ═══════════════════════════════════════════════════════════════


async def test_stream_ends_with_result_then_done():
    frames = await _stream(PAYLOAD)
    names = [n for n, _ in frames]

    assert names[-2:] == ["result", "done"], f"结尾不对:{names[-4:]}"
    assert names.count("result") == 1
    assert names.count("done") == 1
    assert "error" not in names


async def test_progress_frames_come_before_the_result():
    """进度必须在结果之前 —— 否则它就不是进度了。"""
    frames = await _stream(PAYLOAD)
    names = [n for n, _ in frames]

    assert "progress" in names, "一帧进度都没有,前端只能干等"
    assert names.index("progress") < names.index("result")


async def test_progress_frames_carry_the_structured_fields():
    frames = await _stream(PAYLOAD)
    progress = [d for n, d in frames if n == "progress"]

    for frame in progress:
        assert set(frame) >= {
            "phase", "percent", "kind", "sectionIndex", "sectionTitle",
            "slideCount", "tool", "status",
        }, f"进度帧缺字段:{sorted(frame)}"


async def test_percent_in_the_stream_never_goes_backwards():
    """前端据此画进度条。倒退就会抽搐。"""
    frames = await _stream(PAYLOAD)
    percents = [d["percent"] for n, d in frames if n == "progress"]

    assert percents == sorted(percents), f"流里的进度倒退了:{percents}"


async def test_the_stream_reports_slide_count_reaching_the_real_deck_size():
    """「现在写到第几张 ppt」必须是流里能读到的,不能等结果。"""
    frames = await _stream(PAYLOAD)
    progress = [d for n, d in frames if n == "progress"]
    result = next(d for n, d in frames if n == "result")

    real = len(result["package"]["slideDeck"]["slides"])
    assert progress[-1]["slideCount"] == real
    assert any(d["kind"] == "slide" for d in progress), "一条 slide 事件都没有"


async def test_no_reasoning_frames_ever():
    """思考流这条路径整条删掉了 —— 流里不该再有它的位置。

    它曾经占掉一次生成约 35% 的帧(实测 67 帧里 24 帧)。撤掉界面之后
    模型层的流式分支跟着删了,这条守的就是「别哪天又长回来一半」。
    """
    frames = await _stream(PAYLOAD)
    progress = [d for n, d in frames if n == "progress"]
    result = next(d for n, d in frames if n == "result")

    assert all(d["kind"] != "reasoning" for d in progress)
    assert all(e["kind"] != "reasoning" for e in result["events"])
    # thinking 这个请求字段也一并删掉了
    assert all("thinking" not in d for d in progress)


# ═══════════════════════════════════════════════════════════════
# 2. ★ 传输等价 —— 两种传输,一种行为
# ═══════════════════════════════════════════════════════════════


async def test_streaming_and_sync_produce_the_same_package():
    """同一个输入,两条路必须产出**逐字段相同**的包。

    这是整个文件里最重要的一条。两条路各自组装响应、各自跑一遍流水线,
    任何一处写歪了都会让「预览看到的」和「流式拿到的」不一样,
    而且只会在教师真的走那条路时才发现。
    """
    sync = await _sync(PAYLOAD)
    streamed = next(d for n, d in await _stream(PAYLOAD) if n == "result")

    assert streamed["package"] == sync["package"]


async def test_streaming_and_sync_report_the_same_integrity_and_agents():
    sync = await _sync(PAYLOAD)
    streamed = next(d for n, d in await _stream(PAYLOAD) if n == "result")

    assert streamed["integrity_issues"] == sync["integrity_issues"]
    assert streamed["agents"] == sync["agents"]
    assert streamed["model_mode"] == sync["model_mode"]


async def test_streaming_and_sync_report_the_same_events():
    """记录下来的事件列表也要一致 —— 否则两边的「阶段日志」对不上。"""
    sync = await _sync(PAYLOAD)
    streamed = next(d for n, d in await _stream(PAYLOAD) if n == "result")

    assert streamed["events"] == sync["events"]


# ═══════════════════════════════════════════════════════════════
# 3. 状态:流完之后 /state 看得到产物
# ═══════════════════════════════════════════════════════════════


async def test_the_package_is_stored_after_a_streamed_run():
    """刷新页面后前端靠 /state 恢复 —— 流式跑完也得存上。"""
    await _stream(PAYLOAD)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/demo/state")

    body = resp.json()
    assert body["has_package"] is True
    assert body["package"]["slideDeck"]["slides"]


async def test_streaming_also_works_with_materials():
    """带讲义时走的是另一条分支(真摄取 + chunk 检索),同样不能出错。"""
    frames = await _stream({
        **PAYLOAD,
        "material_text": "# 分支\n\n分支让改动互相隔离,主干保持可用。\n",
    })
    names = [n for n, _ in frames]
    result = next(d for n, d in frames if n == "result")

    assert names[-1] == "done"
    assert result["materials"], "给了讲义就该有摄取报告"
    assert result["integrity_issues"] == []


# ═══════════════════════════════════════════════════════════════
# 4. L2:编辑也能看过程
# ═══════════════════════════════════════════════════════════════


async def test_edit_stream_reports_each_tool_before_the_result():
    """L2 更值得看过程:教师能看见 agent 先读了哪一页。"""
    await _sync(PAYLOAD)                      # 先有产物

    frames = await _stream(
        {"message": "第 3 页太难了,降一档。", "use_real_model": False},
        path="/api/demo/edit/stream",
    )
    names = [n for n, _ in frames]
    progress = [d for n, d in frames if n == "progress"]

    assert names[-2:] == ["result", "done"]
    tools = [d.get("tool") for d in progress if d.get("kind") == "tool"]
    assert "read_slide" in tools, f"应该看得见它在读页面:{tools}"
    assert tools.index("read_slide") < tools.index("patch_slide")


async def test_edit_stream_does_not_touch_the_package():
    """★ 核心不变式:提议了改动,但产物一字未变(§7.2)。"""
    before = (await _sync(PAYLOAD))["package"]

    frames = await _stream(
        {"message": "第 3 页太难了,降一档。", "use_real_model": False},
        path="/api/demo/edit/stream",
    )
    result = next(d for n, d in frames if n == "result")

    assert result["package"] == before, "流式路径把「不落库」这条破坏了"
    assert result["patches"], "应该产生待确认的 patch"
    assert all(p["status"] == "proposed" for p in result["patches"])


async def test_edit_stream_understands_the_default_english_slide_reference():
    """教师端默认文案是英文，不能因此把 Slide 2 错改成第 1 页。"""
    await _sync(PAYLOAD)

    frames = await _stream(
        {
            "message": "Slide 2 is too dense for a non-CS audience.",
            "use_real_model": False,
        },
        path="/api/demo/edit/stream",
    )
    result = next(data for name, data in frames if name == "result")

    assert result["patches"]
    assert result["patches"][0]["target_id"] == "s2"


async def test_edit_stream_without_a_package_returns_409():
    """还没生成就来编辑 —— 要立刻 409,而不是开个流在里面报错。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/demo/edit/stream", json={"message": "改一下", "use_real_model": False}
        )

    assert resp.status_code == 409
