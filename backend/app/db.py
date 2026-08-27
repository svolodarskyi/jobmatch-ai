from collections.abc import Generator

from supabase import Client, create_client

from app.settings import settings


def get_db() -> Generator[Client, None, None]:
    """FastAPI dependency that yields a Supabase client.

    Usage in a router::

        @router.get("/example")
        def example(db: Client = Depends(get_db)):
            ...
    """
    client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    yield client
