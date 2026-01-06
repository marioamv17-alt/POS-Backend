"""
Mixin para agregar funcionalidad de paginación a los services.
"""

from sqlalchemy.orm import Query
from typing import TypeVar, List, Tuple
from schemas_pagination import PaginationParams, PaginatedResponse, paginate

T = TypeVar('T')


class PaginationMixin:
    """
    Mixin que agrega métodos de paginación a cualquier service.
    
    Uso:
        class ProductService(PaginationMixin):
            pass
    """
    
    def paginate_query(
        self,
        query: Query,
        pagination: PaginationParams
    ) -> Tuple[List[T], int]:
        """
        Pagina una query de SQLAlchemy.
        
        Args:
            query: Query de SQLAlchemy sin limit/offset
            pagination: Parámetros de paginación
            
        Returns:
            Tupla de (items, total_count)
        """
        # Obtener total de registros
        total = query.count()
        
        # Aplicar paginación
        items = query.offset(pagination.skip).limit(pagination.limit).all()
        
        return items, total
    
    def create_paginated_response(
        self,
        items: List[T],
        total: int,
        pagination: PaginationParams
    ) -> PaginatedResponse[T]:
        """
        Crea una respuesta paginada.
        
        Args:
            items: Lista de items
            total: Total de registros
            pagination: Parámetros de paginación
            
        Returns:
            PaginatedResponse con metadatos
        """
        return paginate(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )