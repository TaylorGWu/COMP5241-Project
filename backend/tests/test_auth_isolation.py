"""Real authentication boundaries and concurrent teacher editing contexts."""
import asyncio
import sqlite3
from contextlib import suppress

import httpx
import pytest

from app.api.routes import demo
from app.main import app
from app.services.auth import get_auth_store, safe_next

ORIGIN = "http://localhost:3000"
PASSWORD = "a long example password"
PDF = b"%PDF-1.7\nqualification\n%%EOF"


@pytest.fixture
async def accounts(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0)
    clients = []

    async def create(email, role="instructor", approved=True, qualification=True):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        csrf = (await client.get("/api/auth/csrf")).json()["csrfToken"]
        response = await client.post(
            "/api/auth/register", data=dict(name=email, email=email, password=PASSWORD, role=role),
            files={"qualification": ("qualification.pdf", PDF, "application/pdf")} if role == "instructor" and qualification else None,
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert response.status_code == 201, response.text
        if role == "instructor" and approved:
            with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
                db.execute("UPDATE users SET status='approved' WHERE id=?", (response.json()["user"]["id"],))
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]})
        return client

    yield create
    for client in clients:
        await client.aclose()


async def course(client, title="Private course"):
    response = await client.post("/api/demo/courses", json={"title": title})
    assert response.status_code == 201, response.text
    item = response.json()
    return item, f"/api/demo/courses/{item['id']}/chapters/{item['chapterIds'][0]}"


async def test_parallel_private_images_read_snapshots_without_taking_the_edit_lock(accounts, monkeypatch, tmp_path):
    import io
    from PIL import Image
    from app.services.illustrations import _save_image
    from app.schemas.ir import CoursePackage

    teacher = await accounts('image-owner@example.test')
    stranger = await accounts('image-stranger@example.test')
    item, path = await course(teacher)
    assert (await teacher.post(path + '/generate', json={'topic': 'Private images'})).status_code == 200
    package = (await teacher.get(path)).json()['package']
    image = io.BytesIO()
    Image.new('RGB', (320, 180), 'white').save(image, 'PNG')
    monkeypatch.setattr(demo.settings, 'upload_dir', str(tmp_path / 'uploads'))
    ids = ['il-' + 'a' * 32, 'il-' + 'b' * 32]
    for aid in ids:
        _save_image(demo.settings.upload_dir, image.getvalue(), aid)
        package['assets'].append({'id': aid, 'kind': 'illustration', 'status': 'ready'})
    package['slideDeck']['slides'][0]['visuals'] = [{'id': str(i), 'kind': 'illustration', 'assetId': aid} for i, aid in enumerate(ids)]
    package['slideDeck']['slides'][0]['animation'] = None
    CoursePackage.model_validate(package)
    chid = path.rsplit('/', 1)[1]
    demo.COURSE_WORKSPACE.repository.update_chapter(item['id'], chid, package=package)
    lock = demo._editing_lock('chapter', item['id'], chid)
    await lock.acquire()
    try:
        images = await asyncio.gather(*(teacher.get(path + f'/assets/{aid}.png') for aid in ids))
        assert [response.status_code for response in images] == [200, 200]
        assert all(response.content.startswith(b'\x89PNG') for response in images)
        assert (await stranger.get(path + f'/assets/{ids[0]}.png')).status_code == 404
        edit = await teacher.post(path + '/manual-edit', json={'kind': 'slide', 'target_id': 's1', 'payload': {'title': 'Must remain locked'}})
        assert edit.status_code == 409
    finally:
        lock.release()


@pytest.mark.parametrize("path", ["/courses", "/state", "/export/deck.pptx", "/export/lesson-plan.docx"])
async def test_teacher_router_requires_authentication(path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/demo" + path)).status_code == 401


async def test_role_and_approval_are_rechecked_on_every_teacher_request(accounts):
    student = await accounts("student@example.test", "student")
    pending = await accounts("pending@example.test", approved=False)
    teacher = await accounts("teacher@example.test")
    assert (await student.get("/api/demo/courses")).status_code == 403
    admin = get_auth_store().create_user(name="Admin", email="admin@example.test", password=PASSWORD, role="admin")
    admin_cookie, admin_csrf = get_auth_store().new_session(admin, None)
    student.cookies.set("coursework_session", admin_cookie)
    student.headers["X-CSRF-Token"] = admin_csrf
    for client in (student, pending):
        assert (await client.get("/api/demo/courses")).status_code == 403
        assert (await client.post("/api/demo/reset")).status_code == 403
    assert (await teacher.get("/api/demo/courses")).status_code == 200
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("UPDATE users SET status='rejected' WHERE email='teacher@example.test'")
    assert (await teacher.get("/api/demo/state")).status_code == 403


async def test_courses_are_created_owned_and_legacy_courses_stay_unowned(accounts):
    legacy = demo.COURSE_WORKSPACE.create_course(title="Legacy", description="", audience="", duration_min=45)
    first, second = await accounts("one@example.test"), await accounts("two@example.test")
    own, _ = await course(first)
    assert [item["id"] for item in (await first.get("/api/demo/courses")).json()["courses"]] == [own["id"]]
    assert (await second.get("/api/demo/courses")).json() == {"courses": []}
    assert (await first.get(f"/api/demo/courses/{legacy.id}")).status_code == 404
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        assert db.execute("SELECT COUNT(*) FROM course_owners WHERE course_id=?", (own["id"],)).fetchone()[0] == 1


async def test_other_teacher_cannot_read_mutate_export_or_render_course(accounts):
    first, second = await accounts("one@example.test"), await accounts("two@example.test")
    item, path = await course(first)
    assert (await first.post(path + "/generate", json={"topic": "Git branching"})).status_code == 200
    attempts = [
        ("GET", f"/api/demo/courses/{item['id']}", None),
        ("GET", f"/api/demo/courses/{item['id']}/analytics", None),
        ("GET", f"/api/demo/courses/{item['id']}/activity", None),
        ("PATCH", f"/api/demo/courses/{item['id']}", {"title": "Stolen"}),
        ("GET", path, None), ("POST", path + "/activate", {}),
        ("POST", path + "/generate/stream", {"topic": "Secret"}),
        ("POST", path + "/edit/stream", {"message": "Change it"}),
        ("POST", path + "/manual-edit", {"kind": "slide", "target_id": "s1", "payload": {"title": "Stolen"}}),
        ("GET", path + "/export/deck.pptx", None),
        ("GET", path + "/export/lesson-plan.docx", None),
        ("GET", path + "/export/exam-paper.docx", None),
        ("GET", path + "/assets/as-1.svg", None),
        ("GET", path + "/assets/as-1.png", None),
    ]
    for method, url, payload in attempts:
        response = await second.request(method, url, json=payload)
        assert response.status_code == 404, (method, url, response.text)
    assert (await second.get("/api/demo/state")).json() == {"has_package": False}


async def test_interleaved_chapters_do_not_change_another_tabs_or_sessions_active_state(accounts):
    first, second = await accounts("one@example.test"), await accounts("two@example.test")
    item, first_path = await course(first)
    chapter = (await first.post(f"/api/demo/courses/{item['id']}/chapters", json={"title": "Second"})).json()
    second_path = f"/api/demo/courses/{item['id']}/chapters/{chapter['id']}"
    _, foreign_path = await course(second)
    for client, path, topic in ((first, first_path, "First chapter"), (first, second_path, "Second chapter"), (second, foreign_path, "Other teacher")):
        assert (await client.post(path + "/generate", json={"topic": topic})).status_code == 200
    assert (await first.post(first_path + "/activate")).status_code == 200
    assert (await second.post(foreign_path + "/activate")).status_code == 200
    assert (await first.post(second_path + "/questions", json={})).status_code == 200
    assert (await first.get(second_path + "/export/lesson-plan.docx")).status_code == 200
    legacy = (await first.get("/api/demo/state")).json()["package"]
    assert legacy["project"]["meta"]["title"] == "First chapter"
    assert legacy.get("questionSet") is None
    await first.post("/api/demo/manual-edit", json={"kind": "slide", "target_id": "s1", "payload": {"title": "Changed only first"}})
    assert (await first.get(first_path)).json()["package"]["slideDeck"]["slides"][0]["title"] == "Changed only first"
    assert (await first.get(second_path)).json()["package"]["slideDeck"]["slides"][0]["title"] != "Changed only first"
    assert (await second.get("/api/demo/state")).json()["package"]["project"]["meta"]["title"] == "Other teacher"


async def test_guessed_patch_cannot_apply_or_reject_another_chapters_proposal(accounts):
    first, second = await accounts("one@example.test"), await accounts("two@example.test")
    _, first_path = await course(first)
    _, second_path = await course(second)
    for client, path in ((first, first_path), (second, second_path)):
        assert (await client.post(path + "/generate", json={"topic": "Git branches"})).status_code == 200
    proposed = await first.post(first_path + "/edit", json={"message": "Make slide 2 easier"})
    patch_id = proposed.json()["patches"][0]["id"]
    for action in ("apply", "reject"):
        assert (await second.post(second_path + "/" + action, json={"patch_id": patch_id})).status_code == 404
    assert (await first.post(first_path + "/apply", json={"patch_id": patch_id})).status_code == 200


@pytest.mark.parametrize("value", ["/courses/../../admin", "/courses/%2e%2e/admin", "/courses/%252e%252e/admin", "/courses/a/%2F..%2F../admin"])
def test_backend_safe_next_rejects_dot_segments_and_encoded_separators(value):
    assert safe_next(value, {"role": "instructor", "status": "approved"}) == "/courses"


async def test_every_teacher_route_authenticates_before_body_or_resource_resolution():
    checked = 0
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for route in demo.router.routes:
            url = "/api" + route.path.replace("{course_id}", "missing").replace("{chapter_id}", "missing").replace("{asset_id}", "missing")
            for method in route.methods:
                assert (await client.request(method, url)).status_code == 401, (method, url)
                checked += 1
    assert checked >= 40


async def test_unsubmitted_instructor_cannot_access_any_teacher_route(accounts):
    instructor = await accounts("unsubmitted@example.test", approved=False, qualification=False)
    user = (await instructor.get("/api/auth/me")).json()["user"]
    assert user["status"] == "pending"
    assert user["qualificationSubmitted"] is False
    checked = 0
    for route in demo.router.routes:
        url = "/api" + route.path.replace("{course_id}", "missing").replace("{chapter_id}", "missing").replace("{asset_id}", "missing")
        for method in route.methods:
            assert (await instructor.request(method, url)).status_code == 403, (method, url)
            checked += 1
    assert checked >= 40


def test_production_state_proxy_has_no_global_fallback():
    token = demo._STATE_CONTEXT.set(None)
    try:
        with pytest.raises(RuntimeError, match="authenticated request context"):
            _ = demo.STATE.package
    finally:
        demo._STATE_CONTEXT.reset(token)


async def test_teacher_mutations_require_origin_and_session_bound_csrf(accounts):
    teacher = await accounts("teacher@example.test")
    teacher.headers.pop("X-CSRF-Token")
    assert (await teacher.post("/api/demo/courses", json={"title": "No CSRF"})).status_code == 403
    teacher.headers["X-CSRF-Token"] = (await teacher.get("/api/auth/me")).json()["csrfToken"]
    teacher.headers["Origin"] = "https://foreign.example"
    assert (await teacher.post("/api/demo/reset")).status_code == 403


async def test_same_account_separate_sessions_keep_separate_legacy_packages(accounts):
    teacher = await accounts("teacher@example.test")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as other:
        csrf = (await other.get("/api/auth/csrf")).json()["csrfToken"]
        login = await other.post("/api/auth/login", json=dict(email="teacher@example.test", password=PASSWORD), headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        other.headers.update({"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrfToken"]})
        await teacher.post("/api/demo/generate", json={"topic": "First session"})
        await other.post("/api/demo/generate", json={"topic": "Second session"})
        assert (await teacher.get("/api/demo/state")).json()["package"]["project"]["meta"]["title"] == "First session"
        assert (await other.get("/api/demo/state")).json()["package"]["project"]["meta"]["title"] == "Second session"
        await other.post("/api/demo/reset")
        assert (await teacher.get("/api/demo/state")).json()["has_package"] is True


def stream_result(response):
    import json
    assert response.status_code == 200, response.text
    for frame in response.text.split("\n\n"):
        if frame.startswith("event: result\n"):
            return json.loads(frame.split("data: ", 1)[1])
    raise AssertionError(response.text)


async def test_interleaved_edit_streams_capture_their_own_package_and_lock(accounts, monkeypatch):
    first, second = await accounts("one@example.test"), await accounts("two@example.test")
    _, first_path = await course(first)
    _, second_path = await course(second)
    for client, path, topic in ((first, first_path, "First teacher"), (second, second_path, "Second teacher")):
        await client.post(path + "/generate", json={"topic": topic})
    started, release = asyncio.Event(), asyncio.Event()
    real_edit = demo.edit_artifact

    async def delayed_edit(**kwargs):
        if kwargs["package"].project.meta.title == "First teacher":
            started.set()
            await release.wait()
        return await real_edit(**kwargs)

    monkeypatch.setattr(demo, "edit_artifact", delayed_edit)
    first_stream = asyncio.create_task(first.post(first_path + "/edit/stream", json={"message": "Make slide 2 easier"}))
    try:
        await asyncio.wait_for(started.wait(), 2)
        busy = await first.post(first_path + "/manual-edit", json={"kind": "slide", "target_id": "s1", "payload": {"title": "Must not race"}})
        assert busy.status_code == 409
        second_result = stream_result(await second.post(second_path + "/edit/stream", json={"message": "Make slide 2 easier"}))
        assert second_result["package"]["project"]["meta"]["title"] == "Second teacher"
    finally:
        release.set()
        first_response = await first_stream
    first_result = stream_result(first_response)
    assert first_result["package"]["project"]["meta"]["title"] == "First teacher"
    assert first_result["patches"][0]["id"] != second_result["patches"][0]["id"]
    assert (await first.get(first_path)).status_code == 200


async def test_cancelled_generation_finishes_cleanup_before_unlocking_chapter(accounts, monkeypatch):
    teacher = await accounts("teacher@example.test")
    _, path = await course(teacher)
    started, cleaned = asyncio.Event(), asyncio.Event()
    real_generation = demo.generate_course

    async def delayed_generation(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    monkeypatch.setattr(demo, "generate_course", delayed_generation)
    stream = asyncio.create_task(teacher.post(path + "/generate/stream", json={"topic": "Cancelled"}))
    await asyncio.wait_for(started.wait(), 2)
    stream.cancel()
    with suppress(asyncio.CancelledError):
        await stream
    assert cleaned.is_set()
    chapter = await teacher.get(path)
    assert chapter.status_code == 200, chapter.text
    assert chapter.json()["status"] == "failed"
    monkeypatch.setattr(demo, "generate_course", real_generation)
    assert (await teacher.post(path + "/generate", json={"topic": "Retry"})).status_code == 200


async def test_ownership_creation_rolls_back_course_and_chapter_if_assignment_fails(accounts, monkeypatch):
    teacher = await accounts("teacher@example.test")
    repository = demo.COURSE_WORKSPACE.repository
    # A failed ownership INSERT must never leave an unowned HTTP-created course.
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("CREATE TRIGGER fail_assignment BEFORE INSERT ON course_owners BEGIN SELECT RAISE(ABORT, 'assignment failed'); END")
    with pytest.raises(sqlite3.IntegrityError):
        await teacher.post("/api/demo/courses", json={"title": "Rollback"})
    assert repository.list_courses() == []
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        assert db.execute("SELECT COUNT(*) FROM chapters").fetchone()[0] == 0


async def test_explicit_workspace_reset_invalidates_cached_auth_schema(accounts):
    await accounts("teacher@example.test")
    demo.reset_course_workspace()
    # Resetting the same path must recreate auth tables instead of reusing a
    # cached AuthStore whose old database file has been removed.
    user = await accounts("fresh@example.test")
    assert (await user.get("/api/demo/courses")).status_code == 200


async def test_sse_disconnect_cancels_model_and_releases_chapter_lock(accounts, monkeypatch):
    import json
    teacher = await accounts("teacher@example.test")
    _, path = await course(teacher)
    started, disconnected, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def blocked_model(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    monkeypatch.setattr(demo, "generate_course", blocked_model)
    payload = json.dumps({"topic": "Disconnected"}).encode()
    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": payload, "more_body": False}
        await disconnected.wait()
        return {"type": "http.disconnect"}

    messages = []

    async def send(message):
        messages.append(message)

    scope = dict(type="http", asgi={"version": "3.0", "spec_version": "2.0"}, http_version="1.1",
                 method="POST", scheme="http", path=path + "/generate/stream", query_string=b"",
                 headers=[(b"cookie", ("coursework_session=" + teacher.cookies.get("coursework_session")).encode()),
                          (b"origin", ORIGIN.encode()), (b"x-csrf-token", teacher.headers["X-CSRF-Token"].encode()),
                          (b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
                 server=("test", 80), client=("127.0.0.1", 1234))
    stream = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(started.wait(), 2)
    disconnected.set()
    await asyncio.wait_for(stream, 2)
    assert cleaned.is_set()
    assert messages[0]["status"] == 200
    chapter = await teacher.get(path)
    assert chapter.status_code == 200, chapter.text
    assert chapter.json()["status"] == "failed"


async def test_stream_failure_is_an_error_frame_and_unlocks_the_chapter(accounts, monkeypatch):
    teacher = await accounts("teacher@example.test")
    _, path = await course(teacher)

    async def failed_model(*args, **kwargs):
        raise RuntimeError("Offline model failed")

    monkeypatch.setattr(demo, "generate_course", failed_model)
    response = await teacher.post(path + "/generate/stream", json={"topic": "Failure"})
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "event: done" not in response.text
    assert (await teacher.get(path)).json()["status"] == "failed"


@pytest.mark.parametrize("streaming", [False, True])
async def test_legacy_generation_after_activation_creates_a_session_package_without_replacing_chapter(accounts, streaming):
    teacher = await accounts("teacher@example.test")
    _, path = await course(teacher)
    await teacher.post(path + "/generate", json={"topic": "Saved chapter"})
    await teacher.post(path + "/activate")
    response = await teacher.post("/api/demo/generate" + ("/stream" if streaming else ""), json={"topic": "Session draft"})
    assert response.status_code == 200
    state = (await teacher.get("/api/demo/state")).json()
    assert state["package"]["project"]["meta"]["title"] == "Session draft"
    assert (await teacher.get(path)).json()["package"]["project"]["meta"]["title"] == "Saved chapter"


async def test_deleted_legacy_selection_returns_404_and_can_be_reset(accounts):
    teacher = await accounts("teacher@example.test")
    item, path = await course(teacher)
    await teacher.post(path + "/generate", json={"topic": "Selected"})
    await teacher.post(path + "/activate")
    await teacher.post(f"/api/demo/courses/{item['id']}/chapters", json={"title": "Remaining"})
    assert (await teacher.delete(path)).status_code == 204
    assert (await teacher.get("/api/demo/state")).status_code == 404
    assert (await teacher.post("/api/demo/reset")).status_code == 200
    assert (await teacher.get("/api/demo/state")).json() == {"has_package": False}
