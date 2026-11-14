"""Versioned storage for authenticated learning and administration."""
import sqlite3
import time
import json


def _add_weekly_minutes(db):
    """v4: a learner's weekly time budget, used to explain the next-step recommendation."""
    columns = {row['name'] for row in db.execute('PRAGMA table_info(portal_profiles)')}
    if 'weekly_minutes' not in columns:
        db.execute('ALTER TABLE portal_profiles ADD COLUMN weekly_minutes INTEGER NOT NULL DEFAULT 0')
    db.execute("INSERT INTO auth_schema_versions VALUES(4, strftime('%s','now'))")


def _deliver_published_courses(db):
    """Give every published course the snapshot learners actually read.

    A published course without a snapshot is invisible to students: the read path
    only serves snapshots. Seeding at v3 and repairing at v5 both go through here,
    so a row that predates the portal layer cannot silently stay undeliverable.
    """
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='chapters'").fetchone():
        return 0
    from app.services.course_repository import Course, Chapter
    from app.services.publication import build_snapshot

    delivered = 0
    for row in db.execute('SELECT id, payload_json FROM courses').fetchall():
        try:
            raw = json.loads(row['payload_json'])
            if raw.get('status') != 'published':
                continue
            if db.execute('SELECT 1 FROM portal_publications WHERE course_id=?', (row['id'],)).fetchone():
                continue
            course = Course(**raw)
            chapters = {r['id']: Chapter(**json.loads(r['payload_json'])) for r in db.execute('SELECT id,payload_json FROM chapters WHERE course_id=?', (course.id,))}

            class SnapshotRepository:
                def get_chapter(self, ignored, chapter_id):
                    return chapters[chapter_id]

            snapshot = build_snapshot(SnapshotRepository(), course)
            if not snapshot['chapters']:
                continue
            db.execute('INSERT INTO portal_publications VALUES(?,?)', (course.id, json.dumps(snapshot, ensure_ascii=False)))
            delivered += 1
        except (TypeError, ValueError, KeyError):
            continue
    return delivered


def _publish_objectives(db):
    """v6: give every existing snapshot the course objectives.

    The learner tutor may only read what was published, so the objectives have to
    live in the snapshot. Chapters are left exactly as they are - this only adds the
    field, it does not re-cut the published content.
    """
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='portal_publications'").fetchone():
        return 0
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='courses'").fetchone():
        return 0
    repaired = 0
    rows = db.execute('SELECT p.course_id, p.snapshot, c.payload_json FROM portal_publications p JOIN courses c ON c.id=p.course_id').fetchall()
    for row in rows:
        try:
            snapshot = json.loads(row['snapshot'])
            if 'learningObjectives' in snapshot:
                continue
            course = json.loads(row['payload_json'])
            snapshot['learningObjectives'] = [
                dict(item) for item in (course.get('learning_objectives') or []) if isinstance(item, dict)
            ]
            db.execute('UPDATE portal_publications SET snapshot=? WHERE course_id=?',
                       (json.dumps(snapshot, ensure_ascii=False), row['course_id']))
            repaired += 1
        except (TypeError, ValueError, KeyError):
            continue
    return repaired


def migrate(store, *, initial_upgrade=False):
    with store.connection() as db:
        present = {row[0] for row in db.execute('SELECT version FROM auth_schema_versions')}
        if {3, 4, 5, 6} <= present:
            return
        if not initial_upgrade:
            backup_path = store.path.with_name(f"{store.path.name}.pre-portal-{time.time_ns()}.bak")
            with sqlite3.connect(backup_path) as backup:
                db.backup(backup)
            backup_path.chmod(0o600)
        if 3 not in present:
            db.executescript('''
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS portal_publications(course_id TEXT PRIMARY KEY REFERENCES courses(id), snapshot TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS portal_profiles(user_id TEXT PRIMARY KEY REFERENCES users(id), background TEXT NOT NULL, goal TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS portal_enrollments(course_id TEXT NOT NULL REFERENCES courses(id), user_id TEXT NOT NULL REFERENCES users(id), created_at REAL NOT NULL, PRIMARY KEY(course_id,user_id));
                CREATE TABLE IF NOT EXISTS portal_visits(course_id TEXT NOT NULL, user_id TEXT NOT NULL, chapter_id TEXT NOT NULL, slide_id TEXT NOT NULL, visited_at REAL NOT NULL, PRIMARY KEY(course_id,user_id,chapter_id,slide_id), FOREIGN KEY(course_id,user_id) REFERENCES portal_enrollments(course_id,user_id));
                CREATE TABLE IF NOT EXISTS portal_attempts(id TEXT PRIMARY KEY, submission_id TEXT NOT NULL, course_id TEXT NOT NULL, user_id TEXT NOT NULL, chapter_id TEXT NOT NULL, question_id TEXT NOT NULL, option_id TEXT NOT NULL, correct INTEGER NOT NULL, correct_option TEXT NOT NULL, explanation TEXT NOT NULL, created_at REAL NOT NULL, question_hash TEXT NOT NULL, UNIQUE(user_id,submission_id), FOREIGN KEY(course_id,user_id) REFERENCES portal_enrollments(course_id,user_id));
                CREATE TABLE IF NOT EXISTS portal_invites(code TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses(id));
                CREATE TABLE IF NOT EXISTS portal_moderation(course_id TEXT PRIMARY KEY REFERENCES courses(id), reason TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id), at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS portal_audit(id TEXT PRIMARY KEY, kind TEXT NOT NULL, actor_id TEXT NOT NULL REFERENCES users(id), course_id TEXT, title TEXT NOT NULL, status TEXT NOT NULL, reason TEXT, at REAL NOT NULL);
            ''')
            _deliver_published_courses(db)
            db.execute("INSERT INTO auth_schema_versions VALUES(3, strftime('%s','now'))")
        if 4 not in present:
            _add_weekly_minutes(db)
        if 5 not in present:
            _deliver_published_courses(db)
            db.execute("INSERT INTO auth_schema_versions VALUES(5, strftime('%s','now'))")
        if 6 not in present:
            _publish_objectives(db)
            db.execute("INSERT INTO auth_schema_versions VALUES(6, strftime('%s','now'))")
