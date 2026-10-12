"""角色鉴权依赖。

NFR-02:授权由后端强制,前端隐藏不作为安全边界。
"""

from enum import StrEnum

from fastapi import Depends, HTTPException, status


class Role(StrEnum):
    """平台只有这三种角色。加角色要同步改 requirements.md 的权限矩阵。"""

    student = "student"
    instructor = "instructor"
    admin = "admin"


async def current_role() -> Role:
    """占位实现:接入 JWT 后从 token 解析角色与身份。

    在鉴权真正接好之前一律返回 401 ——
    宁可让接口不可用,也不能让未授权请求被当作通过。
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="认证尚未接入(见 docs/design/course-generation-design.md §5.5)",
    )


def require_role(*allowed: Role):
    """用法:Depends(require_role(Role.instructor))"""

    async def _guard(role: Role = Depends(current_role)) -> Role:
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="当前角色无权访问"
            )
        return role

    return _guard
