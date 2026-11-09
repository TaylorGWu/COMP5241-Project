
"""FastAPI 入口。

API 契约见 docs/design/course-generation-design.md §13。
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, demo, health, student
from app.config import settings
from app.services.course_repository import CourseLockedError

app = FastAPI(title="COMP5241 API", version="0.1.0")


@app.exception_handler(CourseLockedError)
async def published_course_locked(_request: Request, error: CourseLockedError) -> JSONResponse:
    """Published content is read-only, so changing it is a conflict, not a typo."""
    return JSONResponse(status_code=409, content={"detail": str(error)})


app.add_middleware(auth.RequestLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(demo.router, prefix="/api")
app.include_router(student.router, prefix="/api")
app.include_router(admin.router, prefix="/api")

# 后续按 §13 添加:
#   materials / generation / artifacts / patches / admin
