from collections.abc import Generator

from supabase import Client, create_client

from app.settings import settings


def get_client() -> Client:
    """Return a standalone Supabase client (use outside request context)."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def get_db() -> Generator[Client, None, None]:
    """FastAPI dependency that yields a Supabase client.

    Usage in a router::

        @router.get("/example")
        def example(db: Client = Depends(get_db)):
            ...
    """
    yield get_client()
