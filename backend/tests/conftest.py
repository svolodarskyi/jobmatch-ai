import os

# Set dummy env vars before any app module is imported so pydantic-settings
# doesn't raise ValidationError during test collection.  Real integration
# tests override these at the fixture level.
os.environ.setdefault("ADZUNA_APP_ID", "test-adzuna-id")
os.environ.setdefault("ADZUNA_APP_KEY", "test-adzuna-key")
os.environ.setdefault("JOOBLE_API_KEY", "test-jooble-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-supabase-key")
