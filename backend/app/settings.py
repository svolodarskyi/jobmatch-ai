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


settings = Settings()
