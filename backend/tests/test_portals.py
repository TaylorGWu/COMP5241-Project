import json

from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import demo
from app.services.auth import get_auth_store
from app.services.student_learning import mcqs
import sqlite3

ORIGIN = 'http://localhost:3000'
PASSWORD = 'a long example password'


def test_malformed_mcq_identifiers_are_excluded_without_losing_valid_questions():
    base = {'type': 'mcq', 'stem': 'Question', 'options': [{'id': 'A', 'text': 'a'}, {'id': 'B', 'text': 'b'}], 'answer': 'A'}
    questions = [base | {'id': ''}, base | {'id': 'dup'}, base | {'id': 'dup'}, base | {'id': 'bad', 'options': [{'id': '', 'text': 'a'}, {'id': 'A', 'text': 'b'}]}, base | {'id': 'good'}]
    assert [q['id'] for q in mcqs({'questions': questions})] == ['good']


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


def test_admin_overview_reports_real_disjoint_categories_and_course_memberships():
    # Catches duplicate suspended/published buckets and invented/unique-user totals.
    with TestClient(app) as admin, TestClient(app) as teacher, TestClient(app) as student:
        signed_in(admin, 'dashboard-admin@example.test', 'admin')
        signed_in(teacher, 'dashboard-teacher@example.test', 'instructor')
        signed_in(student, 'dashboard-student@example.test', 'student')
        ids = []
        for title in ['Published', 'Suspended', 'Unpublished']:
            course = teacher.post('/api/demo/courses', json={'title': title}).json()
            ids.append(course['id'])
            if title != 'Unpublished':
                teacher.patch(f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}", json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': 's1', 'title': title}]}}})
                assert teacher.post(f"/api/demo/courses/{course['id']}/publish").status_code == 200
                assert student.post(f"/api/student/courses/{course['id']}/enroll", json={}).status_code == 200
        admin.post(f'/api/admin/courses/{ids[1]}/archive', json={'reason': 'Review'})
        data = admin.get('/api/admin/overview').json()
        assert data['userRoles'] == [
            {'role': 'student', 'count': 1}, {'role': 'instructor', 'count': 1}, {'role': 'admin', 'count': 1}]
        assert data['courseStates'] == [
            {'state': 'published', 'count': 1}, {'state': 'unpublished', 'count': 1}, {'state': 'suspended', 'count': 1}]
        assert (data['users'], data['courses'], data['publishedCourses'], data['enrollments']) == (3, 3, 1, 2)
        assert [(r['courseId'], r['count']) for r in data['courseEnrollments']] == [(ids[0], 1), (ids[1], 1), (ids[2], 0)]
        assert set(data['courseEnrollments'][0]) == {'courseId', 'title', 'courseCode', 'count'}
        assert 'email' not in str(data)
        listed = admin.get('/api/admin/courses').json()['courses']
        assert [(c['id'], c['enrollmentCount']) for c in listed] == [(ids[0], 1), (ids[1], 1), (ids[2], 0)]
        assert student.get('/api/admin/overview').status_code == 403
        assert teacher.get('/api/admin/overview').status_code == 403
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/admin/overview').status_code == 401


def test_admin_overview_empty_course_categories_remain_zero():
    with TestClient(app) as admin:
        signed_in(admin, 'empty-dashboard@example.test', 'admin')
        data = admin.get('/api/admin/overview').json()
        assert data['courses'] == data['enrollments'] == 0
        assert data['courseEnrollments'] == []
        assert data['courseStates'] == [
            {'state': 'published', 'count': 0}, {'state': 'unpublished', 'count': 0}, {'state': 'suspended', 'count': 0}]


def test_stale_question_revision_is_rejected_before_first_submission():
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'revision-teacher@example.test', 'instructor')
        signed_in(student, 'revision-student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Revision'}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        path = f'/api/demo/courses/{cid}/chapters/{chapter_id}'
        url = f'/api/student/courses/{cid}/chapters/{chapter_id}'
        question = {'id': 'q1', 'type': 'mcq', 'stem': 'Original?', 'options': [{'id': 'A', 'text': 'First'}, {'id': 'B', 'text': 'Second'}], 'answer': 'A'}
        package = {'slideDeck': {'slides': [{'id': 's1', 'layout': 'bullets', 'title': 'Slide'}]}, 'questionSet': {'questions': [question]}}
        assert teacher.patch(path, json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200
        old = student.get(url).json()['chapter']['questions'][0]['revision']
        question['stem'] = 'Changed?'
        assert teacher.post(f'/api/demo/courses/{cid}/unpublish').status_code == 200
        assert teacher.patch(path, json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        payload = {'questionId': 'q1', 'optionId': 'A', 'submissionId': 'first', 'questionRevision': old}
        assert student.post(url + '/attempts', json=payload).status_code == 409
        assert student.get(url).json()['results'] == {}
        question['options'][0]['id'] = 'C'
        question['answer'] = 'C'
        assert teacher.post(f'/api/demo/courses/{cid}/unpublish').status_code == 200
        assert teacher.patch(path, json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(url + '/attempts', json=payload).status_code == 409
        payload['optionId'] = 'C'
        payload['questionRevision'] = student.get(url).json()['chapter']['questions'][0]['revision']
        first = student.post(url + '/attempts', json=payload)
        assert first.status_code == 200
        assert student.post(url + '/attempts', json=payload).json()['result']['attemptId'] == first.json()['result']['attemptId']


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
        package = {'slideDeck': {'slides': [{'id': 's1', 'layout': 'bullets', 'title': 'Branches', 'bullets': ['Isolate work'], 'speakerNotes': 'private notes', 'objectiveIds': ['LO1'], 'teachingRole': 'explain'}]},
                   'questionSet': {'questions': [{'id': 'q1', 'type': 'mcq', 'stem': 'Branch?', 'options': [{'id': 'A', 'text': 'Isolate'}, {'id': 'B', 'text': 'Overwrite'}], 'answer': 'A', 'explanation': 'A branch isolates work.', 'objectiveIds': ['LO1']}]}}
        assert teacher.patch(path, json={'status': 'ready', 'package': package}).status_code == 200
        assert student.get('/api/student/home').json()['courses'] == []
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        assert student.put('/api/student/profile', json={'background': 'Git beginner', 'goal': 'Learn Git'}).status_code == 200
        saved = student.put('/api/student/profile', json={'background': 'Git beginner', 'goal': 'Learn Git', 'weeklyMinutes': 90})
        assert saved.json()['profile']['weeklyMinutes'] == 90
        home = student.get('/api/student/home').json()
        assert home['recommendation']['courseId'] == course_id
        # The reason is a code the interface localises, not a rebuilt sentence.
        assert home['recommendation']['reasonCode'] == 'goal'
        assert home['profile']['weeklyMinutes'] == 90
        # Omitting the field keeps the stored budget instead of zeroing it.
        assert student.put('/api/student/profile', json={'background': 'Git beginner', 'goal': 'Learn Git'}).json()['profile']['weeklyMinutes'] == 90
        assert teacher.get('/api/student/home').status_code == 403
        assert student.post(f'/api/student/courses/{course_id}/enroll', json={}).status_code == 200
        imported = teacher.post(f'/api/demo/courses/{course_id}/students/import', json={'rows': [{'row': 2, 'name': 'Legacy Student', 'email': 'student@example.test'}]})
        assert imported.status_code == 200
        legacy_id = imported.json()['students'][0]['id']
        demo.COURSE_WORKSPACE.record_attempt(course_id, legacy_id, completion_percent=100, answers={'q1': False})
        chapter_url = f'/api/student/courses/{course_id}/chapters/{chapter_id}'
        chapter = student.get(chapter_url)
        assert chapter.status_code == 200
        revision = chapter.json()['chapter']['questions'][0]['revision']
        assert 'private notes' not in chapter.text
        assert 'answer' not in chapter.text
        assert student.post(chapter_url + '/progress', json={'slideId': 's1'}).status_code == 200
        assert student.post(chapter_url + '/progress', json={'slideId': 'foreign'}).status_code == 404
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'foreign', 'submissionId': 'invalid', 'questionRevision': revision}).status_code == 422
        result = student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1', 'questionRevision': revision})
        assert result.status_code == 200
        assert result.json()['result']['correct'] is False
        assert result.json()['result']['correctOptionId'] == 'A'
        # A wrong answer points back at the slide that teaches the same objective.
        assert result.json()['result']['reviewSlideId'] == 's1'
        assert result.json()['progress']['completed'] is True
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1', 'questionRevision': revision}).json()['result']['attemptId'] == result.json()['result']['attemptId']
        retry = student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'A', 'submissionId': 'submission-2', 'questionRevision': revision})
        assert retry.json()['result']['correct'] is True
        # Nothing to review after a correct answer.
        assert retry.json()['result']['reviewSlideId'] is None
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1', 'questionRevision': revision}).json()['result']['attemptId'] == result.json()['result']['attemptId']
        from app.services.auth import _store_at
        _store_at.cache_clear()
        demo.reload_course_workspace()
        resumed = student.get(chapter_url).json()
        assert resumed['progress']['lastSlideId'] == 's1'
        assert resumed['results']['q1']['selectedOptionId'] == 'A'
        # A single-chapter course has no neighbours to offer.
        assert resumed['previousChapter'] is None and resumed['nextChapter'] is None
        summary = student.get(f'/api/student/courses/{course_id}').json()['course']
        assert (summary['totalSlides'], summary['visitedSlides']) == (1, 1)
        assert (summary['totalQuestions'], summary['answeredQuestions'], summary['correctAnswers']) == (1, 1, 1)
        analytics = teacher.get(f'/api/demo/courses/{course_id}/analytics').json()
        assert analytics['enrolledCount'] == 1
        assert analytics['mostMissed'] == []
        package['questionSet']['questions'][0]['stem'] = 'A changed question?'
        # Published content is locked, so a learner never sees a half-edited course.
        assert teacher.patch(path, json={'package': package, 'status': 'ready'}).status_code == 409
        assert student.get(chapter_url).json()['chapter']['questions'][0]['stem'] == 'Branch?'
        assert teacher.post(f'/api/demo/courses/{course_id}/unpublish').status_code == 200
        assert teacher.patch(path, json={'package': package, 'status': 'ready'}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        changed = student.get(chapter_url).json()
        assert changed['chapter']['questions'][0]['stem'] == 'A changed question?'
        assert changed['results'] == {}
        assert changed['progress']['completed'] is False
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'A', 'submissionId': 'submission-1', 'questionRevision': revision}).status_code == 409
        assert student.post(chapter_url + '/attempts', json={'questionId': 'q1', 'optionId': 'B', 'submissionId': 'submission-1', 'questionRevision': revision}).json()['result']['attemptId'] == result.json()['result']['attemptId']


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


def test_upgrade_skips_unlearnable_published_course_without_changing_it(tmp_path, monkeypatch):
    from app.services.auth import AuthStore, _store_at
    from app.services.sqlite_workspace import SQLiteCourseRepository

    path = tmp_path / 'unlearnable-legacy.db'
    repo = SQLiteCourseRepository(path)
    course = repo.create_course(title='Legacy', description='', audience='Beginner', duration_min=45, language='en')
    repo.update_chapter(course.id, course.chapter_ids[0], status='ready', package={'slideDeck': {'slides': [{'title': 'Missing ID'}]}})
    repo.update_course(course.id, status='published')
    with sqlite3.connect(path) as db:
        original_payload = db.execute('SELECT payload_json FROM courses WHERE id=?', (course.id,)).fetchone()[0]

    store = AuthStore(path)
    with store.connection() as db:
        assert db.execute('SELECT 1 FROM portal_publications WHERE course_id=?', (course.id,)).fetchone() is None
        assert db.execute('SELECT payload_json FROM courses WHERE id=?', (course.id,)).fetchone()[0] == original_payload
    assert repo.get_course(course.id).status == 'published'
    monkeypatch.setattr(demo, 'TEACHER_WORKSPACE_DB', path)
    _store_at.cache_clear()
    with TestClient(app) as student:
        signed_in(student, 'student@example.test', 'student')
        assert student.get('/api/student/home').json()['courses'] == []


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
        teacher.post(f'/api/demo/courses/{cid}/unpublish')
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


def test_empty_publication_is_rejected_without_replacing_previous_snapshot():
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        chapter_path = f'/api/demo/courses/{cid}/chapters/{chapter_id}'
        teacher.patch(chapter_path, json={'status': 'ready', 'package': {'slideDeck': {'slides': []}}})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 409
        assert teacher.get(f'/api/demo/courses/{cid}').json()['status'] == 'draft'
        assert student.get('/api/student/home').json()['courses'] == []
        teacher.patch(chapter_path, json={'status': 'ready', 'package': {'slideDeck': {'slides': [{'id': 's1', 'title': 'Original'}]}}})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200
        assert teacher.patch(chapter_path, json={'status': 'ready', 'package': {'slideDeck': {'slides': []}}}).status_code == 409
        assert teacher.post(f'/api/demo/courses/{cid}/unpublish').status_code == 200
        teacher.patch(chapter_path, json={'status': 'ready', 'package': {'slideDeck': {'slides': []}}})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 409
        assert teacher.get(f'/api/demo/courses/{cid}').json()['status'] == 'draft'
        # The failed publication left the previously delivered snapshot untouched.
        from app.services.auth import get_auth_store
        with get_auth_store().connection() as db:
            snapshot = json.loads(db.execute('SELECT snapshot FROM portal_publications WHERE course_id=?', (cid,)).fetchone()['snapshot'])
        assert snapshot['chapters'][0]['slides'][0]['title'] == 'Original'


def test_malformed_asset_metadata_is_unavailable_without_breaking_chapter():
    with TestClient(app, raise_server_exceptions=False) as teacher, TestClient(app, raise_server_exceptions=False) as student:
        signed_in(teacher, 'teacher@example.test', 'instructor')
        signed_in(student, 'student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Git'}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        package = {'slideDeck': {'slides': [{'id': 's1', 'title': 'Read', 'visuals': [{'id': 'v1', 'assetId': 42}, {'id': 'v2', 'assetId': 'bad-spec'}]}]}, 'assets': [{'id': 42, 'kind': 'diagram', 'status': 'ready', 'spec': {'code': 'graph LR; A-->B'}}, {'id': 'bad-spec', 'kind': 'diagram', 'status': 'ready', 'spec': None}]}
        teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}', json={'status': 'ready', 'package': package})
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200
        path = f'/api/student/courses/{cid}/chapters/{chapter_id}'
        response = student.get(path)
        assert response.status_code == 200
        assert response.json()['chapter']['slides'][0]['visuals'] == []
        assert student.get(path + '/assets/bad-spec.svg').status_code == 404


def test_registered_student_can_sign_in_and_open_portal():
    with TestClient(app) as client:
        csrf = client.get('/api/auth/csrf').json()['csrfToken']
        response = client.post('/api/auth/register', data={'name': 'Learner', 'email': 'register@example.test', 'password': PASSWORD, 'role': 'student'}, headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
        assert response.status_code == 201
        assert client.get('/api/student/home').json()['courses'] == []
        token = response.json()['csrfToken']
        assert client.post('/api/auth/logout', headers={'Origin': ORIGIN, 'X-CSRF-Token': token}).status_code == 200
        csrf = client.get('/api/auth/csrf').json()['csrfToken']
        response = client.post('/api/auth/login', json={'email': 'register@example.test', 'password': PASSWORD}, headers={'Origin': ORIGIN, 'X-CSRF-Token': csrf})
        assert response.status_code == 200
        assert client.get('/api/student/home').status_code == 200


def test_next_step_recommends_a_new_course_the_profile_points_to():
    from app.api.routes.student import next_step

    def course(**values):
        return {'id': 'x', 'title': '', 'description': '', 'courseCode': '', 'subject': '',
                'durationMin': 60, 'enrolled': False, 'completionPercent': 0} | values

    # What the learner already has on the go stays in the learning tab; the
    # recommendation answers the profile instead of repeating the obvious.
    redirect = next_step([course(id='started', enrolled=True, completionPercent=40), course(id='match', title='Git')],
                         {'background': '', 'goal': 'git', 'weeklyMinutes': 0})
    assert (redirect['courseId'], redirect['reasonCode']) == ('match', 'goal')
    goal = next_step([course(id='match', title='Introduction to Git', durationMin=90), course(id='other', title='Queues', durationMin=20)],
                     {'background': 'commuter', 'goal': 'git', 'weeklyMinutes': 15})
    assert (goal['courseId'], goal['reasonCode']) == ('match', 'goal')
    # With no goal words, the course that fits the weekly budget wins and says why.
    fits = next_step([course(id='long', title='Git basics', durationMin=90), course(id='short', title='Queues', durationMin=20)],
                     {'background': '', 'goal': '', 'weeklyMinutes': 30})
    assert (fits['courseId'], fits['reasonCode']) == ('short', 'time')
    # With nothing to go on, offer the shortest course rather than nothing.
    start = next_step([course(id='long', title='Git basics', durationMin=90), course(id='short', title='Queues', durationMin=20)],
                      {'background': '', 'goal': '', 'weeklyMinutes': 0})
    assert (start['courseId'], start['reasonCode']) == ('short', 'start')
    assert next_step([], {'background': '', 'goal': '', 'weeklyMinutes': 0}) is None
    # Every published course is already on the learner's plate: no new course to name.
    assert next_step([course(id='only', enrolled=True, completionPercent=40)],
                     {'background': '', 'goal': 'git', 'weeklyMinutes': 0}) is None


def test_review_slide_skips_the_question_slide_itself():
    from app.services.student_learning import review_slide

    chapter = {'slides': [
        {'id': 's1', 'objectiveIds': ['LO1'], 'teachingRole': 'explain'},
        {'id': 's2', 'objectiveIds': ['LO1'], 'teachingRole': 'check_understanding'},
        {'id': 's3', 'objectiveIds': ['LO2'], 'teachingRole': 'explain'},
    ]}
    assert review_slide(chapter, {'objectiveIds': ['LO1']}) == 's1'
    assert review_slide(chapter, {'objectiveIds': ['LO2']}) == 's3'
    assert review_slide(chapter, {'objectiveIds': ['LO9']}) is None
    assert review_slide(chapter, {}) is None


def test_weekly_minutes_migration_upgrades_an_existing_profile_table(tmp_path):
    # An existing v3 workspace gains the column without losing stored profiles,
    # and re-running the migration stays idempotent.
    from app.services import portal_store
    from app.services.auth import AuthStore

    path = tmp_path / 'upgrade.db'
    store = AuthStore(path)
    user = store.create_user(name='Learner', email='upgrade@example.test', password=PASSWORD, role='student')
    with store.connection() as db:
        db.execute("INSERT INTO portal_profiles(user_id,background,goal,weekly_minutes) VALUES(?,?,?,?)", (user['id'], 'new', 'learn git', 45))
        db.execute('DELETE FROM auth_schema_versions WHERE version=4')
        db.execute('ALTER TABLE portal_profiles RENAME TO portal_profiles_v4')
        db.execute('CREATE TABLE portal_profiles(user_id TEXT PRIMARY KEY REFERENCES users(id), background TEXT NOT NULL, goal TEXT NOT NULL)')
        db.execute('INSERT INTO portal_profiles SELECT user_id,background,goal FROM portal_profiles_v4')
        db.execute('DROP TABLE portal_profiles_v4')
    portal_store.migrate(store)
    portal_store.migrate(store)
    with store.connection() as db:
        assert 'weekly_minutes' in {row['name'] for row in db.execute('PRAGMA table_info(portal_profiles)')}
        row = db.execute('SELECT background,goal,weekly_minutes FROM portal_profiles WHERE user_id=?', (user['id'],)).fetchone()
        assert (row['background'], row['goal'], row['weekly_minutes']) == ('new', 'learn git', 0)
        assert db.execute('SELECT COUNT(*) FROM auth_schema_versions WHERE version=4').fetchone()[0] == 1
    assert list(tmp_path.glob('upgrade.db.pre-portal-*.bak'))


def test_chapter_navigation_follows_the_published_order():
    # A finished chapter had no way forward, so the reader now returns its
    # published neighbours and never points at an unpublished one.
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'nav-teacher@example.test', 'instructor')
        signed_in(student, 'nav-student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Ordered course', 'durationMin': 30}).json()
        course_id, first_id = course['id'], course['chapterIds'][0]
        second = teacher.post(f'/api/demo/courses/{course_id}/chapters', json={'title': 'Second chapter'}).json()
        second_id = second['id']

        def ready(chapter_id, title):
            package = {'slideDeck': {'slides': [{'id': 's1', 'order': 1, 'layout': 'bullets', 'title': title, 'bullets': ['A point']}]},
                       'questionSet': {'questions': []}}
            return teacher.patch(f'/api/demo/courses/{course_id}/chapters/{chapter_id}', json={'title': title, 'status': 'ready', 'package': package}).status_code
        assert ready(first_id, 'First chapter') == 200
        assert ready(second_id, 'Second chapter') == 200

        # Before publishing there is nothing to navigate, so the student cannot see either.
        assert student.get(f'/api/student/courses/{course_id}/chapters/{first_id}').status_code == 404
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{course_id}/enroll', json={}).status_code == 200

        first = student.get(f'/api/student/courses/{course_id}/chapters/{first_id}').json()
        assert first['previousChapter'] is None
        assert first['nextChapter'] == {'id': second_id, 'title': 'Second chapter'}

        last = student.get(f'/api/student/courses/{course_id}/chapters/{second_id}').json()
        assert last['previousChapter'] == {'id': first_id, 'title': 'First chapter'}
        assert last['nextChapter'] is None


def test_course_summary_reports_pages_and_answers_separately():
    # The percentage blends reading and answers; the raw counts are what let the
    # interface say "3/8 pages read" without inventing a number.
    from app.api.routes.student import course_summary

    snapshot = {'id': 'course-x', 'title': 'X', 'description': '', 'courseCode': '', 'subject': '', 'level': '', 'durationMin': 10,
                'chapters': [{'id': 'c1', 'title': 'One', 'slides': [{'id': 's1'}, {'id': 's2'}],
                              'questions': [{'id': 'q1', 'type': 'mcq', 'stem': 'S', 'options': [{'id': 'A', 'text': 'a'}, {'id': 'B', 'text': 'b'}], 'answer': 'A'}],
                              'glossary': [], 'assets': []}]}
    summary = course_summary(snapshot, 'nobody')
    assert (summary['totalSlides'], summary['totalQuestions']) == (2, 1)
    assert (summary['visitedSlides'], summary['answeredQuestions'], summary['correctAnswers']) == (0, 0, 0)
    assert summary['enrolled'] is False
    # Chapter titles ship with the summary so the catalogue can search them.
    assert summary['chapterTitles'] == ['One']


def test_next_step_ignores_function_words():
    # Recommending a course because both texts contain "and" is not a reason.
    from app.api.routes.student import next_step

    course = {'id': 'se', 'title': 'Software Engineering and Development',
              'description': 'Apply methods across requirements, design and testing.',
              'courseCode': 'COMP5241', 'subject': 'Software Engineering',
              'durationMin': 45, 'enrolled': False, 'completionPercent': 0}
    reason = next_step([course], {'background': 'Computer science student with basic Python experience.',
                                  'goal': 'Understand artificial intelligence concepts and search.',
                                  'weeklyMinutes': 60})
    assert reason['reasonCode'] == 'time', reason
    assert reason['courseId'] == 'se'


def test_chinese_goal_matches_chinese_course_text():
    # The catalogue's teaching content is written in Chinese, so a Chinese goal
    # must be able to find it. Whole-run tokens never would.
    from app.api.routes.student import next_step

    course = {'id': 'sec', 'title': 'Cyber and Internet Security',
              'description': '本课程介绍网络安全基础：資料外洩、加密與防火牆。',
              'courseCode': 'COMP5355', 'subject': 'Computing Foundations',
              'durationMin': 45, 'enrolled': False, 'completionPercent': 0}
    reason = next_step([course], {'background': '', 'goal': '我想了解資料外洩和漏洞', 'weeklyMinutes': 0})
    assert (reason['courseId'], reason['reasonCode']) == ('sec', 'goal')


def test_slide_titles_join_the_match_corpus():
    # Course metadata alone is English; the Chinese goal meets the course in
    # the titles of the slides the publication already carries.
    from app.api.routes.student import next_step

    course = {'id': 'cv', 'title': 'computer vision', 'description': 'learn cv knowledge',
              'courseCode': 'cs4321', 'subject': 'Software Engineering', 'durationMin': 45,
              'enrolled': False, 'completionPercent': 0,
              'matchText': '让计算机看懂图片到底要交出什么 从原始像素到一条可验证的处理链'}
    reason = next_step([course], {'background': '', 'goal': '我想学习图像识别和像素处理', 'weeklyMinutes': 0})
    assert (reason['courseId'], reason['reasonCode']) == ('cv', 'goal')


def test_course_summary_reports_study_days_and_last_activity():
    # Derived facts only: how many days carried activity and when it last
    # happened. No duration is claimed because the timestamps cannot measure it.
    import time as clock
    with TestClient(app) as teacher, TestClient(app) as student:
        teacher_account = signed_in(teacher, 'activity-teacher@example.test', 'instructor')
        student_account = signed_in(student, 'activity-student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Activity course', 'durationMin': 20}).json()
        course_id, chapter_id = course['id'], course['chapterIds'][0]
        package = {'slideDeck': {'slides': [
            {'id': 's1', 'order': 1, 'layout': 'bullets', 'title': 'One', 'bullets': ['a']},
            {'id': 's2', 'order': 2, 'layout': 'bullets', 'title': 'Two', 'bullets': ['b']}]},
            'questionSet': {'questions': []}}
        assert teacher.patch(f'/api/demo/courses/{course_id}/chapters/{chapter_id}',
                             json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{course_id}/enroll', json={}).status_code == 200
        assert student.post(f'/api/student/courses/{course_id}/chapters/{chapter_id}/progress',
                            json={'slideId': 's1'}).status_code == 200

        summary = student.get(f'/api/student/courses/{course_id}').json()['course']
        assert summary['studyDays'] == 1
        assert abs(clock.time() - summary['lastStudiedAt']) < 120

        # A visit three days ago is a second study day, but not the latest one.
        from app.services.auth import get_auth_store
        with get_auth_store().connection() as db:
            db.execute('INSERT INTO portal_visits VALUES(?,?,?,?,?)',
                       (course_id, student_account['id'], chapter_id, 's2', clock.time() - 3 * 86400))
        summary = student.get(f'/api/student/courses/{course_id}').json()['course']
        assert summary['studyDays'] == 2
        assert abs(clock.time() - summary['lastStudiedAt']) < 120

        # An unenrolled learner gets no derived activity at all.
        assert student.get('/api/student/home').json()['courses'][0]['studyDays'] == 2


def test_migration_delivers_a_published_course_that_had_no_snapshot():
    # A published course without a snapshot is invisible to students. Repairing it
    # at migration time is what stops that class of course from silently vanishing.
    from app.services import portal_store
    from app.services.auth import get_auth_store

    with TestClient(app) as teacher:
        signed_in(teacher, 'repair-teacher@example.test', 'instructor')
        course = teacher.post('/api/demo/courses', json={'title': 'Repair me', 'durationMin': 20}).json()
        course_id, chapter_id = course['id'], course['chapterIds'][0]
        package = {'slideDeck': {'slides': [{'id': 's1', 'order': 1, 'layout': 'bullets', 'title': 'One', 'bullets': ['a']}]},
                   'questionSet': {'questions': []}}
        assert teacher.patch(f'/api/demo/courses/{course_id}/chapters/{chapter_id}',
                             json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{course_id}/publish').status_code == 200

        store = get_auth_store()
        with store.connection() as db:
            db.execute('DELETE FROM portal_publications WHERE course_id=?', (course_id,))
            db.execute('DELETE FROM auth_schema_versions WHERE version=5')
        assert portal_store.migrate(store) is None
        with store.connection() as db:
            row = db.execute('SELECT snapshot FROM portal_publications WHERE course_id=?', (course_id,)).fetchone()
            assert row is not None, 'The published course is delivered again'
            assert json.loads(row['snapshot'])['chapters'][0]['id'] == chapter_id
            assert db.execute('SELECT 1 FROM auth_schema_versions WHERE version=5').fetchone()


def test_tutor_context_stays_inside_the_published_slide():
    from app.services import tutor

    snapshot = {
        'title': 'Course',
        'learningObjectives': [{'id': 'LO1', 'text': 'Find paths'}, {'id': 'LO2', 'text': 'Reason'}],
        'chapters': [{
            'id': 'c1', 'title': 'Search',
            'slides': [{'id': 's1', 'title': 'State space', 'bullets': ['States', 'Edges'], 'objectiveIds': ['LO2']}],
        }],
    }
    context = tutor.context_for(snapshot, 'c1', 's1')
    assert context['slide']['title'] == 'State space'
    assert [item['id'] for item in context['objectives']] == ['LO2'], 'Only the objectives this slide serves'
    messages = tutor.build_messages(context, 'What is a state?')
    assert messages[0]['role'] == 'system'
    assert 'State space' in messages[1]['content']
    assert 'Student state-of-the-art' not in messages[1]['content']
    for missing in [('c1', 'nope'), ('nope', 's1')]:
        try:
            tutor.context_for(snapshot, *missing)
        except KeyError:
            continue
        raise AssertionError('A slide outside the publication must not resolve')


def test_tutor_answers_from_the_published_slide_only(monkeypatch):
    from app.config import settings
    from app.llm import client as llm_client
    from app.llm.client import ChatMessage

    captured = {}

    class Stub:
        async def complete(self, *, model, messages, tools=None, temperature=0.0):
            captured['messages'] = messages
            return ChatMessage(content='A state is a situation plus the moves out of it.')

    monkeypatch.setattr(llm_client, 'build_deepseek_client', lambda: Stub())
    monkeypatch.setattr(settings, 'deepseek_api_key', 'test-key')

    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'tutor-teacher@example.test', 'instructor')
        signed_in(student, 'tutor-student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Tutor course', 'learningObjectives': ['Model a problem as states']}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        package = {
            'slideDeck': {'slides': [{'id': 's1', 'order': 1, 'layout': 'bullets', 'title': 'State space', 'bullets': ['States', 'Edges'], 'objectiveIds': ['LO1']}]},
            'questionSet': {'questions': []},
        }
        assert teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}', json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200
        path = f'/api/student/courses/{cid}/chapters/{chapter_id}/tutor'

        # The top bar names the course the chapter belongs to.
        assert student.get(f'/api/student/courses/{cid}/chapters/{chapter_id}').json()['courseTitle'] == 'Tutor course'

        reply = student.post(path, json={'slideId': 's1', 'question': 'What is a state?'})
        assert reply.status_code == 200, reply.text
        assert reply.json()['answer']
        prompt = captured['messages'][1]['content']
        assert 'State space' in prompt and 'Model a problem as states' in prompt
        assert 'What is a state?' in prompt

        # A slide that is not in the publication cannot be asked about.
        assert student.post(path, json={'slideId': 's9', 'question': 'Anything?'}).status_code == 404


def test_quiz_options_reach_the_learner_while_the_answer_stays_gated():
    # Quiz bullets are the lettered options (verified across the generated
    # corpus: the worked answer lives in speakerNotes, never in option text).
    # The old read stripped them as "answers", which erased every exercise.
    from app.services.student_learning import safe_slide_content

    quiz = safe_slide_content({
        'id': 's4', 'order': 4, 'layout': 'quiz',
        'title': 'Which tasks state input and output?',
        'quizInstruction': 'Pick one and justify it.',
        'bullets': ['A. Pedestrian detection.', 'B. Traffic signs.'],
        'speakerNotes': 'The correct answer is A.',
    })
    assert quiz['bullets'] == ['A. Pedestrian detection.', 'B. Traffic signs.']
    assert quiz['quizInstruction'] == 'Pick one and justify it.'
    assert quiz['quizExplanation'] == 'The correct answer is A.'

    # A teaching slide's notes stay private, and its bullets are untouched.
    teaching = safe_slide_content({
        'id': 's2', 'order': 2, 'layout': 'bullets', 'title': 'Concept',
        'bullets': ['A point'], 'speakerNotes': 'Teacher-only notes',
    })
    assert teaching['bullets'] == ['A point']
    assert 'quizExplanation' not in teaching
    assert 'speakerNotes' not in teaching


def test_open_questions_reach_the_learner_without_losing_bank_order():
    # A bank question grades as a choice question when its options and answer
    # validate, whatever its type label (the generator sometimes writes a
    # scenario with options). Genuine free-text travels as an open self-check
    # question with the reference answer, in bank order; one without a
    # reference answer cannot be revealed, so it is dropped.
    with TestClient(app) as teacher, TestClient(app) as student:
        signed_in(teacher, 'openq-teacher@example.test', 'instructor')
        signed_in(student, 'openq-student@example.test', 'student')
        course = teacher.post('/api/demo/courses', json={'title': 'Open questions course', 'durationMin': 20}).json()
        cid, chapter_id = course['id'], course['chapterIds'][0]
        package = {
            'slideDeck': {'slides': [{'id': 's1', 'order': 1, 'layout': 'bullets', 'title': 'One', 'bullets': ['a']}]},
            'questionSet': {'questions': [
                {'id': 'q1', 'type': 'mcq', 'stem': 'Gradeable?', 'options': [
                    {'id': 'A', 'text': 'Yes'}, {'id': 'B', 'text': 'No'}], 'answer': 'A', 'explanation': 'It is.'},
                {'id': 'q2', 'type': 'scenario', 'stem': 'Which definition is testable?', 'options': [
                    {'id': 'A', 'text': 'Understand the desk.'},
                    {'id': 'B', 'text': 'Detect laptop and cup, output boxes and labels.'}],
                 'answer': 'B', 'explanation': 'Observable output.'},
                {'id': 'q3', 'type': 'short', 'stem': 'What is a label?', 'options': [],
                 'answer': 'The human-provided correct answer for a sample.', 'explanation': ''},
                {'id': 'q4', 'type': 'short', 'stem': 'No reference?', 'options': [], 'answer': ''},
            ]},
        }
        assert teacher.patch(f'/api/demo/courses/{cid}/chapters/{chapter_id}',
                             json={'status': 'ready', 'package': package}).status_code == 200
        assert teacher.post(f'/api/demo/courses/{cid}/publish').status_code == 200
        assert student.post(f'/api/student/courses/{cid}/enroll', json={}).status_code == 200

        chapter = student.get(f'/api/student/courses/{cid}/chapters/{chapter_id}').json()['chapter']
        assert [q['id'] for q in chapter['questions']] == ['q1', 'q2']
        assert chapter['questions'][0]['position'] == 0
        assert chapter['questions'][1]['position'] == 1
        assert [q['id'] for q in chapter['openQuestions']] == ['q3']
        assert chapter['openQuestions'][0]['position'] == 2
        assert chapter['openQuestions'][0]['type'] == 'short'
        assert chapter['openQuestions'][0]['answer'] == 'The human-provided correct answer for a sample.'
        assert 'answer' not in chapter['questions'][0]
