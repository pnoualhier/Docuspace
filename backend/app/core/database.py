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
    Uses safe set_config(name, value, is_local) compatible with parameterized queries.
    Prevents any cross-tenant data leakage at database engine level.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)}
    )
    val = "true" if is_superuser else "false"
    await session.execute(
        text("SELECT set_config('app.is_superuser', :val, true)"),
        {"val": val}
    )

async def reset_tenant_context(session: AsyncSession):
    """
    Explicitly resets the tenant RLS context between transactions/connections
    to prevent connection-pool leakage across subsequent requests.
    """
    try:
        await session.execute(text("SELECT set_config('app.current_tenant_id', '', true)"))
        await session.execute(text("SELECT set_config('app.is_superuser', 'false', true)"))
    except Exception:
        pass

