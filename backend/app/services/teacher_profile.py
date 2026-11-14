"""Optional, private teacher profiles. Profile edits never confer permissions."""
from io import BytesIO
import json
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator
from PIL import Image, ImageOps

SUBJECTS = {"software-engineering", "programming", "web-development", "databases", "testing", "systems", "security", "data-science", "other"}


class TeacherProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    bio: str = Field(default="", max_length=1000)
    institution: str = Field(default="", max_length=160)
    independent: StrictBool = False
    position: str = Field(default="", max_length=100)
    university: str = Field(default="", max_length=160)
    degree: Literal["", "secondary", "diploma", "bachelor", "master", "doctorate", "other"] = ""
    experience: Literal["", "0-2", "3-5", "6-10", "11+"] = ""
    subjects: list[str] = Field(default_factory=list, max_length=9)
    otherSubject: str = Field(default="", max_length=100)

    @field_validator("subjects")
    @classmethod
    def valid_subjects(cls, value):
        if len(value) != len(set(value)) or any(item not in SUBJECTS for item in value):
            raise ValueError("Choose distinct supported subjects")
        return value

    @model_validator(mode="after")
    def consistent_fields(self):
        if "other" in self.subjects and not self.otherSubject:
            raise ValueError("Describe your other subject")
        if "other" not in self.subjects:
            self.otherSubject = ""
        if self.independent:
            self.institution = ""
        return self


def migrate(store):
    with store.connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS teacher_profiles(
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                details TEXT NOT NULL DEFAULT '{}', avatar BLOB, avatar_version TEXT);
            INSERT OR IGNORE INTO auth_schema_versions VALUES(2, strftime('%s','now'));
        """)


def profile(store, user_id: str, *, applicant=False):
    with store.connection() as db:
        user = db.execute("SELECT name FROM users WHERE id=? AND role='instructor'", (user_id,)).fetchone()
        if not user or (applicant and not db.execute("SELECT 1 FROM qualifications WHERE user_id=?", (user_id,)).fetchone()):
            raise HTTPException(404, "Teacher profile not found")
        row = db.execute("SELECT details,avatar_version FROM teacher_profiles WHERE user_id=?", (user_id,)).fetchone()
        details = TeacherProfileInput(name=user["name"]).model_dump()
        if row:
            details.update(json.loads(row["details"]))
        details.update(name=user["name"], hasAvatar=bool(row and row["avatar_version"]), avatarVersion=row["avatar_version"] if row else None)
        return details


def save_profile(store, user_id: str, values: TeacherProfileInput):
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM users WHERE id=? AND role='instructor' AND active=1", (user_id,)).fetchone():
            raise HTTPException(403, "Instructor account required")
        db.execute("INSERT INTO teacher_profiles(user_id,details) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET details=excluded.details", (user_id, json.dumps(values.model_dump(), ensure_ascii=False)))
        db.execute("UPDATE users SET name=? WHERE id=?", (values.name, user_id))
    return profile(store, user_id)


def clean_avatar(data: bytes, content_type: str):
    if not data or len(data) > 5 * 1024 * 1024 or content_type not in ("image/png", "image/jpeg"):
        raise ValueError("Choose a JPG or PNG photo no larger than 5 MB")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != {"image/png": "PNG", "image/jpeg": "JPEG"}[content_type] or image.width * image.height > 20_000_000:
                raise ValueError("Choose a JPG or PNG photo with at most 20 million pixels")
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGBA")
            image.thumbnail((512, 512))
            # Re-encode pixel data only: no EXIF, filenames, scripts or animation.
            clean = Image.new("RGB", image.size, "white")
            clean.paste(image, mask=image.getchannel("A"))
            output = BytesIO()
            clean.save(output, format="JPEG", quality=88)
            return output.getvalue()
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("The photo could not be read. Choose another JPG or PNG") from exc


def save_avatar(store, user_id: str, data: bytes | None):
    with store.connection() as db:
        db.execute("INSERT INTO teacher_profiles(user_id,avatar,avatar_version) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET avatar=excluded.avatar,avatar_version=excluded.avatar_version", (user_id, data, secrets.token_urlsafe(12) if data else None))
    return profile(store, user_id)


def avatar(store, user_id: str, *, applicant=False):
    profile(store, user_id, applicant=applicant)
    with store.connection() as db:
        row = db.execute("SELECT avatar FROM teacher_profiles WHERE user_id=?", (user_id,)).fetchone()
        if not row or not row["avatar"]:
            raise HTTPException(404, "Photo not found")
        return row["avatar"]
