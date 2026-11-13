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


# Matching on function words produced nonsense reasons ("both contain 'and'"),
# so the overlap only counts content words.
_STOPWORDS = {
    'and', 'the', 'with', 'for', 'that', 'from', 'into', 'of', 'to', 'in', 'on', 'at',
    'by', 'or', 'as', 'is', 'are', 'be', 'it', 'this', 'these', 'those', 'you', 'your',
    'my', 'me', 'we', 'our', 'they', 'their', 'can', 'will', 'would', 'should', 'about',
    'across', 'after', 'before', 'between', 'each', 'more', 'most', 'other', 'some',
    'such', 'than', 'then', 'there', 'when', 'where', 'which', 'while', 'how', 'what',
    'why', 'who', 'apply', 'use', 'using', 'learn', 'learning',
}


def _tokens(text):
    return {word for word in re.findall(r'\w+', text.casefold())
            if len(word) > 1 and word not in _STOPWORDS}


def next_step(courses, profile):
    """Pick one explainable next course and say why.

    The recommendation answers the learner's profile: rank new courses by goal
    overlap, then by whether they fit the weekly time budget, with the shortest
    course as the default. Courses the learner is already taking stay out of it
    - they keep living in the learning tab, where their progress is shown.
    """
    goal = _tokens(profile.get('background', '') + ' ' + profile.get('goal', ''))
    minutes = profile.get('weeklyMinutes') or 0
    ranked = []
    for item in courses:
        if item['enrolled']:
            continue
        words = _tokens(' '.join(str(item[key]) for key in ('title', 'description', 'courseCode', 'subject')))
        overlap = len(goal & words)
        fits_time = bool(minutes) and item['durationMin'] <= minutes
        ranked.append((min(overlap, 3) * 2 + (1 if fits_time else 0), overlap > 0, fits_time, item['durationMin'], item['id'], item))
    if not ranked:
        return None
    ranked.sort(key=lambda entry: (-entry[0], entry[3], entry[4]))
    _score, matched_goal, fits_time, _duration, _course_id, item = ranked[0]
    if matched_goal:
        reason_code, reason = 'goal', 'It matches words in your background and goal.'
    elif fits_time:
        reason_code, reason = 'time', 'It fits the time you have available each week.'
    else:
        reason_code, reason = 'start', 'A short course to begin with.'
    return {'courseId': item['id'], 'reasonCode': reason_code, 'reason': reason}


@router.get("/home")
async def home(request: Request):
    user = await student_user(request)
    with get_auth_store().connection() as db:
        ids = [r[0] for r in db.execute('SELECT course_id FROM portal_publications')]
        profile = db.execute('SELECT background,goal,weekly_minutes FROM portal_profiles WHERE user_id=?', (user['id'],)).fetchone()
    courses = []
    for course_id in ids:
        try:
            courses.append(course_summary(available(course_id), user['id']))
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
    stored = dict(profile) if profile else {'background': '', 'goal': '', 'weekly_minutes': 0}
    profile = {'background': stored['background'], 'goal': stored['goal'], 'weeklyMinutes': stored['weekly_minutes']}
    return {"courses": courses, "profile": profile, "recommendation": next_step(courses, profile)}


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    background: str = Field(max_length=500)
    goal: str = Field(max_length=500)
    # Optional so older clients keep working; None leaves the stored value alone.
    weeklyMinutes: int | None = Field(default=None, ge=0, le=6000)


class Visit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slideId: str = Field(min_length=1, max_length=128)


class TutorAsk(BaseModel):
    slideId: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=2, max_length=600)


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
    # One state read per chapter already ran for the percentage; keep the answers
    # from the same call so the learner can see pages read and answers correct.
    pairs = [learning.state(snapshot['id'], chapter, user_id) for chapter in chapters] if is_enrolled else []
    states = [progress for progress, _ in pairs]
    answers = [results for _, results in pairs]
    days, last_studied = learning.study_activity(snapshot['id'], user_id) if is_enrolled else (0, None)
    last = (None, None)
    if is_enrolled:
        valid = {(chapter['id'], slide['id']) for chapter in chapters for slide in chapter['slides']}
        with get_auth_store().connection() as db:
            visits = db.execute('SELECT chapter_id,slide_id FROM portal_visits WHERE course_id=? AND user_id=? ORDER BY visited_at DESC', (snapshot['id'], user_id)).fetchall()
        last = next(((row['chapter_id'], row['slide_id']) for row in visits if (row['chapter_id'], row['slide_id']) in valid), last)
    return {key: snapshot[key] for key in ('id', 'title', 'description', 'courseCode', 'subject', 'level', 'durationMin')} | {
        'chapterCount': len(chapters),
        'chapterTitles': [chapter['title'] for chapter in chapters],
        'enrolled': is_enrolled,
        'completionPercent': round(sum(s['completionPercent'] for s in states) / len(states)) if states else 0,
        'lastChapterId': last[0],
        'lastSlideId': last[1],
        'totalSlides': sum(len(chapter['slides']) for chapter in chapters),
        'visitedSlides': sum(len(set(s['visitedSlideIds'])) for s in states),
        'totalQuestions': sum(len(learning.mcqs(chapter)) for chapter in chapters),
        'answeredQuestions': sum(len(chapter_answers) for chapter_answers in answers),
        'correctAnswers': sum(1 for chapter_answers in answers for item in chapter_answers.values() if item['correct']),
        'studyDays': days,
        'lastStudiedAt': last_studied,
    }


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
        stored = db.execute('SELECT weekly_minutes FROM portal_profiles WHERE user_id=?', (user['id'],)).fetchone()
        minutes = body.weeklyMinutes if body.weeklyMinutes is not None else (stored['weekly_minutes'] if stored else 0)
        db.execute('''INSERT INTO portal_profiles(user_id,background,goal,weekly_minutes) VALUES(?,?,?,?)
                      ON CONFLICT(user_id) DO UPDATE SET background=excluded.background,goal=excluded.goal,weekly_minutes=excluded.weekly_minutes''',
                   (user['id'], body.background.strip(), body.goal.strip(), minutes))
    return {'profile': {'background': body.background.strip(), 'goal': body.goal.strip(), 'weeklyMinutes': minutes}}


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
    previous, following = learning.chapter_neighbours(course_id, chapter_id)
    return {'chapter': learning.safe_chapter(course_id, chapter, user['id']), 'progress': progress, 'results': results,
            'previousChapter': previous, 'nextChapter': following,
            # The top bar shows the course this chapter belongs to, like the teacher's.
            'courseTitle': available(course_id).get('title', '')}


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


@router.post('/courses/{course_id}/chapters/{chapter_id}/tutor')
async def tutor_reply(course_id: str, chapter_id: str, request: Request, body: TutorAsk):
    """Answer a question about one slide, from the published snapshot only."""
    from app.config import settings
    from app.llm.client import build_deepseek_client
    from app.services import tutor
    from app.llm.router import get_router

    user = await student_user(request)
    learning.get_chapter(course_id, chapter_id, user['id'])  # enrollment + publication check
    snapshot = available(course_id)
    try:
        context = tutor.context_for(snapshot, chapter_id, body.slideId)
    except KeyError as error:
        raise HTTPException(404, 'That slide is no longer published') from error
    if not settings.deepseek_api_key:
        raise HTTPException(503, 'No model key is configured for the tutor')
    task = get_router().for_task('tutor')
    reply = await tutor.answer(
        build_deepseek_client(), settings.deepseek_model, context, body.question,
        temperature=task.temperature,
    )
    if not reply:
        raise HTTPException(502, 'The tutor did not answer. Try again.')
    return {'answer': reply}

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
