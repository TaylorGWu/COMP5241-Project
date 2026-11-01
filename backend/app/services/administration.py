"""Transactional account and course moderation operations."""
import json
import secrets
import time

from fastapi import HTTPException
from app.services.auth import get_auth_store


def users():
    with get_auth_store().connection() as db:
        return [dict(id=r['id'], name=r['name'], email=r['email'], role=r['role'], status=r['status'], active=bool(r['active']), createdAt=r['created_at']) for r in db.execute('SELECT * FROM users ORDER BY created_at DESC')]


def log(db, actor, kind, title, status, course_id=None, reason=None):
    db.execute('INSERT INTO portal_audit VALUES(?,?,?,?,?,?,?,?)', (secrets.token_urlsafe(18), kind, actor, course_id, title, status, reason, time.time()))


def update_user(actor, user_id, role, active):
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1", (actor,)).fetchone():
            raise HTTPException(403, 'Administrator access is required')
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'User not found')
        role = role if role is not None else row['role']
        active = active if active is not None else bool(row['active'])
        if row['id'] == actor and (role != 'admin' or not active):
            raise HTTPException(409, 'Cannot lock yourself out')
        if row['role'] == 'admin' and row['active'] and (role != 'admin' or not active):
            if db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                raise HTTPException(409, 'At least one administrator must remain enabled')
        if role == row['role'] and active == bool(row['active']):
            return dict(id=row['id'], name=row['name'], email=row['email'], role=row['role'], status=row['status'], active=bool(row['active']), createdAt=row['created_at'])
        status = row['status'] if role == row['role'] else 'pending' if role == 'instructor' else 'active'
        db.execute('UPDATE users SET role=?,active=?,status=?,review_reason=NULL WHERE id=?', (role, int(active), status, user_id))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        log(db, actor, 'user-update', row['name'], role if active else 'disabled')
    return next(user for user in users() if user['id'] == user_id)


def courses():
    with get_auth_store().connection() as db:
        rows = db.execute('SELECT c.id,c.payload_json,u.name AS owner_name,m.reason FROM courses c LEFT JOIN course_owners o ON o.course_id=c.id LEFT JOIN users u ON u.id=o.instructor_id LEFT JOIN portal_moderation m ON m.course_id=c.id ORDER BY c.id').fetchall()
        result = []
        for row in rows:
            course = json.loads(row['payload_json'])
            result.append(dict(id=row['id'], title=course.get('title', ''), courseCode=course.get('course_code', ''), ownerName=row['owner_name'], status=course.get('status', 'draft'), archived=row['reason'] is not None, moderationReason=row['reason'], chapterCount=len(course.get('chapter_ids', []))))
        return result


def moderate(actor, course_id, reason):
    with get_auth_store().connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1", (actor,)).fetchone():
            raise HTTPException(403, 'Administrator access is required')
        row = db.execute('SELECT payload_json FROM courses WHERE id=?', (course_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Course not found')
        title = json.loads(row['payload_json']).get('title', '')
        if reason is not None:
            db.execute('INSERT INTO portal_moderation VALUES(?,?,?,?) ON CONFLICT(course_id) DO UPDATE SET reason=excluded.reason,actor_id=excluded.actor_id,at=excluded.at', (course_id, reason, actor, time.time()))
        else:
            db.execute('DELETE FROM portal_moderation WHERE course_id=?', (course_id,))
        log(db, actor, 'course-archive' if reason is not None else 'course-restore', title, 'archived' if reason is not None else 'restored', course_id, reason)
    return next(course for course in courses() if course['id'] == course_id)


def audit():
    with get_auth_store().connection() as db:
        events = [dict(id=r['id'], kind=r['kind'], actor=r['name'], courseId=r['course_id'], title=r['title'], status=r['status'], at=r['at'], reason=r['reason']) for r in db.execute('SELECT a.*,u.name FROM portal_audit a JOIN users u ON u.id=a.actor_id ORDER BY a.at DESC')]
        events += [dict(id=r['id'], kind='qualification-review', actor=r['reviewer'], title=r['applicant'], status=r['decision'], at=r['reviewed_at'], reason=r['reason']) for r in db.execute('SELECT q.*,a.name AS applicant,u.name AS reviewer FROM qualification_reviews q JOIN users a ON a.id=q.user_id JOIN users u ON u.id=q.reviewer_id')]
        titles = {r['id']: json.loads(r['payload_json']).get('title', '') for r in db.execute('SELECT id,payload_json FROM courses')}
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='teacher_state'").fetchone():
            row = db.execute("SELECT payload_json FROM teacher_state WHERE state_key='teacher-course-service'").fetchone()
            if row:
                for course_id, versions in json.loads(row['payload_json']).get('versions', {}).items():
                    for version in versions:
                        kind = version.get('kind')
                        if course_id in titles and kind in {'generation', 'publish', 'unpublish', 'manual-edit', 'rollback', 'course-update'}:
                            events.append(dict(id=version['id'], kind=kind, actor=None, courseId=course_id, title=titles[course_id], status='recorded', at=None, model=None, reason=None))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='patches'").fetchone():
            for row in db.execute('SELECT id,scope_id,kind,status FROM patches'):
                course_id = row['scope_id'].split(':', 1)[0]
                if course_id in titles:
                    events.append(dict(id=row['id'], kind='patch', actor=None, courseId=course_id, title=titles[course_id], status=row['status'], at=None, model=None, reason=None))
        return sorted(events, key=lambda event: event['at'] or 0, reverse=True)
