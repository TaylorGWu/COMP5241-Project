"""教师端增量的离线假模型 —— **不需要 API key** 就能跑通出题和术语表。

═══════════════════════════════════════════════════════════════════
为什么每个流程都要一个自己的假模型
═══════════════════════════════════════════════════════════════════
`FakeSectionModel` 只认识分节生成的 prompt(「写第 N 节:…」)。
拿它去跑出题,模型看到的是一段它没见过的系统提示,于是返回一段
跟题目无关的文本 —— 出题直接降级成 0 道题。

这不是 bug,是**假模型的职责边界**。L2 编辑当初也踩过同一件事,
所以有了单独的 `FakeEditModel`。这里同理:

    FakeQuestionModel   认得「你在为一份软件工程迷你课程出题」
    FakeGlossaryModel   认得术语表和替代文本那两段

═══════════════════════════════════════════════════════════════════
它们从 prompt 里读输入,而不是写死返回值
═══════════════════════════════════════════════════════════════════
假模型要能反映「我真的把参数传下去了」。所以:

    FakeQuestionModel   从用户消息里 parse 出学习目标 id 和文字,按目标出题
    FakeGlossaryModel   从用户消息里 parse 出 assetId,逐个配说明

写死返回值的话,「语言没传下去」「目标 id 没传下去」这类 bug
在离线 demo 里永远看不见 —— 而那正是我们花最多力气防的一类问题。

═══════════════════════════════════════════════════════════════════
两个假模型都**不做网络请求,也不 await**
═══════════════════════════════════════════════════════════════════
所以行为完全确定,测试和 demo 都可复现。`delay` 和 `FakeSectionModel`
一样只给演示用,默认 0,测试里必须保持 0。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.llm.client import ChatMessage

#: 从用户消息里抓「  LO1  解释分支与主干的关系」
_OBJECTIVE_RE = re.compile(r"^\s*(LO\d+)\s+(.+?)\s*$", re.MULTILINE)

#: 从用户消息里抓「assetId=as-xxxx」
_ASSET_RE = re.compile(r"assetId=(\S+)")


def _objectives_from(user: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in _OBJECTIVE_RE.finditer(user)]


def _language_from(user: str) -> str:
    """从「全部用 xx 书写」里取语言。取不到就给个默认值。"""
    hit = re.search(r"用\s*([A-Za-z\-]+)\s*书写", user)
    return hit.group(1) if hit else "zh-HK"


class FakeQuestionModel:
    """规则版假模型:按用户消息里的学习目标,每个目标出几道题。"""

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self._decide(messages)

    def _decide(self, messages: list[dict[str, Any]]) -> ChatMessage:
        user = messages[-1]["content"] if messages else ""
        objectives = _objectives_from(user)
        count = 2
        hit = re.search(r"每个学习目标出\s*(\d+)\s*道题", user)
        if hit:
            count = int(hit.group(1))
        language = _language_from(user)

        questions: list[dict[str, Any]] = []
        for objective_id, objective_text in objectives:
            for index in range(count):
                questions.append(
                    self._fake_question(
                        objective_id, objective_text, index, len(questions) + 1, language
                    )
                )

        payload = {"questions": questions}
        return ChatMessage(content=json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _fake_question(
        objective_id: str,
        objective_text: str,
        index: int,
        number: int,
        language: str,
    ) -> dict[str, Any]:
        # 难度铺开 1–5 —— 全是同一个难度的话,组卷的难度约束永远做得到,
        # 那样就演示不出「做不到时会报出来」这条行为
        difficulty = 1 + (number % 5)
        return {
            "id": f"q{number}",
            "type": "mcq",
            "stem": f"关于「{objective_text}」的第 {index + 1} 题({language})?",
            "options": [
                {"id": "A", "text": f"{objective_text}:正确说法"},
                {"id": "B", "text": "看起来像但其实不对的说法"},
                {"id": "C", "text": "另一个干扰项"},
            ],
            "answer": "A",
            "explanation": f"因为「{objective_text}」说的是这样,所以选 A。",
            "difficulty": difficulty,
            "objectiveIds": [objective_id],
            "points": 5 if difficulty <= 3 else 10,
        }


class FakeGlossaryModel:
    """规则版假模型:认得出术语表和替代文本两段 prompt。

    ⚠️ 它靠**系统提示的开头**区分这两件事。这不是优雅做法,但假模型本来
    就得知道自己被问了什么。真模型不需要这个判断 —— 它读得懂自然语言。
    """

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        if self.delay:
            await asyncio.sleep(self.delay)
        return self._decide(messages)

    def _decide(self, messages: list[dict[str, Any]]) -> ChatMessage:
        system = messages[0]["content"] if messages else ""
        user = messages[-1]["content"] if messages else ""
        language = _language_from(user)

        if "替代文本" in system:
            payload = {
                "descriptions": [
                    {
                        "assetId": asset_id,
                        "altText": "这张图说明课程材料里的一个关键关系:改动先隔离,确认后再合回主干。",
                    }
                    for asset_id in _ASSET_RE.findall(user)
                ]
            }
        else:
            payload = {
                "glossary": [
                    {
                        "term": "分支",
                        "plain": "一条独立的开发线,改动不会影响别人。",
                        "objectiveIds": [],
                    },
                    {
                        "term": "合并冲突",
                        "plain": "两个人改了同一个文件的同一行,需要人来决定留哪个。",
                        "objectiveIds": [],
                    },
                ]
            }
        return ChatMessage(content=json.dumps(payload, ensure_ascii=False))
