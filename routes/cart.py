from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Any
from datetime import date, datetime
from database import get_db
from app.core.security import get_current_user
from app.services.cart_service import CartService
from models import Users
from schemas import CartSchema, CartItemSchema, AddItemRequest
from app.core.exceptions import AppException, NotFoundError

router = APIRouter(prefix="/api/pos/carts", tags=["Carts"])


# ==================== CREAR CARRITO ====================
@router.post("", response_model=CartSchema, status_code=201)
def crear_carrito_endpoint(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    """
    Crea un nuevo carrito vacío.
    
    **Automáticamente asociado al usuario autenticado.**
    """
    try:
        service = CartService(db)
        cart = service.create_cart(user_id=current_user.ID)
        
        cart_schema = CartSchema.model_validate(cart)
        return cart_schema.model_dump() | {"total": 0.0}
    
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

# ==================== BUSCAR CARRITOS ====================

@router.get("/search")

def buscar_carritos(

    start_date: Optional[str] = Query(None, description="Fecha inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha final (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, pattern="^(open|completed|cancelled)$"),
    min_total: Optional[float] = Query(None, ge=0),
    user_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Búsqueda avanzada de carritos con múltiples filtros.
    **Filtros disponibles:**
    - `start_date`, `end_date`: Rango de fechas
    - `status`: Estado del carrito
    - `min_total`: Total mínimo
    - `user_id`: Usuario específico
    """
    try:
        service = CartService(db)
        # PROCESAMIENTO ROBUSTO DE FECHAS
        start_datetime = None
        end_datetime = None
        if start_date:
            # Tomamos solo YYYY-MM-DD e iniciamos a las 00:00:00
            start_clean = start_date[:10]
            start_datetime = datetime.strptime(start_clean, "%Y-%m-%d")
        
        if end_date:
            # Tomamos solo YYYY-MM-DD para limpiar la "T" del frontend
            end_clean = end_date[:10]
            # IMPORTANTE: Usamos .replace para cubrir TODO el día
            end_datetime = datetime.strptime(end_clean, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        carts = service.search_carts(
            start_date=start_datetime,
            end_date=end_datetime,
            status=status,
            min_total=min_total,
            user_id=user_id,
            skip=skip,
            limit=limit
        )
        return {
            "total": len(carts),
            "carts": [
                {
                    "id": c.id,
                    "status": c.status,
                    "created_at": c.created_at.isoformat(),
                    "items_count": len(c.items),
                    "total": float(sum(i.subtotal for i in c.items))
                }
                for c in carts
            ]
        }
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD"
        )
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

# ==================== AGREGAR ITEM ====================
@router.post("/{cart_id}/items", response_model=CartItemSchema, status_code=201)
def agregar_item_endpoint(
    cart_id: int,
    data: AddItemRequest,
    db: Session = Depends(get_db)
):
    """
    Agrega un producto al carrito.
    
    **Búsqueda flexible:**
    - Por `product_id`
    - Por `code` (código del producto)
    - Por `barcode` (código de barras)
    
    **Validaciones automáticas:**
    - Stock disponible
    - Carrito abierto
    - Producto activo
    
    **Ejemplo:**
    ```json
    {
        "barcode": "7501234567890",
        "quantity": 2
    }
    ```
    """
    try:
        service = CartService(db)
        item = service.add_item_to_cart(cart_id, data)
        return CartItemSchema.model_validate(item)
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== OBTENER CARRITO ====================
@router.get("/{cart_id}", response_model=CartSchema)
def obtener_carrito_endpoint(
    cart_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un carrito con todos sus items y total calculado.
    """
    try:
        service = CartService(db)
        result = service.get_cart_with_total(cart_id)
        
        cart_schema = CartSchema.model_validate(result["cart"])
        return cart_schema.model_dump() | {
            "total": result["total"],
            "items_count": result["items_count"]
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== ACTUALIZAR CANTIDAD ====================
@router.patch("/{cart_id}/items/{item_id}")
def actualizar_cantidad_item(
    cart_id: int,
    item_id: int,
    quantity: int = Query(..., gt=0, description="Nueva cantidad"),
    db: Session = Depends(get_db)
):
    """
    Actualiza la cantidad de un item en el carrito.
    
    **Validaciones:**
    - Cantidad > 0
    - Stock disponible
    """
    try:
        service = CartService(db)
        item = service.update_item_quantity(cart_id, item_id, quantity)
        
        return {
            "message": "Cantidad actualizada",
            "item_id": item.id,
            "product_name": item.product_name,
            "new_quantity": float(item.quantity),
            "new_subtotal": float(item.subtotal)
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== ELIMINAR ITEM ====================
@router.delete("/{cart_id}/items/{item_id}")
def eliminar_item(
    cart_id: int,
    item_id: int,
    db: Session = Depends(get_db)
):
    """Elimina un item específico del carrito."""
    try:
        service = CartService(db)
        service.remove_item_from_cart(cart_id, item_id)
        
        return {
            "success": True,
            "message": "Item eliminado correctamente"
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== VACIAR CARRITO ====================
@router.delete("/{cart_id}/items")
def vaciar_carrito(
    cart_id: int,
    db: Session = Depends(get_db)
):
    """Elimina todos los items del carrito."""
    try:
        service = CartService(db)
        deleted_count = service.clear_cart(cart_id)
        
        return {
            "success": True,
            "message": f"{deleted_count} items eliminados",
            "deleted_count": deleted_count
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ==================== CAMBIAR ESTADO ====================
@router.patch("/{cart_id}/status")
def cambiar_estado_carrito(
    cart_id: int,
    status: str = Query(..., pattern="^(open|completed|cancelled)$"),
    db: Session = Depends(get_db)
):
    """
    Cambia el estado del carrito.
    
    **Estados válidos:**
    - `open`: Carrito activo
    - `completed`: Procesado (no se puede modificar)
    - `cancelled`: Cancelado
    """
    try:
        service = CartService(db)
        cart = service.change_cart_status(cart_id, status)
        
        return {
            "success": True,
            "cart_id": cart.id,
            "new_status": cart.status,
            "updated_at": cart.updated_at.isoformat()
        }
    
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)