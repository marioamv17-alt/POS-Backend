from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from decimal import Decimal
from models import Product, PriceHistory 
from database import unit_of_work
from app.core.cache import get_cached, set_cached

from schemas import ProductoCreate, ProductoUpdate
from app.repositories.product_repository import ProductRepository
from app.core.exceptions import (
    NotFoundError, 
    DuplicateError, 
    ValidationError,
    InvalidOperationError
)

class ProductService:
    """
    Service para gestionar la lógica de negocio de productos.
    Responsabilidad: Validaciones, reglas de negocio, orquestación.
    """
    
    def __init__(self, db: Session):
        """
        Args:
            db: Sesión de SQLAlchemy
        """
        self.db = db
        self.repository = ProductRepository(db)
    
    def get_product_by_id(self, product_id: int) -> Product:
        """
        Obtiene un producto por ID con validación.
        
        Args:
            product_id: ID del producto
            
        Returns:
            Product encontrado
            
        Raises:
            NotFoundError: Si el producto no existe
        """
        producto = self.repository.get_by_id(product_id)
        
        if not producto:
            raise NotFoundError("Producto", product_id)
        
        return producto
    
    def get_all_products(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Product]:
        """
        Obtiene todos los productos activos.
        
        Args:
            skip: Registros a saltar
            limit: Máximo de registros
            
        Returns:
            Lista de productos activos
        """
        # Validar límites
        if limit > 500:
            limit = 500
        
        return self.repository.get_all_active(skip, limit)
    
    def search_products(self, query: str, include_inactive: bool = False) -> List[Product]:
        """
        Busca productos con validaciones.

        include_inactive:
        - False (default): solo activos
        - True: activos + inactivos
        """
        if not query or len(query.strip()) == 0:
            raise ValidationError("query", "El término de búsqueda no puede estar vacío")

        query = query.strip()

        if len(query) > 100:
            raise ValidationError("query", "El término de búsqueda es demasiado largo")

        return self.repository.search(query, include_inactive=include_inactive)

    
    def create_product(self, producto_data: ProductoCreate) -> Product:
        """
        Crea un nuevo producto con validaciones de negocio.
        
        Args:
            producto_data: Datos del producto (schema de Pydantic)
            
        Returns:
            Product creado
            
        Raises:
            DuplicateError: Si el código o barcode ya existe
            ValidationError: Si los datos son inválidos
        """
        # Validar código único
        if self.repository.exists_by_code(str(producto_data.code)):
            raise DuplicateError("Producto", "código", producto_data.code)
        
        # Validar barcode único (si existe)
        if producto_data.barcode:
            if self.repository.exists_by_barcode(str(producto_data.barcode)):
                raise DuplicateError("Producto", "código de barras", producto_data.barcode)
        
        # Validaciones de negocio
        self._validate_product_data(producto_data)
        
        # Crear instancia de modelo SQLAlchemy
        nuevo_producto = Product(
            Code=str(producto_data.code),
            Barcode=str(producto_data.barcode) if producto_data.barcode else None,
            Product=producto_data.product,
            Category=producto_data.category,
            Units=producto_data.units,
            Price=producto_data.price,
            Stock=producto_data.stock,
            Min_Stock=producto_data.min_stock,
            Activo=1
        )
        
        return self.repository.create(nuevo_producto)
    
    def update_product(
        self, 
        product_id: int, 
        update_data: ProductoUpdate
    ) -> Product:
        """
        Actualiza un producto existente.
        
        Args:
            product_id: ID del producto a actualizar
            update_data: Datos a actualizar (schema de Pydantic)
            
        Returns:
            Product actualizado
            
        Raises:
            NotFoundError: Si el producto no existe
            DuplicateError: Si el nuevo código/barcode ya existe
        """
        # Obtener producto existente
        producto = self.get_product_by_id(product_id)
        
        # Actualizar solo campos proporcionados
        update_dict = update_data.model_dump(exclude_unset=True, by_alias=False)
        
        # Validar código único si se está actualizando
        if "code" in update_dict:
            if self.repository.exists_by_code(str(update_dict["code"]), exclude_id=product_id):
                raise DuplicateError("Producto", "código", update_dict["code"])
            producto.Code = str(update_dict["code"])
        
        # Validar barcode único si se está actualizando
        if "barcode" in update_dict and update_dict["barcode"]:
            if self.repository.exists_by_barcode(str(update_dict["barcode"]), exclude_id=product_id):
                raise DuplicateError("Producto", "código de barras", update_dict["barcode"])
            producto.Barcode = str(update_dict["barcode"])
        
        # Actualizar otros campos
        if "product" in update_dict:
            producto.Product = update_dict["product"]
        if "stock" in update_dict:
            if update_dict["stock"] < 0:
                raise ValidationError("stock", "El stock no puede ser negativo")
            producto.Stock = update_dict["stock"]
        if "min_stock" in update_dict:
            if update_dict["min_stock"] < 0:
                raise ValidationError("min_stock", "El stock mínimo no puede ser negativo")
            producto.Min_Stock = update_dict["min_stock"]
        
        return self.repository.update(producto)
    
    def update_stock(self, product_id: int, new_stock: int) -> Product:
        """
        Actualiza el stock de un producto.
        
        Args:
            product_id: ID del producto
            new_stock: Nuevo valor de stock
            
        Returns:
            Product actualizado
            
        Raises:
            NotFoundError: Si el producto no existe
            ValidationError: Si el stock es inválido
        """
        if new_stock < 0:
            raise ValidationError("stock", "El stock no puede ser negativo")
        
        producto = self.get_product_by_id(product_id)
        producto.Stock = new_stock
        
        return self.repository.update(producto)
    
    def reduce_stock(self, product_id: int, quantity: int) -> Product:
        """
        Reduce el stock de un producto (para ventas).
        
        Args:
            product_id: ID del producto
            quantity: Cantidad a reducir
            
        Returns:
            Product actualizado
            
        Raises:
            NotFoundError: Si el producto no existe
            ValidationError: Si la cantidad es inválida
            InvalidOperationError: Si no hay stock suficiente
        """
        if quantity <= 0:
            raise ValidationError("quantity", "La cantidad debe ser mayor a 0")
        
        producto = self.get_product_by_id(product_id)
        
        # Verificar stock suficiente
        if producto.Stock < quantity:
            raise InvalidOperationError(
                f"Stock insuficiente para {producto.Product}. "
                f"Disponible: {producto.Stock}, Solicitado: {quantity}"
            )
        
        producto.Stock = producto.Stock - quantity
        return self.repository.update(producto)
    
    def delete_product(self, product_id: int) -> Product:
        """
        Elimina (desactiva) un producto.
        
        Args:
            product_id: ID del producto a eliminar
            
        Returns:
            Product desactivado
            
        Raises:
            NotFoundError: Si el producto no existe
        """
        return self.repository.soft_delete(product_id)
    
    def get_inventory_summary(self) -> Dict:
        """
        Obtiene un resumen del inventario.
        
        Returns:
            Diccionario con estadísticas de inventario
        """
        total_products = self.repository.count_active()
        low_stock_products = self.repository.get_low_stock_products()
        categories = self.repository.count_by_category()
        
        return {
            "total_products": total_products,
            "low_stock_count": len(low_stock_products),
            "normal_stock_count": total_products - len(low_stock_products),
            "categories_count": categories,
            "low_stock_products": [
                {
                    "id": p.Id,
                    "name": p.Product,
                    "current_stock": int(p.Stock),
                    "min_stock": int(p.Min_Stock)
                }
                for p in low_stock_products[:10]  # Top 10
            ]
        }
    
    def _validate_product_data(self, data: ProductoCreate) -> None:
        """
        Valida datos de producto según reglas de negocio.
        
        Args:
            data: Datos del producto
            
        Raises:
            ValidationError: Si los datos son inválidos
        """
        # Validar precio
        if data.price < 0:
            raise ValidationError("price", "El precio no puede ser negativo")
        
        if data.price > 1000000:
            raise ValidationError("price", "El precio es demasiado alto")
        
        # Validar stock
        if data.stock < 0:
            raise ValidationError("stock", "El stock no puede ser negativo")
        
        # Validar stock mínimo
        if data.min_stock < 0:
            raise ValidationError("min_stock", "El stock mínimo no puede ser negativo")
        
        # Validar nombre
        if len(data.product) < 3:
            raise ValidationError("product", "El nombre debe tener al menos 3 caracteres")
        
        # Validar categoría
        if len(data.category) < 2:
            raise ValidationError("category", "La categoría debe tener al menos 2 caracteres")
    def create_product_with_history(self, product_data: ProductoCreate):
        with unit_of_work(self.db) as db:
            product = self.repository.create(product_data)
            
            # Crear historial
            history = PriceHistory(
                product_id=product.Id,
                old_price=0,
                new_price=product.Price,
                reason="Producto creado"
            )
            db.add(history)
            
            return product
def get_inventory_summary(self) -> Dict:
        """Obtiene un resumen del inventario con soporte de caché."""
        cached = get_cached("inventory_summary")
        if cached:
            return cached
        
        # Implementación real en lugar de _calculate_summary()
        total_products = self.repository.count_active()
        low_stock_products = self.repository.get_low_stock_products()
        categories = self.repository.count_by_category()
        
        summary = {
            "total_products": total_products,
            "low_stock_count": len(low_stock_products),
            "categories_count": categories,
            "low_stock_details": [
                {"id": p.Id, "name": p.Product, "stock": p.Stock}
                for p in low_stock_products[:5]
            ]
        }
        
        set_cached("inventory_summary", summary, ttl_seconds=60)
        return summary