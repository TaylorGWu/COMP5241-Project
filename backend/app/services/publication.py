"""Freeze instructor-reviewed content for separate student delivery."""
import json
import re

from fastapi import HTTPException

from app.services.auth import get_auth_store


def valid_asset_id(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value) is not None


def deliverable_asset(asset):
    if not isinstance(asset, dict) or not valid_asset_id(asset.get('id')) or asset.get('status') != 'ready':
        return False
    if asset.get('kind') == 'illustration':
        return True
    spec = asset.get('spec')
    return asset.get('kind') == 'diagram' and isinstance(spec, dict) and isinstance(spec.get('code'), str) and bool(spec['code'].strip())


def build_snapshot(repository, course):
    chapters = []
    for chapter_id in course.chapter_ids:
        chapter = repository.get_chapter(course.id, chapter_id)
        # A chapter's draft/ready status is a teacher-side hint; what decides
        # whether it can be published is whether it has content.
        if chapter.package is None:
            continue
        package = chapter.package
        if hasattr(package, 'model_dump'):
            package = package.model_dump(by_alias=True)
        if not isinstance(package, dict):
            continue
        deck = package.get('slideDeck')
        slides = deck.get('slides', []) if isinstance(deck, dict) else []
        if not isinstance(slides, list):
            continue
        slides = [dict(slide) for slide in slides if isinstance(slide, dict) and isinstance(slide.get('id'), str) and slide['id']]
        for slide in slides:
            visuals = slide.get('visuals', [])
            slide['visuals'] = [visual for visual in visuals if isinstance(visual, dict) and valid_asset_id(visual.get('assetId'))] if isinstance(visuals, list) else []
        if not slides:
            continue
        question_set = package.get('questionSet')
        questions = question_set.get('questions', []) if isinstance(question_set, dict) else []
        project = package.get('project')
        glossary = project.get('glossary', []) if isinstance(project, dict) else []
        assets = package.get('assets', [])
        chapters.append({'id': chapter.id, 'title': chapter.title, 'slides': slides,
                         'questions': questions if isinstance(questions, list) else [],
                         'glossary': glossary if isinstance(glossary, list) else [],
                         'assets': [asset for asset in assets if isinstance(asset, dict)] if isinstance(assets, list) else []})
    # Learning objectives travel with the snapshot: the learner-facing tutor may only
    # use what was published, never the teacher's working copy.
    objectives = [dict(item) for item in (course.learning_objectives or []) if isinstance(item, dict)]
    return {'id': course.id, 'title': course.title, 'description': course.description,
            'courseCode': course.course_code, 'subject': course.subject, 'level': course.level,
            'durationMin': course.duration_min, 'learningObjectives': objectives,
            'chapters': chapters}


def publish(repository, course_id, instructor_id):
    from app.services.course_repository import Course, Chapter

    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM users u JOIN course_owners o ON o.instructor_id=u.id WHERE u.id=? AND o.course_id=? AND u.role='instructor' AND u.status='approved' AND u.active=1", (instructor_id, course_id)).fetchone():
            raise HTTPException(403, 'An approved course owner is required')
        if db.execute('SELECT 1 FROM portal_moderation WHERE course_id=?', (course_id,)).fetchone():
            raise HTTPException(409, 'This course is suspended')
        row = db.execute('SELECT payload_json FROM courses WHERE id=?', (course_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Course not found')
        course = Course(**json.loads(row['payload_json']))
        chapters = {r['id']: Chapter(**json.loads(r['payload_json'])) for r in db.execute(
            'SELECT id,payload_json FROM chapters WHERE course_id=?', (course_id,))}
        class TransactionRepository:
            def get_chapter(self, ignored, chapter_id):
                return chapters[chapter_id]
        snapshot = build_snapshot(TransactionRepository(), course)
        if not snapshot['chapters']:
            raise HTTPException(409, 'A course needs at least one chapter with slides before publish')
        payload = json.loads(row['payload_json'])
        payload['status'] = 'published'
        db.execute('UPDATE courses SET payload_json=? WHERE id=?', (json.dumps(payload, ensure_ascii=False), course_id))
        db.execute('INSERT INTO portal_publications VALUES(?,?) ON CONFLICT(course_id) DO UPDATE SET snapshot=excluded.snapshot',
                   (course_id, json.dumps(snapshot, ensure_ascii=False)))
    return repository.get_course(course_id)


def available(course_id):
    with get_auth_store().connection() as db:
        row = db.execute('''SELECT p.snapshot, c.payload_json FROM portal_publications p
          JOIN courses c ON c.id=p.course_id LEFT JOIN portal_moderation m ON m.course_id=p.course_id
          WHERE p.course_id=? AND m.course_id IS NULL''', (course_id,)).fetchone()
        if not row or json.loads(row['payload_json']).get('status') != 'published':
            raise HTTPException(404, 'Course is unavailable')
        return json.loads(row['snapshot'])
