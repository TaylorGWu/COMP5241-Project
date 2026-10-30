"""Account, session and private qualification HTTP contracts."""
from __future__ import annotations

import json
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from app.services import teacher_profile

from app.services.auth import (
    CSRF_COOKIE, MAX_FILE_BYTES, SESSION_COOKIE, SESSION_SECONDS, admin_user,
    csrf_for, current_user, get_auth_store, require_csrf, secure_cookie,
)

router=APIRouter()


def cookie(response: Response,name: str,value: str,max_age: int):
    response.set_cookie(name,value,max_age=max_age,httponly=True,secure=secure_cookie(),samesite="lax",path="/")
    response.headers["Cache-Control"]="no-store"


async def session_response(request: Request,response: Response,user: dict) -> dict:
    raw,csrf=await run_in_threadpool(get_auth_store().new_session,user,request.cookies.get(SESSION_COOKIE))
    cookie(response,SESSION_COOKIE,raw,SESSION_SECONDS)
    response.delete_cookie(CSRF_COOKIE,path="/",secure=secure_cookie(),httponly=True,samesite="lax")
    return dict(user=user,csrfToken=csrf)


async def form_data(request: Request):
    # RequestLimitMiddleware bounds the raw stream before multipart parsing.
    content_type=request.headers.get("content-type","")
    if not content_type.startswith(("multipart/form-data", "application/x-www-form-urlencoded")):
        raise HTTPException(415,"Submit form data")
    try:
        return await request.form(max_files=1,max_fields=6,max_part_size=MAX_FILE_BYTES+1)
    except Exception as exc:
        raise HTTPException(422,"The submitted form could not be read") from exc


async def upload(value) -> tuple:
    if not isinstance(value,UploadFile):
        raise HTTPException(422,"Choose a qualification document")
    try:
        data=await value.read(MAX_FILE_BYTES+1)
        if len(data)>MAX_FILE_BYTES:
            raise HTTPException(413,"Upload a document no larger than 5 MiB")
        return (value.filename or "qualification",value.content_type or "",data)
    finally:
        await value.close()


async def json_data(request: Request,allowed: set[str]) -> dict:
    if request.headers.get("content-type","").split(";")[0].strip()!="application/json":
        raise HTTPException(415,"Submit JSON")
    try:
        data=await request.json()
    except (json.JSONDecodeError,UnicodeDecodeError) as exc:
        raise HTTPException(422,"Invalid JSON") from exc
    if not isinstance(data,dict) or set(data)-allowed or any(not isinstance(value,str) for value in data.values()):
        raise HTTPException(422,"Unexpected or invalid fields")
    return data


@router.get("/auth/csrf")
async def csrf(request: Request,response: Response):
    store=get_auth_store()
    raw=request.cookies.get(SESSION_COOKIE)
    if await run_in_threadpool(store.session,raw):
        response.headers["Cache-Control"]="no-store"
        return {"csrfToken":csrf_for(raw)}
    challenge=await run_in_threadpool(store.challenge)
    cookie(response,CSRF_COOKIE,challenge,900)
    return {"csrfToken":csrf_for(challenge)}


@router.post("/auth/register",status_code=201)
async def register(request: Request,response: Response):
    await require_csrf(request)
    form=await form_data(request)
    allowed={"name","email","password","role","qualification"}
    if set(form)-allowed or len(form.multi_items())!=len(form):
        raise HTTPException(422,"Unexpected or repeated fields")
    if any(not isinstance(form.get(key),str) for key in ("name","email","password","role")):
        raise HTTPException(422,"Complete all required fields")
    if form["role"] not in ("student","instructor"):
        raise HTTPException(422,"Choose student or instructor")
    store=get_auth_store()
    await run_in_threadpool(store.throttle,request.client.host if request.client else "unknown",form["email"])
    file=await upload(form["qualification"]) if form["role"]=="instructor" and "qualification" in form else None
    if form["role"]=="student" and form.get("qualification"):
        raise HTTPException(422,"Student accounts do not require qualifications")
    try:
        user=await run_in_threadpool(store.create_user,name=form["name"],email=form["email"],password=form["password"],role=form["role"],qualification=file)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409,"An account already exists for this email") from exc
    return await session_response(request,response,user)


@router.post("/auth/login")
async def login(request: Request,response: Response):
    await require_csrf(request)
    data=await json_data(request,{"email","password"})
    email,password=data.get("email",""),data.get("password","")
    if len(email)>254 or len(password)>128:
        raise HTTPException(422,"Invalid email or password length")
    store=get_auth_store()
    await run_in_threadpool(store.throttle,request.client.host if request.client else "unknown",email)
    user=await run_in_threadpool(store.authenticate,email,password)
    if not user:
        raise HTTPException(401,"Email or password is incorrect")
    return await session_response(request,response,user)


@router.get("/auth/me")
async def me(request: Request,response: Response):
    user=await current_user(request)
    response.headers["Cache-Control"]="no-store"
    return dict(user=user,csrfToken=csrf_for(request.cookies[SESSION_COOKIE]))


@router.post("/auth/logout")
async def logout(request: Request,response: Response):
    await current_user(request)
    await run_in_threadpool(get_auth_store().revoke,request.cookies[SESSION_COOKIE])
    response.delete_cookie(SESSION_COOKIE,path="/",secure=secure_cookie(),httponly=True,samesite="lax")
    response.delete_cookie(CSRF_COOKIE,path="/",secure=secure_cookie(),httponly=True,samesite="lax")
    response.headers["Cache-Control"]="no-store"
    return {"ok":True}


def attachment(file: dict) -> Response:
    return Response(content=file["data"],media_type=file["content_type"],headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(file['filename'],safe='')}","X-Content-Type-Options":"nosniff","Cache-Control":"no-store","Content-Security-Policy":"sandbox; default-src 'none'"})


@router.get("/auth/qualification")
async def qualification(request: Request):
    user=await current_user(request)
    if user["role"]!="instructor":
        raise HTTPException(403,"Instructor account required")
    return attachment(await run_in_threadpool(get_auth_store().qualification,user["id"]))


async def profile_teacher(request: Request):
    user = await current_user(request)
    if user["role"] != "instructor":
        raise HTTPException(403, "Instructor account required")
    return user


@router.get("/auth/profile")
async def get_profile(request: Request):
    user = await profile_teacher(request)
    return {"profile": await run_in_threadpool(teacher_profile.profile, get_auth_store(), user["id"])}


@router.put("/auth/profile")
async def put_profile(request: Request, values: teacher_profile.TeacherProfileInput):
    user = await profile_teacher(request)
    return {"profile": await run_in_threadpool(teacher_profile.save_profile, get_auth_store(), user["id"], values)}


def avatar_response(data: bytes):
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox"})


@router.get("/auth/avatar")
async def get_avatar(request: Request):
    user = await profile_teacher(request)
    return avatar_response(await run_in_threadpool(teacher_profile.avatar, get_auth_store(), user["id"]))


@router.put("/auth/avatar")
async def put_avatar(request: Request):
    user = await profile_teacher(request)
    form = await form_data(request)
    if set(form) != {"avatar"} or len(form.multi_items()) != 1 or not isinstance(form["avatar"], UploadFile):
        raise HTTPException(422, "Choose one photo")
    value = form["avatar"]
    try:
        data = await value.read(MAX_FILE_BYTES + 1)
        clean = await run_in_threadpool(teacher_profile.clean_avatar, data, value.content_type or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        await value.close()
    return {"profile": await run_in_threadpool(teacher_profile.save_avatar, get_auth_store(), user["id"], clean)}


@router.delete("/auth/avatar")
async def delete_avatar(request: Request):
    user = await profile_teacher(request)
    return {"profile": await run_in_threadpool(teacher_profile.save_avatar, get_auth_store(), user["id"], None)}


@router.get("/admin/applications/{user_id}/profile")
async def applicant_profile(user_id: str, request: Request):
    await admin_user(request)
    return {"profile": await run_in_threadpool(teacher_profile.profile, get_auth_store(), user_id, applicant=True)}


@router.get("/admin/applications/{user_id}/avatar")
async def applicant_avatar(user_id: str, request: Request):
    await admin_user(request)
    return avatar_response(await run_in_threadpool(teacher_profile.avatar, get_auth_store(), user_id, applicant=True))


@router.post("/auth/qualification")
async def resubmit(request: Request):
    user=await current_user(request)
    if user["role"]!="instructor":
        raise HTTPException(403,"Instructor account required")
    form=await form_data(request)
    if set(form)!={"qualification"} or len(form.multi_items())!=1:
        raise HTTPException(422,"Choose one qualification document")
    file=await upload(form["qualification"])
    try:
        user=await run_in_threadpool(get_auth_store().resubmit,user["id"],file)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {"user":user}


@router.get("/admin/applications")
async def applications(request: Request):
    await admin_user(request)
    return {"applications":await run_in_threadpool(get_auth_store().applications)}


@router.get("/admin/applications/{user_id}/qualification")
async def application_qualification(user_id: str,request: Request):
    await admin_user(request)
    return attachment(await run_in_threadpool(get_auth_store().qualification,user_id))


@router.post("/admin/applications/{user_id}/review")
async def review(user_id: str,request: Request):
    reviewer=await admin_user(request)
    data=await json_data(request,{"decision","reason"})
    decision,reason=data.get("decision"),data.get("reason","").strip()
    if decision not in ("approved","rejected") or len(reason)>1000 or (decision=="rejected" and not reason):
        raise HTTPException(422,"Choose a decision and give a reason for rejection")
    return {"user":await run_in_threadpool(get_auth_store().review,user_id,reviewer["id"],decision,reason)}


class RequestLimitMiddleware:
    """Bound auth request streams, including chunked bodies, before parsing files."""
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        if scope["type"]!="http":
            return await self.app(scope,receive,send)
        private=scope["path"].startswith(("/api/auth/","/api/admin/","/api/demo/"))
        async def private_send(message):
            if private and message["type"]=="http.response.start":
                message["headers"]=[(key,value) for key,value in message.get("headers",[]) if key.lower()!=b"cache-control"]+[(b"cache-control",b"no-store")]
            await send(message)
        if scope["method"] in ("POST","PUT","PATCH") and scope["path"].startswith(("/api/auth/","/api/admin/")):
            limit=MAX_FILE_BYTES+64*1024 if scope["path"] in ("/api/auth/register","/api/auth/qualification","/api/auth/avatar") else 16*1024
            chunks=[]
            total=0
            while True:
                message=await receive()
                if message["type"]=="http.disconnect":
                    return
                chunk=message.get("body",b"")
                total+=len(chunk)
                if total>limit:
                    return await Response("Request is too large",status_code=413,headers={"Cache-Control":"no-store"})(scope,receive,send)
                chunks.append(chunk)
                if not message.get("more_body"):
                    break
            consumed=False
            async def bounded_receive():
                nonlocal consumed
                if not consumed:
                    consumed=True
                    return {"type":"http.request","body":b"".join(chunks),"more_body":False}
                return await receive()
            return await self.app(scope,bounded_receive,private_send)
        return await self.app(scope,receive,private_send)
