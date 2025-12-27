from decimal import Decimal
from datetime import datetime, UTC
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from models import SaleTicket, SaleTicketItem, Cart, CartItem, Product, CashRegister
from schemas import CreateTicketRequest

def generar_numero_ticket(db: Session) -> str:
    """Genera un número único de ticket: TKT-YYYYMMDD-NNNN"""
    today = datetime.now(UTC).strftime("%Y%m%d")
    
    # Contar tickets del día
    count = db.query(SaleTicket).filter(
        func.date(SaleTicket.created_at) == datetime.now(UTC).date()
    ).count()
    
    numero = f"TKT-{today}-{count + 1:04d}"
    return numero

def crear_ticket(
    db: Session, 
    data: CreateTicketRequest, 
    user_id: int,
    cash_register_id: int | None = None
) -> SaleTicket:
    """Crea un ticket de venta a partir de un carrito"""
    
    # Validar carrito
    cart = db.query(Cart).filter(Cart.id == data.cart_id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Carrito no encontrado")
    
    if cart.status != "open":
        raise HTTPException(status_code=400, detail="El carrito ya fue procesado")
    
    if not cart.items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")
    
    # Validar stock disponible
    for item in cart.items:
        producto = db.query(Product).filter(Product.Id == item.product_id).first()
        if not producto:
            raise HTTPException(
                status_code=404, 
                detail=f"Producto {item.product_name} no encontrado"
            )
        
        if producto.Stock < float(item.quantity):
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para {item.product_name}. Disponible: {producto.Stock}"
            )
    
    # Calcular totales
    subtotal = sum(item.subtotal for item in cart.items)
    total = subtotal + data.tax - data.discount
    
    # Calcular cambio si es pago en efectivo
    change_given = None
    if data.payment_method == "cash" and data.amount_paid:
        if data.amount_paid < total:
            raise HTTPException(
                status_code=400,
                detail=f"Monto insuficiente. Total: ${total}, Recibido: ${data.amount_paid}"
            )
        change_given = data.amount_paid - total
    
    # Generar número de ticket
    ticket_number = generar_numero_ticket(db)
    
    # Crear ticket
    ticket = SaleTicket(
        ticket_number=ticket_number,
        cart_id=cart.id,
        user_id=user_id,
        cash_register_id=cash_register_id,
        subtotal=subtotal,
        tax=data.tax,
        discount=data.discount,
        total=total,
        payment_method=data.payment_method,
        payment_reference=data.payment_reference,
        amount_paid=data.amount_paid,
        change_given=change_given,
        status="completed",
        created_at=datetime.now(UTC)
    )
    
    db.add(ticket)
    db.flush()  # Para obtener el ID del ticket
    
    # Crear items del ticket (snapshot)
    for cart_item in cart.items:
        producto = db.query(Product).filter(Product.Id == cart_item.product_id).first()
        
        ticket_item = SaleTicketItem(
            ticket_id=ticket.id,
            product_id=cart_item.product_id,
            product_code=producto.Code,
            product_name=cart_item.product_name,
            unit_price=cart_item.price,
            quantity=cart_item.quantity,
            subtotal=cart_item.subtotal
        )
        db.add(ticket_item)
        
        # Reducir stock
        producto.Stock -= int(float(cart_item.quantity))
    
    # Marcar carrito como completado
    cart.status = "completed"
    cart.completed_at = datetime.now(UTC)
    
    # Actualizar caja registradora si existe
    if cash_register_id:
        actualizar_caja_con_venta(db, cash_register_id, total, data.payment_method)
    
    db.commit()
    db.refresh(ticket)
    
    return ticket

def obtener_ticket(db: Session, ticket_id: int) -> SaleTicket:
    """Obtiene un ticket por ID"""
    ticket = db.query(SaleTicket).filter(SaleTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket

def obtener_ticket_por_numero(db: Session, ticket_number: str) -> SaleTicket:
    """Obtiene un ticket por número"""
    ticket = db.query(SaleTicket).filter(
        SaleTicket.ticket_number == ticket_number
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    return ticket

def cancelar_ticket(
    db: Session, 
    ticket_id: int, 
    reason: str, 
    user_id: int
) -> SaleTicket:
    """Cancela un ticket y devuelve el stock"""
    ticket = db.query(SaleTicket).filter(SaleTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    if ticket.status == "cancelled":
        raise HTTPException(status_code=400, detail="El ticket ya está cancelado")
    
    # Devolver stock
    for item in ticket.items:
        producto = db.query(Product).filter(Product.Id == item.product_id).first()
        if producto:
            producto.Stock += int(float(item.quantity))
    
    # Actualizar caja registradora si existe
    if ticket.cash_register_id:
        revertir_venta_en_caja(db, ticket.cash_register_id, ticket.total, ticket.payment_method)
    
    # Marcar como cancelado
    ticket.status = "cancelled"
    ticket.cancelled_at = datetime.now(UTC)
    ticket.cancelled_by = user_id
    ticket.cancellation_reason = reason
    
    db.commit()
    db.refresh(ticket)
    
    return ticket

def listar_tickets(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    fecha_desde: datetime | None = None,
    fecha_hasta: datetime | None = None
):
    """Lista tickets con filtros opcionales"""
    query = db.query(SaleTicket)
    
    if status:
        query = query.filter(SaleTicket.status == status)
    
    if fecha_desde:
        query = query.filter(SaleTicket.created_at >= fecha_desde)
    
    if fecha_hasta:
        query = query.filter(SaleTicket.created_at <= fecha_hasta)
    
    return query.order_by(SaleTicket.created_at.desc()).offset(skip).limit(limit).all()

def actualizar_caja_con_venta(
    db: Session,
    cash_register_id: int,
    total: Decimal,
    payment_method: str
):
    """Actualiza los totales de la caja registradora con una venta"""
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        return
    
    caja.total_sales += total
    caja.num_transactions += 1
    
    if payment_method == "cash":
        caja.total_cash += total
        caja.current_cash += total  
    elif payment_method == "card":
        caja.total_card += total
    elif payment_method == "transfer":
        caja.total_transfer += total

def revertir_venta_en_caja(
    db: Session,
    cash_register_id: int,
    total: Decimal,
    payment_method: str
):
    """Revierte una venta en la caja registradora"""
    caja = db.query(CashRegister).filter(CashRegister.id == cash_register_id).first()
    if not caja:
        return
    
    caja.total_sales -= total
    caja.num_transactions -= 1
    
    if payment_method == "cash":
        caja.total_cash -= total
    elif payment_method == "card":
        caja.total_card -= total
    elif payment_method == "transfer":
        caja.total_transfer -= total