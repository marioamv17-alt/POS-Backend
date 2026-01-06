"""
Configuración global para tests con pytest.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from decimal import Decimal

from database import Base, get_db
from main import app
from models import Users, Product, Cart, CartItem
from app.core.security import hash_password, create_access_token

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Crea una sesión de base de datos para cada test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Cliente de prueba de FastAPI."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(db_session):
    """Crea un usuario de prueba."""
    user = Users(
        Username="testuser",
        Password=hash_password("testpass123"),
        Role="cashier"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """Crea un usuario admin de prueba."""
    user = Users(
        Username="admin",
        Password=hash_password("admin123"),
        Role="admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_products(db_session):
    """Crea productos de prueba."""
    products = [
        Product(
            Code="001",
            Barcode="7501234567890",
            Product="Coca Cola 600ml",
            Category="Bebidas",
            Units="Pieza",
            Price=Decimal("15.00"),
            Stock=100,
            Min_Stock=10,
            Activo=1
        ),
        Product(
            Code="002",
            Barcode="7501234567891",
            Product="Sabritas Original",
            Category="Snacks",
            Units="Pieza",
            Price=Decimal("18.50"),
            Stock=50,
            Min_Stock=5,
            Activo=1
        ),
        Product(
            Code="003",
            Barcode="7501234567892",
            Product="Pan Bimbo Blanco",
            Category="Panadería",
            Units="Pieza",
            Price=Decimal("35.00"),
            Stock=30,
            Min_Stock=5,
            Activo=1
        ),
        Product(
            Code="004",
            Barcode="7501234567893",
            Product="Leche Lala 1L",
            Category="Lácteos",
            Units="Litro",
            Price=Decimal("25.00"),
            Stock=20,
            Min_Stock=5,
            Activo=1
        ),
        Product(
            Code="005",
            Barcode="7501234567894",
            Product="Huevos San Juan 12pz",
            Category="Abarrotes",
            Units="Paquete",
            Price=Decimal("45.00"),
            Stock=5,
            Min_Stock=10,
            Activo=1
        )
    ]
    
    for product in products:
        db_session.add(product)
    
    db_session.commit()
    
    for product in products:
        db_session.refresh(product)
    
    return products


@pytest.fixture
def sample_cart(db_session, sample_user, sample_products):
    """Crea un carrito con items de prueba."""
    cart = Cart(
        user_id=sample_user.ID,
        status="open"
    )
    db_session.add(cart)
    db_session.flush()
    
    items = [
        CartItem(
            cart_id=cart.id,
            product_id=sample_products[0].Id,
            product_name=sample_products[0].Product,
            price=sample_products[0].Price,
            quantity=Decimal("2"),
            subtotal=sample_products[0].Price * Decimal("2")
        ),
        CartItem(
            cart_id=cart.id,
            product_id=sample_products[1].Id,
            product_name=sample_products[1].Product,
            price=sample_products[1].Price,
            quantity=Decimal("3"),
            subtotal=sample_products[1].Price * Decimal("3")
        )
    ]
    
    for item in items:
        db_session.add(item)
    
    db_session.commit()
    
    for item in items:
        db_session.refresh(item)
    
    db_session.refresh(cart)
    return cart


@pytest.fixture
def auth_headers(client, sample_user):
    """Headers de autenticación con token JWT válido."""
    response = client.post(
        "/users/login",
        json={
            "Username": "testuser",
            "Password": "testpass123"
        }
    )
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client, admin_user):
    """Headers de autenticación con token JWT de admin."""
    response = client.post(
        "/users/login",
        json={
            "Username": "admin",
            "Password": "admin123"
        }
    )
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def disable_ratelimit():
    """Desactiva el Rate Limiting globalmente para todos los tests"""
    app.state.limiter_enabled = False # Si usas slowapi configurado así
    # O la forma más segura para slowapi:
    from slowapi.extension import Limiter
    # Forzar que el limiter siempre permita la petición
    yield

@pytest.fixture
def auth_headers(sample_user):
    """Genera headers de auth directamente sin pasar por el endpoint de login"""
    access_token = create_access_token(data={"sub": sample_user.Username})
    return {"Authorization": f"Bearer {access_token}"}