from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from backend.app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a database session without preset tenant."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def set_tenant_context(session: AsyncSession, tenant_id: str, is_superuser: bool = False):
    """
    Sets the transaction-scoped PostgreSQL session variables for Row-Level Security (RLS).
    Prevents any cross-tenant data leakage at database engine level.
    """
    await session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_id)}
    )
    if is_superuser:
        await session.execute(text("SET LOCAL app.is_superuser = 'true'"))
    else:
        await session.execute(text("SET LOCAL app.is_superuser = 'false'"))

async def reset_tenant_context(session: AsyncSession):
    """
    Explicitly resets the tenant RLS context between transactions/connections
    to prevent connection-pool leakage across subsequent requests.
    """
    try:
        await session.execute(text("RESET app.current_tenant_id"))
        await session.execute(text("RESET app.is_superuser"))
    except Exception:
        pass

