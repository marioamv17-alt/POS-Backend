from decimal import Decimal
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from models import CashRegister, SaleTicket
from schemas import OpenCashRegisterRequest, CloseCashRegisterRequest

def abrir_caja(db: Session, user_id: int, data: OpenCashRegisterRequest) -> CashRegister:
    """Abre una nueva caja registradora"""
    
    # Verificar si el usuario tiene una caja abierta
    caja_abierta = db.query(CashRegister).filter(
        CashRegister.user_id == user_id,
        CashRegister.status == "open"
    ).first()
    
    if caja_abierta:
        raise HTTPException(
            status_code=400,
            detail=f"Ya tienes una caja abierta (ID: {caja_abierta.id}). Ciérrala antes de abrir una nueva."
        )
    
    # Crear nueva caja
    caja = CashRegister(
        user_id=user_id,
        opened_at=datetime.now(UTC),
        initial_cash=data.initial_cash,
        current_cash=data.initial_cash,
        total_sales=Decimal('0.00'),
        total_cash=Decimal('0.00'),
        total_card=Decimal('0.00'),
        total_transfer=Decimal('0.00'),
        total_withdrawals=Decimal('0.00'),
        num_transactions=0,
        status="open",
        notes=data.notes
    )
    
    db.add(caja)
    db.commit()
    db.refresh(caja)
    
    return caja

def cerrar_caja(
    db: Session, 
    cash_register_id: int, 
    data: CloseCashRegisterRequest,
    user_id: int
) -> CashRegister:
    """Cierra una caja registradora"""
    
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    
    if caja.status == "closed":
        raise HTTPException(status_code=400, detail="La caja ya está cerrada")
    
    # Verificar que sea el dueño de la caja
    if caja.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Solo el cajero que abrió la caja puede cerrarla"
        )
    
    # Calcular efectivo esperado
    expected_cash = caja.initial_cash + caja.total_cash
    difference = data.final_cash - expected_cash
    
    # Actualizar caja
    caja.closed_at = datetime.now(UTC)
    caja.final_cash = data.final_cash
    caja.expected_cash = expected_cash
    caja.difference = difference
    caja.status = "closed"
    
    if data.notes:
        caja.notes = f"{caja.notes or ''}\n[Cierre] {data.notes}"
    
    db.commit()
    db.refresh(caja)
    
    return caja

def obtener_caja(db: Session, cash_register_id: int) -> CashRegister:
    """Obtiene una caja por ID"""
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    return caja

def obtener_caja_abierta(db: Session, user_id: int) -> CashRegister | None:
    """Obtiene la caja abierta del usuario actual"""
    return db.query(CashRegister).filter(
        CashRegister.user_id == user_id,
        CashRegister.status == "open"
    ).first()

def listar_cajas(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    user_id: int | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None
):
    """Lista cajas con filtros opcionales"""
    query = db.query(CashRegister)
    
    if status:
        query = query.filter(CashRegister.status == status)
    
    if user_id:
        query = query.filter(CashRegister.user_id == user_id)
    
    if fecha_desde:
        query = query.filter(CashRegister.opened_at >= fecha_desde)
    
    if fecha_hasta:
        query = query.filter(CashRegister.opened_at <= fecha_hasta)
    
    return query.order_by(CashRegister.opened_at.desc()).offset(skip).limit(limit).all()

def obtener_resumen_caja(db: Session, cash_register_id: int) -> dict:
    """Obtiene un resumen detallado de la caja"""
    caja = obtener_caja(db, cash_register_id)
    
    # Obtener tickets de la caja
    tickets = db.query(SaleTicket).filter(
        SaleTicket.cash_register_id == cash_register_id,
        SaleTicket.status == "completed"
    ).all()
    
    tickets_cancelados = db.query(SaleTicket).filter(
        SaleTicket.cash_register_id == cash_register_id,
        SaleTicket.status == "cancelled"
    ).count()
    
    return {
        "caja": caja,
        "tickets": tickets,
        "num_tickets_completados": len(tickets),
        "num_tickets_cancelados": tickets_cancelados,
        "resumen": {
            "efectivo_inicial": float(caja.initial_cash),
            "efectivo_final": float(caja.final_cash) if caja.final_cash else None,
            "efectivo_esperado": float(caja.expected_cash) if caja.expected_cash else None,
            "diferencia": float(caja.difference) if caja.difference else None,
            "total_ventas": float(caja.total_sales),
            "ventas_efectivo": float(caja.total_cash),
            "ventas_tarjeta": float(caja.total_card),
            "ventas_transferencia": float(caja.total_transfer),
            "num_transacciones": caja.num_transactions
        }
    }

def obtener_ventas_del_dia(db: Session, fecha: datetime | None = None) -> dict:
    """Obtiene el resumen de ventas del día"""
    if not fecha:
        fecha = datetime.now(UTC).date()
    
    # Tickets del día
    tickets = db.query(SaleTicket).filter(
        func.date(SaleTicket.created_at) == fecha,
        SaleTicket.status == "completed"
    ).all()
    
    total_ventas = sum(float(t.total) for t in tickets)
    total_efectivo = sum(float(t.total) for t in tickets if t.payment_method == "cash")
    total_tarjeta = sum(float(t.total) for t in tickets if t.payment_method == "card")
    total_transferencia = sum(float(t.total) for t in tickets if t.payment_method == "transfer")
    
    # Cajas del día
    cajas = db.query(CashRegister).filter(
        func.date(CashRegister.opened_at) == fecha
    ).all()
    
    return {
        "fecha": fecha.isoformat(),
        "num_tickets": len(tickets),
        "total_ventas": total_ventas,
        "ventas_efectivo": total_efectivo,
        "ventas_tarjeta": total_tarjeta,
        "ventas_transferencia": total_transferencia,
        "num_cajas": len(cajas),
        "cajas_abiertas": sum(1 for c in cajas if c.status == "open"),
        "cajas_cerradas": sum(1 for c in cajas if c.status == "closed")
    }