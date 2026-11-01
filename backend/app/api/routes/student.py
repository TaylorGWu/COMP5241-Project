"""Authenticated student portal endpoints."""
import asyncio
import re
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app.services.auth import current_user, get_auth_store
from app.services import student_learning as learning
from app.services.publication import available, deliverable_asset, valid_asset_id

router = APIRouter(prefix="/student", tags=["student"])


async def student_user(request: Request) -> dict:
    user = await current_user(request)
    if user["role"] != "student":
        raise HTTPException(403, "Student account required")
    return user


@router.get("/home")
async def home(request: Request):
    user = await student_user(request)
    with get_auth_store().connection() as db:
        ids = [r[0] for r in db.execute('SELECT course_id FROM portal_publications')]
        profile = db.execute('SELECT background,goal FROM portal_profiles WHERE user_id=?', (user['id'],)).fetchone()
    courses = []
    for course_id in ids:
        try:
            courses.append(course_summary(available(course_id), user['id']))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    profile = dict(profile) if profile else {"background": "", "goal": ""}
    tokens = set(re.findall(r'\w+', (profile['background'] + ' ' + profile['goal']).casefold()))
    matches = []
    for item in courses:
        words = set(re.findall(r'\w+', ' '.join(str(item[k]) for k in ('title', 'description', 'courseCode', 'subject')).casefold()))
        score = len(tokens & words)
        if score and not item['enrolled']:
            matches.append((score, item['id']))
    recommendation = None
    if matches:
        _, course_id = sorted(matches, key=lambda match: (-match[0], match[1]))[0]
        recommendation = {'courseId': course_id, 'reason': f"Matches words in your background ({profile['background'] or 'not provided'}) and goal ({profile['goal'] or 'not provided'})."}
    return {"courses": courses, "profile": profile, "recommendation": recommendation}


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    background: str = Field(max_length=500)
    goal: str = Field(max_length=500)


class Visit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slideId: str = Field(min_length=1, max_length=128)


class Attempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    questionId: str = Field(min_length=1, max_length=128)
    optionId: str = Field(min_length=1, max_length=128)
    submissionId: str = Field(min_length=1, max_length=128)
    questionRevision: str = Field(min_length=64, max_length=64, pattern='^[0-9a-f]{64}$')


class Join(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(min_length=1, max_length=128)


@router.post('/join')
async def join(request: Request, body: Join):
    user = await student_user(request)
    with get_auth_store().connection() as db:
        row = db.execute('SELECT course_id FROM portal_invites WHERE code=?', (body.code,)).fetchone()
    if not row:
        raise HTTPException(404, 'Invite not found')
    learning.enroll(row['course_id'], user['id'])
    return {'courseId': row['course_id']}


def course_summary(snapshot, user_id):
    chapters = snapshot['chapters']
    is_enrolled = learning.enrolled(snapshot['id'], user_id)
    states = [learning.state(snapshot['id'], chapter, user_id)[0] for chapter in chapters] if is_enrolled else []
    last = (None, None)
    if is_enrolled:
        valid = {(chapter['id'], slide['id']) for chapter in chapters for slide in chapter['slides']}
        with get_auth_store().connection() as db:
            visits = db.execute('SELECT chapter_id,slide_id FROM portal_visits WHERE course_id=? AND user_id=? ORDER BY visited_at DESC', (snapshot['id'], user_id)).fetchall()
        last = next(((row['chapter_id'], row['slide_id']) for row in visits if (row['chapter_id'], row['slide_id']) in valid), last)
    return {key: snapshot[key] for key in ('id', 'title', 'description', 'courseCode', 'subject', 'level', 'durationMin')} | {'chapterCount': len(chapters), 'enrolled': is_enrolled, 'completionPercent': round(sum(s['completionPercent'] for s in states) / len(states)) if states else 0, 'lastChapterId': last[0], 'lastSlideId': last[1]}


def overview(snapshot, user_id):
    is_enrolled = learning.enrolled(snapshot['id'], user_id)
    chapters = []
    for chapter in snapshot['chapters']:
        progress = learning.state(snapshot['id'], chapter, user_id)[0] if is_enrolled else {'completionPercent': 0, 'completed': False}
        chapters.append({'id': chapter['id'], 'title': chapter['title'], 'slideCount': len(chapter['slides']), 'questionCount': len(learning.mcqs(chapter)), **{k: progress[k] for k in ('completionPercent', 'completed')}})
    return {'course': course_summary(snapshot, user_id), 'chapters': chapters, 'enrolled': is_enrolled}


@router.put('/profile')
async def profile(request: Request, body: Profile):
    user = await student_user(request)
    with get_auth_store().connection() as db:
        db.execute('INSERT INTO portal_profiles VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET background=excluded.background,goal=excluded.goal', (user['id'], body.background.strip(), body.goal.strip()))
    return {'profile': {'background': body.background.strip(), 'goal': body.goal.strip()}}


@router.get('/courses/{course_id}')
async def course(course_id: str, request: Request):
    user = await student_user(request)
    return overview(available(course_id), user['id'])


@router.post('/courses/{course_id}/enroll')
async def enroll_course(course_id: str, request: Request):
    user = await student_user(request)
    learning.enroll(course_id, user['id'])
    return overview(available(course_id), user['id'])


@router.get('/courses/{course_id}/chapters/{chapter_id}')
async def chapter(course_id: str, chapter_id: str, request: Request):
    user = await student_user(request)
    chapter = learning.get_chapter(course_id, chapter_id, user['id'])
    progress, results = learning.state(course_id, chapter, user['id'])
    return {'chapter': learning.safe_chapter(course_id, chapter, user['id']), 'progress': progress, 'results': results}


@router.post('/courses/{course_id}/chapters/{chapter_id}/progress')
async def progress(course_id: str, chapter_id: str, request: Request, body: Visit):
    user = await student_user(request)
    chapter = learning.get_chapter(course_id, chapter_id, user['id'])
    learning.visit(course_id, chapter, user['id'], body.slideId)
    return {'progress': learning.state(course_id, chapter, user['id'])[0]}


@router.post('/courses/{course_id}/chapters/{chapter_id}/attempts')
async def attempt(course_id: str, chapter_id: str, request: Request, body: Attempt):
    user = await student_user(request)
    chapter = learning.get_chapter(course_id, chapter_id, user['id'])
    result, progress = learning.attempt(course_id, chapter, user['id'], body.questionId, body.optionId, body.submissionId, body.questionRevision)
    return {'result': result, 'progress': progress}


@router.get('/courses/{course_id}/chapters/{chapter_id}/assets/{asset_id}.{extension}')
async def asset(course_id: str, chapter_id: str, asset_id: str, extension: str, request: Request):
    from app.config import settings
    from app.services.illustrations import IllustrationError, read_illustration
    from app.services.svg_diagrams import render_course_svg
    from app.services.mermaid_assets import MermaidRenderError, render_mermaid_png
    user = await student_user(request)
    chapter = learning.get_chapter(course_id, chapter_id, user['id'])
    used = {v.get('assetId') for slide in chapter['slides'] for v in slide.get('visuals', []) if isinstance(v, dict) and valid_asset_id(v.get('assetId'))}
    item = next((a for a in chapter['assets'] if deliverable_asset(a) and a['id'] == asset_id and asset_id in used), None)
    if not item or extension not in ('svg', 'png'):
        raise HTTPException(404, 'Asset not found')
    if item.get('kind') == 'illustration' and extension == 'png':
        try:
            data = await asyncio.to_thread(read_illustration, settings.upload_dir, asset_id)
        except IllustrationError:
            raise HTTPException(404, 'Asset unavailable') from None
    elif item.get('kind') == 'diagram' and isinstance(item.get('spec', {}).get('code'), str):
        code = item['spec']['code']
        try:
            data = render_course_svg(code) if extension == 'svg' else await asyncio.to_thread(render_mermaid_png, code)
        except MermaidRenderError:
            raise HTTPException(503, 'Asset unavailable') from None
    else:
        raise HTTPException(404, 'Asset not found')
    return Response(data, media_type='image/svg+xml' if extension == 'svg' else 'image/png', headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; sandbox"})
