from datetime import datetime, timedelta
from typing import Set

# En producción, usar Redis
token_blacklist: Set[str] = set()

def revoke_token(token: str):
    token_blacklist.add(token)

def is_token_blacklisted(token: str) -> bool:
    return token in token_blacklist