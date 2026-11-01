from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import demo
from app.services.auth import get_auth_store
import sqlite3

ORIGIN = 'http://localhost:3000'
PASSWORD = 'a long example password'


def signed_in(client, email, role):
    store = get_auth_store()
    user = store.create_user(name=email, email=email, password=PASSWORD, role=role)
    if role == 'instructor':
        with store.connection() as db:
            db.execute("UPDATE users SET status='approved' WHERE id=?", (user['id'],))
    token, csrf = store.new_session(user, None)
    client.cookies.set('coursework_session', token)
    client.headers.update({'Origin': ORIGIN, 'X-CSRF-Token': csrf})
    return user


def test_student_home_requires_an_authenticated_session():
    with TestClient(app) as client:
        assert client.get('/api/student/home').status_code == 401


def test_student_mutations_require_csrf_and_disallow_foreign_roles():
    with TestClient(app) as student, TestClient(app) as teacher:
        signed_in(student, 'student@example.test', 'student')
        signed_in(teacher, 'teacher@example.test', 'instructor')
        student.headers.pop('X-CSRF-Token')
        assert student.put('/api/student/profile', json={'background': 'x', 'goal': 'y'}).status_code == 403
        assert teacher.put('/api/student/profile', json={'background': 'x', 'goal': 'y'}).status_code == 403


def test_published_course_enrollment_learning_and_analytics():
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git', 'durationMin': 45}).json()
        course_id, chapter_id = course['id'], course['chapterIds'][0]
        path = f'/api/demo/courses/{course_id}/chapters/{chapter_id}'
        package = {'slideDeck': {'slides': [{'id': 's1', 'layout': 'bullets', 'title': 'Branches', 'bullets': ['Isolate work'], 'speakerNotes': 'private notes'}]},
                   'questionSet': {'questions': [{'id': 'q1', 'type': 'mcq', 'stem': 'Branch?', 'options': [{'id': 'A', 'text': 'Isolate'}, {'id': 'B', 'text': 'Overwrite'}], 'answer': 'A', 'explanation': 'A branch isolates work.'}]}}
        assert teacher.patch(path, json={'status': 'ready', 'package': package}).status_code == 200
        assert student.get('/api/student/home').json()['courses'] == []
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        assert student.put('/api/student/profile', json={'background': 'Git beginner', 'goal': 'Learn Git'}).status_code == 200
        assert student.get('/api/student/home').json()['recommendation']['courseId'] == course_id
        assert teacher.get('/api/student/home').status_code == 403
        assert student.post(f'/api/student/courses/{course_id}/enroll', json={}).status_code == 200
        imported = teacher.post(f'/api/demo/courses/{course_id}/students/import', json={'rows': [{'row': 2, 'name': 'Legacy Student', 'email': 'student@example.test'}]})
        assert imported.status_code == 200
        legacy_id = imported.json()['students'][0]['id']
        demo.COURSE_WORKSPACE.record_attempt(course_id, legacy_id, completion_percent=100, answers={'q1': False})
        chapter_url = f'/api/student/courses/{course_id}/chapters/{chapter_id}'
        chapter = student.get(chapter_url)
        assert chapter.status_code == 200
        assert 'private notes' not in chapter.text
        assert 'answer' not in chapter.text
        assert student.post(chapter_url + '/progress', json={'slideId': 's1'}).status_code == 200
        assert student.post(chapter_url + '/progress', json={'slideId': 'foreign'}).status_code == 404
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'foreign', 'submissionId': 'invalid'}).status_code == 422
        result = student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1'})
        assert result.status_code == 200
        assert result.json()['result']['correct'] is False
        assert result.json()['result']['correctOptionId'] == 'A'
        assert result.json()['progress']['completed'] is True
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1'}).json()['result']['attemptId'] == result.json()['result']['attemptId']
        retry = student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'A', 'submissionId': 'submission-2'})
        assert retry.json()['result']['correct'] is True
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1'}).json()['result']['attemptId'] == result.json()['result']['attemptId']
        from app.services.auth import _store_at
        _store_at.cache_clear()
        demo.reload_course_workspace()
        resumed = student.get(chapter_url).json()
        assert resumed['progress']['lastSlideId'] == 's1'
        assert resumed['results']['q1']['selectedOptionId'] == 'A'
        analytics = teacher.get(f'/api/demo/courses/{course_id}/analytics').json()
        assert analytics['enrolledCount'] == 1
        assert analytics['mostMissed'] == []
        package['questionSet']['questions'][0]['stem'] = 'A changed question?'
        assert teacher.patch(path, json={'package': package, 'status': 'ready'}).status_code == 200
        assert student.get(chapter_url).json()['chapter']['questions'][0]['stem'] == 'Branch?'
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        changed = student.get(chapter_url).json()
        assert changed['chapter']['questions'][0]['stem'] == 'A changed question?'
        assert changed['results'] == {}
        assert changed['progress']['completed'] is False
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'A', 'submissionId': 'submission-1'}).status_code == 409


def test_admin_suspends_and_restores_course_and_protects_accounts():
    with TestClient(app) as admin, TestClient(app) as teacher, TestClient(app) as student:
        admin_user = signed_in(admin, 'admin@example.test', 'admin')
        signed_in(teacher, 'teacher@example.test', 'instructor')
        learner = signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}', json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': 's1', 'title': 'Git', 'layout': 'bullets'}]}}})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200
        assert student.get('/api/admin/users').status_code == 403
        assert admin.patch(f"/api/admin/users/{admin_user['id']}", json={'active': False}).status_code == 409
        assert admin.post(f'/api/admin/courses/{cid}/archive', json={'reason': 'Review needed'}).status_code == 200
        assert student.get(f'/api/student/courses/{cid}').status_code == 404
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 409
        assert admin.post(f'/api/admin/courses/{cid}/restore', json={}).status_code == 200
        assert student.get(f'/api/student/courses/{cid}').status_code == 200
        assert admin.patch(f"/api/admin/users/{learner['id']}", json={'active': False}).status_code == 200
        assert student.get('/api/student/home').status_code == 401
        assert admin.patch(f"/api/admin/users/{learner['id']}", json={'active': True, 'role': 'instructor'}).json()['user']['status'] == 'pending'
        assert student.get('/api/auth/me').status_code == 401
        audit = admin.get('/api/admin/audit').json()['events']
        assert len(audit) >= 3
        assert any(event['kind'] == 'publish' and event['courseId'] == cid and event['at'] is None and event['model'] is None for event in audit)


def test_invite_and_private_snapshot_asset_boundaries():
    with TestClient(app) as teacher, TestClient(app) as student, TestClient(app) as outsider:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        signed_in(outsider, 'other@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        package = {'slideDeck': {'slides': [{'id': 's1', 'layout': 'diagram', 'title': 'Flow', 'bullets': ['Safe', {'answer': 'SECRET'}], 'statusGroups': [{'title': 'Group', 'items': [{'label': 'Item', 'answer': 'SECRET'}], 'speakerNotes': 'SECRET'}], 'visuals': [{'id': 'v1', 'kind': 'diagram', 'assetId': 'asset1'}]}]}, 'assets': [{'id': 'asset1', 'kind': 'diagram', 'status': 'ready', 'spec': {'code': 'graph LR; A-->B'}, 'altText': 'A to B'}, {'id': 'secret', 'kind': 'diagram', 'status': 'ready', 'spec': {'code': 'graph LR; X-->Y'}}]}
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}', json={'status': 'ready', 'package': package})
        teacher.post(f'/api/demo/courses/{cid}/publish')
        invite = teacher.post(f'/api/demo/courses/{cid}/invites', json={}).json()['code']
        assert student.post('/api/student/join', json={'code': invite}).json() == {'courseId': cid}
        assert student.post('/api/student/join', json={'code': invite}).status_code == 200
        assert student.post('/api/student/join', json={'code': 'invalid'}).status_code == 404
        asset = f'/api/student/courses/{cid}/chapters/{chapter_id}/assets/asset1.svg'
        assert outsider.get(asset).status_code == 403
        assert student.get(asset).status_code == 200
        assert student.get(asset.replace('asset1', 'secret')).status_code == 404
        chapter = student.get(f'/api/student/courses/{cid}/chapters/{chapter_id}').json()['chapter']
        assert chapter['slides'][0]['visuals'][0]['url'] == asset
        assert 'SECRET' not in str(chapter)


def test_upgrade_seeds_only_existing_published_courses_and_preserves_backup(tmp_path):
    from app.services.auth import AuthStore
    from app.services.sqlite_workspace import SQLiteCourseRepository
    path = tmp_path / 'legacy.db'
    repo = SQLiteCourseRepository(path)
    course = repo.create_course(title='Published', description='', audience='Beginner', duration_min=45, language='en')
    draft = repo.create_course(title='Draft', description='', audience='Beginner', duration_min=45, language='en')
    for item in (course, draft):
        repo.update_chapter(item.id, item.chapter_ids[0], status='ready', package={'slideDeck': {'slides': [{'id': 's1', 'title': 'One'}]}})
    repo.update_course(course.id, status='published')
    store = AuthStore(path)
    with store.connection() as db:
        assert [r[0] for r in db.execute('SELECT course_id FROM portal_publications')] == [course.id]
    with sqlite3.connect(next(tmp_path.glob('*.bak'))) as backup:
        assert backup.execute('SELECT count(*) FROM courses').fetchone()[0] == 2
    AuthStore(path)
    with store.connection() as db:
        assert db.execute('SELECT count(*) FROM portal_publications').fetchone()[0] == 1


def test_last_location_follows_latest_visit_and_removed_slides_do_not_count():
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, first = course['id'], course['chapterIds'][0]
        second = teacher.post(f'/api/demo/courses/{cid}/chapters', json={'title': 'Second'}).json()['id']
        for chapter_id, slide_id in ((first, 's1'), (second, 's2')):
            teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}', json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': slide_id, 'title': 'Read', 'layout': 'bullets'}]}}})
        teacher.post(f'/api/demo/courses/{cid}/publish')
        student.post(f'/api/student/courses/{cid}/enroll', json={})
        for chapter_id, slide_id in ((second, 's2'), (first, 's1')):
            student.post(f'/api/student/courses/{cid}/chapters/{chapter_id}/progress', json={'slideId': slide_id})
        summary = student.get('/api/student/home').json()['courses'][0]
        assert summary['lastChapterId'] == first
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{first}', json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': 's3', 'title': 'New', 'layout': 'bullets'}]}}})
        teacher.post(f'/api/demo/courses/{cid}/publish')
        summary = student.get('/api/student/home').json()['courses'][0]
        assert summary['lastChapterId'] == second
        assert summary['completionPercent'] == 50
        teacher.post(f'/api/demo/courses/{cid}/unpublish')
        assert student.get(f'/api/student/courses/{cid}').status_code == 404
        assert teacher.get(f'/api/demo/courses/{cid}/analytics').json()['enrolledCount'] == 1


def test_invalid_ready_chapter_does_not_break_other_published_chapters():
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, first = course['id'], course['chapterIds'][0]
        second = teacher.post(f'/api/demo/courses/{cid}/chapters', json={'title': 'Valid'}).json()['id']
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{first}', json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'title': 'Missing ID'}]}}})
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{second}', json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': 's1', 'title': 'Read', 'visuals': ['broken']}]}}})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).json()['chapters'][0]['id'] == second
        assert student.get(f'/api/student/courses/{cid}/chapters/{second}').json()['chapter']['slides'][0]['visuals'] == []
