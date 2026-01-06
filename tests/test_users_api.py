def test_register_user(client):
    response = client.post("/users/register", json={
        "username": "newuser",
        "password": "password123"
    })
    assert response.status_code == 201
    assert response.json()["message"] == "Usuario creado exitosamente"

def test_login_success(client, db):
    # Primero creamos el usuario
    client.post("/users/register", json={"username": "user1", "password": "abc"})
    
    # Intentamos login
    response = client.post("/users/login", json={"username": "user1", "password": "abc"})
    assert response.status_code == 200
    assert "access_token" in response.json()