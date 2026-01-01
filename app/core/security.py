from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

# Importaciones locales
from app.core.token_blacklist import is_token_blacklisted
from database import get_db
from models import Users
from app.core.config import settings
# Configuración de Hasheo
# Bcrypt tiene un límite de 72 caracteres; el pepper ayuda pero hay que manejarlo con cuidado.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Token expiration time in minutes
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ------------------ Hash de contraseñas ------------------

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar los 72 caracteres.")
    
    # Usamos el PEPPER de los settings
    peppered = f"{password}{settings.PASSWORD_PEPPER}"
    return pwd_context.hash(peppered)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    peppered = f"{plain_password}{settings.PASSWORD_PEPPER}"
    return pwd_context.verify(peppered, hashed_password)

# ------------------ JWT Tokens ------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    # Usamos SECRET_KEY y ALGORITHM desde settings
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
# ------------------ Dependencias de autenticación ------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Users:
    token = credentials.credentials
    payload = decode_access_token(token)
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token no contiene el usuario",
        )
    
    # Nota: Asegúrate que en tu modelo Users el atributo sea 'Username' (con U mayúscula)
    user = db.query(Users).filter(Users.Username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado en el sistema",
        )
    
    return user

# ------------------ Control de roles ------------------

class RoleChecker:
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: Users = Depends(get_current_user)) -> Users:
        if current_user.Role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere uno de estos roles: {', '.join(self.allowed_roles)}"
            )
        return current_user

# Dependencias listas para usar en tus Endpoints
require_admin = RoleChecker(["admin"])
require_manager = RoleChecker(["admin", "manager"])
require_cashier = RoleChecker(["admin", "manager", "cashier"])