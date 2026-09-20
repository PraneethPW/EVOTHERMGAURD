from app.db.session import sync_database_url


def test_alembic_uses_installed_sync_database_drivers():
    assert sync_database_url("postgresql+asyncpg://u:p@db/name") == "postgresql+psycopg://u:p@db/name"
    assert sync_database_url("postgresql://u:p@db/name") == "postgresql+psycopg://u:p@db/name"
    assert sync_database_url("sqlite+aiosqlite:///./local.db") == "sqlite:///./local.db"
