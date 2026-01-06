from collections import defaultdict
from datetime import datetime, timedelta

login_attempts = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

def record_failed_login(username: str):
    now = datetime.utcnow()
    login_attempts[username].append(now)
    
    # Limpiar intentos antiguos
    login_attempts[username] = [
        attempt for attempt in login_attempts[username]
        if now - attempt < LOCKOUT_DURATION
    ]

def is_account_locked(username: str) -> bool:
    recent_attempts = login_attempts[username]
    return len(recent_attempts) >= MAX_ATTEMPTS

def reset_login_attempts(username: str):
    login_attempts[username] = []