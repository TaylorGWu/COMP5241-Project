"""角色鉴权依赖。

NFR-02:授权由后端强制,前端隐藏不作为安全边界。
"""

from enum import StrEnum

from fastapi import Depends, HTTPException, Request, status
from app.services.auth import current_user


class Role(StrEnum):
    """平台只有这三种角色。加角色要同步改 requirements.md 的权限矩阵。"""

    student = "student"
    instructor = "instructor"
    admin = "admin"


async def current_role(request: Request) -> Role:
    """Resolve server-owned identity and current instructor approval each time."""
    user = await current_user(request)
    if user["role"] == "instructor" and user["status"] != "approved":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "An approved instructor account is required")
    return Role(user["role"])


def require_role(*allowed: Role):
    """用法:Depends(require_role(Role.instructor))"""

    async def _guard(role: Role = Depends(current_role)) -> Role:
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权访问"
            )
        return role

    return _guard
