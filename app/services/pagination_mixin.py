"""
Mixin para agregar funcionalidad de paginación a los services.
"""

from sqlalchemy.orm import Query
from typing import TypeVar, List, Tuple
from schemas_pagination import PaginationParams, PaginatedResponse, paginate

T = TypeVar('T')


class PaginationMixin:
    def paginate_query(
        self,
        query: Query,
        pagination: PaginationParams
    ) -> Tuple[List[T], int]:
        total = query.count()
        items = query.offset(pagination.skip).limit(pagination.limit).all()
        return items, total

    def create_paginated_response(
        self,
        items: List[T],
        total: int,
        pagination: PaginationParams
    ) -> PaginatedResponse[T]:
        return {
            "data": items,   # ✅ clave corregida
            "meta": {
                "page": pagination.page,
                "page_size": pagination.page_size,
                "total": total,
                "has_next": pagination.page * pagination.page_size < total,
                "has_prev": pagination.page > 1,
                "next_page": pagination.page + 1 if pagination.page * pagination.page_size < total else None,
                "prev_page": pagination.page - 1 if pagination.page > 1 else None,
            }
        }
