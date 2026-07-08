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
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default model for simple queries
    OPENAI_MODEL_COMPLEX: str = os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4o")  # Model for complex queries
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    
    # Conversation history limits (for prompt compression)
    MAX_HISTORY_IN_PROMPT: int = int(os.getenv("MAX_HISTORY_IN_PROMPT", "6"))  # Last N messages in OpenAI prompt
    
    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bank_chatbot")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_POOL_SIZE: int = int(os.getenv("POSTGRES_POOL_SIZE", "10"))
    POSTGRES_MAX_OVERFLOW: int = int(os.getenv("POSTGRES_MAX_OVERFLOW", "20"))
    POSTGRES_POOL_RECYCLE: int = int(os.getenv("POSTGRES_POOL_RECYCLE", "3600"))
    POSTGRES_POOL_TIMEOUT: int = int(os.getenv("POSTGRES_POOL_TIMEOUT", "30"))
    
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
    ENABLE_LIGHTRAG_RERANK: bool = os.getenv("ENABLE_LIGHTRAG_RERANK", "False").lower() == "true"
    LIGHTRAG_TOP_K: int = int(os.getenv("LIGHTRAG_TOP_K", "8"))
    LIGHTRAG_CHUNK_TOP_K: int = int(os.getenv("LIGHTRAG_CHUNK_TOP_K", "10"))
    LIGHTRAG_POLICY_TOP_K: int = int(os.getenv("LIGHTRAG_POLICY_TOP_K", "15"))
    LIGHTRAG_POLICY_CHUNK_TOP_K: int = int(os.getenv("LIGHTRAG_POLICY_CHUNK_TOP_K", "20"))
    MIN_GROUNDING_CONTEXT_CHARS: int = int(os.getenv("MIN_GROUNDING_CONTEXT_CHARS", "100"))
    
    # Card rates microservice
    CARD_RATES_URL: str = os.getenv("CARD_RATES_URL", "http://localhost:8002")  # Legacy service
    FEE_ENGINE_URL: str = os.getenv("FEE_ENGINE_URL", "http://localhost:8003")  # New fee-engine service
    
    # Location service
    LOCATION_SERVICE_URL: str = os.getenv("LOCATION_SERVICE_URL", "http://localhost:8004")  # Location/address service
    
    # Chat settings
    MAX_CONVERSATION_HISTORY: int = int(os.getenv("MAX_CONVERSATION_HISTORY", "10"))
    ENABLE_STREAMING: bool = os.getenv("ENABLE_STREAMING", "True").lower() == "true"

    # --- Per-user chat history (secure, AD-scoped) ---
    # Max number of prior messages (user+assistant) loaded from DB and fed to the
    # LLM as context for the authenticated user. Kept small to bound tokens/latency.
    CHAT_HISTORY_CONTEXT_LIMIT: int = int(os.getenv("CHAT_HISTORY_CONTEXT_LIMIT", "20"))
    # Redact sensitive banking data (OTP/PIN/CVV/card/account/password) before any
    # message is written to the database. Strongly recommended to leave enabled.
    CHAT_HISTORY_REDACTION_ENABLED: bool = os.getenv("CHAT_HISTORY_REDACTION_ENABLED", "True").lower() == "true"
    # Optional application-layer encryption-at-rest for stored message content.
    # When a Fernet key is provided, message text is encrypted before storage and
    # transparently decrypted on read. Leave empty to store plaintext (default,
    # preserves existing rows). Generate a key with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    CHAT_HISTORY_ENCRYPTION_KEY: str = os.getenv("CHAT_HISTORY_ENCRYPTION_KEY", "")
    
    # Lead generation (disabled by default - set ENABLE_LEAD_GENERATION=True to enable)
    ENABLE_LEAD_GENERATION: bool = os.getenv("ENABLE_LEAD_GENERATION", "False").lower() == "true"

    # Employee authentication (Active Directory)
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "True").lower() == "true"
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # Dashboard / internal analytics API (X-Analytics-Key header)
    ANALYTICS_API_KEY: str = os.getenv("ANALYTICS_API_KEY", "")

    # LDAP / Active Directory (phonebook sync + employee login)
    LDAP_SERVER: str = os.getenv("LDAP_SERVER", "")
    LDAP_PORT: int = int(os.getenv("LDAP_PORT", "389"))
    LDAP_BASE_DN: str = os.getenv("LDAP_BASE_DN", "")
    LDAP_BIND_USER: str = os.getenv("LDAP_BIND_USER", "")
    LDAP_BIND_PASSWORD: str = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_USE_SSL: bool = os.getenv("LDAP_USE_SSL", "False").lower() == "true"
    LDAP_DOMAIN: str = os.getenv("LDAP_DOMAIN", "ebl.bd")
    LDAP_NETBIOS_DOMAIN: str = os.getenv("LDAP_NETBIOS_DOMAIN", "EBL")
    LDAP_EMAIL_DOMAIN: str = os.getenv("LDAP_EMAIL_DOMAIN", "@ebl-bd.com")
    LDAP_CONNECT_TIMEOUT: int = int(os.getenv("LDAP_CONNECT_TIMEOUT", "10"))
    LDAP_AUTH_SEARCH_BASE: str = os.getenv("LDAP_AUTH_SEARCH_BASE", "")
    LDAP_USERS_OU: str = os.getenv("LDAP_USERS_OU", "")
    LDAP_DEFAULT_USER_PASSWORD: str = os.getenv("LDAP_DEFAULT_USER_PASSWORD", "Ebl123")
    LDAP_PROVISION_ENABLED: bool = os.getenv("LDAP_PROVISION_ENABLED", "False").lower() == "true"

    # EBL Home intranet forms (metadata index + links only)
    ENABLE_EBLHOME_FORMS: bool = os.getenv("ENABLE_EBLHOME_FORMS", "True").lower() == "true"
    ENABLE_EBLHOME_APPS: bool = os.getenv("ENABLE_EBLHOME_APPS", "True").lower() == "true"
    ENABLE_EBLHOME_LEADERSHIP: bool = os.getenv("ENABLE_EBLHOME_LEADERSHIP", "True").lower() == "true"
    ENABLE_EBLHOME_SOC: bool = os.getenv("ENABLE_EBLHOME_SOC", "True").lower() == "true"
    ENABLE_EBLHOME_PROPOSALS: bool = os.getenv("ENABLE_EBLHOME_PROPOSALS", "True").lower() == "true"
    ENABLE_EBLHOME_CIRCULARS: bool = os.getenv("ENABLE_EBLHOME_CIRCULARS", "True").lower() == "true"
    EBLHOME_BASE_URL: str = os.getenv("EBLHOME_BASE_URL", "http://eblhome")
    EBLHOME_MYSQL_HOST: str = os.getenv("EBLHOME_MYSQL_HOST", "192.168.3.57")
    EBLHOME_MYSQL_PORT: int = int(os.getenv("EBLHOME_MYSQL_PORT", "3306"))
    EBLHOME_MYSQL_DB: str = os.getenv("EBLHOME_MYSQL_DB", "ebl_home")
    EBLHOME_MYSQL_USER: str = os.getenv("EBLHOME_MYSQL_USER", "tanvir")
    EBLHOME_MYSQL_PASSWORD: str = os.getenv("EBLHOME_MYSQL_PASSWORD", "tanvir")
    # Server-side fetch base for form file proxy (defaults to EBLHOME_BASE_URL)
    EBLHOME_FETCH_BASE_URL: str = os.getenv("EBLHOME_FETCH_BASE_URL", "")
    PUBLIC_HOST: str = os.getenv("PUBLIC_HOST", "dia.ebl-bd.com")
    PUBLIC_API_BASE_URL: str = os.getenv("PUBLIC_API_BASE_URL", "")

    @property
    def public_api_base_url(self) -> str:
        """Public chatbot API base used in downloadable form links."""
        explicit = (self.PUBLIC_API_BASE_URL or "").strip().rstrip("/")
        if explicit:
            return explicit
        origins = self.CORS_ORIGINS
        if isinstance(origins, list):
            for origin in origins:
                if origin and origin != "*" and origin.startswith("http"):
                    return f"{origin.rstrip('/')}/api"
        return f"https://{self.PUBLIC_HOST}/api"

    @property
    def eblhome_fetch_base_url(self) -> str:
        """Base URL the backend uses to fetch files from EBL Home."""
        explicit = (self.EBLHOME_FETCH_BASE_URL or "").strip().rstrip("/")
        if explicit:
            return explicit
        return self.EBLHOME_BASE_URL.rstrip("/")

    @property
    def jwt_secret_key(self) -> str:
        """JWT signing key — must be set in production when auth is enabled."""
        if self.JWT_SECRET:
            return self.JWT_SECRET
        if self.DEBUG:
            return "dev-insecure-jwt-secret-change-in-production"
        if self.AUTH_ENABLED:
            raise ValueError(
                "JWT_SECRET must be set when AUTH_ENABLED=True and DEBUG=False"
            )
        return "auth-disabled"


settings = Settings()

