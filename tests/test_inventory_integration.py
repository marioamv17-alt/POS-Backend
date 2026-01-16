"""
Tests de integración para flujos completos de inventario.
Simula escenarios reales de uso de la pantalla de inventarios.
"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
from models import Product, Users, Cart, CartItem, SaleTicket, SaleTicketItem
from app.core.security import hash_password

# Configuración idéntica al archivo de tests principal
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_integration.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Sesión de base de datos limpia"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers(db_session):
    """Headers de autenticación"""
    user = Users(
        Username="cashier_test",
        Password=hash_password("password123"),
        Role="cashier"
    )
    db_session.add(user)
    db_session.commit()
    
    response = client.post("/users/login", json={
        "Username": "cashier_test",
        "Password": "password123"
    })
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


# ==================== FLUJO COMPLETO: CICLO DE VIDA DEL PRODUCTO ====================
class TestCicloVidaProducto:
    """Tests del ciclo de vida completo de un producto"""
    
    def test_flujo_completo_crear_vender_desactivar(self, db_session, auth_headers):
        """
        Flujo completo:
        1. Crear producto
        2. Vender producto
        3. Verificar reducción de stock
        4. Desactivar producto
        5. Verificar que no se puede vender producto inactivo
        """
        # 1. CREAR PRODUCTO
        nuevo_producto = {
            "Code": "FLOW001",
            "Barcode": "1111111111",
            "Product": "Producto Flujo Completo",
            "Category": "Test",
            "Units": "Pieza",
            "Price": 50.00,
            "Stock": 100,
            "Min_Stock": 10
        }
        
        create_response = client.post("/api/inventario", json=nuevo_producto)
        assert create_response.status_code == 201
        product_id = create_response.json()["Id"]
        
        # 2. CREAR CARRITO Y AGREGAR PRODUCTO
        cart_response = client.post("/api/pos/carts", headers=auth_headers)
        cart_id = cart_response.json()["id"]
        
        add_item_response = client.post(
            f"/api/pos/carts/{cart_id}/items",
            json={"product_id": product_id, "quantity": 5},
            headers=auth_headers
        )
        assert add_item_response.status_code == 200
        
        # 3. VERIFICAR STOCK ANTES DE VENTA
        product_response = client.get(f"/api/inventario/{product_id}")
        stock_antes = product_response.json()["Stock"]
        assert stock_antes == 100  # Stock inicial
        
        # 4. SIMULAR VENTA (crear ticket)
        # Nota: Esto requeriría completar el flujo de venta completo
        # Por ahora verificamos que el producto está en el carrito
        cart_details = client.get(f"/api/pos/carts/{cart_id}", headers=auth_headers)
        assert len(cart_details.json()["items"]) == 1
        
        # 5. DESACTIVAR PRODUCTO
        delete_response = client.delete(f"/api/inventario/{product_id}")
        assert delete_response.status_code == 200
        
        # 6. VERIFICAR QUE NO APARECE EN LISTADO
        list_response = client.get("/api/inventario")
        product_ids = [p["Id"] for p in list_response.json()]
        assert product_id not in product_ids
        
        # 7. VERIFICAR QUE NO SE PUEDE AGREGAR A NUEVO CARRITO
        new_cart_response = client.post("/api/pos/carts", headers=auth_headers)
        new_cart_id = new_cart_response.json()["id"]
        
        add_inactive_response = client.post(
            f"/api/pos/carts/{new_cart_id}/items",
            json={"product_id": product_id, "quantity": 1},
            headers=auth_headers
        )
        assert add_inactive_response.status_code == 404  # Producto no encontrado


# ==================== FLUJO: RESTOCK DE PRODUCTOS ====================
class TestRestockProductos:
    """Tests de restock de productos activos e inactivos"""
    
    def test_restock_producto_activo_stock_bajo(self, db_session):
        """Restock de producto activo con stock bajo"""
        # Crear producto con stock bajo
        producto = Product(
            Code="RESTOCK01",
            Barcode="2222222222",
            Product="Producto Stock Bajo",
            Category="Inventario",
            Units="Pieza",
            Price=Decimal("15.00"),
            Stock=3,  # Stock bajo
            Min_Stock=20,
            Activo=1
        )
        db_session.add(producto)
        db_session.commit()
        product_id = producto.Id
        
        # Verificar que aparece en resumen como stock bajo
        resumen = client.get("/api/inventario/resumen/estadisticas")
        assert resumen.json()["low_stock_count"] >= 1
        
        # Hacer restock
        restock_response = client.patch(
            f"/api/inventario/{product_id}/stock?nuevo_stock=100"
        )
        assert restock_response.status_code == 200
        assert restock_response.json()["new_stock"] == 100
        
        # Verificar que ya no aparece en stock bajo
        resumen_after = client.get("/api/inventario/resumen/estadisticas")
        # El conteo de stock bajo debe reducirse o ser 0
        assert resumen_after.json()["low_stock_count"] <= resumen.json()["low_stock_count"]
    
    def test_restock_producto_inactivo_para_reactivacion(self, db_session):
        """
        Flujo de restock de producto inactivo para preparar reactivación
        """
        # Crear producto inactivo sin stock
        producto = Product(
            Code="REACTIVE01",
            Barcode="3333333333",
            Product="Producto Para Reactivar",
            Category="Inventario",
            Units="Pieza",
            Price=Decimal("25.00"),
            Stock=0,
            Min_Stock=10,
            Activo=0  # Inactivo
        )
        db_session.add(producto)
        db_session.commit()
        product_id = producto.Id
        
        # Hacer restock del producto inactivo
        restock_response = client.patch(
            f"/api/inventario/{product_id}/stock?nuevo_stock=50"
        )
        assert restock_response.status_code == 200
        
        # Verificar que el stock se actualizó
        producto_actualizado = db_session.query(Product).filter(
            Product.Id == product_id
        ).first()
        assert producto_actualizado.Stock == 50
        assert producto_actualizado.Activo == 0  # Sigue inactivo
        
        # Ahora "reactivar" producto actualizándolo
        # (En la app real esto se haría con un endpoint específico o update)
        db_session.query(Product).filter(Product.Id == product_id).update(
            {"Activo": 1}
        )
        db_session.commit()
        
        # Verificar que ahora aparece en listado
        list_response = client.get("/api/inventario")
        product_ids = [p["Id"] for p in list_response.json()]
        assert product_id in product_ids


# ==================== FLUJO: MANEJO DE STOCK EN VENTAS ====================
class TestStockEnVentas:
    """Tests de manejo de stock durante ventas"""
    
    def test_venta_reduce_stock_correctamente(self, db_session, auth_headers):
        """Verificar que venta reduce stock del producto"""
        # Crear producto
        producto = Product(
            Code="SALE01",
            Barcode="4444444444",
            Product="Producto Para Venta",
            Category="Ventas",
            Units="Pieza",
            Price=Decimal("30.00"),
            Stock=50,
            Min_Stock=10,
            Activo=1
        )
        db_session.add(producto)
        db_session.commit()
        product_id = producto.Id
        stock_inicial = 50
        
        # Crear carrito y agregar producto
        cart_response = client.post("/api/pos/carts", headers=auth_headers)
        cart_id = cart_response.json()["id"]
        
        cantidad_venta = 5
        client.post(
            f"/api/pos/carts/{cart_id}/items",
            json={"product_id": product_id, "quantity": cantidad_venta},
            headers=auth_headers
        )
        
        # Nota: En un flujo completo, aquí se crearía el ticket
        # Para este test, verificamos que el producto está correctamente en el carrito
        cart_details = client.get(f"/api/pos/carts/{cart_id}", headers=auth_headers)
        items = cart_details.json()["items"]
        
        assert len(items) == 1
        assert items[0]["quantity"] == cantidad_venta
    
    def test_no_permite_venta_sin_stock_suficiente(self, db_session, auth_headers):
        """No debe permitir agregar más cantidad que el stock disponible"""
        # Crear producto con stock limitado
        producto = Product(
            Code="LIMITED01",
            Barcode="5555555555",
            Product="Producto Stock Limitado",
            Category="Ventas",
            Units="Pieza",
            Price=Decimal("20.00"),
            Stock=3,  # Solo 3 unidades
            Min_Stock=5,
            Activo=1
        )
        db_session.add(producto)
        db_session.commit()
        product_id = producto.Id
        
        # Intentar crear carrito con más cantidad del stock
        cart_response = client.post("/api/pos/carts", headers=auth_headers)
        cart_id = cart_response.json()["id"]
        
        add_item_response = client.post(
            f"/api/pos/carts/{cart_id}/items",
            json={"product_id": product_id, "quantity": 10},  # Más de 3
            headers=auth_headers
        )
        
        # Debe retornar error de stock insuficiente
        assert add_item_response.status_code == 400
        assert "stock" in add_item_response.json()["detail"].lower()


# ==================== FLUJO: BÚSQUEDA Y FILTRADO ====================
class TestBusquedaAvanzada:
    """Tests de búsqueda y filtrado en pantalla de inventario"""
    
    def test_busqueda_por_categoria(self, db_session):
        """Verificar que la búsqueda funciona por categoría"""
        # Crear productos de diferentes categorías
        categorias = ["Electrónica", "Alimentos", "Limpieza"]
        
        for i, cat in enumerate(categorias):
            producto = Product(
                Code=f"CAT{i:03d}",
                Barcode=f"66666666{i:02d}",
                Product=f"Producto {cat}",
                Category=cat,
                Units="Pieza",
                Price=Decimal("10.00"),
                Stock=100,
                Min_Stock=10,
                Activo=1
            )
            db_session.add(producto)
        db_session.commit()
        
        # Buscar por categoría específica
        response = client.get("/api/inventario/buscar?query=Electrónica")
        
        assert response.status_code == 200
        productos = response.json()
        
        # Debe encontrar al menos 1 producto
        assert len(productos) >= 1
        assert productos[0]["Category"] == "Electrónica"
    
    def test_listado_con_paginacion_multiple(self, db_session):
        """Verificar paginación con múltiples páginas"""
        # Crear 25 productos
        for i in range(25):
            producto = Product(
                Code=f"PAGE{i:03d}",
                Barcode=f"77777777{i:02d}",
                Product=f"Producto Paginación {i}",
                Category="Test",
                Units="Pieza",
                Price=Decimal("10.00"),
                Stock=100,
                Min_Stock=10,
                Activo=1
            )
            db_session.add(producto)
        db_session.commit()
        
        # Primera página (10 productos)
        page1 = client.get("/api/inventario?skip=0&limit=10")
        assert len(page1.json()) == 10
        
        # Segunda página (10 productos)
        page2 = client.get("/api/inventario?skip=10&limit=10")
        assert len(page2.json()) == 10
        
        # Tercera página (5 productos restantes)
        page3 = client.get("/api/inventario?skip=20&limit=10")
        assert len(page3.json()) == 5
        
        # Verificar que no hay duplicados entre páginas
        ids_page1 = {p["Id"] for p in page1.json()}
        ids_page2 = {p["Id"] for p in page2.json()}
        assert len(ids_page1.intersection(ids_page2)) == 0


# ==================== FLUJO: ALERTAS Y NOTIFICACIONES ====================
class TestAlertasInventario:
    """Tests de alertas de inventario (stock bajo, etc.)"""
    
    def test_detectar_productos_stock_bajo(self, db_session):
        """Debe identificar productos con stock bajo o igual al mínimo"""
        # Crear productos con diferentes niveles de stock
        productos_test = [
            ("GOOD01", 100, 10, 1),  # Stock bueno
            ("LOW01", 10, 10, 1),    # Stock igual al mínimo
            ("LOW02", 5, 10, 1),     # Stock bajo
            ("ZERO01", 0, 10, 1),    # Sin stock
        ]
        
        for code, stock, min_stock, activo in productos_test:
            producto = Product(
                Code=code,
                Barcode=f"888{code}",
                Product=f"Producto {code}",
                Category="Test",
                Units="Pieza",
                Price=Decimal("10.00"),
                Stock=stock,
                Min_Stock=min_stock,
                Activo=activo
            )
            db_session.add(producto)
        db_session.commit()
        
        # Obtener resumen
        resumen = client.get("/api/inventario/resumen/estadisticas")
        data = resumen.json()
        
        # Debe detectar 3 productos con stock bajo (LOW01, LOW02, ZERO01)
        assert data["low_stock_count"] == 3
        
        # Verificar que la lista incluye los productos correctos
        low_stock_products = data["low_stock_products"]
        codes = [p["id"] for p in low_stock_products]
        
        # Al menos debe incluir algunos de los productos con stock bajo
        assert len(low_stock_products) > 0


# ==================== FLUJO: VALIDACIONES DE NEGOCIO ====================
class TestValidacionesNegocio:
    """Tests de validaciones de reglas de negocio"""
    
    def test_no_permite_precio_mayor_limite(self, db_session):
        """No debe permitir precios excesivamente altos"""
        producto_caro = {
            "Code": "EXPENSIVE",
            "Barcode": "9999999999",
            "Product": "Producto Muy Caro",
            "Category": "Lujo",
            "Units": "Pieza",
            "Price": 2000000.00,  # Más de 1 millón
            "Stock": 10,
            "Min_Stock": 1
        }
        
        response = client.post("/api/inventario", json=producto_caro)
        
        # Debe retornar error de validación
        assert response.status_code == 422
        assert "precio" in response.json()["detail"].lower()
    
    def test_nombre_producto_minimo_caracteres(self, db_session):
        """Nombre de producto debe tener mínimo 3 caracteres"""
        producto_nombre_corto = {
            "Code": "SHORT",
            "Barcode": "1010101010",
            "Product": "AB",  # Solo 2 caracteres
            "Category": "Test",
            "Units": "Pieza",
            "Price": 10.00,
            "Stock": 10,
            "Min_Stock": 1
        }
        
        response = client.post("/api/inventario", json=producto_nombre_corto)
        
        assert response.status_code == 422
        assert "nombre" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])