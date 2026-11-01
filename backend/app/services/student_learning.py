"""Account-linked enrolment, reading progress, and MCQ grading."""
import hashlib
import json
import re
import secrets
import time

from fastapi import HTTPException
from app.services.auth import get_auth_store
from app.services.publication import available


def verify_access(db, course_id, user_id, chapter=None):
    row = db.execute('''SELECT p.snapshot,c.payload_json FROM portal_publications p JOIN courses c ON c.id=p.course_id LEFT JOIN portal_moderation m ON m.course_id=p.course_id WHERE p.course_id=? AND m.course_id IS NULL''', (course_id,)).fetchone()
    if not row or json.loads(row['payload_json']).get('status') != 'published':
        raise HTTPException(404, 'Course is unavailable')
    if not db.execute("SELECT 1 FROM users WHERE id=? AND role='student' AND active=1", (user_id,)).fetchone():
        raise HTTPException(403, 'Student account required')
    if chapter is not None:
        current = next((c for c in json.loads(row['snapshot'])['chapters'] if c['id'] == chapter['id']), None)
        if current != chapter:
            raise HTTPException(409, 'Course changed; reload and retry')
        if not db.execute('SELECT 1 FROM portal_enrollments WHERE course_id=? AND user_id=?', (course_id, user_id)).fetchone():
            raise HTTPException(403, 'Enroll to open this chapter')


def enroll(course_id, user_id):
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        verify_access(db, course_id, user_id)
        db.execute('INSERT OR IGNORE INTO portal_enrollments VALUES(?,?,?)', (course_id, user_id, time.time()))


def enrolled(course_id, user_id):
    with get_auth_store().connection() as db:
        return bool(db.execute('SELECT 1 FROM portal_enrollments WHERE course_id=? AND user_id=?', (course_id, user_id)).fetchone())


def get_chapter(course_id, chapter_id, user_id):
    snapshot = available(course_id)
    if not enrolled(course_id, user_id):
        raise HTTPException(403, 'Enroll to open this chapter')
    chapter = next((c for c in snapshot['chapters'] if c['id'] == chapter_id), None)
    if not chapter:
        raise HTTPException(404, 'Chapter not found')
    return chapter


def mcqs(chapter):
    valid = []
    for q in chapter['questions']:
        if not isinstance(q, dict) or q.get('type') != 'mcq' or not isinstance(q.get('id'), str) or not isinstance(q.get('stem'), str) or not isinstance(q.get('answer'), str) or not isinstance(q.get('explanation', ''), str):
            continue
        options = q.get('options')
        if not isinstance(options, list) or len(options) < 2 or any(not isinstance(o, dict) or not isinstance(o.get('id'), str) or not isinstance(o.get('text'), str) for o in options):
            continue
        ids = [o['id'] for o in options]
        if len(ids) == len(set(ids)) and q['answer'] in ids:
            valid.append(q)
    return valid


def question_hash(question):
    value = {k: question.get(k) for k in ('id', 'stem', 'options', 'answer', 'explanation')}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def state(course_id, chapter, user_id):
    with get_auth_store().connection() as db:
        visits = db.execute('SELECT slide_id FROM portal_visits WHERE course_id=? AND user_id=? AND chapter_id=? ORDER BY visited_at', (course_id, user_id, chapter['id'])).fetchall()
        attempts = db.execute('SELECT * FROM portal_attempts WHERE course_id=? AND user_id=? AND chapter_id=? ORDER BY created_at,rowid', (course_id, user_id, chapter['id'])).fetchall()
    slide_ids = {s['id'] for s in chapter['slides']}
    visited = [r['slide_id'] for r in visits if r['slide_id'] in slide_ids]
    questions = {q['id']: q for q in mcqs(chapter)}
    results = {}
    for row in attempts:
        if row['question_id'] in questions and row['question_hash'] == question_hash(questions[row['question_id']]):
            results[row['question_id']] = dict(questionId=row['question_id'], selectedOptionId=row['option_id'], correct=bool(row['correct']), correctOptionId=row['correct_option'], explanation=row['explanation'], attemptId=row['id'])
    total = len(slide_ids) + len(questions)
    done = len(set(visited)) + len(results)
    return dict(visitedSlideIds=visited, lastSlideId=visited[-1] if visited else None, completionPercent=round(done * 100 / total) if total else 0, completed=bool(total and done == total)), results


def safe_chapter(course_id, chapter):
    slides = []
    for source in chapter['slides']:
        # Quiz slide bullets can themselves contain answers; omit them entirely.
        fields = ('id', 'order', 'layout', 'title', 'bullets', 'quizInstruction')
        slide = {key: source[key] for key in fields if key in source and ((key == 'order' and type(source[key]) is int) or (key != 'order' and key != 'bullets' and isinstance(source[key], str)))}
        slide['bullets'] = [item for item in source.get('bullets', []) if isinstance(item, str)] if isinstance(source.get('bullets', []), list) else []
        groups = source.get('statusGroups', [])
        slide['statusGroups'] = [{'title': group.get('title') if isinstance(group.get('title'), str) else '', 'items': [{key: item[key] for key in ('label', 'status') if isinstance(item.get(key), str)} for item in group.get('items', []) if isinstance(item, dict)]} for group in groups if isinstance(group, dict) and isinstance(group.get('items', []), list)] if isinstance(groups, list) else []
        if source.get('layout') == 'quiz':
            slide.pop('bullets', None)
        visuals = []
        for visual in source.get('visuals', []):
            asset_id = visual.get('assetId')
            asset = next((a for a in chapter['assets'] if a.get('id') == asset_id and a.get('status') == 'ready' and a.get('kind') in ('diagram', 'illustration')), None)
            if asset and re.fullmatch(r'[A-Za-z0-9_-]+', asset_id):
                extension = 'svg' if asset['kind'] == 'diagram' else 'png'
                visuals.append({'id': visual.get('id') if isinstance(visual.get('id'), str) else '', 'kind': asset['kind'], 'altText': asset.get('altText') if isinstance(asset.get('altText'), str) else '', 'url': f"/api/student/courses/{course_id}/chapters/{chapter['id']}/assets/{asset_id}.{extension}"})
        slide['visuals'] = visuals
        slides.append(slide)
    questions = [{'id': q['id'], 'stem': q.get('stem', ''), 'options': [{'id': o['id'], 'text': o['text']} for o in q['options']]} for q in mcqs(chapter)]
    return {'id': chapter['id'], 'title': chapter['title'], 'slides': slides, 'questions': questions, 'glossary': [{k: g[k] for k in ('term', 'plain') if isinstance(g.get(k), str)} for g in chapter['glossary'] if isinstance(g, dict)]}


def visit(course_id, chapter, user_id, slide_id):
    if slide_id not in {s['id'] for s in chapter['slides']}:
        raise HTTPException(404, 'Slide not found')
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        verify_access(db, course_id, user_id, chapter)
        db.execute('INSERT INTO portal_visits VALUES(?,?,?,?,?) ON CONFLICT(course_id,user_id,chapter_id,slide_id) DO UPDATE SET visited_at=excluded.visited_at', (course_id, user_id, chapter['id'], slide_id, time.time()))


def attempt(course_id, chapter, user_id, question_id, option_id, submission_id):
    question = next((q for q in mcqs(chapter) if q['id'] == question_id), None)
    if not question or option_id not in {o['id'] for o in question['options']}:
        raise HTTPException(422, 'Unknown question or option')
    if not submission_id or len(submission_id) > 128:
        raise HTTPException(422, 'Invalid submission ID')
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        verify_access(db, course_id, user_id, chapter)
        previous = db.execute('SELECT * FROM portal_attempts WHERE user_id=? AND submission_id=?', (user_id, submission_id)).fetchone()
        if previous and (previous['course_id'], previous['chapter_id'], previous['question_id'], previous['option_id'], previous['question_hash']) != (course_id, chapter['id'], question_id, option_id, question_hash(question)):
            raise HTTPException(409, 'Submission ID already used')
        if not previous:
            attempt_id = secrets.token_urlsafe(18)
            db.execute('INSERT INTO portal_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (attempt_id, submission_id, course_id, user_id, chapter['id'], question_id, option_id, int(option_id == question['answer']), question['answer'], question.get('explanation', ''), time.time(), question_hash(question)))
        else:
            attempt_id = previous['id']
    result = dict(questionId=question_id, selectedOptionId=option_id, correct=option_id == question['answer'], correctOptionId=question['answer'], explanation=question.get('explanation', ''), attemptId=attempt_id)
    return result, state(course_id, chapter, user_id)[0]
