# app/services/ticket_service.py
"""
Service para lógica de negocio de tickets de venta.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime, UTC
from decimal import Decimal

from models import SaleTicket, SaleTicketItem, Cart, Product, CashRegister
from schemas import CreateTicketRequest
from schemas_pagination import PaginationParams, PaginatedResponse
from app.repositories.ticket_repository import TicketRepository, TicketItemRepository
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.services.pagination_mixin import PaginationMixin
from app.core.exceptions import (
    NotFoundError,
    InvalidOperationError,
    ValidationError,
    InsufficientStockError
)


class TicketService(PaginationMixin):
    """Service para gestionar la lógica de negocio de tickets."""
    
    def __init__(self, db: Session):
        self.db = db
        self.ticket_repo = TicketRepository(db)
        self.ticket_item_repo = TicketItemRepository(db)
        self.cart_repo = CartRepository(db)
        self.product_repo = ProductRepository(db)
    
    def create_ticket(
        self,
        request: CreateTicketRequest,
        user_id: int,
        cash_register_id: Optional[int] = None
    ) -> SaleTicket:
        """
        Crea un ticket de venta a partir de un carrito.
        
        Args:
            request: Datos del ticket
            user_id: ID del usuario (cajero)
            cash_register_id: ID de la caja registradora (opcional)
            
        Returns:
            SaleTicket creado
            
        Raises:
            NotFoundError: Si el carrito no existe
            InvalidOperationError: Si el carrito ya fue procesado
            InsufficientStockError: Si no hay stock suficiente
        """
        # 1. Validar carrito
        cart = self.cart_repo.get_by_id(request.cart_id)
        if not cart:
            raise NotFoundError("Carrito", request.cart_id)
        
        if cart.status != "open":
            raise InvalidOperationError(
                f"El carrito ya fue procesado (estado: {cart.status})"
            )
        
        if not cart.items:
            raise InvalidOperationError("El carrito está vacío")
        
        # 2. Validar stock de todos los productos
        self._validate_stock_availability(cart.items)
        
        # 3. Calcular totales
        subtotal = sum(item.subtotal for item in cart.items)
        total = subtotal + request.tax - request.discount
        
        # 4. Validar pago en efectivo
        change_given = None
        if request.payment_method == "cash":
            if not request.amount_paid:
                raise ValidationError(
                    "amount_paid",
                    "Se requiere monto pagado para pagos en efectivo"
                )
            
            if request.amount_paid < total:
                raise InvalidOperationError(
                    f"Monto insuficiente. Total: ${total}, Recibido: ${request.amount_paid}"
                )
            
            change_given = request.amount_paid - total
        
        # 5. Generar número de ticket
        ticket_number = self.ticket_repo.generate_ticket_number()
        
        # 6. Crear ticket
        ticket = SaleTicket(
            ticket_number=ticket_number,
            cart_id=cart.id,
            user_id=user_id,
            cash_register_id=cash_register_id,
            subtotal=subtotal,
            tax=request.tax,
            discount=request.discount,
            total=total,
            payment_method=request.payment_method,
            payment_reference=request.payment_reference,
            amount_paid=request.amount_paid,
            change_given=change_given,
            status="completed",
            created_at=datetime.now(UTC)
        )
        
        ticket = self.ticket_repo.create(ticket)
        
        # 7. Crear items del ticket (snapshot)
        ticket_items = []
        for cart_item in cart.items:
            producto = self.product_repo.get_by_id(cart_item.product_id)
            
            ticket_item = SaleTicketItem(
                ticket_id=ticket.id,
                product_id=cart_item.product_id,
                product_code=producto.Code,
                product_name=cart_item.product_name,
                unit_price=cart_item.price,
                quantity=cart_item.quantity,
                subtotal=cart_item.subtotal
            )
            ticket_items.append(ticket_item)
            
            # 8. Reducir stock
            producto.Stock -= int(float(cart_item.quantity))
        
        self.ticket_item_repo.create_batch(ticket_items)
        
        # 9. Marcar carrito como completado
        self.cart_repo.update_status(cart.id, "completed")
        
        # 10. Actualizar caja registradora si existe
        if cash_register_id:
            self._update_cash_register(cash_register_id, total, request.payment_method)
        
        return self.ticket_repo.get_by_id(ticket.id)
    
    def get_ticket(self, ticket_id: int) -> SaleTicket:
        """
        Obtiene un ticket por ID.
        
        Args:
            ticket_id: ID del ticket
            
        Returns:
            SaleTicket encontrado
            
        Raises:
            NotFoundError: Si el ticket no existe
        """
        ticket = self.ticket_repo.get_by_id(ticket_id)
        if not ticket:
            raise NotFoundError("Ticket", ticket_id)
        return ticket
    
    def get_ticket_by_number(self, ticket_number: str) -> SaleTicket:
        """
        Obtiene un ticket por número.
        
        Args:
            ticket_number: Número del ticket
            
        Returns:
            SaleTicket encontrado
            
        Raises:
            NotFoundError: Si el ticket no existe
        """
        ticket = self.ticket_repo.get_by_ticket_number(ticket_number)
        if not ticket:
            raise NotFoundError("Ticket", ticket_number)
        return ticket
    
    def list_tickets_paginated(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        cash_register_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        min_total: Optional[float] = None,
        max_total: Optional[float] = None
    ) -> PaginatedResponse[SaleTicket]:
        """
        Lista tickets con paginación mejorada.
        
        Args:
            pagination: Parámetros de paginación
            ... (resto de filtros)
            
        Returns:
            PaginatedResponse con tickets y metadatos
        """
        # Construir query base
        query = self.db.query(SaleTicket).options(
            self.ticket_repo.db.query(SaleTicket)._joinedload(SaleTicket.cashier)
        )
        
        # Aplicar filtros
        if status:
            query = query.filter(SaleTicket.status == status)
        
        if start_date:
            query = query.filter(SaleTicket.created_at >= start_date)
        
        if end_date:
            query = query.filter(SaleTicket.created_at <= end_date)
        
        if user_id:
            query = query.filter(SaleTicket.user_id == user_id)
        
        if cash_register_id:
            query = query.filter(SaleTicket.cash_register_id == cash_register_id)
        
        if payment_method:
            query = query.filter(SaleTicket.payment_method == payment_method)
        
        if min_total is not None:
            query = query.filter(SaleTicket.total >= min_total)
        
        if max_total is not None:
            query = query.filter(SaleTicket.total <= max_total)
        
        # Ordenar
        query = query.order_by(SaleTicket.created_at.desc())
        
        # Paginar
        tickets, total = self.paginate_query(query, pagination)
        
        return self.create_paginated_response(tickets, total, pagination)
    
    def list_tickets(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_id: Optional[int] = None,
        cash_register_id: Optional[int] = None,
        payment_method: Optional[str] = None,
        min_total: Optional[float] = None,
        max_total: Optional[float] = None
    ) -> List[SaleTicket]:
        """
        Lista tickets con filtros opcionales.
        
        Args:
            skip: Registros a saltar (paginación)
            limit: Máximo de registros
            status: Filtrar por estado
            start_date: Fecha inicial
            end_date: Fecha final
            user_id: Filtrar por cajero
            cash_register_id: Filtrar por caja
            payment_method: Filtrar por método de pago
            min_total: Total mínimo
            max_total: Total máximo
            
        Returns:
            Lista de tickets
        """
        return self.ticket_repo.list_tickets(
            skip=skip,
            limit=limit,
            status=status,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            cash_register_id=cash_register_id,
            payment_method=payment_method,
            min_total=min_total,
            max_total=max_total
        )
    
    def cancel_ticket(
        self,
        ticket_id: int,
        reason: str,
        user_id: int
    ) -> SaleTicket:
        """
        Cancela un ticket y devuelve el stock.
        
        Args:
            ticket_id: ID del ticket a cancelar
            reason: Razón de cancelación
            user_id: ID del usuario que cancela
            
        Returns:
            SaleTicket cancelado
            
        Raises:
            NotFoundError: Si el ticket no existe
            InvalidOperationError: Si el ticket ya está cancelado
        """
        ticket = self.get_ticket(ticket_id)
        
        if ticket.status == "cancelled":
            raise InvalidOperationError("El ticket ya está cancelado")
        
        # Devolver stock
        for item in ticket.items:
            producto = self.product_repo.get_by_id(item.product_id)
            if producto:
                producto.Stock += int(float(item.quantity))
        
        # Actualizar caja registradora si existe
        if ticket.cash_register_id:
            self._revert_cash_register(
                ticket.cash_register_id,
                ticket.total,
                ticket.payment_method
            )
        
        # Marcar como cancelado
        ticket.status = "cancelled"
        ticket.cancelled_at = datetime.now(UTC)
        ticket.cancelled_by = user_id
        ticket.cancellation_reason = reason
        
        return self.ticket_repo.update(ticket)
    
    def get_tickets_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """
        Obtiene un resumen de tickets en un período.
        
        Args:
            start_date: Fecha inicial (default: hoy)
            end_date: Fecha final (default: hoy)
            
        Returns:
            Diccionario con estadísticas
        """
        if not start_date:
            start_date = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        if not end_date:
            end_date = datetime.now(UTC)
        
        tickets = self.ticket_repo.get_sales_by_date_range(start_date, end_date)
        
        completed = [t for t in tickets if t.status == "completed"]
        cancelled = [t for t in tickets if t.status == "cancelled"]
        
        total_sales = sum(float(t.total) for t in completed)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_tickets": len(tickets),
            "completed": len(completed),
            "cancelled": len(cancelled),
            "total_sales": round(total_sales, 2),
            "average_ticket": round(
                total_sales / len(completed), 2
            ) if completed else 0
        }
    
    def _validate_stock_availability(self, cart_items: List) -> None:
        """
        Valida que haya stock suficiente para todos los items.
        
        Args:
            cart_items: Lista de items del carrito
            
        Raises:
            InsufficientStockError: Si no hay stock suficiente
        """
        for item in cart_items:
            producto = self.product_repo.get_by_id(item.product_id)
            
            if not producto:
                raise NotFoundError("Producto", item.product_id)
            
            if producto.Stock < float(item.quantity):
                raise InsufficientStockError(
                    producto.Product,
                    int(producto.Stock),
                    int(item.quantity)
                )
    
    def _update_cash_register(
        self,
        cash_register_id: int,
        total: Decimal,
        payment_method: str
    ) -> None:
        """Actualiza los totales de la caja registradora."""
        caja = self.db.query(CashRegister).filter(
            CashRegister.id == cash_register_id
        ).first()
        
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
        
        self.db.commit()
    
    def _revert_cash_register(
        self,
        cash_register_id: int,
        total: Decimal,
        payment_method: str
    ) -> None:
        """Revierte una venta en la caja registradora."""
        caja = self.db.query(CashRegister).filter(
            CashRegister.id == cash_register_id
        ).first()
        
        if not caja:
            return
        
        caja.total_sales -= total
        caja.num_transactions -= 1
        
        if payment_method == "cash":
            caja.total_cash -= total
            caja.current_cash -= total
        elif payment_method == "card":
            caja.total_card -= total
        elif payment_method == "transfer":
            caja.total_transfer -= total
        
        self.db.commit()