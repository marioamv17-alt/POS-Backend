import pytest

def test_health_check(client):
    """Prueba que el endpoint de salud base funcione"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "3.0.0"}

def test_read_root(client):
    """Prueba que la raíz responda correctamente"""
    response = client.get("/")
    assert response.status_code == 200
    assert "API POS v3.0" in response.json()["message"]