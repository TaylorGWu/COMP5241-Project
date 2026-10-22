"""L2 编辑编排 —— 设计规格 §7。

═══════════════════════════════════════════════════════════════════
L2 和 L1 的关系
═══════════════════════════════════════════════════════════════════
    共用:agent.py 的那个循环(一行都不用改)
    不同:L1 是「管道里跑 agent」,L2 是「整个交互就是 agent」
    不同:L1 可以写自己的产出,L2 只能**暂存 patch**

═══════════════════════════════════════════════════════════════════
EditDeps 是什么
═══════════════════════════════════════════════════════════════════
tools.py 里的 `EditDepsProtocol` 声明了工具要调的四个方法,
`EditDeps` 是它们的真实实现 —— 这就是之前缺的那台「机器」。

因为工具是面向接口的,所以换实现(内存版 → 数据库版)不用动 agent。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from app.llm.client import ChatClient
from app.schemas.ir import CoursePackage
from app.services.agent import AgentResult, AgentStep, run_agent
from app.services.patches import (
    InMemoryPatchStore,
    Patch,
    PatchStore,
    artifact_id_for,
    find_question,
    find_slide,
    make_diff,
)
from app.services.tools import build_edit_tools

#: 编辑 Agent 的系统提示。
#: 三条规定对应三条设计约束:先读再改(不许瞎改)、改动要暂存(不许直接落库)、改动要留理由。
EDIT_SYSTEM_PROMPT = """你在帮一位教师修改一份已经生成好的教学材料。

必须遵守:
1. **先读再改。** 修改课件用 read_slide,修改题目用 read_question,修改试卷用 read_paper。
   不要凭猜测对没读过的内容提改动。
2. 所有改动通过对应的 patch 工具提出。**改动不会立刻生效** ——
   教师确认之后才会写入,所以你可以放心提议。
3. 每次改动都要填 reason,说明为什么这么改(会记入版本历史供教师审查)。
4. 提完改动后,用一到两句话说明你做了什么。不要反复提同一个改动。
5. 教师要求逐步讲解概念时，可以提出 `animation` patch；它只能编排当前页已有的
   title、bullet:索引或 visual:视觉 id，不能用它偷偷新增内容。先 read_slide 再确认目标存在。
"""


def _bullet_edits(before: list[str], after: list[str]) -> list[dict[str, Any]]:
    """Turn one list replacement into reviewable edits for individual bullets.

    A slide's bullets share one IR field, but they are not one editorial decision.
    Storing the old text gives ``apply_patch`` a stable anchor even when the
    teacher accepts the surrounding edits in a different order.
    """
    edits: list[dict[str, Any]] = []
    for tag, old_start, old_end, new_start, new_end in SequenceMatcher(a=before, b=after).get_opcodes():
        if tag == "equal":
            continue
        old_items = before[old_start:old_end]
        new_items = after[new_start:new_end]
        shared = min(len(old_items), len(new_items))
        for offset in range(shared):
            edits.append({"before": old_items[offset], "after": new_items[offset]})
        for item in old_items[shared:]:
            edits.append({"before": item, "after": None})
        for offset, item in enumerate(new_items[shared:]):
            edits.append({"before": None, "after": item, "position": old_start + shared + offset})
    return edits


def _bullet_edit_diff(edit: dict[str, Any]) -> str:
    before, after = edit.get("before"), edit.get("after")
    old_values = [] if before is None else [before]
    new_values = [] if after is None else [after]
    return make_diff({"bullets": old_values}, {"bullets": new_values})


@dataclass
class EditDeps:
    """编辑 Agent 的依赖 —— `EditDepsProtocol` 的真实实现。"""

    package: CoursePackage
    store: PatchStore

    @property
    def artifact_id(self) -> str:
        """当前编辑的产物 id。有课件时用课件的 id,否则退回项目 id。"""
        if self.package.slide_deck is not None:
            return self.package.slide_deck.artifact_id
        return self.package.project.id

    def artifact_id_for(self, kind: str) -> str:
        return artifact_id_for(self.package, kind)  # type: ignore[arg-type]

    # ── 工具会调的第一个方法:读 ────────────────────────────
    async def read_slide(self, slide_id: str) -> dict[str, Any]:
        """返回 camelCase —— 和模型看到的工具 schema 保持一致(§5.1)。"""
        return find_slide(self.package, slide_id).model_dump(by_alias=True)

    async def read_question(self, question_id: str) -> dict[str, Any]:
        return find_question(self.package, question_id).model_dump(by_alias=True)

    async def read_paper(self) -> dict[str, Any]:
        if self.package.exam_paper is None:
            raise KeyError("该产物还没有试卷")
        return self.package.exam_paper.model_dump(by_alias=True)

    # ── 工具会调的第二个方法:提议改动(只暂存,不落库)────
    async def propose_patch(self, kind: str, args: dict[str, Any]) -> str:
        """工具 patch_slide / patch_plan 的实现。**只暂存,绝不落库。**"""

        payload: dict[str, Any] = args.get("patch") or {}
        target_id: str = args.get("slide_id") or args.get("question_id") or "paper"
        reason: str = args.get("reason") or "(模型未说明理由)"

        # diff 需要「改之前是什么」,所以先去取当前值
        before = self._current_values(kind, target_id, list(payload))

        # 一页课件的标题、要点、讲稿和视觉是教师分别审的内容；不能把多个
        # 字段塞进同一条 patch，否则「同意标题、驳回要点」会变成不可能。
        # 只对 slide 拆分，其他产物仍保持原子性，避免无意义地拆散一条试卷规则。
        field_payloads: list[dict[str, Any]] = []
        if kind in ("slide", "regenerate_slide"):
            for field, value in payload.items():
                if field == "bullets" and isinstance(value, list):
                    field_payloads.extend(
                        {"bulletEdit": edit}
                        for edit in _bullet_edits(list(before.get("bullets") or []), value)
                    )
                else:
                    field_payloads.append({field: value})
        else:
            field_payloads = [payload]
        patches = [
            self.store.propose(
                artifact_id=self.artifact_id_for(kind),
                kind=kind,  # type: ignore[arg-type]
                target_id=target_id,
                payload=field_payload,
                reason=reason,
                diff=(
                    _bullet_edit_diff(field_payload["bulletEdit"])
                    if "bulletEdit" in field_payload
                    else make_diff({key: before.get(key) for key in field_payload}, field_payload)
                ),
            )
            for field_payload in field_payloads
        ]
        return ", ".join(patch.id for patch in patches)


    def _current_values(self, kind: str, target_id: str, keys: list[str]) -> dict[str, Any]:
        """取要改的那几个字段的当前值,用于生成 diff。

        **必须用 by_alias=True(camelCase)**,因为 payload 里的字段名
        来自工具 schema,也是 camelCase。两边不一致的话,像
        `speakerNotes`(内部是 speaker_notes)这种字段就会取不到,
        diff 里会显示成「改前是 None」—— 而其实它有值。
        """
        if kind in ("slide", "regenerate_slide"):
            try:
                slide = find_slide(self.package, target_id)
            except KeyError:
                return {}
            current = slide.model_dump(by_alias=True)
        elif kind == "plan" and self.package.lesson_plan is not None:
            current = self.package.lesson_plan.model_dump(by_alias=True)
        elif kind == "question":
            try:
                current = find_question(self.package, target_id).model_dump(by_alias=True)
            except KeyError:
                return {}
        elif kind == "paper" and self.package.exam_paper is not None:
            current = self.package.exam_paper.model_dump(by_alias=True)
        else:
            return {}
        return {k: current[k] for k in keys if k in current}

    # ── 另外两个只读查询工具 ────────────────────────────────
    async def estimate_timing(self) -> dict[str, Any]:
        """工具 estimate_timing 的实现。只读。"""

        plan = self.package.lesson_plan
        limit = self.package.project.meta.duration_min
        if plan is None:
            return {"limit_min": limit, "total_min": None, "over": False,
                    "note": "该产物没有教案"}
        total = sum(entry.minutes for entry in plan.timeline)
        return {
            "limit_min": limit,
            "total_min": total,
            "over": total > limit,
            "over_by": max(0, total - limit),
        }


    async def check_coverage(self) -> dict[str, Any]:
        """工具 check_coverage 的实现。查哪些学习目标还没有对应幻灯片。只读。"""
        slides = self.package.slide_deck.slides if self.package.slide_deck else []
        covered = sorted({oid for s in slides for oid in s.objective_ids})
        all_ids = sorted(o.id for o in self.package.project.learning_objectives)
        return {"covered": covered, "gaps": [o for o in all_ids if o not in covered]}


@dataclass
class EditResult:
    """一次编辑交互的结果。"""

    reply: str = ""
    #: 本次产生的待确认改动 —— 前端拿它渲染 diff
    proposed: list[Patch] = field(default_factory=list)
    agent: AgentResult | None = None

    @property
    def call_names(self) -> list[str]:
        """本次交互调用了哪些工具 —— 测试的断言对象。"""

        return self.agent.call_names if self.agent else []


async def edit_artifact(
    *,
    client: ChatClient,
    model: str,
    package: CoursePackage,
    message: str,
    images: list[str] | None = None,
    target: str = "slides",
    store: PatchStore | None = None,
    max_turns: int = 8,
    on_step: Callable[[AgentStep], None] | None = None,
) -> EditResult:
    """让 agent 根据教师的话提出改动。

    **注意:这个函数不会改变 `package` 的内容。**
    它只是把改动暂存成 patch。要让改动生效,必须由上层显式调用
    `apply_patch()` —— 那才是唯一能改产物的路径(§7.2)。

    `on_step` 是可选观察者,原样转交给 agent 循环(§6.1.2)。
    L2 尤其值得看过程:教师能看见 agent 先读了哪一页、为什么这么改。
    不传就没有任何开销,现有调用方一个字都不用改。
    """
    store = store if store is not None else InMemoryPatchStore()
    deps = EditDeps(package=package, store=store)

    extra: dict[str, Any] = {}
    if on_step is not None:
        extra["on_step"] = on_step

    user: str | list[dict[str, Any]] = f"[revision target: {target}]\n{message}"
    if images:
        user = [
            {"type": "text", "text": user},
            *[{"type": "image_url", "image_url": {"url": image}} for image in images],
        ]

    agent_result = await run_agent(
        client=client,
        model=model,
        system=f"{EDIT_SYSTEM_PROMPT}\n\n本次只能修改: {target}。请只使用匹配该材料的 read / patch 工具。",
        user=user,
        tools=build_edit_tools(deps),
        max_turns=max_turns,
        **extra,
    )

    return EditResult(
        reply=agent_result.content,
        proposed=store.list(deps.artifact_id_for({"slides": "slide", "questions": "question", "paper": "paper"}.get(target, "slide")), status="proposed"),
        agent=agent_result,
    )
