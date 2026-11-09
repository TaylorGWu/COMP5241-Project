"""Learner help that is grounded in the page in front of them.

This is deliberately **not** a general chat tutor. The only material the model
sees is the published snapshot's current slide, the chapter title and the course
objectives - it cannot browse the rest of the course, and it is told to admit when
the slide does not cover the question. Everything it reads is the same snapshot the
learner is looking at, so an answer can never quote unpublished teacher work.
"""
from __future__ import annotations

import json
from typing import Any

from app.llm.client import ChatClient

SYSTEM = """You are a study helper inside one slide of a course.

Rules:
- Answer only from the slide and the course objectives given below.
- If the slide does not cover it, say so plainly and name what to read instead.
- Explain the idea; do not simply hand over the answer to a practice question.
- Keep it under 120 words. Write in the language of the question.
- Plain prose only: no markdown, no headings, no bullet symbols."""


def context_for(snapshot: dict[str, Any], chapter_id: str, slide_id: str) -> dict[str, Any]:
    """Pick the slide the learner is looking at plus the objectives it serves."""
    chapter = next((item for item in snapshot.get('chapters', []) if item.get('id') == chapter_id), None)
    if chapter is None:
        raise KeyError('chapter was not found in the publication')
    slide = next((item for item in chapter.get('slides', []) if item.get('id') == slide_id), None)
    if slide is None:
        raise KeyError('slide was not found in the publication')
    objective_ids = {str(item) for item in slide.get('objectiveIds', [])}
    objectives = [item for item in snapshot.get('learningObjectives', []) if isinstance(item, dict)]
    return {
        'course': snapshot.get('title', ''),
        'chapter': chapter.get('title', ''),
        'slide': {
            'title': slide.get('title', ''),
            'bullets': [str(item) for item in slide.get('bullets', [])],
            'layout': slide.get('layout', ''),
        },
        'objectives': [item for item in objectives if item.get('id') in objective_ids] or objectives,
    }


def build_messages(context: dict[str, Any], question: str) -> list[dict[str, Any]]:
    """The whole prompt: system rules, the grounding material, then the question."""
    material = json.dumps(context, ensure_ascii=False, indent=2)
    return [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': f'Material:\n{material}\n\nQuestion: {question.strip()}'},
    ]


async def answer(client: ChatClient, model: str, context: dict[str, Any], question: str, temperature: float = 0.3) -> str:
    reply = await client.complete(model=model, messages=build_messages(context, question), temperature=temperature)
    return (reply.content or '').strip()
