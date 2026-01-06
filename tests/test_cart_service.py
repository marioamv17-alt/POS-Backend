"""
Tests para CartService.
"""

import pytest
from decimal import Decimal
from app.services.cart_service import CartService
from app.core.exceptions import (
    NotFoundError,
    InvalidOperationError,
    InsufficientStockError
)
from schemas import AddItemRequest


class TestCartService:
    """Tests para CartService"""
    
    def test_create_cart(self, db_session, sample_user):
        """Test: Crear carrito"""
        service = CartService(db_session)
        cart = service.create_cart(user_id=sample_user.ID)
        
        assert cart.id is not None
        assert cart.user_id == sample_user.ID
        assert cart.status == "open"
    
    def test_get_cart(self, db_session, sample_cart):
        """Test: Obtener carrito"""
        service = CartService(db_session)
        cart = service.get_cart(sample_cart.id)
        
        assert cart.id == sample_cart.id
        assert len(cart.items) == 2
    
    def test_get_cart_not_found(self, db_session):
        """Test: Carrito no encontrado"""
        service = CartService(db_session)
        
        with pytest.raises(NotFoundError):
            service.get_cart(9999)
    
    def test_get_cart_with_total(self, db_session, sample_cart):
        """Test: Obtener carrito con total"""
        service = CartService(db_session)
        result = service.get_cart_with_total(sample_cart.id)
        
        assert "cart" in result
        assert "total" in result
        assert "items_count" in result
        assert result["items_count"] == 2
        assert result["total"] > 0
    
    def test_add_item_by_product_id(self, db_session, sample_cart, sample_products):
        """Test: Agregar item por product_id"""
        service = CartService(db_session)
        
        request = AddItemRequest(
            product_id=sample_products[2].Id,
            quantity=Decimal("1.0")
        )
        
        item = service.add_item_to_cart(sample_cart.id, request)
        
        assert item.product_id == sample_products[2].Id
        assert item.quantity == 1.0
    
    def test_add_item_by_barcode(self, db_session, sample_cart, sample_products):
        """Test: Agregar item por barcode"""
        service = CartService(db_session)
        
        request = AddItemRequest(
            barcode="7501234567892",  # Pan Bimbo
            quantity=Decimal("2.0")
        )
        
        item = service.add_item_to_cart(sample_cart.id, request)
        
        assert item.product_name == "Pan Bimbo Blanco"
        assert item.quantity == 2.0
    
    def test_add_item_duplicate_increases_quantity(self, db_session, sample_cart, sample_products):
        """Test: Agregar item duplicado incrementa cantidad"""
        service = CartService(db_session)
        
        # El carrito ya tiene Coca Cola (sample_products[0])
        request = AddItemRequest(
            product_id=sample_products[0].Id,
            quantity=Decimal("3.0")
        )
        
        item = service.add_item_to_cart(sample_cart.id, request)
        
        # Debe sumar: 2 (inicial) + 3 (nuevo) = 5
        assert item.quantity == 5.0
    
    def test_add_item_insufficient_stock(self, db_session, sample_cart, sample_products):
        """Test: Agregar item sin stock suficiente"""
        service = CartService(db_session)
        
        request = AddItemRequest(
            product_id=sample_products[0].Id,
            quantity=Decimal("200.0")  # Más del stock disponible
        )
        
        with pytest.raises(InsufficientStockError):
            service.add_item_to_cart(sample_cart.id, request)
    
    def test_add_item_to_closed_cart(self, db_session, sample_cart, sample_products):
        """Test: No se puede agregar items a carrito cerrado"""
        service = CartService(db_session)
        
        # Cerrar carrito
        sample_cart.status = "completed"
        db_session.commit()
        
        request = AddItemRequest(
            product_id=sample_products[2].Id,
            quantity=Decimal("1.0")
        )
        
        with pytest.raises(InvalidOperationError):
            service.add_item_to_cart(sample_cart.id, request)
    
    def test_update_item_quantity(self, db_session, sample_cart):
        """Test: Actualizar cantidad de item"""
        service = CartService(db_session)
        
        item_id = sample_cart.items[0].id
        cart_id = sample_cart.id
        
        updated_item = service.update_item_quantity(cart_id, item_id, Decimal("5.0"))
        
        assert updated_item.quantity == 5.0
        assert updated_item.subtotal == updated_item.price * Decimal("5.0")
    
    def test_update_item_quantity_negative(self, db_session, sample_cart):
        """Test: No se puede actualizar con cantidad negativa"""
        service = CartService(db_session)
        
        item_id = sample_cart.items[0].id
        cart_id = sample_cart.id
        
        with pytest.raises(Exception):  # ValidationError
            service.update_item_quantity(cart_id, item_id, Decimal("-1.0"))
    
    def test_remove_item_from_cart(self, db_session, sample_cart):
        """Test: Eliminar item del carrito"""
        service = CartService(db_session)
        
        item_id = sample_cart.items[0].id
        cart_id = sample_cart.id
        
        service.remove_item_from_cart(cart_id, item_id)
        
        # Verificar que el item fue eliminado
        cart = service.get_cart(cart_id)
        assert len(cart.items) == 1
    
    def test_clear_cart(self, db_session, sample_cart):
        """Test: Vaciar carrito"""
        service = CartService(db_session)
        
        deleted_count = service.clear_cart(sample_cart.id)
        
        assert deleted_count == 2
        
        cart = service.get_cart(sample_cart.id)
        assert len(cart.items) == 0
    
    def test_change_cart_status(self, db_session, sample_cart):
        """Test: Cambiar estado del carrito"""
        service = CartService(db_session)
        
        cart = service.change_cart_status(sample_cart.id, "completed")
        
        assert cart.status == "completed"
        assert cart.completed_at is not None
    
    def test_change_cart_status_invalid(self, db_session, sample_cart):
        """Test: Estado inválido lanza error"""
        service = CartService(db_session)
        
        with pytest.raises(Exception):  # ValidationError
            service.change_cart_status(sample_cart.id, "invalid_status")


class TestCartServiceIntegration:
    """Tests de integración con endpoints"""
    
    def test_create_cart_endpoint(self, client, auth_headers):
        """Test: Endpoint crear carrito"""
        response = client.post(
            "/api/pos/carts",
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "open"
        assert data["total"] == '0.0'
    
    def test_add_item_endpoint(self, client, auth_headers, sample_cart, sample_products):
        """Test: Endpoint agregar item"""
        response = client.post(
            f"/api/pos/carts/{sample_cart.id}/items",
            json={
                "product_id": sample_products[2].Id,
                "quantity": 2
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["product_name"] == "Pan Bimbo Blanco"
        assert data["quantity"] == '2.0000'
    
    def test_get_cart_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint obtener carrito"""
        response = client.get(
            f"/api/pos/carts/{sample_cart.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_cart.id
        assert "total" in data
        assert len(data["items"]) == 2
    
    def test_update_item_quantity_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint actualizar cantidad"""
        item_id = sample_cart.items[0].id
        
        response = client.patch(
            f"/api/pos/carts/{sample_cart.id}/items/{item_id}?quantity=5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_quantity"] == 5.0
    
    def test_remove_item_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint eliminar item"""
        item_id = sample_cart.items[0].id
        
        response = client.delete(
            f"/api/pos/carts/{sample_cart.id}/items/{item_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_clear_cart_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint vaciar carrito"""
        response = client.delete(
            f"/api/pos/carts/{sample_cart.id}/items",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["deleted_count"] == 2
    
    def test_change_status_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint cambiar estado"""
        response = client.patch(
            f"/api/pos/carts/{sample_cart.id}/status?status=cancelled",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "cancelled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])