# tests/test_product_service.py
"""
Tests para ProductService.
"""

import pytest
from decimal import Decimal
from app.services.product_service import ProductService
from app.core.exceptions import (
    NotFoundError,
    DuplicateError,
    ValidationError
)
from schemas import ProductoCreate, ProductoUpdate


class TestProductService:
    """Tests para ProductService"""
    
    def test_get_all_products(self, db_session, sample_products):
        """Test: Obtener todos los productos"""
        service = ProductService(db_session)
        products = service.get_all_products()
        
        assert len(products) == 5
        assert all(p.Activo == 1 for p in products)
    
    def test_get_product_by_id(self, db_session, sample_products):
        """Test: Obtener producto por ID"""
        service = ProductService(db_session)
        product = service.get_product_by_id(sample_products[0].Id)
        
        assert product.Product == "Coca Cola 600ml"
        assert product.Price == 15.00
    
    def test_get_product_by_id_not_found(self, db_session):
        """Test: Producto no encontrado lanza excepción"""
        service = ProductService(db_session)
        
        with pytest.raises(NotFoundError) as exc_info:
            service.get_product_by_id(9999)
        
        assert "Producto con ID 9999 no encontrado" in str(exc_info.value.message)
    
    def test_search_products(self, db_session, sample_products):
        """Test: Buscar productos por nombre"""
        service = ProductService(db_session)
        results = service.search_products("coca")
        
        assert len(results) == 1
        assert results[0].Product == "Coca Cola 600ml"
    
    def test_search_products_by_barcode(self, db_session, sample_products):
        """Test: Buscar por código de barras"""
        service = ProductService(db_session)
        results = service.search_products("7501234567891")
        
        assert len(results) == 1
        assert results[0].Product == "Sabritas Original"
    
    def test_search_products_empty_query(self, db_session):
        """Test: Búsqueda con query vacío lanza error"""
        service = ProductService(db_session)
        
        with pytest.raises(ValidationError):
            service.search_products("")
    
    def test_create_product(self, db_session):
        """Test: Crear nuevo producto"""
        service = ProductService(db_session)
        
        producto_data = ProductoCreate(
            code="999",
            barcode="7509999999999",
            product="Producto Nuevo",
            category="Test",
            units="Pieza",
            price=Decimal("50.00"),
            stock=100,
            min_stock=10
        )
        
        producto = service.create_product(producto_data)
        
        assert producto.Id is not None
        assert producto.Product == "Producto Nuevo"
        assert producto.Price == 50.00
        assert producto.Activo == 1
    
    def test_create_product_duplicate_code(self, db_session, sample_products):
        """Test: Crear producto con código duplicado"""
        service = ProductService(db_session)
        
        producto_data = ProductoCreate(
            code="001",  # Código duplicado
            barcode="7509999999998",
            product="Producto Duplicado",
            category="Test",
            units="Pieza",
            price=Decimal("50.00"),
            stock=100,
            min_stock=10
        )
        
        with pytest.raises(DuplicateError):
            service.create_product(producto_data)
    
    def test_create_product_duplicate_barcode(self, db_session, sample_products):
        """Test: Crear producto con barcode duplicado"""
        service = ProductService(db_session)
        
        producto_data = ProductoCreate(
            code="998",
            barcode="7501234567890",  # Barcode duplicado
            product="Producto Duplicado",
            category="Test",
            units="Pieza",
            price=Decimal("50.00"),
            stock=100,
            min_stock=10
        )
        
        with pytest.raises(DuplicateError):
            service.create_product(producto_data)
    
    def test_create_product_negative_price(self, db_session):
        """Test: Crear producto con precio negativo"""
        from pydantic import ValidationError as PydanticValidationError
        
        # Pydantic captura el error antes del service
        with pytest.raises(PydanticValidationError):
            producto_data = ProductoCreate(
                code="997",
                barcode="7509999999997",
                product="Producto Invalido",
                category="Test",
                units="Pieza",
                price=Decimal("-10.00"),  # Precio negativo
                stock=100,
                min_stock=10
            )
    
    def test_update_product(self, db_session, sample_products):
        """Test: Actualizar producto"""
        service = ProductService(db_session)
        
        update_data = ProductoUpdate(
            product="Coca Cola 600ml ACTUALIZADA",
            stock=150
            # Activo es opcional ahora
        )
        
        producto = service.update_product(sample_products[0].Id, update_data)
        
        assert producto.Product == "Coca Cola 600ml ACTUALIZADA"
        assert producto.Stock == 150
    
    def test_update_stock(self, db_session, sample_products):
        """Test: Actualizar stock"""
        service = ProductService(db_session)
        
        producto = service.update_stock(sample_products[0].Id, 200)
        
        assert producto.Stock == 200
    
    def test_update_stock_negative(self, db_session, sample_products):
        """Test: Actualizar stock con valor negativo"""
        service = ProductService(db_session)
        
        with pytest.raises(ValidationError):
            service.update_stock(sample_products[0].Id, -10)
    
    def test_reduce_stock(self, db_session, sample_products):
        """Test: Reducir stock"""
        service = ProductService(db_session)
        
        initial_stock = sample_products[0].Stock
        producto = service.reduce_stock(sample_products[0].Id, 10)
        
        assert producto.Stock == initial_stock - 10
    
    def test_reduce_stock_insufficient(self, db_session, sample_products):
        """Test: Reducir stock sin suficiente disponible"""
        service = ProductService(db_session)
        
        with pytest.raises(Exception):  # InvalidOperationError
            service.reduce_stock(sample_products[0].Id, 1000)
    
    def test_delete_product(self, db_session, sample_products):
        """Test: Eliminar (desactivar) producto"""
        service = ProductService(db_session)
        
        producto = service.delete_product(sample_products[0].Id)
        
        assert producto.Activo == 0
    
    def test_get_inventory_summary(self, db_session, sample_products):
        """Test: Obtener resumen de inventario"""
        service = ProductService(db_session)
        
        summary = service.get_inventory_summary()
        
        assert summary["total_products"] == 5
        assert summary["low_stock_count"] == 1  # Huevos tiene stock bajo
        assert summary["normal_stock_count"] == 4
        assert summary["categories_count"] > 0
        assert len(summary["low_stock_products"]) == 1


class TestProductServiceIntegration:
    """Tests de integración con endpoints"""
    
    def test_create_product_endpoint(self, client, auth_headers):
        """Test: Endpoint crear producto"""
        response = client.post(
            "/api/inventario",
            json={
                "Code": "TEST001",
                "Barcode": "7509999999999",
                "Product": "Producto Test",
                "Category": "Test",
                "Units": "Pieza",
                "Price": 100.00,
                "Stock": 50,
                "Min_Stock": 10
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["Product"] == "Producto Test"
        assert float(data["Price"]) == 100.00  # Convertir a float
    
    def test_get_products_endpoint(self, client, auth_headers, sample_products):
        """Test: Endpoint listar productos"""
        response = client.get(
            "/api/inventario",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
    
    def test_search_products_endpoint(self, client, auth_headers, sample_products):
        """Test: Endpoint buscar productos"""
        response = client.get(
            "/api/inventario/buscar?query=coca",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any("Coca" in p["Product"] for p in data)
    
    def test_update_product_endpoint(self, client, auth_headers, sample_products):
        """Test: Endpoint actualizar producto"""
        product_id = sample_products[0].Id
        
        response = client.patch(
            f"/api/inventario/{product_id}",
            json={"Product": "Coca Cola ACTUALIZADA"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["Product"] == "Coca Cola ACTUALIZADA"
    
    def test_delete_product_endpoint(self, client, auth_headers, sample_products):
        """Test: Endpoint eliminar producto"""
        product_id = sample_products[0].Id
        
        response = client.delete(
            f"/api/inventario/{product_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "inactivo" in data["message"].lower()
    
    def test_inventory_summary_endpoint(self, client, auth_headers, sample_products):
        """Test: Endpoint resumen de inventario"""
        response = client.get(
            "/api/inventario/resumen/estadisticas",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "total_products" in data
        assert "low_stock_count" in data
        assert data["total_products"] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])