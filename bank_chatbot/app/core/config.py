"""
Configuration management for the Bank Chatbot application.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings"""

    # Ignore unrelated keys in the environment/.env (e.g. LDAP_* used by other scripts)
    # so the API can boot even when additional variables are present.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Application
    APP_NAME: str = "Bank Chatbot"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    CORS_ORIGINS: Union[str, List[str]] = "*"  # Can be "*" or list of origins
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list"""
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            # Handle comma-separated list
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    
    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bank_chatbot")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct PostgreSQL database URL"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_CACHE_TTL: int = int(os.getenv("REDIS_CACHE_TTL", "3600"))  # 1 hour default
    
    # LightRAG
    LIGHTRAG_URL: str = os.getenv("LIGHTRAG_URL", "http://localhost:9262/query")
    LIGHTRAG_API_KEY: str = os.getenv("LIGHTRAG_API_KEY", "MyCustomLightRagKey456")
    LIGHTRAG_KNOWLEDGE_BASE: str = os.getenv("LIGHTRAG_KNOWLEDGE_BASE", "default")
    LIGHTRAG_TIMEOUT: int = int(os.getenv("LIGHTRAG_TIMEOUT", "30"))
    
    # Card rates microservice
    CARD_RATES_URL: str = os.getenv("CARD_RATES_URL", "http://localhost:8002")  # Legacy service
    FEE_ENGINE_URL: str = os.getenv("FEE_ENGINE_URL", "http://localhost:8003")  # New fee-engine service
    
    # Location service
    LOCATION_SERVICE_URL: str = os.getenv("LOCATION_SERVICE_URL", "http://localhost:8004")  # Location/address service
    
    # Chat settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "True").lower() == "true"
    
    # Lead generation (disabled by default - set ENABLE_LEAD_GENERATION=True to enable)
    ENABLE_LEAD_GENERATION: bool = os.getenv("ENABLE_LEAD_GENERATION", "False").lower() == "true"


settings = Settings()

