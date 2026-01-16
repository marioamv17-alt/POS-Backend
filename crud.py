import bcrypt
import re
from sqlalchemy import or_, and_, func
from decimal import Decimal
from sqlalchemy.exc import IntegrityError 
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, String, Index
from models import Product, Cart, CartItem, Users, PriceHistory
from schemas import ProductoCreate, ProductoUpdate
from fastapi import HTTPException
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict
from app.core.security import hash_password, verify_password
from app.core.exceptions import NotFoundError

# ------------------ Usuarios ------------------
def get_user_by_username(db: Session, username: str) -> Users | None:
    return db.query(Users).filter(Users.Username == username).first()

def create_user(db: Session, username: str, password: str, role: str = "cashier") -> Users:
    """Crea un nuevo usuario con contraseña hasheada"""
    hashed_pwd = hash_password(password)
    new_user = Users(Username=username, Password=hashed_pwd, Role=role)
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="El usuario ya existe")

def authenticate_user(db: Session, username: str, password: str) -> Users | None:
    """Autentica un usuario"""
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.Password):
        return None
    return user

def update_user_role(db: Session, user_id: int, new_role: str) -> Users:
    """Actualiza el rol de un usuario (solo admin)"""
    valid_roles = ["admin", "manager", "cashier"]
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Use: {', '.join(valid_roles)}")
    
    user = db.query(Users).filter(Users.ID == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user.Role = new_role
    db.commit()
    db.refresh(user)
    return user

# ------------------ Productos ------------------
def obtener_productos(db: Session, skip: int = 0, limit: int = 100) -> list[Product]:
    return db.query(Product).filter(Product.Activo == 1).offset(skip).limit(limit).all()

def buscar_producto(db: Session, product_id=None, code=None, barcode=None) -> Product | None:
    """
    Busca un producto ACTIVO por ID, código o código de barras.
    
    IMPORTANTE: Solo retorna productos activos (Activo=1)
    para evitar que se agreguen productos inactivos al carrito.
    """
    # SIEMPRE filtrar por productos activos
    q = db.query(Product).filter(Product.Activo == 1)
    
    if product_id:
        return q.filter(Product.Id == product_id).first()
    if code:
        return q.filter(cast(Product.Code, String).ilike(f"%{code}%")).first()
    if barcode:
        return q.filter(cast(Product.Barcode, String).ilike(f"%{barcode}%")).first()
    return None

def crear_producto(db: Session, producto: ProductoCreate) -> Product:
    try:
        nuevo = Product(**producto.model_dump(by_alias=True))
        db.add(nuevo)
        db.commit()
        db.refresh(nuevo)
        return nuevo
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Código o código de barras duplicado")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear producto: {str(e)}")

def actualizar_stock(db: Session, id: int, nuevo_stock: int) -> Product:
    producto = db.query(Product).filter(Product.Id == id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if nuevo_stock < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    
    producto.Stock = nuevo_stock
    db.commit()
    db.refresh(producto)
    return producto

def eliminar_producto(db: Session, id: int):
    producto = db.query(Product).filter(Product.Id == id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.Activo = 0
    db.commit()
    return producto

def resumen_inventario(db: Session) -> dict:
    total = db.query(Product).filter(Product.Activo == 1).count()
    bajo = db.query(Product).filter(
        Product.Stock <= Product.Min_Stock, 
        Product.Activo == 1
    ).count()
    normal = total - bajo
    categorias = db.query(Product.Category).filter(Product.Activo == 1).distinct().count()
    return {
        "TotalProductos": total,
        "StockBajo": bajo,
        "StockNormal": normal,
        "Categorias": categorias
    }

def actualizar_producto(db: Session, product_id: int, data: ProductoUpdate) -> Product | None:
    producto = db.query(Product).filter(Product.Id == product_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    for field, value in data.model_dump(exclude_unset=True, by_alias=False).items():
        setattr(producto, field, value)
    db.commit()
    db.refresh(producto)
    return producto

# ------------------ Carritos ------------------
def crear_carrito(db: Session, user_id: int | None = None) -> Cart:
    """Crea un nuevo carrito, opcionalmente asociado a un usuario"""
    cart = Cart(user_id=user_id)  # Aquí está el user_id que causaba error
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart

def obtener_carrito(db: Session, cart_id: int) -> Cart | None:
    return db.query(Cart).filter(Cart.id == cart_id).first()

def buscar_producto(db: Session, product_id=None, code=None, barcode=None) -> Product | None:
    q = db.query(Product).filter(Product.Activo == 1)
    if product_id:
        return q.filter(Product.Id == product_id).first()
    if code:
        return q.filter(cast(Product.Code, String).ilike(f"%{code}%")).first()
    if barcode:
        return q.filter(cast(Product.Barcode, String).ilike(f"%{barcode}%")).first()
    return None

def agregar_item(db: Session, cart_id: int, product: Product, quantity: Decimal) -> CartItem:
    if product.Stock < float(quantity):
        raise HTTPException(status_code=400, detail="Stock insuficiente")
    subtotal = float(product.Price) * float(quantity)

     # Verificar si el item ya existe en el carrito
    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart_id,
        CartItem.product_id == product.Id
    ).first()
    
    if existing_item:
        # Actualizar cantidad existente
        existing_item.quantity += quantity
        existing_item.subtotal = existing_item.price * existing_item.quantity
        db.commit()
        db.refresh(existing_item)
        return existing_item
    
    # Crear nuevo item
    subtotal = product.Price * quantity
    item = CartItem(
        cart_id=cart_id,
        product_id=product.Id,
        product_name=product.Product,
        price=product.Price,
        quantity=quantity,
        subtotal=subtotal,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def actualizar_item(db: Session, item_id: int, quantity: Decimal) -> CartItem | None:
    item = db.query(CartItem).filter(CartItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a 0")
    
    item.quantity = quantity
    item.subtotal = item.price * item.quantity
    db.commit()
    db.refresh(item)
    return item

def resumen_carrito(db: Session, cart_id: int):
    cart = db.query(Cart).options(
        joinedload(Cart.items).joinedload(CartItem.product)
    ).filter(Cart.id == cart_id).first()
    
    if not cart:
        raise NotFoundError("Carrito", cart_id)
    
    total = sum(i.subtotal for i in cart.items)
    return {"cart": cart, "total": total}

def eliminar_item_carrito(db: Session, cart_id: int, item_id: int):
    item = db.query(CartItem).filter(
        CartItem.cart_id == cart_id, 
        CartItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    
    db.delete(item)
    db.commit()
    return {"message": "Item eliminado"}

def vaciar_carrito(db: Session, cart_id: int):
    items = db.query(CartItem).filter(CartItem.cart_id == cart_id).all()
    for item in items:
        db.delete(item)
    db.commit()
    return {"message": "Carrito vaciado"}

def cambiar_estado_carrito(db: Session, cart_id: int, new_status: str):
    cart = db.query(Cart).filter(Cart.id == cart_id).first()
    if not cart:
        return None, "Carrito no encontrado"
    
    cart.status = new_status
    now = datetime.now(UTC)

    if new_status == "completed":
        cart.completed_at = datetime.now(UTC)
    elif new_status == "cancelled":
        cart.cancelled_at = now
    
    cart.updated_at = now
    
    db.commit()
    db.refresh(cart)
    return cart, None

def actualizar_cantidad_item(db: Session, cart_id: int, item_id: int, new_qty: int):
    item = db.query(CartItem).filter(CartItem.cart_id == cart_id, CartItem.id == item_id).first()
    if not item:
        return None, "Item no encontrado en el carrito"
    if item.product.Stock < new_qty:
         return None, f"Stock insuficiente. Disponible: {item.product.Stock}"
    item.quantity = new_qty
    db.commit()
    db.refresh(item)
    return item, None

def calcular_total_carrito(db: Session, cart_id: int):
    items = db.query(CartItem).filter(CartItem.cart_id == cart_id).all()
    total = sum(i.price * i.quantity for i in items)
    return total

# NUEVA FUNCIÓN PARA PUNTO 5: Búsqueda avanzada
def buscar_carritos_avanzado(db: Session, fecha_inicio: datetime = None, fecha_fin: datetime = None, min_total: float = None, status: str = None, item_name: str = None):
    query = db.query(Cart).options(joinedload(Cart.items).joinedload(CartItem.product))
    
    if fecha_inicio:
       query = query.filter(func.date(Cart.created_at) >= fecha_inicio)
    if fecha_fin:
        query = query.filter(func.date(Cart.created_at) <= fecha_fin)
    if status:
        query = query.filter(Cart.status == status)
        
    # Filtro por nombre de producto dentro del carrito
    if item_name:
        query = query.join(Cart.items).join(CartItem.product).filter(Product.Product.ilike(f"%{item_name}%"))
    
    carts = query.all()
    
    # Filtro por total (calculado, ya que el total a veces no se guarda en la tabla Cart hasta cerrar)
    # Si tienes una columna 'total' en Cart, úsala en el query. Si no, filtra en Python:
    if min_total is not None:
        carts = [c for c in carts if sum(i.quantity * i.price_at_add for i in c.items) >= min_total]
        
    return carts


#Precios
def actualizar_precio(db: Session, product_id: int, new_price: float, reason: str | None = None):
    producto = db.query(Product).filter(Product.Id == product_id).first()
    if not producto:
        return None, "Producto no encontrado"

    if producto.Activo == 0:
        return None, "Producto inactivo"

    if new_price < 0:
        return None, "Precio no puede ser negativo"

    old_price = producto.Price
    if round(old_price, 2) == round(new_price, 2):
        return None, "El nuevo precio es igual al actual"

    producto.Price = float(round(new_price, 2))
    db.add(producto)

    # Registrar historial (opcional pero recomendado)
    hist = PriceHistory(
        product_id=producto.Id,
        old_price=old_price,
        new_price=producto.Price,
        reason=reason,
        changed_at=datetime.now(UTC)
    )
    db.add(hist)

    db.commit()
    db.refresh(producto)
    return producto, None

def actualizar_precios_en_lote(db: Session, items: list[dict]):
    resultados = []
    for item in items:
        pid = int(item["Id"])
        price = float(item["Price"])
        reason = item.get("Reason")
        producto, error = actualizar_precio(db, pid, price, reason)
        resultados.append({
            "Id": pid,
            "Success": error is None,
            "Error": error if error else None,
            "NewPrice": producto.Price if producto else None
        })
    return resultados

def obtener_historial_precios(db: Session, product_id: int, limit: int = 50):
    return (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.changed_at.desc())
        .limit(limit)
        .all()
    )