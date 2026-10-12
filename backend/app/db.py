
"""数据库连接。

表结构见 docs/design/course-generation-design.md §5.3,ERD 见 §5.4。
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖:每个请求一个 session,用完自动关闭。"""

    async with SessionLocal() as session:
        yield session
