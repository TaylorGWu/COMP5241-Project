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


def migrate(store, *, initial_upgrade=False):
    with store.connection() as db:
        has_v3 = bool(db.execute("SELECT 1 FROM auth_schema_versions WHERE version=3").fetchone())
        has_v4 = bool(db.execute("SELECT 1 FROM auth_schema_versions WHERE version=4").fetchone())
        if has_v3 and has_v4:
            return
        if not initial_upgrade:
            backup_path = store.path.with_name(f"{store.path.name}.pre-portal-{time.time_ns()}.bak")
            with sqlite3.connect(backup_path) as backup:
                db.backup(backup)
            backup_path.chmod(0o600)
        if has_v3 and not has_v4:
            _add_weekly_minutes(db)
            return
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
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='chapters'").fetchone():
            from app.services.course_repository import Course, Chapter
            from app.services.publication import build_snapshot
            rows = db.execute('SELECT payload_json FROM courses').fetchall()
            for row in rows:
                try:
                    raw = json.loads(row['payload_json'])
                    if raw.get('status') != 'published':
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
                except (TypeError, ValueError, KeyError):
                    continue
        db.execute("INSERT INTO auth_schema_versions VALUES(3, strftime('%s','now'))")
        _add_weekly_minutes(db)
