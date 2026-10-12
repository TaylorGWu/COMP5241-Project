
"""FastAPI 入口。

API 契约见 docs/design/course-generation-design.md §13。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import demo, health
from app.config import settings

app = FastAPI(title="COMP5241 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(demo.router, prefix="/api")

# 后续按 §13 添加:
#   materials / generation / artifacts / patches / admin
