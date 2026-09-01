from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TTS_ENABLED: bool = False
    TTS_MOCK_MODE: bool = True
    RESPEECHER_API_KEY: str = ""
    RESPEECHER_VOICE_ID: str = ""
    MCP_MOCK_MODE: bool = True
    OPENAI_API_KEY: str = ""


settings = Settings()
