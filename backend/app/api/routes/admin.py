"""Administrator portal; qualification routes remain in auth."""
from typing import Literal
from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from app.services.auth import admin_user
from app.services import administration

router = APIRouter(prefix='/admin', tags=['admin'])


class UserChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Literal['student', 'instructor', 'admin'] | None = None
    active: StrictBool | None = None


class Archive(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=1000)


@router.get('/users')
async def users(request: Request):
    await admin_user(request)
    return {'users': administration.users()}


@router.patch('/users/{user_id}')
async def update_user(user_id: str, request: Request, body: UserChange):
    actor = await admin_user(request)
    return {'user': administration.update_user(actor['id'], user_id, body.role, body.active)}


@router.get('/courses')
async def courses(request: Request):
    await admin_user(request)
    return {'courses': administration.courses()}


@router.post('/courses/{course_id}/archive')
async def archive(course_id: str, request: Request, body: Archive):
    actor = await admin_user(request)
    return {'course': administration.moderate(actor['id'], course_id, body.reason)}


@router.post('/courses/{course_id}/restore')
async def restore(course_id: str, request: Request):
    actor = await admin_user(request)
    return {'course': administration.moderate(actor['id'], course_id, None)}


@router.get('/audit')
async def audit(request: Request):
    await admin_user(request)
    return {'events': administration.audit()}


@router.get('/overview')
async def overview(request: Request):
    await admin_user(request)
    return administration.overview()
