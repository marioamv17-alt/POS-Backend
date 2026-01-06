# app/repositories/ticket_repository.py
"""
Repository para operaciones de base de datos de tickets de venta.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract, and_, or_
from typing import List, Optional
from datetime import datetime, date, UTC

from models import SaleTicket, SaleTicketItem, CashRegister


class TicketRepository:
    """Repository para gestionar tickets de venta."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, ticket_id: int, with_items: bool = True) -> Optional[SaleTicket]:
        """
        Obtiene un ticket por ID.
        
        Args:
            ticket_id: ID del ticket
            with_items: Si debe cargar los items
            
        Returns:
            SaleTicket o None
        """
        query = self.db.query(SaleTicket)
        
        if with_items:
            query = query.options(
                joinedload(SaleTicket.items),
                joinedload(SaleTicket.cashier),
                joinedload(SaleTicket.cart)
            )
        
        return query.filter(SaleTicket.id == ticket_id).first()
    
    def get_by_ticket_number(self, ticket_number: str) -> Optional[SaleTicket]:
        """
        Obtiene un ticket por número.
        
        Args:
            ticket_number: Número del ticket (ej: TKT-20231207-0001)
            
        Returns:
            SaleTicket o None
        """
        return self.db.query(SaleTicket).options(
            joinedload(SaleTicket.items),
            joinedload(SaleTicket.cashier)
        ).filter(SaleTicket.ticket_number == ticket_number).first()
    
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
        Lista tickets con múltiples filtros.
        
        Args:
            skip: Paginación
            limit: Límite de resultados
            status: Estado (completed, cancelled)
            start_date: Fecha inicial
            end_date: Fecha final
            user_id: ID del cajero
            cash_register_id: ID de la caja registradora
            payment_method: Método de pago
            min_total: Total mínimo
            max_total: Total máximo
            
        Returns:
            Lista de tickets
        """
        query = self.db.query(SaleTicket).options(
            joinedload(SaleTicket.cashier)
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
        
        return query.order_by(
            SaleTicket.created_at.desc()
        ).offset(skip).limit(limit).all()
    
    def count_tickets_today(self) -> int:
        """
        Cuenta tickets del día actual.
        
        Returns:
            Número de tickets
        """
        today = datetime.now(UTC).date()
        return self.db.query(SaleTicket).filter(
            func.date(SaleTicket.created_at) == today
        ).count()
    
    def generate_ticket_number(self) -> str:
        """
        Genera un número único de ticket.
        
        Returns:
            Número de ticket (formato: TKT-YYYYMMDD-NNNN)
        """
        today = datetime.now(UTC).strftime("%Y%m%d")
        count = self.count_tickets_today()
        return f"TKT-{today}-{count + 1:04d}"
    
    def create(self, ticket: SaleTicket) -> SaleTicket:
        """
        Crea un nuevo ticket.
        
        Args:
            ticket: Instancia de SaleTicket
            
        Returns:
            SaleTicket guardado
        """
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def update(self, ticket: SaleTicket) -> SaleTicket:
        """
        Actualiza un ticket.
        
        Args:
            ticket: Instancia de SaleTicket con cambios
            
        Returns:
            SaleTicket actualizado
        """
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def get_sales_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: str = "completed"
    ) -> List[SaleTicket]:
        """
        Obtiene ventas en un rango de fechas.
        
        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            status: Estado de los tickets
            
        Returns:
            Lista de tickets
        """
        return self.db.query(SaleTicket).filter(
            SaleTicket.created_at.between(start_date, end_date),
            SaleTicket.status == status
        ).all()
    
    def get_tickets_by_cash_register(
        self,
        cash_register_id: int
    ) -> List[SaleTicket]:
        """
        Obtiene todos los tickets de una caja registradora.
        
        Args:
            cash_register_id: ID de la caja
            
        Returns:
            Lista de tickets
        """
        return self.db.query(SaleTicket).filter(
            SaleTicket.cash_register_id == cash_register_id
        ).order_by(SaleTicket.created_at).all()


class TicketItemRepository:
    """Repository para items de tickets."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, ticket_item: SaleTicketItem) -> SaleTicketItem:
        """
        Crea un item de ticket.
        
        Args:
            ticket_item: Instancia de SaleTicketItem
            
        Returns:
            SaleTicketItem guardado
        """
        self.db.add(ticket_item)
        self.db.commit()
        self.db.refresh(ticket_item)
        return ticket_item
    
    def create_batch(self, items: List[SaleTicketItem]) -> None:
        """
        Crea múltiples items de ticket en lote.
        
        Args:
            items: Lista de SaleTicketItem
        """
        self.db.add_all(items)
        self.db.commit()
    
    def get_items_by_ticket(self, ticket_id: int) -> List[SaleTicketItem]:
        """
        Obtiene todos los items de un ticket.
        
        Args:
            ticket_id: ID del ticket
            
        Returns:
            Lista de items
        """
        return self.db.query(SaleTicketItem).filter(
            SaleTicketItem.ticket_id == ticket_id
        ).all()