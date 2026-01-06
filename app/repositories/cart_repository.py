"""
Repository para operaciones de base de datos de carritos.
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, UTC, date
from decimal import Decimal

from models import Cart, CartItem, Product


class CartRepository:
    """Repository para gestionar carritos en la base de datos."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, cart_id: int, with_items: bool = True) -> Optional[Cart]:
        """
        Obtiene un carrito por ID.
        
        Args:
            cart_id: ID del carrito
            with_items: Si debe cargar los items con eager loading
            
        Returns:
            Cart o None
        """
        query = self.db.query(Cart)
        
        if with_items:
            query = query.options(
                joinedload(Cart.items).joinedload(CartItem.product)
            )
        
        return query.filter(Cart.id == cart_id).first()
    
    def get_by_user(
        self, 
        user_id: int, 
        status: Optional[str] = None
    ) -> List[Cart]:
        """
        Obtiene carritos de un usuario.
        
        Args:
            user_id: ID del usuario
            status: Filtrar por estado (open, completed, cancelled)
            
        Returns:
            Lista de carritos
        """
        query = self.db.query(Cart).filter(Cart.user_id == user_id)
        
        if status:
            query = query.filter(Cart.status == status)
        
        return query.order_by(Cart.created_at.desc()).all()
    
    def get_open_cart_by_user(self, user_id: int) -> Optional[Cart]:
        """
        Obtiene el carrito abierto de un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Cart abierto o None
        """
        return self.db.query(Cart).filter(
            Cart.user_id == user_id,
            Cart.status == "open"
        ).first()
    
    def search_carts(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
        min_total: Optional[float] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Cart]:
        """
        Busca carritos con múltiples filtros.
        
        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            status: Estado del carrito
            min_total: Total mínimo
            user_id: Usuario específico
            skip: Paginación
            limit: Límite de resultados
            
        Returns:
            Lista de carritos
        """
        query = self.db.query(Cart).options(
            joinedload(Cart.items).joinedload(CartItem.product)
        )
        
        # Aplicar filtros
        if start_date:
            # Comparamos solo la parte de la FECHA del registro contra tu objeto start_date
            query = query.filter(func.date(Cart.created_at) >= start_date)
        
        if end_date:
            query = query.filter(func.date(Cart.created_at) <= end_date)
        
        if status:
            query = query.filter(Cart.status == status)
        
        if user_id:
            query = query.filter(Cart.user_id == user_id)
        
        # Ordenar y paginar
        carts = query.order_by(Cart.created_at.desc()).offset(skip).limit(limit).all()
        
        # Filtrar por total si es necesario (se calcula en Python)
        if min_total is not None:
            carts = [
                c for c in carts 
                if sum(float(i.subtotal) for i in c.items) >= min_total
            ]
        
        return carts
    
    def create(self, user_id: Optional[int] = None) -> Cart:
        """
        Crea un nuevo carrito.
        
        Args:
            user_id: ID del usuario (opcional)
            
        Returns:
            Cart creado
        """
        cart = Cart(
            user_id=user_id,
            status="open",
            created_at=datetime.now(UTC)
        )
        self.db.add(cart)
        self.db.commit()
        self.db.refresh(cart)
        return cart
    
    def update_status(
        self, 
        cart_id: int, 
        new_status: str
    ) -> Optional[Cart]:
        """
        Actualiza el estado de un carrito.
        
        Args:
            cart_id: ID del carrito
            new_status: Nuevo estado
            
        Returns:
            Cart actualizado o None
        """
        cart = self.get_by_id(cart_id, with_items=False)
        if not cart:
            return None
        
        cart.status = new_status
        cart.updated_at = datetime.now(UTC)
        
        if new_status == "completed":
            cart.completed_at = datetime.now(UTC)
        elif new_status == "cancelled":
            cart.cancelled_at = datetime.now(UTC)
        
        self.db.commit()
        self.db.refresh(cart)
        return cart
    
    def delete(self, cart_id: int) -> bool:
        """
        Elimina un carrito y sus items.
        
        Args:
            cart_id: ID del carrito
            
        Returns:
            True si se eliminó, False si no existe
        """
        cart = self.get_by_id(cart_id, with_items=False)
        if not cart:
            return False
        
        self.db.delete(cart)
        self.db.commit()
        return True


class CartItemRepository:
    """Repository para gestionar items de carrito."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, item_id: int) -> Optional[CartItem]:
        """Obtiene un item por ID."""
        return self.db.query(CartItem).filter(CartItem.id == item_id).first()
    
    def get_by_cart_and_product(
        self, 
        cart_id: int, 
        product_id: int
    ) -> Optional[CartItem]:
        """
        Busca si un producto ya existe en el carrito.
        
        Args:
            cart_id: ID del carrito
            product_id: ID del producto
            
        Returns:
            CartItem existente o None
        """
        return self.db.query(CartItem).filter(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id
        ).first()
    
    def get_items_by_cart(self, cart_id: int) -> List[CartItem]:
        """Obtiene todos los items de un carrito."""
        return self.db.query(CartItem).filter(
            CartItem.cart_id == cart_id
        ).all()
    
    def create(
        self,
        cart_id: int,
        product_id: int,
        product_name: str,
        price: Decimal,
        quantity: Decimal
    ) -> CartItem:
        """
        Crea un nuevo item en el carrito.
        
        Args:
            cart_id: ID del carrito
            product_id: ID del producto
            product_name: Nombre del producto
            price: Precio unitario
            quantity: Cantidad
            
        Returns:
            CartItem creado
        """
        subtotal = price * quantity
        
        item = CartItem(
            cart_id=cart_id,
            product_id=product_id,
            product_name=product_name,
            price=price,
            quantity=quantity,
            subtotal=subtotal
        )
        
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
    
    def update_quantity(
        self, 
        item_id: int, 
        new_quantity: Decimal
    ) -> Optional[CartItem]:
        """
        Actualiza la cantidad de un item.
        
        Args:
            item_id: ID del item
            new_quantity: Nueva cantidad
            
        Returns:
            CartItem actualizado o None
        """
        item = self.get_by_id(item_id)
        if not item:
            return None
        
        item.quantity = new_quantity
        item.subtotal = item.price * new_quantity
        
        self.db.commit()
        self.db.refresh(item)
        return item
    
    def delete(self, item_id: int) -> bool:
        """
        Elimina un item del carrito.
        
        Args:
            item_id: ID del item
            
        Returns:
            True si se eliminó, False si no existe
        """
        item = self.get_by_id(item_id)
        if not item:
            return False
        
        self.db.delete(item)
        self.db.commit()
        return True
    
    def delete_all_from_cart(self, cart_id: int) -> int:
        """
        Elimina todos los items de un carrito.
        
        Args:
            cart_id: ID del carrito
            
        Returns:
            Número de items eliminados
        """
        count = self.db.query(CartItem).filter(
            CartItem.cart_id == cart_id
        ).delete()
        self.db.commit()
        return count