# routes/tickets.py - VERSIÓN ACTUALIZADA
"""
Rutas de tickets de venta usando Service Layer.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from database import get_db
from app.core.security import get_current_user, require_admin
from app.services.ticket_service import TicketService
from models import Users
from schemas import (
    CreateTicketRequest,
    SaleTicketSchema,
    SaleTicketItemSchema,
    CancelTicketRequest
)
from schemas_pagination import PaginationParams, PaginatedResponse
from app.core.exceptions import AppException, NotFoundError
import crud_cash_register

router = APIRouter(prefix="/tickets", tags=["Tickets de Venta"])


# ==================== CREAR TICKET ====================
@router.post("/", response_model=SaleTicketSchema, status_code=201)
def create_ticket(
    data: CreateTicketRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Crea un ticket de venta a partir de un carrito.
    
    **Proceso automático:**
    - Valida stock disponible
    - Reduce el inventario
    - Calcula cambio para efectivo
    - Asocia a caja registradora abierta
    - Genera número único de ticket
    
    **Ejemplo:**
    ```json
    {
        "CartId": 123,
        "PaymentMethod": "cash",
        "AmountPaid": 1000.00,
        "Tax": 0.00,
        "Discount": 0.00
    }
    ```
    """
    try:
        service = TicketService(db)
        
        # Obtener caja abierta del usuario
        caja_abierta = crud_cash_register.obtener_caja_abierta(db, current_user.ID)
        cash_register_id = caja_abierta.id if caja_abierta else None
        
        # Crear ticket
        ticket = service.create_ticket(data, current_user.ID, cash_register_id)
        
        # Preparar respuesta
        items_schema = [
            SaleTicketItemSchema(
                product_code=item.product_code,
                product_name=item.product_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal
            )
            for item in ticket.items
        ]
        
        return SaleTicketSchema(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            subtotal=ticket.subtotal,
            tax=ticket.tax,
            discount=ticket.discount,
            total=ticket.total,
            payment_method=ticket.payment_method,
            payment_reference=ticket.payment_reference,
            amount_paid=ticket.amount_paid,
            change_given=ticket.change_given,
            status=ticket.status,
            created_at=ticket.created_at,
            cashier_name=ticket.cashier.Username,
            items=items_schema
        )
    
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== OBTENER TICKET POR ID ====================
@router.get("/{ticket_id}", response_model=SaleTicketSchema)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Obtiene un ticket por ID.
    
    **Útil para:**
    - Impresión de tickets
    - Visualización de detalles
    - Reimpresión
    """
    try:
        service = TicketService(db)
        ticket = service.get_ticket(ticket_id)
        
        items_schema = [
            SaleTicketItemSchema(
                product_code=item.product_code,
                product_name=item.product_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal
            )
            for item in ticket.items
        ]
        
        return SaleTicketSchema(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            subtotal=ticket.subtotal,
            tax=ticket.tax,
            discount=ticket.discount,
            total=ticket.total,
            payment_method=ticket.payment_method,
            payment_reference=ticket.payment_reference,
            amount_paid=ticket.amount_paid,
            change_given=ticket.change_given,
            status=ticket.status,
            created_at=ticket.created_at,
            cashier_name=ticket.cashier.Username,
            items=items_schema
        )
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== OBTENER POR NÚMERO ====================
@router.get("/number/{ticket_number}", response_model=SaleTicketSchema)
def get_ticket_by_number(
    ticket_number: str,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Obtiene un ticket por número.
    
    **Formato:** TKT-20231207-0001
    """
    try:
        service = TicketService(db)
        ticket = service.get_ticket_by_number(ticket_number)
        
        items_schema = [
            SaleTicketItemSchema(
                product_code=item.product_code,
                product_name=item.product_name,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal
            )
            for item in ticket.items
        ]
        
        return SaleTicketSchema(
            id=ticket.id,
            ticket_number=ticket.ticket_number,
            subtotal=ticket.subtotal,
            tax=ticket.tax,
            discount=ticket.discount,
            total=ticket.total,
            payment_method=ticket.payment_method,
            payment_reference=ticket.payment_reference,
            amount_paid=ticket.amount_paid,
            change_given=ticket.change_given,
            status=ticket.status,
            created_at=ticket.created_at,
            cashier_name=ticket.cashier.Username,
            items=items_schema
        )
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== LISTAR TICKETS CON PAGINACIÓN ====================
@router.get("/", response_model=PaginatedResponse[SaleTicketSchema])
def list_tickets_paginated(
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=100, description="Registros por página"),
    status: Optional[str] = Query(None, pattern="^(completed|cancelled)$", description="Estado del ticket"),
    start_date: Optional[str] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="ID del cajero"),
    cash_register_id: Optional[int] = Query(None, description="ID de la caja registradora"),
    payment_method: Optional[str] = Query(None, pattern="^(cash|card|transfer)$", description="Método de pago"),
    min_total: Optional[float] = Query(None, ge=0, description="Total mínimo"),
    max_total: Optional[float] = Query(None, ge=0, description="Total máximo"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Lista tickets con paginación mejorada y metadatos completos.
    
    **Metadatos incluidos:**
    - `total`: Total de registros
    - `page`: Página actual
    - `page_size`: Registros por página
    - `total_pages`: Total de páginas
    - `has_next`: ¿Hay página siguiente?
    - `has_prev`: ¿Hay página anterior?
    - `next_page`: Número de siguiente página
    - `prev_page`: Número de página anterior
    
    **Filtros disponibles:**
    - `status`: completed, cancelled
    - `start_date`: Fecha inicial en formato YYYY-MM-DD
    - `end_date`: Fecha final en formato YYYY-MM-DD
    - `user_id`: Filtrar por cajero específico
    - `cash_register_id`: Filtrar por caja registradora
    - `payment_method`: cash, card, transfer
    - `min_total`: Total mínimo del ticket
    - `max_total`: Total máximo del ticket
    
    **Ejemplos de uso:**
    ```
    # Página 1 con 20 tickets
    GET /tickets/?page=1&page_size=20
    
    # Tickets completados de diciembre
    GET /tickets/?start_date=2024-12-01&end_date=2024-12-31&status=completed
    
    # Tickets de un cajero específico
    GET /tickets/?user_id=5&page=2
    
    # Tickets en efectivo mayores a $100
    GET /tickets/?payment_method=cash&min_total=100
    ```
    
    **Respuesta:**
    ```json
    {
      "data": [...],
      "meta": {
        "total": 250,
        "page": 1,
        "page_size": 50,
        "total_pages": 5,
        "has_next": true,
        "has_prev": false,
        "next_page": 2,
        "prev_page": null
      }
    }
    ```
    """
    try:
        service = TicketService(db)
        
        # Crear parámetros de paginación
        pagination = PaginationParams(page=page, page_size=page_size)
        
        # Convertir fechas
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                start_datetime = start_datetime.replace(hour=0, minute=0, second=0)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de start_date inválido. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de end_date inválido. Use YYYY-MM-DD"
                )
        
        # Obtener tickets paginados
        result = service.list_tickets_paginated(
            pagination=pagination,
            status=status,
            start_date=start_datetime,
            end_date=end_datetime,
            user_id=user_id,
            cash_register_id=cash_register_id,
            payment_method=payment_method,
            min_total=min_total,
            max_total=max_total
        )
        
        return result
    
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== LISTAR TICKETS (VERSIÓN ANTERIOR SIN PAGINACIÓN) ====================
@router.get("/simple")
def list_tickets(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(50, ge=1, le=100, description="Máximo de registros"),
    status: Optional[str] = Query(None, regex="^(completed|cancelled)$", description="Estado del ticket"),
    start_date: Optional[str] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="ID del cajero"),
    cash_register_id: Optional[int] = Query(None, description="ID de la caja registradora"),
    payment_method: Optional[str] = Query(None, regex="^(cash|card|transfer)$", description="Método de pago"),
    min_total: Optional[float] = Query(None, ge=0, description="Total mínimo"),
    max_total: Optional[float] = Query(None, ge=0, description="Total máximo"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Lista tickets con filtros avanzados.
    
    **Filtros disponibles:**
    - `status`: completed, cancelled
    - `start_date`: Fecha inicial en formato YYYY-MM-DD (ej: 2024-01-15)
    - `end_date`: Fecha final en formato YYYY-MM-DD
    - `user_id`: Filtrar por cajero específico
    - `cash_register_id`: Filtrar por caja registradora
    - `payment_method`: cash, card, transfer
    - `min_total`: Total mínimo del ticket
    - `max_total`: Total máximo del ticket
    
    **Ejemplos de uso:**
    - Tickets de hoy: `/tickets?start_date=2024-12-24&end_date=2024-12-24`
    - Tickets de un cajero: `/tickets?user_id=5`
    - Tickets > $1000: `/tickets?min_total=1000`
    - Tickets en efectivo del mes: `/tickets?start_date=2024-12-01&payment_method=cash`
    
    **Respuesta:**
    Lista resumida de tickets (sin items, para mejor rendimiento)
    """
    try:
        service = TicketService(db)
        
        # Convertir fechas string a datetime
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                start_datetime = start_datetime.replace(hour=0, minute=0, second=0)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de start_date inválido. Use YYYY-MM-DD"
                )
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Formato de end_date inválido. Use YYYY-MM-DD"
                )
        
        # Obtener tickets
        tickets = service.list_tickets(
            skip=skip,
            limit=limit,
            status=status,
            start_date=start_datetime,
            end_date=end_datetime,
            user_id=user_id,
            cash_register_id=cash_register_id,
            payment_method=payment_method,
            min_total=min_total,
            max_total=max_total
        )
        
        return {
            "total": len(tickets),
            "skip": skip,
            "limit": limit,
            "filters": {
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "user_id": user_id,
                "cash_register_id": cash_register_id,
                "payment_method": payment_method,
                "min_total": min_total,
                "max_total": max_total
            },
            "tickets": [
                {
                    "id": t.id,
                    "ticket_number": t.ticket_number,
                    "total": float(t.total),
                    "payment_method": t.payment_method,
                    "status": t.status,
                    "created_at": t.created_at.isoformat(),
                    "cashier": t.cashier.Username,
                    "items_count": len(t.items) if hasattr(t, 'items') else 0
                }
                for t in tickets
            ]
        }
    
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== CANCELAR TICKET ====================
@router.patch("/{ticket_id}/cancel", dependencies=[Depends(require_admin)])
def cancel_ticket(
    ticket_id: int,
    data: CancelTicketRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Cancela un ticket (solo admin).
    
    **Proceso:**
    - Devuelve stock al inventario
    - Actualiza caja registradora
    - Registra usuario y razón de cancelación
    - Mantiene historial completo
    
    **Requiere rol:** Admin
    """
    try:
        service = TicketService(db)
        ticket = service.cancel_ticket(ticket_id, data.reason, current_user.ID)
        
        return {
            "message": "Ticket cancelado exitosamente",
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "cancelled_by": current_user.Username,
            "cancelled_at": ticket.cancelled_at.isoformat(),
            "reason": ticket.cancellation_reason,
            "refunded_amount": float(ticket.total)
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== RESUMEN DE TICKETS ====================
@router.get("/reports/summary")
def get_tickets_summary(
    start_date: Optional[str] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Resumen de tickets en un período.
    
    **Por defecto:** Tickets del día actual
    
    **Incluye:**
    - Total de tickets
    - Tickets completados vs cancelados
    - Total de ventas
    - Ticket promedio
    """
    try:
        service = TicketService(db)
        
        # Convertir fechas
        start_datetime = None
        end_datetime = None
        
        if start_date:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        
        if end_date:
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
        
        summary = service.get_tickets_summary(start_datetime, end_datetime)
        return summary
    
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)