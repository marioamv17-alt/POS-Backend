from functools import lru_cache
from datetime import datetime, timedelta, UTC

# Caché simple en memoria (usar Redis en producción)
cache = {}

def get_cached(key: str, ttl_seconds: int = 300):
    if key in cache:
        value, expiry = cache[key]
        if datetime.now(UTC) < expiry:
            return value
        del cache[key]
    return None

def set_cached(key: str, value, ttl_seconds: int = 300):
    expiry = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    cache[key] = (value, expiry)
def clear_cache():
    cache.clear()
@lru_cache(maxsize=128)
def cached_function_example(param: str):
    # Ejemplo de función cuyo resultado se cachea
    return f"Resultado para {param} a las {datetime.now(UTC)}"
def invalidate_cached_function_example(param: str):
    # Invalida la caché para la función de ejemplo
    cached_function_example.cache_clear()