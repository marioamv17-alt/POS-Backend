from decimal import Decimal
from sqlalchemy import Column, Integer, String, NUMERIC, ForeignKey, BigInteger, Text, Index, DateTime, Sequence
from datetime import datetime, UTC
from database import Base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

class Users(Base):
    __tablename__ = "Users"

    ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Username = Column(String, unique=True, index=True, nullable=False)
    Password = Column(String, nullable=False)
    Role = Column(String, default="cashier")


class Product(Base):
    __tablename__ = "Master_Data"

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Code = Column(String, unique=True, index=True, nullable=False)
    Barcode = Column(String, unique=True, index=True, nullable=False)
    Product = Column(String, nullable=False)
    Category = Column(String, nullable=False)
    Units = Column(String, nullable=False)
    Price = Column(NUMERIC(10, 2), nullable=False)
    Stock = Column(NUMERIC(10, 4), nullable=False) 
    Min_Stock = Column(NUMERIC(10, 4), nullable=False)
    Activo = Column(Integer, default=1)
    
    __table_args__ = (
        Index('idx_product_active', 'Activo'),
        Index('idx_product_category_active', 'Category', 'Activo'),
    )


class Cart(Base):
    __tablename__ = "cart"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.ID"), nullable=True)
    status = Column(Text, default="open")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)) # Actualización general
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")
    user = relationship("Users", foreign_keys=[user_id])


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cart_id = Column(Integer, ForeignKey("cart.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("Master_Data.Id"), nullable=False)
    product_name = Column(Text, nullable=False)
    price = Column(NUMERIC(10, 2), nullable=False)
    quantity = Column(NUMERIC(10, 4), nullable=False)
    subtotal = Column(NUMERIC(10, 2), nullable=False)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("Master_Data.Id"), nullable=False, index=True)
    old_price = Column(NUMERIC(10, 2), nullable=False)
    new_price = Column(NUMERIC(10, 2), nullable=False)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=datetime.now(UTC))
    product = relationship("Product")


class CashRegister(Base):
    __tablename__ = "cash_register"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("Users.ID"), nullable=False)
    opened_at = Column(DateTime, default=datetime.now(UTC))
    closed_at = Column(DateTime, nullable=True)
    initial_cash = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    final_cash = Column(NUMERIC(10, 2), nullable=True)
    expected_cash = Column(NUMERIC(10, 2), nullable=True)
    difference = Column(NUMERIC(10, 2), nullable=True)
    total_sales = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    total_cash = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    total_card = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    total_transfer = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    total_withdrawals = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    current_cash = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    cash_limit = Column(NUMERIC(10, 2), default=Decimal('5000.00'))
    num_transactions = Column(Integer, default=0)
    status = Column(String, default="open")
    notes = Column(Text, nullable=True)
    
    user = relationship("Users")
    tickets = relationship("SaleTicket", back_populates="cash_register", foreign_keys="[SaleTicket.cash_register_id]")
    withdrawals = relationship("CashWithdrawal", back_populates="cash_register", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_register_date', 'opened_at'),
        Index('idx_register_user', 'user_id'),
        Index('idx_register_status', 'status'),
    )


class CashWithdrawal(Base):
    __tablename__ = "cash_withdrawals"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    cash_register_id = Column(Integer, ForeignKey("cash_register.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("Users.ID"), nullable=False)
    amount = Column(NUMERIC(10, 2), nullable=False)
    reason = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    
    cash_before = Column(NUMERIC(10, 2), nullable=False)
    cash_after = Column(NUMERIC(10, 2), nullable=False)
    
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=datetime.now(UTC))
    
    approved_by = Column(Integer, ForeignKey("Users.ID"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    cash_register = relationship("CashRegister", back_populates="withdrawals")
    user = relationship("Users", foreign_keys=[user_id])
    approver = relationship("Users", foreign_keys=[approved_by])
    
    __table_args__ = (
        Index('idx_withdrawal_date', 'created_at'),
        Index('idx_withdrawal_register', 'cash_register_id'),
        Index('idx_withdrawal_user', 'user_id'),
    )


class SaleTicket(Base):
    __tablename__ = "sale_tickets"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_number = Column(String, unique=True, nullable=False, index=True)
    cart_id = Column(Integer, ForeignKey("cart.id"), nullable=False)
    cash_register_id = Column(BigInteger, ForeignKey("cash_register.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("Users.ID"), nullable=False)
    
    subtotal = Column(NUMERIC(10, 2), nullable=False)
    tax = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    discount = Column(NUMERIC(10, 2), default=Decimal('0.00'))
    total = Column(NUMERIC(10, 2), nullable=False)
    
    payment_method = Column(String, nullable=False)
    payment_reference = Column(String, nullable=True)
    amount_paid = Column(NUMERIC(10, 2), nullable=True)
    change_given = Column(NUMERIC(10, 2), nullable=True)
    
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=datetime.now(UTC))
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_by = Column(Integer, ForeignKey("Users.ID"), nullable=True)
    cancellation_reason = Column(Text, nullable=True)

    cart = relationship("Cart", foreign_keys=[cart_id])
    cashier = relationship("Users", foreign_keys=[user_id])
    cancelled_by_user = relationship("Users", foreign_keys=[cancelled_by])
    cash_register = relationship("CashRegister", foreign_keys=[cash_register_id], back_populates="tickets")
    items = relationship("SaleTicketItem", back_populates="ticket", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_ticket_date', 'created_at'),
        Index('idx_ticket_status', 'status'),
        Index('idx_ticket_cashier', 'user_id'),
    )


class SaleTicketItem(Base):
    __tablename__ = "sale_ticket_items"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id = Column(Integer, ForeignKey("sale_tickets.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    product_code = Column(String, nullable=False)
    product_name = Column(Text, nullable=False)
    unit_price = Column(NUMERIC(10, 2), nullable=False)
    quantity = Column(NUMERIC(10, 4), nullable=False)
    subtotal = Column(NUMERIC(10, 2), nullable=False)
    ticket = relationship("SaleTicket", back_populates="items")