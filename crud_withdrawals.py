from decimal import Decimal
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from models import CashWithdrawal, CashRegister
from schemas import CreateWithdrawalRequest

def crear_retiro(
    db: Session,
    cash_register_id: int,
    user_id: int,
    data: CreateWithdrawalRequest
) -> CashWithdrawal:
    """Crea un retiro de efectivo de la caja registradora"""
    
    # Verificar que la caja existe y está abierta
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    
    if caja.status != "open":
        raise HTTPException(status_code=400, detail="La caja está cerrada")
    
    # Calcular efectivo actual
    efectivo_actual = caja.initial_cash + caja.total_cash - caja.total_withdrawals
    
    # Validar que hay suficiente efectivo
    if data.amount > efectivo_actual:
        raise HTTPException(
            status_code=400,
            detail=f"Efectivo insuficiente. Disponible: ${efectivo_actual}, Solicitado: ${data.amount}"
        )
    
    # Calcular efectivo después del retiro
    efectivo_despues = efectivo_actual - data.amount
    
    # Crear registro de retiro
    retiro = CashWithdrawal(
        cash_register_id=cash_register_id,
        user_id=user_id,
        amount=data.amount,
        reason=data.reason,
        notes=data.notes,
        cash_before=efectivo_actual,
        cash_after=efectivo_despues,
        status="completed",
        created_at=datetime.now(UTC)
    )
    
    db.add(retiro)
    
    # Actualizar totales de la caja
    caja.total_withdrawals += data.amount
    caja.current_cash = efectivo_despues
    
    db.commit()
    db.refresh(retiro)
    
    return retiro


def obtener_retiro(db: Session, withdrawal_id: int) -> CashWithdrawal:
    """Obtiene un retiro por ID"""
    retiro = db.query(CashWithdrawal).filter(CashWithdrawal.id == withdrawal_id).first()
    if not retiro:
        raise HTTPException(status_code=404, detail="Retiro no encontrado")
    return retiro


def listar_retiros_de_caja(
    db: Session,
    cash_register_id: int,
    skip: int = 0,
    limit: int = 50
) -> list[CashWithdrawal]:
    """Lista todos los retiros de una caja específica"""
    return (
        db.query(CashWithdrawal)
        .filter(CashWithdrawal.cash_register_id == cash_register_id)
        .order_by(CashWithdrawal.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def listar_retiros_del_dia(
    db: Session,
    fecha: datetime | None = None,
    skip: int = 0,
    limit: int = 100
) -> list[CashWithdrawal]:
    """Lista todos los retiros del día"""
    if not fecha:
        fecha = datetime.now(UTC).date()
    
    return (
        db.query(CashWithdrawal)
        .filter(func.date(CashWithdrawal.created_at) == fecha)
        .order_by(CashWithdrawal.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def verificar_limite_efectivo(db: Session, cash_register_id: int) -> dict:
    """Verifica si el efectivo en caja supera el límite de seguridad"""
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    
    efectivo_actual = caja.initial_cash + caja.total_cash - caja.total_withdrawals
    exceso = efectivo_actual - caja.cash_limit
    
    if exceso <= 0:
        return {
            "status": "ok",
            "message": "El efectivo está dentro del límite",
            "current_cash": float(efectivo_actual),
            "cash_limit": float(caja.cash_limit),
            "excess": 0.0,
            "alert_level": "none"
        }
    
    # Determinar nivel de alerta
    porcentaje_exceso = (exceso / caja.cash_limit) * 100
    
    if porcentaje_exceso >= 50:
        nivel = "critical"
        mensaje = f"¡CRÍTICO! El efectivo supera el límite en ${exceso:.2f}"
    elif porcentaje_exceso >= 20:
        nivel = "warning"
        mensaje = f"¡ADVERTENCIA! El efectivo supera el límite en ${exceso:.2f}"
    else:
        nivel = "info"
        mensaje = f"El efectivo supera ligeramente el límite en ${exceso:.2f}"
    
    return {
        "status": "alert",
        "message": mensaje,
        "current_cash": float(efectivo_actual),
        "cash_limit": float(caja.cash_limit),
        "excess": float(exceso),
        "alert_level": nivel,
        "suggested_withdrawal": float(exceso)
    }


def obtener_resumen_retiros(db: Session, cash_register_id: int) -> dict:
    """Obtiene un resumen de todos los retiros de una caja"""
    retiros = db.query(CashWithdrawal).filter(
        CashWithdrawal.cash_register_id == cash_register_id
    ).all()
    
    total_retirado = sum(float(r.amount) for r in retiros)
    
    retiros_por_razon = {}
    for retiro in retiros:
        razon = retiro.reason
        if razon not in retiros_por_razon:
            retiros_por_razon[razon] = {
                "count": 0,
                "total": 0.0
            }
        retiros_por_razon[razon]["count"] += 1
        retiros_por_razon[razon]["total"] += float(retiro.amount)
    
    return {
        "total_withdrawals": len(retiros),
        "total_amount": total_retirado,
        "by_reason": retiros_por_razon,
        "withdrawals": [
            {
                "id": r.id,
                "amount": float(r.amount),
                "reason": r.reason,
                "created_at": r.created_at,
                "user": r.user.Username
            }
            for r in retiros
        ]
    }


def cancelar_retiro(
    db: Session,
    withdrawal_id: int,
    user_id: int
) -> CashWithdrawal:
    """Cancela un retiro (solo manager/admin)"""
    retiro = db.query(CashWithdrawal).filter(CashWithdrawal.id == withdrawal_id).first()
    if not retiro:
        raise HTTPException(status_code=404, detail="Retiro no encontrado")
    
    if retiro.status == "cancelled":
        raise HTTPException(status_code=400, detail="El retiro ya está cancelado")
    
    # Obtener caja
    caja = db.query(CashRegister).filter(CashRegister.id == retiro.cash_register_id).first()
    
    # Revertir el retiro
    caja.total_withdrawals -= retiro.amount
    caja.current_cash += retiro.amount
    
    # Marcar como cancelado
    retiro.status = "cancelled"
    
    db.commit()
    db.refresh(retiro)
    
    return retiro