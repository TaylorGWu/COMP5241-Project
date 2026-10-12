"""共享测试夹具。"""

from __future__ import annotations

import pytest

from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


@pytest.fixture
async def pipeline_result():
    """跑一遍完整 L1,拿一个真实的 CoursePackage。

    比手工拼一个 IR 更可靠 —— 手拼的容易漏掉流水线实际会产出的形状。
    """
    return await generate_course(
        GenerationRequest(topic="Git 分支", audience="初学者", duration_min=45),
        PipelineDeps(
            client=FakeSectionModel(),
            model="fake-model",
            search_materials=fake_search,
            make_diagram=fake_make_diagram,
            request_illustration=fake_illustration,
        ),
    )
