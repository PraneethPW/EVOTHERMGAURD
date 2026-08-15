from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings

def async_database_url(url: str) -> str:
    """Accept Neon URLs copied from its dashboard and select the async driver."""
    if url.startswith("postgresql+asyncpg://"):
        normalized = url
    if url.startswith("postgresql+psycopg2://"):
        normalized = "postgresql+asyncpg://" + url.removeprefix("postgresql+psycopg2://")
    elif url.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    elif url.startswith("postgres://"):
        normalized = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    else:
        return url
    # Neon supplies libpq parameters; asyncpg accepts ssl but not channel_binding.
    parts = urlsplit(normalized)
    query = [("ssl" if key == "sslmode" else key, value) for key, value in parse_qsl(parts.query) if key != "channel_binding"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

engine = create_async_engine(async_database_url(settings.database_url), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
async def get_db():
    async with SessionLocal() as session:
        yield session
