"""
Repository para operaciones de base de datos de productos.
Capa de acceso a datos - solo consultas SQL, sin lógica de negocio.
"""

from sqlalchemy.orm import Session
from sqlalchemy import cast, String, or_, and_
from typing import List, Optional
from decimal import Decimal

# Importar modelo de SQLAlchemy
from models import Product

# Importar excepciones
from app.core.exceptions import NotFoundError, DuplicateError


class ProductRepository:
    """
    Repository para gestionar productos en la base de datos.
    Responsabilidad: Solo operaciones CRUD, sin lógica de negocio.
    """
    
    def __init__(self, db: Session):
        """
        Args:
            db: Sesión de SQLAlchemy
        """
        self.db = db
    
    def get_by_id(self, product_id: int) -> Optional[Product]:
        """
        Obtiene un producto por ID.
        
        Args:
            product_id: ID del producto
            
        Returns:
            Product o None si no existe
        """
        return self.db.query(Product).filter(
            Product.Id == product_id
        ).first()
    
    def get_by_code(self, code: str) -> Optional[Product]:
        """
        Obtiene un producto por código.
        
        Args:
            code: Código del producto
            
        Returns:
            Product o None si no existe
        """
        return self.db.query(Product).filter(
            cast(Product.Code, String) == str(code)
        ).first()
    
    def get_by_barcode(self, barcode: str) -> Optional[Product]:
        """
        Obtiene un producto por código de barras.
        
        Args:
            barcode: Código de barras
            
        Returns:
            Product o None si no existe
        """
        return self.db.query(Product).filter(
            cast(Product.Barcode, String) == str(barcode)
        ).first()
    
    def get_all_active(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Product]:
        """
        Obtiene todos los productos activos con paginación.
        
        Args:
            skip: Registros a saltar
            limit: Máximo de registros
            
        Returns:
            Lista de productos activos
        """
        return self.db.query(Product).filter(
            Product.Activo == 1
        ).offset(skip).limit(limit).all()
    
def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
    """Obtiene todos los productos (activos e inactivos)"""
    return (
        self.db.query(Product)
        .offset(skip)
        .limit(limit)
        .all()
    )

def search(self, query: str, include_inactive: bool = False, limit: int = 100) -> List[Product]:
    search_pattern = f"%{query}%"
    base_filter = or_(
        Product.Product.ilike(search_pattern),
        cast(Product.Code, String).ilike(search_pattern),
        cast(Product.Barcode, String).ilike(search_pattern),
    )
    q = self.db.query(Product).filter(base_filter)
    if not include_inactive:
        q = q.filter(Product.Activo == 1)
    return q.limit(limit).all()


    def exists_by_code(self, code: str, exclude_id: Optional[int] = None) -> bool:
        """
        Verifica si existe un producto con el código dado.
        
        Args:
            code: Código a verificar
            exclude_id: ID de producto a excluir (para updates)
            
        Returns:
            True si existe, False si no
        """
        query = self.db.query(Product).filter(
            cast(Product.Code, String) == str(code)
        )
        
        if exclude_id:
            query = query.filter(Product.Id != exclude_id)
        
        return query.first() is not None
    
    def exists_by_barcode(
        self, 
        barcode: str, 
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Verifica si existe un producto con el código de barras dado.
        
        Args:
            barcode: Código de barras a verificar
            exclude_id: ID de producto a excluir (para updates)
            
        Returns:
            True si existe, False si no
        """
        query = self.db.query(Product).filter(
            cast(Product.Barcode, String) == str(barcode)
        )
        
        if exclude_id:
            query = query.filter(Product.Id != exclude_id)
        
        return query.first() is not None
    
    def get_low_stock_products(self) -> List[Product]:
        """
        Obtiene productos con stock bajo o igual al mínimo.
        
        Returns:
            Lista de productos con stock bajo
        """
        return self.db.query(Product).filter(
            Product.Stock <= Product.Min_Stock,
            Product.Activo == 1
        ).all()
    
    def get_by_category(self, category: str) -> List[Product]:
        """
        Obtiene productos por categoría.
        
        Args:
            category: Nombre de la categoría
            
        Returns:
            Lista de productos de esa categoría
        """
        return self.db.query(Product).filter(
            Product.Category == category,
            Product.Activo == 1
        ).all()
    
    def create(self, product: Product) -> Product:
        """
        Crea un nuevo producto en la base de datos.
        
        Args:
            product: Instancia de Product a guardar
            
        Returns:
            Product guardado con ID asignado
        """
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product
    
    def update(self, product: Product) -> Product:
        """
        Actualiza un producto existente.
        
        Args:
            product: Instancia de Product con cambios
            
        Returns:
            Product actualizado
        """
        self.db.commit()
        self.db.refresh(product)
        return product
    
    def soft_delete(self, product_id: int) -> Product:
        """
        Marca un producto como inactivo (borrado suave).
        
        Args:
            product_id: ID del producto a desactivar
            
        Returns:
            Product desactivado
            
        Raises:
            NotFoundError: Si el producto no existe
        """
        producto = self.get_by_id(product_id)
        
        if not producto:
            raise NotFoundError("Producto", product_id)
        
        producto.Activo = 0
        self.db.commit()
        self.db.refresh(producto)
        return producto
    
    def count_active(self) -> int:
        """
        Cuenta productos activos.
        
        Returns:
            Número de productos activos
        """
        return self.db.query(Product).filter(Product.Activo == 1).count()
    
    def count_by_category(self) -> int:
        """
        Cuenta categorías distintas.
        
        Returns:
            Número de categorías únicas
        """
        return self.db.query(Product.Category).filter(
            Product.Activo == 1
        ).distinct().count()