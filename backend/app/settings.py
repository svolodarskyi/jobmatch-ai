from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Adzuna Canada job search API credentials
    ADZUNA_APP_ID: str
    ADZUNA_APP_KEY: str

    # Jooble job search API key
    JOOBLE_API_KEY: str

    # OpenAI API key for Pass 2 re-ranking
    OPENAI_API_KEY: str

    # Supabase connection details
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Scheduler: how often to run the fetch pipeline (in hours)
    FETCH_INTERVAL_HOURS: int = 24

    # Fetch window: days of listings to retrieve on first run vs. subsequent runs
    FETCH_INITIAL_DAYS: int = 15
    FETCH_INCREMENTAL_DAYS: int = 1


settings = Settings()
