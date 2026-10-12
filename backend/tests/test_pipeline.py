
"""流水线测试 —— 对应设计规格 §6.1(阶段与进度)与 §6.4(交叉引用校验)。"""

from __future__ import annotations

from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.services.pipeline import PHASES, GenerationRequest, PipelineDeps, generate_course


def _deps(**overrides) -> PipelineDeps:
    """造一份流水线依赖(假模型 + 假检索渲染)。"""

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
    """造一个生成请求。"""

    base = dict(topic="Git 分支", audience="初学者", duration_min=45)
    base.update(overrides)
    return GenerationRequest(**base)


async def test_all_six_phases_are_emitted_in_defined_order():
    """六个阶段必须按定义顺序出现,且不跳步。"""

    result = await generate_course(_req(), _deps())
    seen: list[str] = []
    for ev in result.events:
        if not seen or seen[-1] != ev.phase:
            seen.append(ev.phase)
    assert seen == [p[0] for p in PHASES]


async def test_progress_never_goes_backwards():
    """进度条不能倒退,否则前端会闪。"""
    result = await generate_course(_req(), _deps())
    percents = [ev.percent for ev in result.events]
    assert percents == sorted(percents)
    assert percents[-1] == 100


async def test_each_section_agent_stops_at_terminal_tool():
    """三节各跑一个 agent,且都由 write_section 正常收尾。"""
    result = await generate_course(_req(), _deps())
    assert len(result.agents) == 3
    for agent in result.agents:
        assert agent.stopped_by == "terminal"
        # 顺序固定:先检索、再画图、写教案环节、最后提交(终止工具)
        assert agent.call_names == [
            "search_materials",
            "make_diagram",
            "write_plan_entry",
            "write_section",
        ]


async def test_sections_are_ordered_by_the_order_field():
    """并发跑完之后必须按 order 排好,否则课件页码是乱的。"""
    result = await generate_course(_req(), _deps())
    slides = result.package.slide_deck.slides
    assert [s.order for s in slides] == [1, 2, 3]
    assert [s.id for s in slides] == ["s1", "s2", "s3"]


async def test_generated_package_passes_integrity_check():
    result = await generate_course(_req(), _deps())
    assert result.integrity_issues == []


async def test_both_artifacts_are_produced():
    """回归测试:教案曾经被静默丢弃 —— agent 写进 written_plan,
    流水线却从没读过它,产出的包永远只有课件。

    现在必须同时产出课件和教案,而且教案的 slideIds 指向真实存在的页。
    """
    result = await generate_course(_req(), _deps())
    pkg = result.package

    assert pkg.slide_deck is not None and len(pkg.slide_deck.slides) == 3
    assert pkg.lesson_plan is not None
    assert len(pkg.lesson_plan.timeline) == 3

    slide_ids = {s.id for s in pkg.slide_deck.slides}
    for entry in pkg.lesson_plan.timeline:
        assert set(entry.slide_ids) <= slide_ids

    # 三节各 15 分钟,合计 45 = 设定课时,校验应通过
    assert sum(e.minutes for e in pkg.lesson_plan.timeline) == 45
    assert result.integrity_issues == []


async def test_concurrency_limit_does_not_change_the_result():
    """并发 1 和并发 3 应产出同样的东西 —— 并发只影响速度,不影响内容。"""
    serial = await generate_course(_req(), _deps(section_concurrency=1))
    parallel = await generate_course(_req(), _deps(section_concurrency=3))
    assert [s.id for s in serial.package.slide_deck.slides] == [
        s.id for s in parallel.package.slide_deck.slides
    ]
    assert serial.integrity_issues == parallel.integrity_issues == []


async def test_visual_needs_and_assets_are_counted():
    """回归测试:曾经这里对 dict 用了 getattr,导致恒报「0 处」。

    三页幻灯片各配一张示意图 → 阶段 4 必须报 3 处,资产池必须有 3 个资产。
    """
    result = await generate_course(_req(), _deps())

    visual_events = [e for e in result.events if e.phase == "判定视觉需求"]
    assert "3 处视觉需求" in visual_events[-1].detail

    asset_events = [e for e in result.events if e.phase == "生成资产"]
    assert "3 个资产入池" in asset_events[-1].detail

    assert len(result.package.assets) == 3
    assert all(a.kind == "diagram" for a in result.package.assets)


async def test_assets_are_deduplicated_by_id():
    """同一个 Mermaid 源码应只产生一个资产(§8.6 按 hash 去重)。"""
    result = await generate_course(_req(), _deps())
    ids = [a.id for a in result.package.assets]
    assert len(ids) == len(set(ids))


async def test_uncovered_objective_is_caught_end_to_end():
    """多给一个学习目标但不给对应幻灯片 → 校验必须报出来(§6.4)。"""
    result = await generate_course(_req(objectives=["目标一", "目标二", "目标三"]), _deps())
    assert any("LO3" in issue for issue in result.integrity_issues)


# ═══════════════════════════════════════════════════════════
# 阶段 1 接真摄取
# ═══════════════════════════════════════════════════════════


async def test_pipeline_runs_real_ingestion_when_materials_are_given(tmp_path):
    """给了材料就走真实摄取:探测 → 抽取 → 分块 → 真检索。"""
    from app.services.ingest import IngestDeps

    material = tmp_path / "讲义.md"
    material.write_text(
        "# Git 分支\n\n分支让改动互相隔离,主干保持可用。\n" * 20, encoding="utf-8"
    )

    result = await generate_course(
        _req(material_paths=[material]),
        _deps(ingest_deps=IngestDeps(ocr_image=_noop_ocr)),
    )

    assert len(result.materials) == 1
    assert result.materials[0].status == "ok"
    assert result.materials[0].extracted_chars > 0
    assert result.failed_materials == []
    # 材料确实被检索到了(假检索返回固定两条,真检索返回命中的 chunk)
    assert result.agents and all(a.called("search_materials") for a in result.agents)


async def test_pipeline_reports_a_failed_material_without_aborting(tmp_path):
    """一份材料读不到字,**不该让整次生成失败**(§14)。"""
    from app.services.ingest import IngestDeps

    bad = tmp_path / "空.pdf"
    bad.write_bytes(b"\x00\x01\x02" * 100)          # 不是合法 PDF

    result = await generate_course(
        _req(material_paths=[bad]),
        _deps(ingest_deps=IngestDeps(ocr_image=_noop_ocr)),
    )

    assert len(result.materials) == 1
    assert result.materials[0].status == "failed"
    assert result.failed_materials            # 上层能查到是哪份失败
    assert result.package.slide_deck is not None   # 但产物照样产出了


async def _noop_ocr(_: bytes) -> str:
    return ""


# ═══════════════════════════════════════════════════════════
# 教案时长:以大纲为准(真模型测出来的问题)
# ═══════════════════════════════════════════════════════════


class _SillyMinutesModel(FakeSectionModel):
    """假模型,但故意把每条教案环节都写成 100 分钟。

    真实情况没这么夸张,但方向一样:各节 agent 并发跑,
    各自独立猜自己那一节要花多久,加起来跟大纲对不上。
    """

    async def complete(self, *, model, messages, tools=None, temperature=0.0):
        reply = await super().complete(
            model=model, messages=messages, tools=tools, temperature=temperature,
        )
        for tc in reply.tool_calls:
            if tc.name == "write_plan_entry":
                tc.arguments["entry"]["minutes"] = 100
        return reply


async def test_plan_minutes_are_normalized_to_the_outline():
    """各节写的教案时长必须被缩放到大纲给的时长。

    真模型第一次跑通 L1 时,大纲规划 45 分钟、教案加起来只有 32 分钟,
    交叉引用校验直接报「教案总时长 32 分钟与设定 45 分钟相差超过 10%」。

    根因是职责没分清:时长是**课程级**属性,大纲已经定好了;
    每节 agent 该管的是「这节讲什么」,不该由它决定时长。
    """
    result = await generate_course(_req(duration_min=45), _deps(client=_SillyMinutesModel()))

    timeline = result.package.lesson_plan.timeline
    assert timeline, "教案不该为空"
    assert sum(t.minutes for t in timeline) == 45


async def test_normalization_preserves_relative_weight():
    """归一化只改总量,不改各环节之间的相对轻重。"""
    result = await generate_course(_req(duration_min=45), _deps(client=_SillyMinutesModel()))
    timeline = result.package.lesson_plan.timeline

    # 假模型给每节都写一样的 100 分钟,所以归一化后应该三节等分
    by_phase = sorted(t.minutes for t in timeline)
    assert by_phase[-1] - by_phase[0] <= 1, f"等长的环节归一化后不该差很多:{by_phase}"


async def test_assembly_errors_are_empty_on_the_happy_path():
    """正常路径下不该有内容被跳过 —— 非空就说明模型产出的结构有问题。"""
    result = await generate_course(_req(), _deps())
    assert result.assembly_errors == []


# ═══════════════════════════════════════════════════════════
# 失败隔离:一节崩了不能搞垮整包(§14)
# ═══════════════════════════════════════════════════════════


class _FlakyModel(FakeSectionModel):
    """第 2 节的 agent 一调用就抛网络错误,其余节正常。

    真模型实测遇到过 `APIConnectionError` —— 当时直接把整次生成打断,
    前面几节烧掉的 token 全白费。
    """

    def __init__(self) -> None:
        super().__init__()
        self._section_no = 0

    async def complete(self, *, model, messages, tools=None, temperature=0.0):
        # 只有分节生成那次调用会带 tools;数一下是第几节
        if tools:
            text = " ".join(
                m.get("content") or "" for m in messages if isinstance(m.get("content"), str)
            )
            if "写第 2 节" in text:
                raise ConnectionError("模拟网络抖动")
        return await super().complete(
            model=model, messages=messages, tools=tools, temperature=temperature,
        )


async def test_one_failed_section_does_not_kill_the_whole_run():
    """第三节崩了,第一、三节照样产出 —— 包还得出得来。"""
    result = await generate_course(_req(), _deps(client=_FlakyModel()))

    assert result.package.slide_deck is not None
    # 三节都留下了记录,其中一节标了 error
    assert len(result.agents) == 3
    assert sum(1 for a in result.agents if a.stopped_by == "error") == 1
    # 其余两节正常产出幻灯片
    assert len(result.package.slide_deck.slides) >= 2


async def test_failed_section_is_visible_not_silent():
    """失败必须看得见 —— 静默少一节课件,教师以为模型就这水平。"""
    result = await generate_course(_req(), _deps(client=_FlakyModel()))

    failed = [a for a in result.agents if a.stopped_by == "error"]
    assert failed, "应该有且仅有一节失败"
    assert failed[0].content, "失败原因必须记录在案"
    assert any(c.error for c in failed[0].calls)
