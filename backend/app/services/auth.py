"""Local opaque sessions and manually reviewed instructor applications.

No database is touched on import. The first store access backs up an existing
workspace through SQLite's backup API before adding the versioned auth schema.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
import hashlib
import hmac
from io import BytesIO
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import unquote, urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import HTTPException, Request
from PIL import Image
from starlette.concurrency import run_in_threadpool

from app.config import settings

SESSION_COOKIE = "coursework_session"
CSRF_COOKIE = "coursework_csrf"
SESSION_SECONDS = 7 * 24 * 3600
MAX_FILE_BYTES = 5 * 1024 * 1024
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_for(token: str) -> str:
    return digest("coursework-csrf:" + token)


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    return PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def normalized_email(value: str) -> str:
    value = value.strip().casefold()
    if len(value) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid email address")
    return value


def validate_password(value: str) -> None:
    if not 15 <= len(value) <= 128:
        raise ValueError("Use a password between 15 and 128 characters")


def safe_next(value: str | None, user: dict) -> str:
    destination = "/student" if user["role"] == "student" else "/admin" if user["role"] == "admin" else "/courses" if user["status"] == "approved" else "/application"
    if not value or "\\" in value or any(ord(char) < 32 for char in value):
        return destination
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith("//"):
        return destination
    decoded = parsed.path
    # Browsers normalize dot segments and encoded separators before navigation.
    # Reject ambiguous paths rather than checking the unnormalized prefix.
    for _ in range(8):
        following = unquote(decoded)
        if following == decoded:
            break
        decoded = following
    if "%" in decoded or "\\" in decoded or any(part in (".", "..") for part in decoded.split("/")):
        return destination
    # A role destination or its descendants is the only accepted continuation.
    if parsed.path == destination or parsed.path.startswith(destination + "/"):
        return value
    return destination


def qualification_file(filename: str, content_type: str, data: bytes) -> tuple[str, str, bytes]:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Upload a PDF, JPEG or PNG no larger than 5 MiB")
    suffix = Path(filename).suffix.lower()
    expected = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    if suffix not in expected or content_type != expected[suffix]:
        raise ValueError("Upload a PDF, JPEG or PNG document")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:] or b"<html" in data[:1024].lower():
            raise ValueError("The file does not have a valid PDF signature")
    else:
        signature = data.startswith(b"\x89PNG\r\n\x1a\n") if suffix == ".png" else data.startswith(b"\xff\xd8\xff")
        try:
            if not signature:
                raise ValueError("Invalid image signature")
            with Image.open(BytesIO(data)) as image:
                if image.format != ("PNG" if suffix == ".png" else "JPEG") or image.width * image.height > 20_000_000:
                    raise ValueError("Unsupported image dimensions or format")
                image.verify()
            # JPEG verify() checks headers only; decode pixels as well to reject
            # truncated files that otherwise have a plausible signature.
            with Image.open(BytesIO(data)) as image:
                image.load()
        except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise ValueError("The image could not be read") from exc
    # Store a display name only; never use a user-supplied filename as a path.
    name = filename.replace("\\", "/").split("/")[-1]
    name = "".join(char for char in name if ord(char) >= 32 and char not in '\";')[:160]
    return name or "qualification" + suffix, expected[suffix], data


def public_user(row: sqlite3.Row) -> dict:
    return dict(id=row["id"], name=row["name"], email=row["email"], role=row["role"], status=row["status"], reviewReason=row["review_reason"])


class AuthStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()
        self.path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _migrate(self):
        existed = self.path.exists() and self.path.stat().st_size > 0
        with self.connection() as db:
            present = db.execute("SELECT 1 FROM sqlite_master WHERE name='auth_schema_versions'").fetchone()
            if present and db.execute("SELECT 1 FROM auth_schema_versions WHERE version=1").fetchone():
                return
            if existed:
                backup_path = self.path.with_name(f"{self.path.name}.pre-auth-{time.time_ns()}.bak")
                with sqlite3.connect(backup_path) as backup:
                    db.backup(backup)
                backup_path.chmod(0o600)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS auth_schema_versions(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS users(
                    id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','instructor','admin')),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    status TEXT NOT NULL CHECK(status IN ('active','pending','approved','rejected')),
                    review_reason TEXT, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions(
                    token_digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    created_at REAL NOT NULL, expires_at REAL NOT NULL, csrf_digest TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
                CREATE TABLE IF NOT EXISTS auth_challenges(token_digest TEXT PRIMARY KEY, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS qualifications(
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL, content_type TEXT NOT NULL, data BLOB NOT NULL, submitted_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS qualification_reviews(
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
                    reviewer_id TEXT NOT NULL REFERENCES users(id), decision TEXT NOT NULL,
                    reason TEXT NOT NULL, reviewed_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS course_owners(
                    course_id TEXT PRIMARY KEY REFERENCES courses(id) ON DELETE CASCADE,
                    instructor_id TEXT NOT NULL REFERENCES users(id), assigned_at REAL NOT NULL);
                INSERT OR IGNORE INTO auth_schema_versions VALUES(1, strftime('%s','now'));
            """)

    def create_user(self, *, name: str, email: str, password: str, role: str, qualification=None) -> dict:
        email = normalized_email(email)
        validate_password(password)
        if not name.strip() or len(name.strip()) > 100 or role not in ("student", "instructor", "admin"):
            raise ValueError("Enter a name and valid account type")
        if role == "instructor" and qualification is None:
            raise ValueError("Instructor applications require a qualification document")
        if qualification:
            qualification = qualification_file(*qualification)
        password_hash = PASSWORD_HASHER.hash(password)
        user_id, now = secrets.token_urlsafe(18), time.time()
        with self.connection() as db:
            db.execute("INSERT INTO users VALUES(?,?,?,?,?,1,?,NULL,?)", (user_id,email,name.strip(),password_hash,role,"pending" if role == "instructor" else "active",now))
            if qualification:
                db.execute("INSERT INTO qualifications VALUES(?,?,?,?,?)", (user_id,*qualification,now))
            return public_user(db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    def authenticate(self, email: str, password: str) -> dict | None:
        try:
            email = normalized_email(email)
        except ValueError:
            email = ""
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        try:
            valid = PASSWORD_HASHER.verify(row["password_hash"] if row else dummy_hash(), password)
        except (VerificationError, InvalidHashError):
            valid = False
        return public_user(row) if valid and row and row["active"] else None

    def session(self, token: str | None) -> dict | None:
        if not token or len(token) > 256:
            return None
        with self.connection() as db:
            row = db.execute("SELECT u.*,s.csrf_digest FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_digest=? AND s.expires_at>? AND u.active=1", (digest(token),time.time())).fetchone()
            return public_user(row) if row else None

    def new_session(self, user: dict, old: str | None) -> tuple[str,str]:
        raw = secrets.token_urlsafe(32)
        csrf = csrf_for(raw)
        now = time.time()
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE expires_at<=? OR token_digest=?", (now,digest(old or "")))
            db.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (digest(raw),user["id"],now,now+SESSION_SECONDS,digest(csrf)))
        return raw,csrf

    def revoke(self, raw: str):
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token_digest=?", (digest(raw),))

    def challenge(self) -> str:
        token = secrets.token_urlsafe(32)
        with self.connection() as db:
            db.execute("DELETE FROM auth_challenges WHERE expires_at<=?", (time.time(),))
            # Bound persisted pre-auth rows against unbounded GET requests.
            db.execute("DELETE FROM auth_challenges WHERE token_digest IN (SELECT token_digest FROM auth_challenges ORDER BY expires_at DESC LIMIT -1 OFFSET 1000)")
            db.execute("INSERT INTO auth_challenges VALUES(?,?)", (digest(token),time.time()+900))
        return token

    def valid_csrf(self, session_token: str | None, challenge: str | None, header: str) -> bool:
        if session_token and self.session(session_token):
            with self.connection() as db:
                row=db.execute("SELECT csrf_digest FROM sessions WHERE token_digest=?",(digest(session_token),)).fetchone()
            return bool(row and hmac.compare_digest(row[0],digest(header)))
        if not challenge or not hmac.compare_digest(csrf_for(challenge),header):
            return False
        with self.connection() as db:
            return db.execute("SELECT 1 FROM auth_challenges WHERE token_digest=? AND expires_at>?",(digest(challenge),time.time())).fetchone() is not None

    def throttle(self, ip: str, email: str):
        now=time.time()
        with self.connection() as db:
            db.execute("DELETE FROM auth_attempts WHERE expires_at<=?",(now,))
            for key,limit in (("ip:"+digest(ip),30),("account:"+digest(email.strip().casefold()),6)):
                row=db.execute("SELECT count FROM auth_attempts WHERE key=?",(key,)).fetchone()
                if row and row[0]>=limit:
                    raise HTTPException(429,"Too many attempts. Try again in 15 minutes.",headers={"Retry-After":"900"})
            for key in ("ip:"+digest(ip),"account:"+digest(email.strip().casefold())):
                db.execute("INSERT INTO auth_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1",(key,now+900))
            db.execute("DELETE FROM auth_attempts WHERE key IN (SELECT key FROM auth_attempts ORDER BY expires_at DESC LIMIT -1 OFFSET 10000)")

    def applications(self) -> list[dict]:
        with self.connection() as db:
            rows=db.execute("SELECT u.*,q.filename,q.submitted_at FROM users u JOIN qualifications q ON q.user_id=u.id WHERE u.role='instructor' ORDER BY q.submitted_at DESC LIMIT 500").fetchall()
        return [dict(**public_user(row),qualificationFilename=row["filename"],submittedAt=row["submitted_at"]) for row in rows]

    def qualification(self,user_id: str):
        with self.connection() as db:
            row=db.execute("SELECT * FROM qualifications WHERE user_id=?",(user_id,)).fetchone()
            if not row:
                raise HTTPException(404,"Application not found")
            return dict(row)

    def review(self,user_id: str,reviewer_id: str,decision: str,reason: str) -> dict:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM users WHERE id=? AND role='instructor'",(user_id,)).fetchone()
            if not row:
                raise HTTPException(404,"Application not found")
            if row["status"]!="pending":
                raise HTTPException(409,"Only pending applications can be reviewed")
            db.execute("INSERT INTO qualification_reviews VALUES(?,?,?,?,?,?)",(secrets.token_urlsafe(18),user_id,reviewer_id,decision,reason.strip(),time.time()))
            db.execute("UPDATE users SET status=?,review_reason=? WHERE id=?",(decision,reason.strip() or None,user_id))
            return public_user(db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone())

    def resubmit(self,user_id: str,qualification: tuple) -> dict:
        qualification=qualification_file(*qualification)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone()
            if row["role"]!="instructor" or row["status"]!="rejected":
                raise HTTPException(409,"Only rejected applications can be resubmitted")
            db.execute("UPDATE qualifications SET filename=?,content_type=?,data=?,submitted_at=? WHERE user_id=?",(*qualification,time.time(),user_id))
            db.execute("UPDATE users SET status='pending',review_reason=NULL WHERE id=?",(user_id,))
            return public_user(db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone())

    def claim_unowned(self,email: str,course_ids: list[str]) -> list[str]:
        if not course_ids or len(set(course_ids))!=len(course_ids):
            raise ValueError("List explicit, distinct course IDs")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            user=db.execute("SELECT * FROM users WHERE email=? AND role='instructor' AND active=1",(normalized_email(email),)).fetchone()
            if not user:
                raise ValueError("Choose an existing enabled instructor")
            for course_id in course_ids:
                if not db.execute("SELECT 1 FROM courses WHERE id=?",(course_id,)).fetchone() or db.execute("SELECT 1 FROM course_owners WHERE course_id=?",(course_id,)).fetchone():
                    raise ValueError(f"Course {course_id} is missing or already owned")
            for course_id in course_ids:
                db.execute("INSERT INTO course_owners VALUES(?,?,?)",(course_id,user["id"],time.time()))
        return course_ids


@lru_cache(maxsize=32)
def _store_at(path: str) -> AuthStore:
    return AuthStore(Path(path))


def get_auth_store() -> AuthStore:
    # Import only when called: demo can import these dependencies without a cycle,
    # and the existing temporary-workspace monkeypatch remains authoritative.
    from app.api.routes import demo
    return _store_at(str(Path(demo.TEACHER_WORKSPACE_DB).resolve()))


def secure_cookie() -> bool:
    return settings.auth_cookie_secure or settings.app_env != "development"


def check_origin(request: Request):
    origin=request.headers.get("origin", "")
    if not origin or origin == "null" or origin not in settings.cors_origins or origin == "*":
        raise HTTPException(403,"Request origin is not allowed")
    if secure_cookie() and urlsplit(origin).scheme != "https":
        raise HTTPException(403,"HTTPS is required for this deployment")
    if not secure_cookie() and (urlsplit(origin).scheme!="http" or urlsplit(origin).hostname not in ("localhost","127.0.0.1","::1")):
        raise HTTPException(403,"HTTP development is limited to loopback origins")


async def require_csrf(request: Request):
    check_origin(request)
    valid=await run_in_threadpool(get_auth_store().valid_csrf,request.cookies.get(SESSION_COOKIE),request.cookies.get(CSRF_COOKIE),request.headers.get("x-csrf-token",""))
    if not valid:
        raise HTTPException(403,"The form expired. Reload and try again.")


async def current_user(request: Request) -> dict:
    user=await run_in_threadpool(get_auth_store().session,request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(401,"Sign in to continue")
    if request.method not in ("GET","HEAD","OPTIONS"):
        await require_csrf(request)
    request.state.user=user
    return user


async def approved_instructor(request: Request) -> dict:
    user=await current_user(request)
    if user["role"]!="instructor" or user["status"]!="approved":
        raise HTTPException(403,"An approved instructor account is required")
    return user


async def admin_user(request: Request) -> dict:
    user=await current_user(request)
    if user["role"]!="admin":
        raise HTTPException(403,"Administrator access is required")
    return user
