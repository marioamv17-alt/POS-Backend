from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # --- Configuración de Base de Datos ---
    DATABASE_URL: str
    
    # --- Seguridad y JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    PASSWORD_PEPPER: str  # Agregado para seguridad de hashes

    # --- Integraciones Externas ---
    WHATSAPP_API_TOKEN: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Configuración de Pydantic
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # Validación adicional para la SECRET_KEY
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if len(self.SECRET_KEY) < 32:
            raise ValueError("❌ SECRET_KEY debe tener al menos 32 caracteres para ser segura.")

@lru_cache()
def get_settings():
    """Carga los settings una sola vez y los mantiene en caché."""
    return Settings()

# Instancia lista para usar
settings = get_settings()