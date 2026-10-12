"""Patch 暂存区 —— 设计规格 §7.2。

═══════════════════════════════════════════════════════════════════
这是 L2 的核心机制,也是整个设计里最该讲清楚的一条
═══════════════════════════════════════════════════════════════════
AI 提出改动时**不直接改产物**,而是先变成一个 `proposed` 状态的 patch:

    教师说话 → agent 提议 → patch(status=proposed)   ← 产物此刻一字未变
                              │
                              └─ 教师点「确认」→ apply → 产物才真的变

为什么必须这样:NFR-04 要求「AI 内容在教师发布前标记为草稿」。
如果 agent 每句话都直接改产物,这条在**每次编辑**上就失效了 ——
审核会从「事前把关」退化成「事后补救」。

所以:**`apply_patch()` 是唯一能改变产物内容的路径。**
其余任何地方都不许碰它。这条是 §13.3 的接口层不变式,也是测试断言的对象。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.schemas.ir import CoursePackage, Slide

PatchStatus = Literal["proposed", "applied", "rejected"]
PatchKind = Literal["slide", "plan", "regenerate_slide", "timeline"]
#: 谁提的这个改动。**审计和「这页是人改的还是 AI 改的」都靠它。**
PatchAuthor = Literal["ai", "teacher"]


@dataclass
class Patch:
    """一次**待确认**的改动。"""

    id: str
    artifact_id: str
    kind: PatchKind
    target_id: str          # 改的是哪一页 / 哪个环节
    payload: dict[str, Any] # 要写进去的新值
    reason: str             # 为什么这么改 —— 会记入版本历史,是 AI Fluency 的证据
    diff: str = ""          # 给人看的差异
    status: PatchStatus = "proposed"
    #: 提议者。AI 提议要教师确认;教师自己改的,保存即确认。
    author: PatchAuthor = "ai"

    @property
    def is_pending(self) -> bool:
        return self.status == "proposed"


class PatchStore(Protocol):
    """暂存区接口。内存版够用就跑内存版,要持久化就换成数据库实现。"""


    def propose(self, *, artifact_id: str, kind: PatchKind, target_id: str,
                payload: dict[str, Any], reason: str, diff: str,
                author: PatchAuthor = "ai") -> Patch:
        """登记一个待确认改动,返回 patch id。此时产物一字未变。"""
        ...
    def get(self, patch_id: str) -> Patch:
        """按 id 取 patch。取不到直接报错,不返回 None。"""
        ...


    def list(self, artifact_id: str, status: PatchStatus | None = None) -> list[Patch]:
        """列出某产物下的 patch,可按状态过滤。"""
        ...
    def mark(self, patch_id: str, status: PatchStatus) -> None:
        """改状态(proposed → applied / rejected)。这是唯一改状态的地方。"""
        ...


class InMemoryPatchStore:
    """内存版暂存区 —— 用来先跑通流程。

    换成数据库时,只要实现同样的四个方法,`edit.py` 和 agent 一行都不用改。
    """

    def __init__(self) -> None:
        self._patches: dict[str, Patch] = {}
        self._counter = 0

    def propose(self, *, artifact_id: str, kind: PatchKind, target_id: str,
                payload: dict[str, Any], reason: str, diff: str,
                author: PatchAuthor = "ai") -> Patch:
        """登记一个待确认改动,返回 patch id。此时产物一字未变。"""

        self._counter += 1
        patch = Patch(
            id=f"pt-{self._counter}",          # 可读、确定,便于测试断言
            artifact_id=artifact_id,
            kind=kind,
            target_id=target_id,
            payload=payload,
            reason=reason,
            diff=diff,
            author=author,
        )
        self._patches[patch.id] = patch
        return patch

    def get(self, patch_id: str) -> Patch:
        """按 id 取 patch。取不到直接报错,不返回 None。"""

        if patch_id not in self._patches:
            raise KeyError(f"找不到 patch {patch_id}")
        return self._patches[patch_id]

    def list(self, artifact_id: str, status: PatchStatus | None = None) -> list[Patch]:
        """列出某产物下的 patch,可按状态过滤。"""

        items = [p for p in self._patches.values() if p.artifact_id == artifact_id]
        if status is not None:
            items = [p for p in items if p.status == status]
        return items

    def mark(self, patch_id: str, status: PatchStatus) -> None:
        """改状态(proposed → applied / rejected)。这是唯一改状态的地方。"""

        self.get(patch_id).status = status


# ═══════════════════════════════════════════════════════════════
# diff:教师要看的是「改了什么」,不是「现在什么样」
# ═══════════════════════════════════════════════════════════════


def make_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    """生成人可读的差异。

    列表字段(比如 bullets)走 difflib 的逐行对比,其余字段直接 -/+ 展示。
    """
    lines: list[str] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        if isinstance(old, list) and isinstance(new, list):
            for line in difflib.unified_diff(
                [str(x) for x in old], [str(x) for x in new], lineterm="", n=0
            ):
                if line.startswith(("---", "+++", "@@")):
                    continue
                lines.append(f"    {line}")
        else:
            lines.append(f"    - {key}: {old!r}")
            lines.append(f"    + {key}: {new!r}")
    return "\n".join(lines) if lines else "    (无实际变化)"


# ═══════════════════════════════════════════════════════════════
# 确认 / 驳回
# ═══════════════════════════════════════════════════════════════


class PatchAlreadyDecided(Exception):
    """对已经确认或驳回过的 patch 再操作一次。"""


def find_slide(package: CoursePackage, slide_id: str) -> Slide:
    """按 id 找幻灯片。找不到就报错,不静默返回 None。"""

    if package.slide_deck is None:
        raise KeyError("该产物没有课件")
    for slide in package.slide_deck.slides:
        if slide.id == slide_id:
            return slide
    raise KeyError(f"找不到幻灯片 {slide_id}")


def find_timeline_entry(package: CoursePackage, entry_id: str):
    """按 id 找教案环节。找不到就报错,不静默返回 None。"""

    if package.lesson_plan is None:
        raise KeyError("该产物没有教案")
    for entry in package.lesson_plan.timeline:
        if entry.id == entry_id:
            return entry
    raise KeyError(f"找不到教案环节 {entry_id}")


def artifact_id_of(package: CoursePackage) -> str:
    """取产物 id。课件和教案属于同一个产物。"""

    if package.slide_deck is not None:
        return package.slide_deck.artifact_id
    if package.lesson_plan is not None:
        return package.lesson_plan.artifact_id
    return package.project.id


def current_values(package: CoursePackage, kind: PatchKind, target_id: str) -> dict[str, Any]:
    """取某个目标当前的字段值(对外名,即 camelCase)。

    手动编辑要靠它算出「到底改了什么」,再据此生成 diff。
    **必须用 by_alias=True** —— 否则存进去的是 snake_case,
    和工具 schema / 前端用的 camelCase 对不上(diff 会显示成 None)。
    """
    if kind in ("slide", "regenerate_slide"):
        return find_slide(package, target_id).model_dump(by_alias=True)
    if kind == "timeline":
        return find_timeline_entry(package, target_id).model_dump(by_alias=True)
    raise ValueError(f"不支持查看 {kind} 的当前值")


def manual_edit(
    package: CoursePackage,
    store: PatchStore,
    *,
    kind: PatchKind,
    target_id: str,
    payload: dict[str, Any],
    note: str = "教师手动修改",
) -> tuple[Patch, CoursePackage]:
    """教师**直接改内容** —— 但仍然走 patch 机制。

    ═══════════════════════════════════════════════════════════════
    为什么不让教师「直接改」
    ═══════════════════════════════════════════════════════════════
    直觉上教师手动改该是最直接的路径。可一旦它直接写产物:

      · `apply_patch()` 就不再是唯一能改编产物的函数 ——
        所有断言这条不变式的测试和文档**立刻变成假话**
      · 改动没有记录,§10 的 AI 审计里看不出
        「这一页是教师改的还是 AI 改的」
      · 没法撤销 —— patch 记录本来就是天然的撤销栈

    所以手动改也生成 patch,只是 `author="teacher"`,
    并且**在同一个动作里立刻 apply** —— 教师点「保存」就是确认,
    不需要再点一次。对用户是一次点击;对系统,产物仍然只被
    `apply_patch()` 改过。

    返回 (patch, package)。**patch 会留在历史里**,所以可审计、可回退。
    """
    before = current_values(package, kind, target_id)

    # 只留下真正变了的字段 —— 否则 diff 里全是噪音,
    # 而且「什么都没改」也会生成一条 patch。
    changed = {k: v for k, v in payload.items() if before.get(k) != v}
    if not changed:
        raise ValueError("没有任何字段发生变化")

    patch = store.propose(
        artifact_id=artifact_id_of(package),
        kind=kind,
        target_id=target_id,
        payload=changed,
        reason=note,
        diff=make_diff({k: before.get(k) for k in changed}, changed),
        author="teacher",
    )
    try:
        apply_patch(package, store, patch.id)
    except Exception:
        # 校验没过的改动不要留在「待确认」里 —— 教师已经看到报错了,
        # 再挂一条 pending 只会让列表变乱。
        store.mark(patch.id, "rejected")
        raise
    return patch, package


def apply_patch(package: CoursePackage, store: PatchStore, patch_id: str) -> CoursePackage:
    """把待确认的 patch **真正**写进产物。

    这是唯一改变产物内容的函数。它做三件事:

      1. 检查 patch 还是 proposed 状态(不许重复确认)
      2. 把改动合并进去,**并重新跑一遍 Pydantic 校验**
         —— 所以一个会让产物非法的 patch 会在这里被挡住
      3. 把 patch 标为 applied

    注意第 2 点:`model_validate` 而不是直接 setattr。
    直接改属性会绕过校验,等于把「AI 输出必须过 schema」这条规则
    在编辑路径上又打开了一个口子。
    """
    patch = store.get(patch_id)
    if not patch.is_pending:
        raise PatchAlreadyDecided(f"patch {patch_id} 已经是 {patch.status} 状态")

    if patch.kind in ("slide", "regenerate_slide"):
        deck = package.slide_deck
        if deck is None:
            raise KeyError("该产物没有课件")
        index = next(
            (i for i, s in enumerate(deck.slides) if s.id == patch.target_id), None
        )
        if index is None:
            raise KeyError(f"找不到幻灯片 {patch.target_id}")

        merged = {**deck.slides[index].model_dump(), **patch.payload}
        deck.slides[index] = Slide.model_validate(merged)   # ← 重新校验

    elif patch.kind == "timeline":
        # 按环节 id 精确定位。比「整份替换教案」精确得多 ——
        # diff 只显示真正改的那几个字段,也不会误伤别的环节。
        plan = package.lesson_plan
        if plan is None:
            raise KeyError("该产物没有教案")
        index = next(
            (i for i, t in enumerate(plan.timeline) if t.id == patch.target_id), None
        )
        if index is None:
            raise KeyError(f"找不到教案环节 {patch.target_id}")
        merged = {**plan.timeline[index].model_dump(), **patch.payload}
        plan.timeline[index] = type(plan.timeline[index]).model_validate(merged)

    elif patch.kind == "plan":
        plan = package.lesson_plan
        if plan is None:
            raise KeyError("该产物没有教案")
        merged = {**plan.model_dump(), **patch.payload}
        package.lesson_plan = type(plan).model_validate(merged)

    store.mark(patch_id, "applied")
    return package


def reject_patch(store: PatchStore, patch_id: str) -> None:
    """驳回。产物本来就没被改过,所以这里只需要改状态。"""
    patch = store.get(patch_id)
    if not patch.is_pending:
        raise PatchAlreadyDecided(f"patch {patch_id} 已经是 {patch.status} 状态")
    store.mark(patch_id, "rejected")
