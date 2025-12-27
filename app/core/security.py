from datetime import datetime, timedelta, UTC
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import Users
from slowapi import Limiter
from slowapi.util import get_remote_address
import os

limiter = Limiter(key_func=get_remote_address)

PEPPER = os.getenv("PASSWORD_PEPPER", "default-pepper-change-in-prod")

# Configuración
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ------------------ Hash de contraseñas ------------------
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("La contraseña no puede superar los 72 caracteres.")
    
    # Agregar pepper antes de hashear
    peppered = f"{password}{PEPPER}"
    return pwd_context.hash(peppered)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    peppered = f"{plain_password}{PEPPER}"
    return pwd_context.verify(peppered, hashed_password)

# ------------------ JWT Tokens ------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decodifica y valida un token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
    """Obtiene el usuario actual desde el token JWT"""
    token = credentials.credentials
    payload = decode_access_token(token)
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )
    
    user = db.query(Users).filter(Users.Username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    
    return user

def get_current_active_user(current_user: Users = Depends(get_current_user)) -> Users:
    """Verifica que el usuario esté activo"""
    # Podrías añadir un campo "is_active" al modelo Users si lo necesitas
    return current_user

# ------------------ Control de roles ------------------
class RoleChecker:
    """Clase para verificar roles de usuarios"""
    
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: Users = Depends(get_current_user)) -> Users:
        if current_user.Role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere rol: {', '.join(self.allowed_roles)}"
            )
        return current_user

# Roles predefinidos
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_CASHIER = "cashier"

# Dependencias reutilizables
require_admin = RoleChecker([ROLE_ADMIN])
require_manager = RoleChecker([ROLE_ADMIN, ROLE_MANAGER])
require_cashier = RoleChecker([ROLE_ADMIN, ROLE_MANAGER, ROLE_CASHIER])