from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import get_db
from app.core.security import get_current_user, require_manager
from models import Users
from schemas import (
    OpenCashRegisterRequest,
    CloseCashRegisterRequest,
    CashRegisterSchema,
    CashRegisterSummary
)
import crud_cash_register
from datetime import datetime

router = APIRouter(prefix="/cash-register", tags=["Caja Registradora"])

# ==================== ABRIR CAJA ====================
@router.post("/open", response_model=CashRegisterSchema, status_code=201)
def open_cash_register(
    data: OpenCashRegisterRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Abre una nueva caja registradora.
    
    - Solo se puede tener una caja abierta a la vez por usuario
    - Registra el efectivo inicial
    - Se activa automáticamente al realizar la primera venta
    """
    caja = crud_cash_register.abrir_caja(db, current_user.ID, data)
    return caja

# ==================== CERRAR CAJA ====================
@router.post("/{cash_register_id}/close", response_model=CashRegisterSchema)
def close_cash_register(
    cash_register_id: int,
    data: CloseCashRegisterRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Cierra una caja registradora.
    
    - Calcula el efectivo esperado vs. el efectivo real
    - Muestra la diferencia (faltante o sobrante)
    - Solo el cajero que abrió la caja puede cerrarla
    """
    caja = crud_cash_register.cerrar_caja(db, cash_register_id, data, current_user.ID)
    return caja

# ==================== OBTENER CAJA ====================
@router.get("/{cash_register_id}", response_model=CashRegisterSchema)
def get_cash_register(
    cash_register_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Obtiene los detalles de una caja registradora"""
    caja = crud_cash_register.obtener_caja(db, cash_register_id)
    return caja

# ==================== CAJA ABIERTA ACTUAL ====================
@router.get("/me/current")
def get_my_open_register(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """Obtiene la caja abierta del usuario actual"""
    caja = crud_cash_register.obtener_caja_abierta(db, current_user.ID)
    
    if not caja:
        return {
            "message": "No tienes una caja abierta",
            "has_open_register": False,
            "register": None
        }
    
    return {
        "message": "Caja abierta encontrada",
        "has_open_register": True,
        "register": {
            "id": caja.id,
            "opened_at": caja.opened_at,
            "initial_cash": float(caja.initial_cash),
            "total_sales": float(caja.total_sales),
            "total_cash": float(caja.total_cash),
            "total_card": float(caja.total_card),
            "total_transfer": float(caja.total_transfer),
            "num_transactions": caja.num_transactions,
            "status": caja.status
        }
    }

# ==================== RESUMEN DE CAJA ====================
@router.get("/{cash_register_id}/summary")
def get_register_summary(
    cash_register_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Obtiene un resumen detallado de la caja.
    
    - Lista de todos los tickets
    - Totales por método de pago
    - Diferencias de efectivo
    """
    resumen = crud_cash_register.obtener_resumen_caja(db, cash_register_id)
    
    return {
        "caja": {
            "id": resumen["caja"].id,
            "cajero": resumen["caja"].user.Username,
            "opened_at": resumen["caja"].opened_at,
            "closed_at": resumen["caja"].closed_at,
            "status": resumen["caja"].status
        },
        "num_tickets_completados": resumen["num_tickets_completados"],
        "num_tickets_cancelados": resumen["num_tickets_cancelados"],
        "resumen": resumen["resumen"],
        "tickets": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "total": float(t.total),
                "payment_method": t.payment_method,
                "created_at": t.created_at
            }
            for t in resumen["tickets"]
        ]
    }

# ==================== LISTAR CAJAS ====================
@router.get("/")
def list_cash_registers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = Query(None, pattern="^(open|closed)$"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Lista cajas registradoras con filtros opcionales.
    
    - **status**: open, closed
    - Manager y admin pueden ver todas las cajas
    - Cajeros solo ven sus propias cajas
    """
    # Si no es admin/manager, solo mostrar sus cajas
    user_filter = None if current_user.Role in ["admin", "manager"] else current_user.ID
    
    cajas = crud_cash_register.listar_cajas(
        db,
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_filter
    )
    
    return [
        CashRegisterSummary(
            register_id=c.id,
            cashier=c.user.Username,
            opened_at=c.opened_at,
            closed_at=c.closed_at,
            status=c.status,
            total_sales=c.total_sales,
            total_cash=c.total_cash,
            total_card=c.total_card,
            total_transfer=c.total_transfer,
            num_transactions=c.num_transactions,
            difference=c.difference
        )
        for c in cajas
    ]

# ==================== REPORTE DEL DÍA ====================
@router.get("/reports/today", dependencies=[Depends(require_manager)])
def sales_report_today(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Reporte de ventas del día (solo manager y admin).
    
    - Total de ventas
    - Desglose por método de pago
    - Número de tickets
    - Estado de cajas
    """
    reporte = crud_cash_register.obtener_ventas_del_dia(db)
    return reporte

# ==================== REPORTE POR FECHA ====================
@router.get("/reports/date/{fecha}", dependencies=[Depends(require_manager)])
def sales_report_by_date(
    fecha: str,  # Formato: YYYY-MM-DD
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Reporte de ventas por fecha específica (solo manager y admin).
    
    - **fecha**: en formato YYYY-MM-DD (ej: 2023-12-07)
    """
    try:
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    
    reporte = crud_cash_register.obtener_ventas_del_dia(db, fecha_obj)
    return reporte