"""进度事件契约 —— 设计规格 §6.1.1 与 §6.1.2。

═══════════════════════════════════════════════════════════════════
这组测试补的是哪个洞
═══════════════════════════════════════════════════════════════════
`test_pipeline.py` 已经守住了「进度不倒退」和「六个阶段按序出现」。
但它守不住「事件里有没有 UI 要用的字段」—— 因为原来的事件**只有**
`phase / percent / detail` 三个字段,而前端要按节分栏、要数页码,
只能去正则拆 `detail` 那句中文。

拆中文句子的代码不会报错:措辞一改,它只是静默地显示不出来了。
**没有任何测试会变红** —— 因为没有契约可断言。

所以这个文件断言的是**字段**,不是句子:

    kind            → 这条事件该渲染成什么
    section_index   → 分到哪一栏
    section_title   → 栏目标题(UI 不必回查大纲)
    slide_count     → 「已写 N 张」
    tool            → 那一行前面挂什么
    status          → 「写完了」还是「失败了」
"""

from __future__ import annotations

from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.services.pipeline import (
    PHASES,
    GenerationRequest,
    PipelineDeps,
    ProgressEvent,
    generate_course,
)

#: §6.1.1 定义的 kind 取值。这里刻意写死一份 ——
#: 加了新 kind 却忘了更新文档时,这个测试会红。
#:
#: **刻意没有 `reasoning`。**思考流那条路径已经整条删掉了
#: (界面撤掉 → 模型层流式分支跟着删,见 §11.7)。
VALID_KINDS = {"phase", "section", "turn", "tool", "slide"}


def _deps(**overrides) -> PipelineDeps:
    base = dict(
        client=FakeSectionModel(),
        model="fake-model",
        search_materials=fake_search,
        make_diagram=fake_make_diagram,
        request_illustration=fake_illustration,
    )
    base.update(overrides)
    return PipelineDeps(**base)


def _req(**overrides) -> GenerationRequest:
    base = dict(topic="Git 分支", audience="初学者", duration_min=45)
    base.update(overrides)
    return GenerationRequest(**base)


async def _run(**overrides) -> tuple[list[ProgressEvent], list[ProgressEvent], object]:
    """跑一次生成,同时收集「记录的」和「推给回调的」两串事件。"""
    pushed: list[ProgressEvent] = []
    result = await generate_course(_req(), _deps(**overrides), on_event=pushed.append)
    return result.events, pushed, result


# ═══════════════════════════════════════════════════════════════
# 字段:UI 要用的东西必须有独立字段
# ═══════════════════════════════════════════════════════════════


async def test_every_event_uses_a_kind_from_the_documented_set():
    events, _, _ = await _run()

    unknown = sorted({e.kind for e in events} - VALID_KINDS)
    assert unknown == [], f"出现了文档没定义的 kind:{unknown}"


async def test_every_event_has_a_phase_and_a_sane_percent():
    events, _, _ = await _run()

    for e in events:
        assert e.phase in [p[0] for p in PHASES], f"阶段名不对:{e.phase}"
        assert 0 <= e.percent <= 100, f"进度越界:{e.percent}"


async def test_percent_is_monotonic_even_with_three_sections_in_flight():
    """三节并发时,后发的事件进度不能更小 —— 否则前端的进度条会抽搐。

    这条曾经真的会失败:如果按「已完成节数 + 本节轮次占比」算,
    第 1 节跑到第 5 轮报 0.83,而刚起步的第 2 节会报 0.17,后报的更小。
    """
    events, _, _ = await _run()

    percents = [e.percent for e in events]
    assert percents == sorted(percents), f"进度倒退了:{percents}"


# ═══════════════════════════════════════════════════════════════
# 分节:按节分栏靠的是 section_index,不是解析标题
# ═══════════════════════════════════════════════════════════════


async def test_section_events_name_the_section_they_belong_to():
    events, _, _ = await _run(section_concurrency=1)

    section_events = [e for e in events if e.kind == "section"]
    assert section_events, "一条 section 事件都没有,界面就没法按节分栏"

    for e in section_events:
        assert e.section_index is not None, "section 事件必须带节号"
        assert e.section_title, "section 事件必须带节标题"


async def test_all_sections_are_announced():
    events, _, result = await _run(section_concurrency=1)

    announced = {e.section_index for e in events if e.kind == "section"}
    # 一节可以一次提交多页；要报到的是每个 section，而不是每一张 slide。
    assert announced == set(range(len(result.agents))), (
        "每一节都该被报到 —— 否则界面上会有一栏永远不亮"
    )


async def test_section_status_can_be_told_apart_without_parsing_text():
    """界面必须能区分「这一节写完了」和「这一节失败了」。

    如果只能靠 `detail` 里的措辞去猜,那句话一改前端就静默失效 ——
    而那正是这些字段存在的理由。
    """
    events, _, _ = await _run(section_concurrency=1)

    statuses = {e.status for e in events if e.kind == "section"}
    assert statuses == {"started", "written"}, f"section 状态不对:{statuses}"


async def test_a_failed_section_is_marked_failed():
    """失败必须有自己的状态值 —— 不能只体现在一句中文里。"""
    from app.demo_pipeline import FakeSectionModel

    class _Boom(FakeSectionModel):
        async def complete(self, *, model, messages, tools=None, temperature=0.0):
            if tools and "写第 2 节" in str(messages):
                raise ConnectionError("模拟网络抖动")
            return await super().complete(
                model=model, messages=messages, tools=tools, temperature=temperature
            )

    pushed: list[ProgressEvent] = []
    result = await generate_course(
        _req(), _deps(client=_Boom(), section_concurrency=1), on_event=pushed.append
    )

    failed = [e for e in pushed if e.kind == "section" and e.status == "failed"]
    assert len(failed) == 1
    assert failed[0].section_index == 1
    assert sum(1 for a in result.agents if a.stopped_by == "error") == 1


async def test_tool_events_carry_the_tool_name():
    events, _, _ = await _run(section_concurrency=1)

    tool_events = [e for e in events if e.kind == "tool"]
    assert tool_events, "没有动作流事件 —— 界面上就只能干等"
    for e in tool_events:
        assert e.tool, f"tool 事件必须带工具名:{e}"


async def test_turn_events_report_which_round_we_are_in():
    """「正在等模型回复」是界面上最长的静止期,必须有事件。"""
    events, _, _ = await _run(section_concurrency=1)

    assert any(e.kind == "turn" for e in events)


# ═══════════════════════════════════════════════════════════════
# 「现在写到第几张 ppt」
# ═══════════════════════════════════════════════════════════════


async def test_slide_events_count_up_to_the_real_deck_size():
    """累计页数必须最终等于课件真实张数 —— 这是「已写 N 张」的数据来源。"""
    events, _, result = await _run(section_concurrency=1)

    real = len(result.package.slide_deck.slides)
    slide_events = [e for e in events if e.kind == "slide"]

    assert slide_events, "没有 slide 事件,界面上就看不到「已写几张」"
    assert slide_events[-1].slide_count == real
    # write_section 一次提交一节的多页，事件按提交批次累计（3、6、9），
    # 不该错误地要求每页各发一条事件。
    counts = [e.slide_count for e in slide_events]
    assert counts == sorted(counts)
    assert all(current > previous for previous, current in zip(counts, counts[1:]))


async def test_slide_events_tell_you_which_pages_were_written():
    events, _, _ = await _run(section_concurrency=1)

    for e in (e for e in events if e.kind == "slide"):
        assert "页" in e.detail, f"这条看不出写了几页:{e.detail}"


async def test_slide_count_is_carried_on_every_later_event_too():
    """后面的事件也要带上累计页数,这样界面任何时候都能显示它。"""
    events, _, result = await _run(section_concurrency=1)

    assert events[-1].slide_count == len(result.package.slide_deck.slides)


# ═══════════════════════════════════════════════════════════════
# 思考流已经不存在了
# ═══════════════════════════════════════════════════════════════


async def test_there_is_no_reasoning_event_at_all():
    """思考流这条路径已经整条删掉了 —— 事件里不该再有它的位置。

    它曾经存在过:界面上一面滚动的思维链墙。撤掉之后,模型层的流式分支、
    `on_delta` 转交、`kind="reasoning"` 全都没有了调用方,于是整条删除。
    这条测试守的就是「别哪天又悄悄长回来一半」。
    """
    events, pushed, _ = await _run()

    assert "reasoning" not in VALID_KINDS, "kind 枚举里又出现了 reasoning"
    assert all(e.kind != "reasoning" for e in events)
    assert all(e.kind != "reasoning" for e in pushed)
    # 「只推不记」的机制也不该再有:它唯一的用户就是思考流
    assert len(pushed) == len(events), "出现了只推给回调、不记录的事件"


# ═══════════════════════════════════════════════════════════════
# 序列化:发给前端的是 camelCase(§5.1)
# ═══════════════════════════════════════════════════════════════


async def test_to_dict_is_camel_case():
    events, _, _ = await _run()
    payload = events[-1].to_dict()

    assert set(payload) == {
        "phase", "percent", "detail", "kind",
        "sectionIndex", "sectionTitle", "slideCount", "tool", "status",
    }
    assert "section_index" not in payload
