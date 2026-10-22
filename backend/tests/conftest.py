"""共享测试夹具。"""

from __future__ import annotations

import pytest
import httpx
import sqlite3

from app.api.routes import demo
from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


@pytest.fixture(autouse=True)
def isolate_demo_workspace(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Never let tests read, reset, or write a developer's local SQLite data."""
    monkeypatch.setattr(demo, "TEACHER_WORKSPACE_DB", tmp_path / "teacher-workspace.db")
    monkeypatch.setattr(demo, "DEMO_WORKSPACE_PATH", tmp_path / "legacy-workspace.json")
    # Direct service tests explicitly bind their own state. HTTP routes always
    # replace it with their authenticated context; production has no fallback.
    token = demo._STATE_CONTEXT.set(demo._State())
    try:
        demo.reset_course_workspace()
        yield
    finally:
        demo._STATE_CONTEXT.reset(token)


@pytest.fixture(autouse=True)
def authenticated_teacher_regressions(request, monkeypatch, isolate_demo_workspace):
    """Old teacher API suites now send a real temporary session and valid CSRF.

    Authentication/isolation suites deliberately do not use this fixture: they
    exercise missing credentials, public registration and role changes directly.
    """
    if request.node.path.name not in {
        "test_teacher_courses_api.py", "test_teacher_endpoints.py", "test_progress_stream.py",
        "test_mermaid_assets.py", "test_demo_workspace_sqlite.py",
    }:
        return
    from app.services.auth import SESSION_COOKIE, get_auth_store

    original = httpx.AsyncClient.__init__
    sessions = {}

    def authenticated_client(client, *args, **kwargs):
        store = get_auth_store()
        key = str(demo.TEACHER_WORKSPACE_DB)
        credentials = sessions.get(key)
        if credentials is None or store.session(credentials[0]) is None:
            user = store.create_user(
                name="Regression instructor", email="regression@example.test",
                password="a long regression password", role="instructor",
                qualification=("qualification.pdf", "application/pdf", b"%PDF-1.7\nexample\n%%EOF"),
            )
            with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
                db.execute("UPDATE users SET status='approved' WHERE id=?", (user["id"],))
            credentials = store.new_session(user, None)
            sessions[key] = credentials
        cookies = dict(kwargs.pop("cookies", {}) or {})
        cookies.setdefault(SESSION_COOKIE, credentials[0])
        headers = {"Origin": "http://localhost:3000", "X-CSRF-Token": credentials[1], **dict(kwargs.pop("headers", {}) or {})}
        original(client, *args, cookies=cookies, headers=headers, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", authenticated_client)


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
