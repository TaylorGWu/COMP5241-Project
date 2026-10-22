"""The question writer must not turn slide text into a fictitious handout citation."""

import json

from app.llm.client import ChatMessage
from app.schemas.ir import LearningObjective
from app.services.questions import QuestionRequest, build_user_message, generate_questions


class _CitingModel:
    async def complete(self, **_kwargs):
        return ChatMessage(content=json.dumps({"questions": [{
            "id": "q1",
            "type": "short",
            "stem": "What does a branch isolate?",
            "answer": "Changes",
            "objectiveIds": ["LO1"],
            "sourceRefs": [{"materialId": "invented-handout", "page": 3}],
        }]}))


async def test_course_slide_context_cannot_be_cited_as_uploaded_material():
    req = QuestionRequest(
        objectives=[LearningObjective(id="LO1", text="Explain branches")],
        audience="beginners",
        material_context="# Slide 1\nBranches isolate changes.",
    )
    assert "课件正文" in build_user_message(req)
    assert "不要编造讲义" in build_user_message(req)

    result = await generate_questions(req, client=_CitingModel(), model="fake-model")

    assert len(result.question_set.questions) == 1
    assert result.question_set.questions[0].source_refs == []
