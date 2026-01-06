"""
Tests para TicketService.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from app.services.ticket_service import TicketService
from app.core.exceptions import (
    NotFoundError,
    InvalidOperationError
)
from schemas import CreateTicketRequest


class TestTicketService:
    """Tests para TicketService"""
    
    def test_create_ticket_cash(self, db_session, sample_cart, sample_user):
        """Test: Crear ticket con pago en efectivo"""
        service = TicketService(db_session)
        
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("100.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        ticket = service.create_ticket(request, sample_user.ID)
        
        assert ticket.id is not None
        assert ticket.ticket_number.startswith("TKT-")
        assert ticket.status == "completed"
        assert ticket.payment_method == "cash"
        assert ticket.change_given is not None
        assert len(ticket.items) == 2
    
    def test_create_ticket_card(self, db_session, sample_cart, sample_user):
        """Test: Crear ticket con pago en tarjeta"""
        service = TicketService(db_session)
        
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="card",
            payment_reference="AUTH123456",
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        ticket = service.create_ticket(request, sample_user.ID)
        
        assert ticket.payment_method == "card"
        assert ticket.payment_reference == "AUTH123456"
        assert ticket.change_given is None
    
    def test_create_ticket_insufficient_payment(self, db_session, sample_cart, sample_user):
        """Test: Pago insuficiente en efectivo"""
        service = TicketService(db_session)
        
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("10.00"),  # Muy poco
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        with pytest.raises(InvalidOperationError):
            service.create_ticket(request, sample_user.ID)
    
    def test_create_ticket_empty_cart(self, db_session, sample_user):
        """Test: No se puede crear ticket de carrito vacío"""
        service = TicketService(db_session)
        
        # Crear carrito vacío
        from models import Cart
        cart = Cart(user_id=sample_user.ID, status="open")
        db_session.add(cart)
        db_session.commit()
        
        request = CreateTicketRequest(
            cart_id=cart.id,
            payment_method="cash",
            amount_paid=Decimal("100.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        with pytest.raises(InvalidOperationError):
            service.create_ticket(request, sample_user.ID)
    
    def test_create_ticket_reduces_stock(self, db_session, sample_cart, sample_user, sample_products):
        """Test: Crear ticket reduce el stock"""
        service = TicketService(db_session)
        
        # Guardar stock inicial
        initial_stock_product_0 = sample_products[0].Stock
        initial_stock_product_1 = sample_products[1].Stock
        
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        ticket = service.create_ticket(request, sample_user.ID)
        
        # Verificar reducción de stock
        db_session.refresh(sample_products[0])
        db_session.refresh(sample_products[1])
        
        assert sample_products[0].Stock < initial_stock_product_0
        assert sample_products[1].Stock < initial_stock_product_1
    
    def test_get_ticket(self, db_session, sample_cart, sample_user):
        """Test: Obtener ticket por ID"""
        service = TicketService(db_session)
        
        # Crear ticket primero
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        created_ticket = service.create_ticket(request, sample_user.ID)
        
        # Obtener ticket
        ticket = service.get_ticket(created_ticket.id)
        
        assert ticket.id == created_ticket.id
        assert len(ticket.items) > 0
    
    def test_get_ticket_by_number(self, db_session, sample_cart, sample_user):
        """Test: Obtener ticket por número"""
        service = TicketService(db_session)
        
        # Crear ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        created_ticket = service.create_ticket(request, sample_user.ID)
        
        # Buscar por número
        ticket = service.get_ticket_by_number(created_ticket.ticket_number)
        
        assert ticket.id == created_ticket.id
    
    def test_list_tickets(self, db_session, sample_cart, sample_user):
        """Test: Listar tickets"""
        service = TicketService(db_session)
        
        # Crear un ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        service.create_ticket(request, sample_user.ID)
        
        # Listar tickets
        tickets = service.list_tickets(limit=10)
        
        assert len(tickets) == 1
    
    def test_list_tickets_with_date_filter(self, db_session, sample_cart, sample_user):
        """Test: Listar tickets con filtro de fecha"""
        service = TicketService(db_session)
        
        # Crear ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        service.create_ticket(request, sample_user.ID)
        
        # Filtrar por fecha de hoy
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        tomorrow = today + timedelta(days=1)
        
        tickets = service.list_tickets(
            start_date=today,
            end_date=tomorrow
        )
        
        assert len(tickets) == 1
    
    def test_list_tickets_with_status_filter(self, db_session, sample_cart, sample_user):
        """Test: Listar tickets con filtro de estado"""
        service = TicketService(db_session)
        
        # Crear ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        service.create_ticket(request, sample_user.ID)
        
        # Filtrar por completados
        tickets = service.list_tickets(status="completed")
        
        assert len(tickets) == 1
        assert all(t.status == "completed" for t in tickets)
    
    def test_cancel_ticket(self, db_session, sample_cart, sample_user, sample_products):
        """Test: Cancelar ticket"""
        service = TicketService(db_session)
        
        # Crear ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        ticket = service.create_ticket(request, sample_user.ID)
        
        # Guardar stock después de la venta
        stock_after_sale = sample_products[0].Stock
        
        # Cancelar ticket
        cancelled_ticket = service.cancel_ticket(
            ticket.id,
            "Error en la venta",
            sample_user.ID
        )
        
        assert cancelled_ticket.status == "cancelled"
        assert cancelled_ticket.cancelled_at is not None
        assert cancelled_ticket.cancellation_reason == "Error en la venta"
        
        # Verificar que el stock se devolvió
        db_session.refresh(sample_products[0])
        assert sample_products[0].Stock > stock_after_sale
    
    def test_cancel_ticket_already_cancelled(self, db_session, sample_cart, sample_user):
        """Test: No se puede cancelar ticket ya cancelado"""
        service = TicketService(db_session)
        
        # Crear y cancelar ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        ticket = service.create_ticket(request, sample_user.ID)
        service.cancel_ticket(ticket.id, "Primera cancelación", sample_user.ID)
        
        # Intentar cancelar de nuevo
        with pytest.raises(InvalidOperationError):
            service.cancel_ticket(ticket.id, "Segunda cancelación", sample_user.ID)
    
    def test_get_tickets_summary(self, db_session, sample_cart, sample_user):
        """Test: Obtener resumen de tickets"""
        service = TicketService(db_session)
        
        # Crear ticket
        request = CreateTicketRequest(
            cart_id=sample_cart.id,
            payment_method="cash",
            amount_paid=Decimal("200.00"),
            tax=Decimal("0.00"),
            discount=Decimal("0.00")
        )
        
        service.create_ticket(request, sample_user.ID)
        
        # Obtener resumen
        summary = service.get_tickets_summary()
        
        assert "total_tickets" in summary
        assert "completed" in summary
        assert "total_sales" in summary
        assert summary["total_tickets"] == 1
        assert summary["completed"] == 1


class TestTicketServiceIntegration:
    """Tests de integración con endpoints"""
    
    def test_create_ticket_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint crear ticket"""
        response = client.post(
            "/tickets/",
            json={
                "CartId": sample_cart.id,
                "PaymentMethod": "cash",
                "AmountPaid": 200.00,
                "Tax": 0.00,
                "Discount": 0.00
            },
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "ticket_number" in data
        assert data["status"] == "completed"
        assert data["payment_method"] == "cash"
    
    def test_get_ticket_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint obtener ticket"""
        # Crear ticket primero
        create_response = client.post(
            "/tickets/",
            json={
                "CartId": sample_cart.id,
                "PaymentMethod": "cash",
                "AmountPaid": 200.00,
                "Tax": 0.00,
                "Discount": 0.00
            },
            headers=auth_headers
        )
        
        ticket_id = create_response.json()["id"]
        
        # Obtener ticket
        response = client.get(
            f"/tickets/{ticket_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ticket_id
    
    def test_list_tickets_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint listar tickets"""
        # Crear ticket
        client.post(
            "/tickets/",
            json={
                "CartId": sample_cart.id,
                "PaymentMethod": "cash",
                "AmountPaid": 200.00,
                "Tax": 0.00,
                "Discount": 0.00
            },
            headers=auth_headers
        )
        
        # Listar tickets
        response = client.get(
            "/tickets/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "tickets" in data
        assert len(data["tickets"]) == 1
    
    def test_list_tickets_with_date_filter_endpoint(self, client, auth_headers, sample_cart):
        """Test: Endpoint listar tickets con filtro de fecha"""
        # Crear ticket
        client.post(
            "/tickets/",
            json={
                "CartId": sample_cart.id,
                "PaymentMethod": "cash",
                "AmountPaid": 200.00,
                "Tax": 0.00,
                "Discount": 0.00
            },
            headers=auth_headers
        )
        
        # Listar con filtro de fecha
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        
        response = client.get(
            f"/tickets/?start_date={today}&end_date={today}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tickets"]) == 1
    
    def test_cancel_ticket_endpoint(self, client, admin_auth_headers, sample_cart):
        """Test: Endpoint cancelar ticket (requiere admin)"""
        # Crear ticket
        create_response = client.post(
            "/tickets/",
            json={
                "CartId": sample_cart.id,
                "PaymentMethod": "cash",
                "AmountPaid": 200.00,
                "Tax": 0.00,
                "Discount": 0.00
            },
            headers=admin_auth_headers
        )
        
        ticket_id = create_response.json()["id"]
        
        # Cancelar ticket
        response = client.patch(
            f"/tickets/{ticket_id}/cancel",
            json={"Reason": "Error en la venta, cliente se arrepintió"},
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "cancelled_at" in data
        assert data["reason"] == "Error en la venta, cliente se arrepintió"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])