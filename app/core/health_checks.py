import httpx
import redis
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings

# ---------------------------------------------------------
# 1. Chequeo de Base de Datos
# ---------------------------------------------------------
def check_database(db: Session) -> dict:
    """Verifica la conexión con PostgreSQL"""
    try:
        # Ejecutamos una consulta simple para validar la conexión
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "service": "database"}
    except Exception as e:
        return {"status": "unhealthy", "service": "database", "error": str(e)}

# ---------------------------------------------------------
# 2. Chequeo de Redis (Si lo usas para caché o colas)
# ---------------------------------------------------------
def check_redis() -> dict:
    """Verifica la conexión con Redis"""
    try:
        # Intentamos conectar usando una URL de redis (ajusta si la tienes en settings)
        # Por ahora usaremos localhost por defecto
        r = redis.from_url("redis://localhost:6379", socket_connect_timeout=1)
        if r.ping():
            return {"status": "healthy", "service": "redis"}
    except Exception as e:
        return {"status": "unhealthy", "service": "redis", "error": str(e)}

# ---------------------------------------------------------
# 3. Chequeo de APIs Externas (Anthropic / WhatsApp)
# ---------------------------------------------------------
async def check_external_api() -> dict:
    """Verifica si las APIs externas están alcanzables"""
    # Usamos Anthropic como ejemplo de prueba de conectividad
    url = "https://api.anthropic.com/v1/messages" 
    try:
        async with httpx.AsyncClient() as client:
            # Solo hacemos un GET o un HEAD para ver si el servidor responde
            response = await client.get("https://api.anthropic.com/", timeout=2.0)
            if response.status_code < 500: # 401/403 significa que responde (aunque falte auth)
                return {"status": "healthy", "service": "anthropic_api"}
            else:
                return {"status": "unhealthy", "service": "anthropic_api", "code": response.status_code}
    except Exception as e:
        return {"status": "unhealthy", "service": "external_api", "error": str(e)}