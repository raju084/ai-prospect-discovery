from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str = "AI-Powered Multi-Platform Prospect Discovery API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    APP_PORT: int = 4000
    APP_HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # LLM Settings
    # Supported: "gemini", "openai", "anthropic", "groq", "mock"
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-1.5-flash"
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # Search Settings
    # Supported: "ddg", "serpapi", "serper", "mock"
    SEARCH_PROVIDER: str = "ddg"
    SERPAPI_API_KEY: Optional[str] = None
    SERPER_API_KEY: Optional[str] = None

    # Concurrency and Discovery limits
    MAX_RESULTS_PER_PLATFORM: int = 5
    HTTP_TIMEOUT_SECONDS: float = 10.0
    CACHE_TTL_SECONDS: int = 3600
    ENABLE_MOCK_FALLBACK: bool = True
    MIN_RELEVANCE_SCORE: float = 0.5


settings = Settings()
