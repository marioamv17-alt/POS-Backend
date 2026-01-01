import crud
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import timedelta
from pydantic import BaseModel, Field

# --- Importaciones de la App ---
from database import get_db
from models import Users
from schemas import LoginRequest, RegisterRequest, UserSchema
from app.core.logging_config import security_logger
from app.core.security import (
    create_access_token, 
    get_current_user, 
    require_admin,
    security,
    ACCESS_TOKEN_EXPIRE_MINUTES
)

# --- Rate Limiting ---
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/users", tags=["Usuarios y Autenticación"])

# --- Esquemas Locales ---
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserSchema

class UserRoleUpdate(BaseModel):
    role: str = Field(..., alias="Role")

# --- Funciones Auxiliares (Placeholders para que no den error) ---
# Tip: Estas funciones deberían ir en app/core/security.py o un servicio aparte
def is_account_locked(username: str) -> bool:
    # Lógica de Redis o DB para verificar bloqueos
    return False 

def record_failed_login(username: str):
    # Lógica para incrementar intentos fallidos
    pass

def reset_login_attempts(username: str):
    # Lógica para limpiar intentos tras login exitoso
    pass

def revoke_token(token: str):
    # Lógica para meter el token en una "Blacklist" (usualmente en Redis)
    pass

# ------------------ Endpoints ------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    user = crud.create_user(db, request.username, request.password)
    return {"message": "Usuario creado exitosamente", "user_id": user.ID}

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)):
    # 1. Verificar si la cuenta está bloqueada
    if is_account_locked(data.username):
        security_logger.warning(f"Intento de login en cuenta bloqueada: {data.username}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cuenta bloqueada temporalmente por seguridad."
        )
    
    # 2. Autenticar
    user = crud.authenticate_user(db, data.username, data.password)
    
    if not user:
        record_failed_login(data.username)
        security_logger.warning(f"Login fallido: {data.username} desde IP {request.client.host}")
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    # 3. Éxito: Resetear intentos y generar token
    reset_login_attempts(data.username)
    security_logger.info(f"Login exitoso: {user.Username}")
    
    access_token = create_access_token(
        data={"sub": user.Username, "role": user.Role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserSchema(ID=user.ID, Username=user.Username)
    }

@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: Users = Depends(get_current_user)
):
    token = credentials.credentials
    revoke_token(token)
    return {"message": "Sesión cerrada exitosamente"}

# ------------------ Perfil del usuario actual ------------------
@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: Users = Depends(get_current_user)):
    """Obtiene la información del usuario autenticado"""
    return UserSchema(ID=current_user.ID, Username=current_user.Username)

# ------------------ Consultar nivel de acceso ------------------
@router.get("/me/role")
def get_my_role(current_user: Users = Depends(get_current_user)):
    """Obtiene el rol del usuario autenticado"""
    return {
        "user_id": current_user.ID,
        "username": current_user.Username,
        "role": current_user.Role
    }

# ------------------ Actualizar rol (solo admin) ------------------
@router.patch("/{user_id}/role", dependencies=[Depends(require_admin)])
def update_role(
    user_id: int, 
    role_data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Actualiza el rol de un usuario (solo admin)"""
    user = crud.update_user_role(db, user_id, role_data.role)
    return {
        "message": "Rol actualizado",
        "user_id": user.ID,
        "new_role": user.Role
    }

# ------------------ Listar usuarios (solo admin) ------------------
@router.get("/", dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    """Lista todos los usuarios (solo admin)"""
    users = db.query(Users).all()
    return [{"id": u.ID, "username": u.Username, "role": u.Role} for u in users]