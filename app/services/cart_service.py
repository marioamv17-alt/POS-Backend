from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
from decimal import Decimal

from models import Cart, CartItem, Product
from schemas import AddItemRequest
from app.repositories.cart_repository import CartRepository, CartItemRepository
from app.repositories.product_repository import ProductRepository
from app.core.exceptions import (
    NotFoundError,
    InvalidOperationError,
    ValidationError,
    InsufficientStockError
)


class CartService:
    """Service para gestionar la lógica de negocio de carritos."""
    
    def __init__(self, db: Session):
        self.db = db
        self.cart_repo = CartRepository(db)
        self.cart_item_repo = CartItemRepository(db)
        self.product_repo = ProductRepository(db)
    
    def create_cart(self, user_id: Optional[int] = None) -> Cart:
        """
        Crea un nuevo carrito.
        
        Args:
            user_id: ID del usuario (opcional)
            
        Returns:
            Cart creado
        """
        return self.cart_repo.create(user_id)
    
    def get_cart(self, cart_id: int) -> Cart:
        """
        Obtiene un carrito por ID.
        
        Args:
            cart_id: ID del carrito
            
        Returns:
            Cart encontrado
            
        Raises:
            NotFoundError: Si el carrito no existe
        """
        cart = self.cart_repo.get_by_id(cart_id)
        if not cart:
            raise NotFoundError("Carrito", cart_id)
        return cart
    
    def get_cart_with_total(self, cart_id: int) -> Dict:
        """
        Obtiene un carrito con su total calculado.
        
        Args:
            cart_id: ID del carrito
            
        Returns:
            Diccionario con cart y total
        """
        cart = self.get_cart(cart_id)
        total = self._calculate_total(cart)
        
        return {
            "cart": cart,
            "total": float(total),
            "items_count": len(cart.items)
        }
    
    def add_item_to_cart(
        self, 
        cart_id: int, 
        request: AddItemRequest
    ) -> CartItem:
        """
        Agrega un producto al carrito.
        
        Args:
            cart_id: ID del carrito
            request: Datos del item (product_id, code, barcode, quantity)
            
        Returns:
            CartItem creado o actualizado
            
        Raises:
            NotFoundError: Si el carrito o producto no existe
            InvalidOperationError: Si el carrito no está abierto
            InsufficientStockError: Si no hay stock suficiente
        """
        # Validar carrito
        cart = self.get_cart(cart_id)
        
        if cart.status != "open":
            raise InvalidOperationError(
                f"No se puede agregar items a un carrito {cart.status}"
            )
        
        # Buscar producto
        product = self._find_product(request)
        if not product:
            raise NotFoundError("Producto", "especificado")
        
        # Validar stock
        if product.Stock < float(request.quantity):
            raise InsufficientStockError(
                product.Product,
                int(product.Stock),
                int(request.quantity)
            )
        
        # Verificar si el producto ya está en el carrito
        existing_item = self.cart_item_repo.get_by_cart_and_product(
            cart_id, 
            product.Id
        )
        
        if existing_item:
            # Actualizar cantidad existente
            new_quantity = existing_item.quantity + request.quantity
            
            # Validar stock total
            if product.Stock < float(new_quantity):
                raise InsufficientStockError(
                    product.Product,
                    int(product.Stock),
                    int(new_quantity)
                )
            
            return self.cart_item_repo.update_quantity(existing_item.id, new_quantity)
        else:
            # Crear nuevo item
            return self.cart_item_repo.create(
                cart_id=cart_id,
                product_id=product.Id,
                product_name=product.Product,
                price=product.Price,
                quantity=request.quantity
            )
    
    def update_item_quantity(
        self, 
        cart_id: int, 
        item_id: int, 
        new_quantity: Decimal
    ) -> CartItem:
        """
        Actualiza la cantidad de un item en el carrito.
        
        Args:
            cart_id: ID del carrito
            item_id: ID del item
            new_quantity: Nueva cantidad
            
        Returns:
            CartItem actualizado
            
        Raises:
            NotFoundError: Si el item no existe
            ValidationError: Si la cantidad es inválida
            InsufficientStockError: Si no hay stock suficiente
        """
        # Validar cantidad
        if new_quantity <= 0:
            raise ValidationError("quantity", "La cantidad debe ser mayor a 0")
        
        # Obtener item
        item = self.cart_item_repo.get_by_id(item_id)
        if not item or item.cart_id != cart_id:
            raise NotFoundError("Item", item_id)
        
        # Validar stock
        product = self.product_repo.get_by_id(item.product_id)
        if product and product.Stock < float(new_quantity):
            raise InsufficientStockError(
                product.Product,
                int(product.Stock),
                int(new_quantity)
            )
        
        return self.cart_item_repo.update_quantity(item_id, new_quantity)
    
    def remove_item_from_cart(self, cart_id: int, item_id: int) -> None:
        """
        Elimina un item del carrito.
        
        Args:
            cart_id: ID del carrito
            item_id: ID del item
            
        Raises:
            NotFoundError: Si el item no existe o no pertenece al carrito
        """
        item = self.cart_item_repo.get_by_id(item_id)
        
        if not item or item.cart_id != cart_id:
            raise NotFoundError("Item", item_id)
        
        success = self.cart_item_repo.delete(item_id)
        if not success:
            raise NotFoundError("Item", item_id)
    
    def clear_cart(self, cart_id: int) -> int:
        """
        Vacía todos los items de un carrito.
        
        Args:
            cart_id: ID del carrito
            
        Returns:
            Número de items eliminados
            
        Raises:
            NotFoundError: Si el carrito no existe
        """
        # Validar que el carrito existe
        self.get_cart(cart_id)
        
        return self.cart_item_repo.delete_all_from_cart(cart_id)
    
    def change_cart_status(self, cart_id: int, new_status: str) -> Cart:
        """
        Cambia el estado de un carrito.
        
        Args:
            cart_id: ID del carrito
            new_status: Nuevo estado (open, completed, cancelled)
            
        Returns:
            Cart actualizado
            
        Raises:
            NotFoundError: Si el carrito no existe
            ValidationError: Si el estado es inválido
        """
        # Validar estado
        valid_statuses = ["open", "completed", "cancelled"]
        if new_status not in valid_statuses:
            raise ValidationError(
                "status", 
                f"Estado debe ser: {', '.join(valid_statuses)}"
            )
        
        cart = self.cart_repo.update_status(cart_id, new_status)
        if not cart:
            raise NotFoundError("Carrito", cart_id)
        
        return cart
    
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
        Busca carritos con filtros.
        
        Args:
            start_date: Fecha inicial
            end_date: Fecha final
            status: Estado del carrito
            min_total: Total mínimo
            user_id: Usuario específico
            skip: Paginación
            limit: Límite
            
        Returns:
            Lista de carritos
        """
        return self.cart_repo.search_carts(
            start_date=start_date,
            end_date=end_date,
            status=status,
            min_total=min_total,
            user_id=user_id,
            skip=skip,
            limit=limit
        )
    
    def _find_product(self, request: AddItemRequest) -> Optional[Product]:
        """
        Busca un producto por ID, código o barcode.
        
        Args:
            request: Request con product_id, code o barcode
            
        Returns:
            Product encontrado o None
        """
        if request.product_id:
            return self.product_repo.get_by_id(request.product_id)
        
        if request.code:
            return self.product_repo.get_by_code(str(request.code))
        
        if request.barcode:
            return self.product_repo.get_by_barcode(str(request.barcode))
        
        return None
    
    def _calculate_total(self, cart: Cart) -> Decimal:
        """
        Calcula el total de un carrito.
        
        Args:
            cart: Carrito a calcular
            
        Returns:
            Total del carrito
        """
        return sum(item.subtotal for item in cart.items)