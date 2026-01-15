from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from schemas import ProductoSchema, ProductoCreate, ProductoUpdate
from app.services.product_service import ProductService
from app.core.exceptions import (
    AppException,
    NotFoundError,
    DuplicateError,
    ValidationError
)

router = APIRouter(prefix="/api/inventario", tags=["Inventario"])


# ==================== LISTAR PRODUCTOS ====================
@router.get("", response_model=List[ProductoSchema])
def obtener_inventario(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    include_inactive: bool = Query(False, description="Incluir productos inactivos"),
    db: Session = Depends(get_db)
):
    service = ProductService(db)
    productos = service.get_all_products(skip=skip, limit=limit, include_inactive=include_inactive)
    return productos

# ==================== BUSCAR PRODUCTOS ====================
@router.get("/buscar", response_model=List[ProductoSchema])
def buscar_productos(
    query: str = Query(..., min_length=1),
    include_inactive: bool = Query(False, description="Incluir productos inactivos"),
    db: Session = Depends(get_db)
):
    service = ProductService(db)
    productos = service.search_products(query, include_inactive=include_inactive)
    return productos

# ==================== OBTENER UN PRODUCTO ====================
@router.get("/{product_id}", response_model=ProductoSchema)
def obtener_producto(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un producto específico por ID.
    
    - **product_id**: ID del producto
    """
    try:
        service = ProductService(db)
        producto = service.get_product_by_id(product_id)
        return producto
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== CREAR PRODUCTO ====================
@router.post("", response_model=ProductoSchema, status_code=201)
def crear_producto(
    producto: ProductoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo producto en el inventario.
    
    **Validaciones:**
    - Código único
    - Código de barras único
    - Precio mayor o igual a 0
    - Stock mayor o igual a 0
    """
    try:
        service = ProductService(db)
        nuevo_producto = service.create_product(producto)
        return nuevo_producto
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== ACTUALIZAR PRODUCTO ====================
@router.patch("/{product_id}", response_model=ProductoSchema)
def actualizar_producto(
    product_id: int,
    data: ProductoUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un producto existente.
    
    - Solo se actualizan los campos proporcionados
    - **product_id**: ID del producto a actualizar
    """
    try:
        service = ProductService(db)
        producto_actualizado = service.update_product(product_id, data)
        return producto_actualizado
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except DuplicateError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== ACTUALIZAR SOLO STOCK ====================
@router.patch("/{product_id}/stock")
def actualizar_stock(
    product_id: int,
    nuevo_stock: int = Query(..., ge=0, description="Nuevo valor de stock"),
    db: Session = Depends(get_db)
):
    """
    Actualiza solo el stock de un producto.
    
    - **product_id**: ID del producto
    - **nuevo_stock**: Nuevo valor de stock (debe ser >= 0)
    """
    try:
        service = ProductService(db)
        producto = service.update_stock(product_id, nuevo_stock)
        return {
            "message": "Stock actualizado exitosamente",
            "product_id": producto.Id,
            "product_name": producto.Product,
            "new_stock": int(producto.Stock)
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== ELIMINAR PRODUCTO ====================
@router.delete("/{product_id}")
def eliminar_producto(
    product_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina (desactiva) un producto del inventario.
    
    - El producto se marca como inactivo, no se elimina físicamente
    - **product_id**: ID del producto a eliminar
    """
    try:
        service = ProductService(db)
        producto = service.delete_product(product_id)
        return {
            "message": "Producto marcado como inactivo exitosamente",
            "product_id": producto.Id,
            "product_name": producto.Product
        }
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== RESUMEN DE INVENTARIO ====================
@router.get("/resumen/estadisticas")
def resumen_inventario(db: Session = Depends(get_db)):
    """
    Obtiene un resumen completo del inventario.
    
    **Incluye:**
    - Total de productos activos
    - Productos con stock bajo
    - Número de categorías
    - Top 10 productos con stock bajo
    """
    try:
        service = ProductService(db)
        resumen = service.get_inventory_summary()
        return resumen
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)