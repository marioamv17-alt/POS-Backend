"""
Schemas para paginación mejorada con metadatos completos.
"""
from schemas import SaleTicketSchema 
from pydantic import BaseModel, Field, ConfigDict
from typing import Generic, TypeVar, List, Optional
from math import ceil

T = TypeVar('T')


class PaginationMeta(BaseModel):
    """Metadatos de paginación"""
    total: int = Field(..., description="Total de registros")
    page: int = Field(..., description="Página actual")
    page_size: int = Field(..., description="Registros por página")
    total_pages: int = Field(..., description="Total de páginas")
    has_next: bool = Field(..., description="¿Hay página siguiente?")
    has_prev: bool = Field(..., description="¿Hay página anterior?")
    next_page: Optional[int] = Field(None, description="Número de página siguiente")
    prev_page: Optional[int] = Field(None, description="Número de página anterior")
    
    model_config = ConfigDict(from_attributes=True)

class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada genérica"""
    data: List[T] = Field(..., description="Lista de resultados")
    meta: PaginationMeta = Field(..., description="Metadatos de paginación")

    model_config = ConfigDict(from_attributes=True)

class TicketPaginatedResponse(BaseModel):
    """Respuesta paginada específica para tickets"""
    tickets: List[SaleTicketSchema] = Field(..., description="Lista de tickets")  # ✅ usar schema Pydantic
    meta: PaginationMeta = Field(..., description="Metadatos de paginación")

    model_config = ConfigDict(from_attributes=True)



class PaginationParams(BaseModel):
    """Parámetros de paginación reutilizables"""
    page: int = Field(1, ge=1, description="Número de página")
    page_size: int = Field(50, ge=1, le=100, description="Registros por página")
    
    @property
    def skip(self) -> int:
        """Calcula el offset para la query"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Retorna el límite"""
        return self.page_size
    
    model_config = ConfigDict(from_attributes=True)


def create_pagination_meta(
    total: int,
    page: int,
    page_size: int
) -> PaginationMeta:
    """
    Crea metadatos de paginación.
    
    Args:
        total: Total de registros
        page: Página actual
        page_size: Registros por página
        
    Returns:
        PaginationMeta con todos los campos calculados
    """
    total_pages = ceil(total / page_size) if total > 0 else 0
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginationMeta(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        next_page=page + 1 if has_next else None,
        prev_page=page - 1 if has_prev else None
    )


def paginate(
    items: List[T],
    total: int,
    page: int,
    page_size: int
) -> TicketPaginatedResponse[T]:
    """
    Envuelve una lista en una respuesta paginada.
    
    Args:
        items: Lista de items
        total: Total de registros en la base de datos
        page: Página actual
        page_size: Registros por página
        
    Returns:
        PaginatedResponse con data y metadatos
    """
    meta = create_pagination_meta(total, page, page_size)
    
    return TicketPaginatedResponse(
        tickets=items,
        meta=meta
    )