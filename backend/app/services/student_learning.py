"""Account-linked enrolment, reading progress, and MCQ grading."""
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException
from app.services.auth import get_auth_store
from app.services.publication import available, deliverable_asset, valid_asset_id


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
    counts = {}
    for q in chapter['questions']:
        if isinstance(q, dict) and isinstance(q.get('id'), str):
            counts[q['id']] = counts.get(q['id'], 0) + 1
    for q in chapter['questions']:
        if not isinstance(q, dict) or q.get('type') != 'mcq' or not isinstance(q.get('id'), str) or not q['id'].strip() or counts[q['id']] != 1 or not isinstance(q.get('stem'), str) or not isinstance(q.get('answer'), str) or not isinstance(q.get('explanation', ''), str):
            continue
        options = q.get('options')
        if not isinstance(options, list) or len(options) < 2 or any(not isinstance(o, dict) or not isinstance(o.get('id'), str) or not o['id'].strip() or not isinstance(o.get('text'), str) for o in options):
            continue
        ids = [o['id'] for o in options]
        if len(ids) == len(set(ids)) and q['answer'] in ids:
            valid.append(q)
    return valid


def question_hash(question):
    value = {k: question.get(k) for k in ('id', 'stem', 'options', 'answer', 'explanation')}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def question_revision(db, user_id, digest):
    key = db.execute('SELECT password_hash FROM users WHERE id=?', (user_id,)).fetchone()['password_hash']
    return hmac.new(key.encode(), digest.encode(), hashlib.sha256).hexdigest()


def review_slide(chapter, question):
    """A teaching slide that covers the same objective, for reviewing a wrong answer.

    Check-understanding slides are skipped: they ask the question rather than
    explain it, so sending a learner back there teaches nothing.
    """
    objectives = set(question.get('objectiveIds') or []) if isinstance(question, dict) else set()
    if not objectives:
        return None
    for slide in chapter['slides']:
        if not isinstance(slide, dict) or not isinstance(slide.get('id'), str) or not slide['id']:
            continue
        if slide.get('teachingRole') == 'check_understanding':
            continue
        if objectives & set(slide.get('objectiveIds') or []):
            return slide['id']
    return None


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
            correct = bool(row['correct'])
            results[row['question_id']] = dict(questionId=row['question_id'], selectedOptionId=row['option_id'], correct=correct, correctOptionId=row['correct_option'], explanation=row['explanation'], attemptId=row['id'], reviewSlideId=None if correct else review_slide(chapter, questions[row['question_id']]))
    total = len(slide_ids) + len(questions)
    done = len(set(visited)) + len(results)
    return dict(visitedSlideIds=visited, lastSlideId=visited[-1] if visited else None, completionPercent=round(done * 100 / total) if total else 0, completed=bool(total and done == total)), results


def safe_status_groups(groups):
    if not isinstance(groups, list):
        return []
    result = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get('items', []), list):
            continue
        title = group.get('title') if isinstance(group.get('title'), str) else ''
        items = []
        for item in group.get('items', []):
            if isinstance(item, dict):
                items.append({key: item[key] for key in ('label', 'status') if isinstance(item.get(key), str)})
        result.append({'title': title, 'items': items})
    return result


def safe_slide_content(source):
    slide = {key: source[key] for key in ('id', 'layout', 'title', 'quizInstruction') if isinstance(source.get(key), str)}
    if type(source.get('order')) is int:
        slide['order'] = source['order']
    bullets = source.get('bullets', [])
    # Quiz slide bullets can themselves contain answers; omit them entirely.
    if source.get('layout') != 'quiz':
        slide['bullets'] = [item for item in bullets if isinstance(item, str)] if isinstance(bullets, list) else []
    slide['statusGroups'] = safe_status_groups(source.get('statusGroups', []))
    return slide


def safe_chapter(course_id, chapter, user_id):
    slides = []
    for source in chapter['slides']:
        slide = safe_slide_content(source)
        visuals = []
        for visual in source.get('visuals', []):
            asset_id = visual.get('assetId')
            if not valid_asset_id(asset_id):
                continue
            asset = next((a for a in chapter['assets'] if deliverable_asset(a) and a['id'] == asset_id), None)
            if asset:
                extension = 'svg' if asset['kind'] == 'diagram' else 'png'
                visuals.append({'id': visual.get('id') if isinstance(visual.get('id'), str) else '', 'kind': asset['kind'], 'altText': asset.get('altText') if isinstance(asset.get('altText'), str) else '', 'url': f"/api/student/courses/{course_id}/chapters/{chapter['id']}/assets/{asset_id}.{extension}"})
        slide['visuals'] = visuals
        slides.append(slide)
    with get_auth_store().connection() as db:
        questions = [{'id': q['id'], 'stem': q.get('stem', ''), 'revision': question_revision(db, user_id, question_hash(q)), 'options': [{'id': o['id'], 'text': o['text']} for o in q['options']]} for q in mcqs(chapter)]
    return {'id': chapter['id'], 'title': chapter['title'], 'slides': slides, 'questions': questions, 'glossary': [{k: g[k] for k in ('term', 'plain') if isinstance(g.get(k), str)} for g in chapter['glossary'] if isinstance(g, dict)]}


def visit(course_id, chapter, user_id, slide_id):
    if slide_id not in {s['id'] for s in chapter['slides']}:
        raise HTTPException(404, 'Slide not found')
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        verify_access(db, course_id, user_id, chapter)
        db.execute('INSERT INTO portal_visits VALUES(?,?,?,?,?) ON CONFLICT(course_id,user_id,chapter_id,slide_id) DO UPDATE SET visited_at=excluded.visited_at', (course_id, user_id, chapter['id'], slide_id, time.time()))


def attempt(course_id, chapter, user_id, question_id, option_id, submission_id, revision):
    question = next((q for q in mcqs(chapter) if q['id'] == question_id), None)
    if not submission_id or len(submission_id) > 128:
        raise HTTPException(422, 'Invalid submission ID')
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        verify_access(db, course_id, user_id, chapter)
        previous = db.execute('SELECT * FROM portal_attempts WHERE user_id=? AND submission_id=?', (user_id, submission_id)).fetchone()
        if previous and ((previous['course_id'], previous['chapter_id'], previous['question_id'], previous['option_id']) != (course_id, chapter['id'], question_id, option_id) or not hmac.compare_digest(revision, question_revision(db, user_id, previous['question_hash']))):
            raise HTTPException(409, 'Submission ID already used')
        if not previous:
            if not question:
                raise HTTPException(422, 'Unknown question or option')
            if not hmac.compare_digest(revision, question_revision(db, user_id, question_hash(question))):
                raise HTTPException(409, 'Question changed; reload chapter')
            if option_id not in {o['id'] for o in question['options']}:
                raise HTTPException(422, 'Unknown question or option')
        if not previous:
            attempt_id = secrets.token_urlsafe(18)
            db.execute('INSERT INTO portal_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (attempt_id, submission_id, course_id, user_id, chapter['id'], question_id, option_id, int(option_id == question['answer']), question['answer'], question.get('explanation', ''), time.time(), question_hash(question)))
        else:
            attempt_id = previous['id']
    correct = bool(previous['correct']) if previous else option_id == question['answer']
    result = dict(questionId=question_id, selectedOptionId=option_id, correct=correct, correctOptionId=previous['correct_option'] if previous else question['answer'], explanation=previous['explanation'] if previous else question.get('explanation', ''), attemptId=attempt_id, reviewSlideId=None if correct else review_slide(chapter, question))
    return result, state(course_id, chapter, user_id)[0]
