from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from app.core.security import get_current_user, require_manager
from models import Users
from schemas import CreateWithdrawalRequest, CashWithdrawalSchema
import crud_withdrawals
import crud_cash_register
from datetime import datetime, timezone as UTC

router = APIRouter(prefix="/withdrawals", tags=["Retiros de Efectivo"])

# ==================== CREAR RETIRO ====================
@router.post("/", response_model=CashWithdrawalSchema, status_code=201)
def create_withdrawal(
    data: CreateWithdrawalRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Registra un retiro de efectivo de la caja registradora.
    
    **Razones válidas:**
    - `security_limit`: Retiro por exceder límite de seguridad
    - `end_of_shift`: Retiro al final del turno
    - `deposit`: Depósito a banco
    - `other`: Otra razón (especificar en notes)
    
    **Validaciones:**
    - Solo se puede retirar de una caja abierta
    - El monto debe ser menor o igual al efectivo disponible
    - Monto máximo: $50,000 por retiro
    """
    # Obtener caja abierta del usuario
    caja_abierta = crud_cash_register.obtener_caja_abierta(db, current_user.ID)
    
    if not caja_abierta:
        raise HTTPException(
            status_code=400,
            detail="No tienes una caja abierta. Abre una caja primero."
        )
    
    # Crear retiro
    retiro = crud_withdrawals.crear_retiro(
        db,
        caja_abierta.id,
        current_user.ID,
        data
    )
    
    return CashWithdrawalSchema(
        id=retiro.id,
        cash_register_id=retiro.cash_register_id,
        user_id=retiro.user_id,
        amount=retiro.amount,
        reason=retiro.reason,
        notes=retiro.notes,
        cash_before=retiro.cash_before,
        cash_after=retiro.cash_after,
        status=retiro.status,
        created_at=retiro.created_at,
        user_name=retiro.user.Username
    )


# ==================== OBTENER RETIRO ====================
@router.get("/{withdrawal_id}", response_model=CashWithdrawalSchema)
def get_withdrawal(
    withdrawal_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Obtiene los detalles de un retiro específico"""
    retiro = crud_withdrawals.obtener_retiro(db, withdrawal_id)
    
    return CashWithdrawalSchema(
        id=retiro.id,
        cash_register_id=retiro.cash_register_id,
        user_id=retiro.user_id,
        amount=retiro.amount,
        reason=retiro.reason,
        notes=retiro.notes,
        cash_before=retiro.cash_before,
        cash_after=retiro.cash_after,
        status=retiro.status,
        created_at=retiro.created_at,
        user_name=retiro.user.Username
    )


# ==================== LISTAR RETIROS DE MI CAJA ====================
@router.get("/me/current")
def get_my_withdrawals(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Lista los retiros de la caja abierta del usuario actual"""
    caja_abierta = crud_cash_register.obtener_caja_abierta(db, current_user.ID)
    
    if not caja_abierta:
        return {
            "message": "No tienes una caja abierta",
            "withdrawals": []
        }
    
    retiros = crud_withdrawals.listar_retiros_de_caja(
        db,
        caja_abierta.id,
        skip=skip,
        limit=limit
    )
    
    return {
        "cash_register_id": caja_abierta.id,
        "total_withdrawals": len(retiros),
        "withdrawals": [
            {
                "id": r.id,
                "amount": float(r.amount),
                "reason": r.reason,
                "notes": r.notes,
                "cash_before": float(r.cash_before),
                "cash_after": float(r.cash_after),
                "created_at": r.created_at,
                "user": r.user.Username
            }
            for r in retiros
        ]
    }


# ==================== VERIFICAR LÍMITE DE EFECTIVO ====================
@router.get("/me/check-limit")
def check_cash_limit(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Verifica si el efectivo en la caja supera el límite de seguridad.
    
    Retorna alertas en 3 niveles:
    - **info**: Ligero exceso (< 20%)
    - **warning**: Exceso moderado (20-50%)
    - **critical**: Exceso crítico (> 50%)
    """
    caja_abierta = crud_cash_register.obtener_caja_abierta(db, current_user.ID)
    
    if not caja_abierta:
        raise HTTPException(
            status_code=400,
            detail="No tienes una caja abierta"
        )
    
    return crud_withdrawals.verificar_limite_efectivo(db, caja_abierta.id)


# ==================== RESUMEN DE RETIROS POR CAJA ====================
@router.get("/cash-register/{cash_register_id}/summary")
def get_withdrawals_summary(
    cash_register_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Obtiene un resumen completo de retiros de una caja específica.
    
    Incluye:
    - Total retirado
    - Número de retiros
    - Desglose por razón
    - Lista de retiros
    """
    return crud_withdrawals.obtener_resumen_retiros(db, cash_register_id)


# ==================== LISTAR RETIROS DEL DÍA (MANAGER) ====================
@router.get("/reports/today", dependencies=[Depends(require_manager)])
def get_today_withdrawals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Lista todos los retiros del día actual (solo manager/admin)"""
    retiros = crud_withdrawals.listar_retiros_del_dia(db, skip=skip, limit=limit)
    
    total_retirado = sum(float(r.amount) for r in retiros)
    
    return {
        "fecha": datetime.now(UTC).date().isoformat(),
        "total_withdrawals": len(retiros),
        "total_amount": total_retirado,
        "withdrawals": [
            {
                "id": r.id,
                "cash_register_id": r.cash_register_id,
                "user": r.user.Username,
                "amount": float(r.amount),
                "reason": r.reason,
                "notes": r.notes,
                "created_at": r.created_at,
                "status": r.status
            }
            for r in retiros
        ]
    }


# ==================== CANCELAR RETIRO (MANAGER) ====================
@router.patch("/{withdrawal_id}/cancel", dependencies=[Depends(require_manager)])
def cancel_withdrawal(
    withdrawal_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Cancela un retiro y revierte el efectivo a la caja (solo manager/admin).
    
    **ADVERTENCIA:** Esta operación es sensible y debe hacerse con precaución.
    """
    retiro = crud_withdrawals.cancelar_retiro(db, withdrawal_id, current_user.ID)
    
    return {
        "message": "Retiro cancelado exitosamente",
        "withdrawal_id": retiro.id,
        "amount_reverted": float(retiro.amount),
        "cancelled_by": current_user.Username
    }