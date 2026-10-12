"""健康检查路由。部署平台和前端用它确认服务在跑。"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """存活探测。部署平台和前端都用它确认服务在跑。"""

    return {"status": "ok"}
