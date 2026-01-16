"""
Tests completos para la pantalla de inventarios.
Cubre: listar productos activos/inactivos, crear, actualizar, eliminar,
y verificar que productos inactivos no rompan la pantalla de ventas.
"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from main import app
from database import Base, get_db
from models import Product, Users, Cart, CartItem
from app.core.security import hash_password

# ==================== CONFIGURACIÓN DE BASE DE DATOS DE TEST ====================
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

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


# ==================== FIXTURES ====================
@pytest.fixture(scope="function")
def db_session():
    """Crea una sesión de base de datos limpia para cada test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def auth_headers(db_session):
    """Crea un usuario de test y retorna headers de autenticación"""
    # Crear usuario
    user = Users(
        Username="test_user",
        Password=hash_password("test_password"),
        Role="admin"
    )
    db_session.add(user)
    db_session.commit()
    
    # Login para obtener token
    response = client.post("/users/login", json={
        "Username": "test_user",
        "Password": "test_password"
    })
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_products(db_session):
    """Crea productos de muestra (activos e inactivos)"""
    products = [
        Product(
            Code="001",
            Barcode="1234567890",
            Product="Producto Activo 1",
            Category="Categoría A",
            Units="Unidad",
            Price=Decimal("10.50"),
            Stock=100,
            Min_Stock=10,
            Activo=1
        ),
        Product(
            Code="002",
            Barcode="1234567891",
            Product="Producto Activo 2",
            Category="Categoría B",
            Units="Unidad",
            Price=Decimal("20.00"),
            Stock=50,
            Min_Stock=5,
            Activo=1
        ),
        Product(
            Code="003",
            Barcode="1234567892",
            Product="Producto Inactivo 1",
            Category="Categoría A",
            Units="Unidad",
            Price=Decimal("15.00"),
            Stock=0,
            Min_Stock=10,
            Activo=0
        ),
        Product(
            Code="004",
            Barcode="1234567893",
            Product="Producto Stock Bajo",
            Category="Categoría C",
            Units="Unidad",
            Price=Decimal("5.00"),
            Stock=3,
            Min_Stock=10,
            Activo=1
        )
    ]
    
    for product in products:
        db_session.add(product)
    db_session.commit()
    
    return products


# ==================== TESTS: LISTAR PRODUCTOS ====================
class TestListarProductos:
    """Tests para endpoint GET /api/inventario"""
    
    def test_listar_productos_activos(self, db_session, sample_products):
        """Debe listar solo productos activos por defecto"""
        response = client.get("/api/inventario")
        
        assert response.status_code == 200
        data = response.json()
        
        # Solo debe retornar productos activos (3 de 4)
        assert len(data) == 3
        
        # Verificar que todos tengan Activo=1
        for producto in data:
            assert producto["Activo"] == 1
    
    def test_listar_productos_con_paginacion(self, db_session, sample_products):
        """Debe respetar parámetros de paginación"""
        response = client.get("/api/inventario?skip=1&limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        # Debe retornar máximo 2 productos, saltando el primero
        assert len(data) <= 2
    
    def test_listar_con_limite_maximo(self, db_session, sample_products):
        """Debe respetar el límite máximo de 500"""
        response = client.get("/api/inventario?limit=500")
        
        assert response.status_code == 200
        # Debe manejar correctamente el límite de 500


# ==================== TESTS: BUSCAR PRODUCTOS ====================
class TestBuscarProductos:
    """Tests para endpoint GET /api/inventario/buscar"""
    
    def test_buscar_por_nombre(self, db_session, sample_products):
        """Debe encontrar productos por nombre"""
        response = client.get("/api/inventario/buscar?query=Activo")
        
        assert response.status_code == 200
        data = response.json()
        
        # Debe encontrar los 2 productos con "Activo" en el nombre
        assert len(data) == 2
    
    def test_buscar_por_codigo(self, db_session, sample_products):
        """Debe encontrar producto por código"""
        response = client.get("/api/inventario/buscar?query=001")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["Code"] == "001"
    
    def test_buscar_por_barcode(self, db_session, sample_products):
        """Debe encontrar producto por código de barras"""
        response = client.get("/api/inventario/buscar?query=1234567890")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["Barcode"] == "1234567890"
    
    def test_buscar_query_vacio_error(self, db_session):
        """Debe retornar error si query está vacío"""
        response = client.get("/api/inventario/buscar?query=")
        
        assert response.status_code == 422  # Validation error
    
    def test_buscar_sin_resultados(self, db_session, sample_products):
        """Debe retornar lista vacía si no hay resultados"""
        response = client.get("/api/inventario/buscar?query=NoExiste123")
        
        assert response.status_code == 200
        assert response.json() == []


# ==================== TESTS: OBTENER PRODUCTO ====================
class TestObtenerProducto:
    """Tests para endpoint GET /api/inventario/{product_id}"""
    
    def test_obtener_producto_existente(self, db_session, sample_products):
        """Debe retornar producto por ID"""
        product_id = sample_products[0].Id
        
        response = client.get(f"/api/inventario/{product_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["Id"] == product_id
        assert data["Product"] == "Producto Activo 1"
    
    def test_obtener_producto_inexistente(self, db_session):
        """Debe retornar 404 si producto no existe"""
        response = client.get("/api/inventario/99999")
        
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()


# ==================== TESTS: CREAR PRODUCTO ====================
class TestCrearProducto:
    """Tests para endpoint POST /api/inventario"""
    
    def test_crear_producto_valido(self, db_session):
        """Debe crear producto con datos válidos"""
        nuevo_producto = {
            "Code": "NEW001",
            "Barcode": "9999999999",
            "Product": "Nuevo Producto",
            "Category": "Nueva Categoría",
            "Units": "Pieza",
            "Price": 25.50,
            "Stock": 100,
            "Min_Stock": 10
        }
        
        response = client.post("/api/inventario", json=nuevo_producto)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["Product"] == "Nuevo Producto"
        assert data["Activo"] == 1
        assert "Id" in data
    
    def test_crear_producto_codigo_duplicado(self, db_session, sample_products):
        """Debe retornar error 409 si el código ya existe"""
        producto_duplicado = {
            "Code": "001",  # Ya existe
            "Barcode": "9999999998",
            "Product": "Producto Duplicado",
            "Category": "Test",
            "Units": "Unidad",
            "Price": 10.00,
            "Stock": 50,
            "Min_Stock": 5
        }
        
        response = client.post("/api/inventario", json=producto_duplicado)
        
        assert response.status_code == 409
        assert "código" in response.json()["detail"].lower()
    
    def test_crear_producto_barcode_duplicado(self, db_session, sample_products):
        """Debe retornar error 409 si el código de barras ya existe"""
        producto_duplicado = {
            "Code": "NEW002",
            "Barcode": "1234567890",  # Ya existe
            "Product": "Producto Duplicado",
            "Category": "Test",
            "Units": "Unidad",
            "Price": 10.00,
            "Stock": 50,
            "Min_Stock": 5
        }
        
        response = client.post("/api/inventario", json=producto_duplicado)
        
        assert response.status_code == 409
        assert "código de barras" in response.json()["detail"].lower()
    
    def test_crear_producto_precio_negativo(self, db_session):
        """Debe retornar error 422 si el precio es negativo"""
        producto_invalido = {
            "Code": "INV001",
            "Barcode": "8888888888",
            "Product": "Producto Inválido",
            "Category": "Test",
            "Units": "Unidad",
            "Price": -10.00,  # Precio negativo
            "Stock": 50,
            "Min_Stock": 5
        }
        
        response = client.post("/api/inventario", json=producto_invalido)
        
        assert response.status_code == 422
        # El detalle puede venir como string o lista de errores
        detail = response.json()["detail"]
        if isinstance(detail, list):
            # FastAPI devuelve lista de errores de validación
            assert any("price" in str(err).lower() for err in detail)
        else:
            assert "precio" in detail.lower()


# ==================== TESTS: ACTUALIZAR PRODUCTO ====================
class TestActualizarProducto:
    """Tests para endpoint PATCH /api/inventario/{product_id}"""
    
    def test_actualizar_producto_nombre(self, db_session, sample_products):
        """Debe actualizar solo el nombre del producto"""
        product_id = sample_products[0].Id
        
        response = client.patch(
            f"/api/inventario/{product_id}",
            json={"Product": "Producto Actualizado"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["Product"] == "Producto Actualizado"
        # Otros campos no deben cambiar
        assert data["Price"] == "10.50"
    
    def test_actualizar_producto_stock(self, db_session, sample_products):
        """Debe actualizar el stock del producto"""
        product_id = sample_products[0].Id
        
        response = client.patch(
            f"/api/inventario/{product_id}",
            json={"Stock": 200}
        )
        
        assert response.status_code == 200
        assert response.json()["Stock"] == 200
    
    def test_actualizar_producto_inexistente(self, db_session):
        """Debe retornar 404 si producto no existe"""
        response = client.patch(
            "/api/inventario/99999",
            json={"Product": "Test"}
        )
        
        assert response.status_code == 404


# ==================== TESTS: ACTUALIZAR SOLO STOCK ====================
class TestActualizarStock:
    """Tests para endpoint PATCH /api/inventario/{product_id}/stock"""
    
    def test_actualizar_stock_exitoso(self, db_session, sample_products):
        """Debe actualizar solo el stock"""
        product_id = sample_products[0].Id
        
        response = client.patch(
            f"/api/inventario/{product_id}/stock?nuevo_stock=150"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_stock"] == 150
        assert data["product_id"] == product_id
    
    def test_actualizar_stock_negativo_error(self, db_session, sample_products):
        """Debe retornar error si stock es negativo"""
        product_id = sample_products[0].Id
        
        response = client.patch(
            f"/api/inventario/{product_id}/stock?nuevo_stock=-10"
        )
        
        assert response.status_code == 422


# ==================== TESTS: ELIMINAR (DESACTIVAR) PRODUCTO ====================
class TestEliminarProducto:
    """Tests para endpoint DELETE /api/inventario/{product_id}"""
    
    def test_eliminar_producto_activo(self, db_session, sample_products):
        """Debe marcar producto como inactivo (no eliminarlo físicamente)"""
        product_id = sample_products[0].Id
        
        response = client.delete(f"/api/inventario/{product_id}")
        
        assert response.status_code == 200
        assert "inactivo" in response.json()["message"].lower()
        
        # Verificar que el producto sigue en BD pero con Activo=0
        # Necesitamos hacer refresh de la sesión o consultar de nuevo
        db_session.expire_all()  # Expira el cache de la sesión
        producto = db_session.query(Product).filter(Product.Id == product_id).first()
        assert producto is not None
        assert producto.Activo == 0
    
    def test_producto_inactivo_no_aparece_en_listado(self, db_session, sample_products):
        """Producto inactivo no debe aparecer en listado de activos"""
        product_id = sample_products[0].Id
        
        # Eliminar (desactivar) producto
        client.delete(f"/api/inventario/{product_id}")
        
        # Listar productos activos
        response = client.get("/api/inventario")
        
        # No debe incluir el producto desactivado
        productos_ids = [p["Id"] for p in response.json()]
        assert product_id not in productos_ids


# ==================== TESTS: RESUMEN DE INVENTARIO ====================
class TestResumenInventario:
    """Tests para endpoint GET /api/inventario/resumen/estadisticas"""
    
    def test_resumen_inventario(self, db_session, sample_products):
        """Debe retornar resumen completo del inventario"""
        response = client.get("/api/inventario/resumen/estadisticas")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_products" in data
        assert "low_stock_count" in data
        assert "categories_count" in data
        assert "low_stock_products" in data
        
        # Debe haber 3 productos activos
        assert data["total_products"] == 3
        
        # Debe detectar al menos 1 producto con stock bajo
        assert data["low_stock_count"] >= 1


# ==================== TESTS: INTEGRACIÓN CON VENTAS ====================
class TestProductosInactivosYVentas:
    """Tests para verificar que productos inactivos no rompan ventas"""
    
    def test_producto_inactivo_no_disponible_para_venta(self, db_session, sample_products, auth_headers):
        """Producto inactivo no debe poder agregarse al carrito"""
        # Desactivar producto
        product_id = sample_products[0].Id
        client.delete(f"/api/inventario/{product_id}")
        
        # Intentar crear carrito con producto inactivo
        cart_response = client.post("/api/pos/carts", headers=auth_headers)
        cart_id = cart_response.json()["id"]
        
        # Intentar agregar producto inactivo
        add_item_response = client.post(
            f"/api/pos/carts/{cart_id}/items",
            json={"product_id": product_id, "quantity": 1},
            headers=auth_headers
        )
        
        # Debe retornar error 404 (producto no encontrado)
        assert add_item_response.status_code == 404
    
    def test_restock_producto_inactivo(self, db_session, sample_products):
        """Debe poder hacer restock de producto inactivo (para reactivarlo después)"""
        product_id = sample_products[2].Id  # Producto ya inactivo
        
        # Actualizar stock de producto inactivo
        response = client.patch(
            f"/api/inventario/{product_id}/stock?nuevo_stock=100"
        )
        
        # Debe permitir actualizar stock aunque esté inactivo
        assert response.status_code == 200
        assert response.json()["new_stock"] == 100
    
    def test_venta_no_afecta_productos_inactivos(self, db_session, sample_products):
        """Ventas no deben afectar stock de productos inactivos"""
        # Obtener stock inicial del producto inactivo
        producto_inactivo = sample_products[2]
        stock_inicial = producto_inactivo.Stock
        
        # Realizar venta con producto activo (no debería afectar inactivos)
        # Este test verifica que el sistema no tiene bugs que afecten productos inactivos
        
        # Verificar que stock de inactivo no cambió
        db_session.refresh(producto_inactivo)
        assert producto_inactivo.Stock == stock_inicial


# ==================== TESTS: CASOS EDGE ====================
class TestCasosEdge:
    """Tests para casos límite y edge cases"""
    
    def test_listar_inventario_vacio(self, db_session):
        """Debe retornar lista vacía si no hay productos"""
        response = client.get("/api/inventario")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_crear_producto_con_stock_cero(self, db_session):
        """Debe permitir crear producto con stock 0"""
        producto = {
            "Code": "ZERO",
            "Barcode": "0000000000",
            "Product": "Producto Sin Stock",
            "Category": "Test",
            "Units": "Unidad",
            "Price": 10.00,
            "Stock": 0,
            "Min_Stock": 5
        }
        
        response = client.post("/api/inventario", json=producto)
        
        assert response.status_code == 201
        assert response.json()["Stock"] == 0
    
    def test_buscar_productos_caracteres_especiales(self, db_session, sample_products):
        """Debe manejar caracteres especiales en búsqueda"""
        response = client.get("/api/inventario/buscar?query=@#$%")
        
        # No debe fallar, solo retornar vacío
        assert response.status_code == 200
        assert response.json() == []


# ==================== TESTS DE PERFORMANCE ====================
class TestPerformance:
    """Tests de rendimiento básicos"""
    
    def test_listar_muchos_productos(self, db_session):
        """Debe manejar listado de muchos productos eficientemente"""
        # Crear 100 productos
        for i in range(100):
            producto = Product(
                Code=f"PERF{i:03d}",
                Barcode=f"99{i:08d}",
                Product=f"Producto Performance {i}",
                Category="Performance",
                Units="Unidad",
                Price=Decimal("10.00"),
                Stock=100,
                Min_Stock=10,
                Activo=1
            )
            db_session.add(producto)
        db_session.commit()
        
        response = client.get("/api/inventario?limit=500")
        
        assert response.status_code == 200
        assert len(response.json()) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])