"""
Script para cargar datos de prueba en la base de datos.
Útil para configurar un nuevo entorno de desarrollo o testing.

Uso:
    python scripts/seed_database.py
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import Users, Product, Cart, CartItem, CashRegister, SaleTicket, SaleTicketItem
from app.core.security import hash_password
from decimal import Decimal
from datetime import datetime, timedelta
import random


def clear_database(db: Session):
    """Limpia todas las tablas (¡CUIDADO! Elimina todos los datos)"""
    print("⚠️  Limpiando base de datos...")
    
    # Orden importante: primero tablas dependientes
    db.query(SaleTicketItem).delete()
    db.query(SaleTicket).delete()
    db.query(CartItem).delete()
    db.query(Cart).delete()
    db.query(CashRegister).delete()
    db.query(Product).delete()
    db.query(Users).delete()
    
    db.commit()
    print("✅ Base de datos limpiada")


def seed_users(db: Session):
    """Crea usuarios de prueba"""
    print("\n👤 Creando usuarios...")
    
    users_data = [
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "manager1", "password": "manager123", "role": "manager"},
        {"username": "cajero1", "password": "cajero123", "role": "cashier"},
        {"username": "cajero2", "password": "cajero123", "role": "cashier"},
        {"username": "cajero3", "password": "cajero123", "role": "cashier"},
    ]
    
    users = []
    for user_data in users_data:
        user = Users(
            Username=user_data["username"],
            Password=hash_password(user_data["password"]),
            Role=user_data["role"]
        )
        db.add(user)
        users.append(user)
        print(f"   - {user_data['username']} ({user_data['role']})")
    
    db.commit()
    
    for user in users:
        db.refresh(user)
    
    print(f"✅ {len(users)} usuarios creados")
    return users


def seed_products(db: Session):
    """Crea productos de prueba"""
    print("\n📦 Creando productos...")
    
    products_data = [
        # Bebidas
        {"code": "BEB001", "barcode": "7501234567890", "name": "Coca Cola 600ml", "category": "Bebidas", "price": 15.00, "stock": 100},
        {"code": "BEB002", "barcode": "7501234567891", "name": "Coca Cola 2L", "category": "Bebidas", "price": 35.00, "stock": 50},
        {"code": "BEB003", "barcode": "7501234567892", "name": "Sprite 600ml", "category": "Bebidas", "price": 15.00, "stock": 80},
        {"code": "BEB004", "barcode": "7501234567893", "name": "Agua Ciel 1L", "category": "Bebidas", "price": 10.00, "stock": 150},
        {"code": "BEB005", "barcode": "7501234567894", "name": "Jugo Del Valle 1L", "category": "Bebidas", "price": 25.00, "stock": 60},
        
        # Snacks
        {"code": "SNK001", "barcode": "7502234567890", "name": "Sabritas Original", "category": "Snacks", "price": 18.50, "stock": 120},
        {"code": "SNK002", "barcode": "7502234567891", "name": "Sabritas Adobadas", "category": "Snacks", "price": 18.50, "stock": 100},
        {"code": "SNK003", "barcode": "7502234567892", "name": "Doritos Nacho", "category": "Snacks", "price": 20.00, "stock": 80},
        {"code": "SNK004", "barcode": "7502234567893", "name": "Cheetos Poffs", "category": "Snacks", "price": 17.00, "stock": 90},
        {"code": "SNK005", "barcode": "7502234567894", "name": "Ruffles Queso", "category": "Snacks", "price": 19.00, "stock": 70},
        
        # Lácteos
        {"code": "LAC001", "barcode": "7503234567890", "name": "Leche Lala 1L", "category": "Lácteos", "price": 25.00, "stock": 50},
        {"code": "LAC002", "barcode": "7503234567891", "name": "Yogurt Danone 1L", "category": "Lácteos", "price": 35.00, "stock": 40},
        {"code": "LAC003", "barcode": "7503234567892", "name": "Queso Panela 400g", "category": "Lácteos", "price": 45.00, "stock": 30},
        {"code": "LAC004", "barcode": "7503234567893", "name": "Crema Lala 200ml", "category": "Lácteos", "price": 20.00, "stock": 45},
        
        # Panadería
        {"code": "PAN001", "barcode": "7504234567890", "name": "Pan Bimbo Blanco", "category": "Panadería", "price": 35.00, "stock": 60},
        {"code": "PAN002", "barcode": "7504234567891", "name": "Pan Bimbo Integral", "category": "Panadería", "price": 38.00, "stock": 50},
        {"code": "PAN003", "barcode": "7504234567892", "name": "Tostadas Charras", "category": "Panadería", "price": 15.00, "stock": 80},
        {"code": "PAN004", "barcode": "7504234567893", "name": "Tortillas 1kg", "category": "Panadería", "price": 22.00, "stock": 40},
        
        # Abarrotes
        {"code": "ABA001", "barcode": "7505234567890", "name": "Huevos San Juan 12pz", "category": "Abarrotes", "price": 45.00, "stock": 8},  # Stock bajo
        {"code": "ABA002", "barcode": "7505234567891", "name": "Arroz Verde Valle 1kg", "category": "Abarrotes", "price": 28.00, "stock": 50},
        {"code": "ABA003", "barcode": "7505234567892", "name": "Frijol La Costeña 1kg", "category": "Abarrotes", "price": 32.00, "stock": 45},
        {"code": "ABA004", "barcode": "7505234567893", "name": "Aceite 123 1L", "category": "Abarrotes", "price": 35.00, "stock": 35},
        {"code": "ABA005", "barcode": "7505234567894", "name": "Sal La Fina 1kg", "category": "Abarrotes", "price": 12.00, "stock": 100},
        
        # Dulces
        {"code": "DUL001", "barcode": "7506234567890", "name": "Chocolate Carlos V", "category": "Dulces", "price": 8.00, "stock": 200},
        {"code": "DUL002", "barcode": "7506234567891", "name": "Chicles Trident", "category": "Dulces", "price": 12.00, "stock": 150},
        {"code": "DUL003", "barcode": "7506234567892", "name": "Paleta Vero Mango", "category": "Dulces", "price": 3.00, "stock": 300},
        {"code": "DUL004", "barcode": "7506234567893", "name": "Mazapán De La Rosa", "category": "Dulces", "price": 5.00, "stock": 250},
        
        # Limpieza
        {"code": "LMP001", "barcode": "7507234567890", "name": "Papel Higiénico Petalo 4pz", "category": "Limpieza", "price": 35.00, "stock": 40},
        {"code": "LMP002", "barcode": "7507234567891", "name": "Jabón Zote 200g", "category": "Limpieza", "price": 18.00, "stock": 60},
        {"code": "LMP003", "barcode": "7507234567892", "name": "Cloro Cloralex 1L", "category": "Limpieza", "price": 22.00, "stock": 50},
        {"code": "LMP004", "barcode": "7507234567893", "name": "Suavitel 1L", "category": "Limpieza", "price": 35.00, "stock": 45},
    ]
    
    products = []
    for p_data in products_data:
        product = Product(
            Code=p_data["code"],
            Barcode=p_data["barcode"],
            Product=p_data["name"],
            Category=p_data["category"],
            Units="Pieza",
            Price=Decimal(str(p_data["price"])),
            Stock=p_data["stock"],
            Min_Stock=10,
            Activo=1
        )
        db.add(product)
        products.append(product)
    
    db.commit()
    
    for product in products:
        db.refresh(product)
    
    print(f"✅ {len(products)} productos creados")
    return products


def seed_sample_sales(db: Session, users: list, products: list):
    """Crea ventas de ejemplo (últimos 7 días)"""
    print("\n💰 Creando ventas de ejemplo...")
    
    cashiers = [u for u in users if u.Role == "cashier"]
    tickets_created = 0
    
    # Crear ventas para los últimos 7 días
    for days_ago in range(7):
        date = datetime.utcnow() - timedelta(days=days_ago)
        
        # 5-15 ventas por día
        num_sales = random.randint(5, 15)
        
        for _ in range(num_sales):
            # Seleccionar cajero aleatorio
            cashier = random.choice(cashiers)
            
            # Crear carrito
            cart = Cart(
                user_id=cashier.ID,
                status="completed",
                created_at=date - timedelta(hours=random.randint(8, 20))
            )
            db.add(cart)
            db.flush()
            
            # Agregar 1-5 productos al carrito
            num_items = random.randint(1, 5)
            cart_items = []
            cart_total = Decimal("0.00")
            
            selected_products = random.sample(products, num_items)
            
            for product in selected_products:
                quantity = random.randint(1, 3)
                subtotal = product.Price * quantity
                cart_total += subtotal
                
                cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product.Id,
                    product_name=product.Product,
                    price=product.Price,
                    quantity=quantity,
                    subtotal=subtotal
                )
                cart_items.append(cart_item)
                db.add(cart_item)
            
            db.flush()
            
            # Crear ticket
            payment_methods = ["cash", "card", "transfer"]
            payment_method = random.choice(payment_methods)
            
            ticket_number = f"TKT-{date.strftime('%Y%m%d')}-{tickets_created + 1:04d}"
            
            ticket = SaleTicket(
                ticket_number=ticket_number,
                cart_id=cart.id,
                user_id=cashier.ID,
                subtotal=cart_total,
                tax=Decimal("0.00"),
                discount=Decimal("0.00"),
                total=cart_total,
                payment_method=payment_method,
                amount_paid=cart_total if payment_method == "cash" else None,
                change_given=Decimal("0.00") if payment_method == "cash" else None,
                status="completed",
                created_at=cart.created_at
            )
            db.add(ticket)
            db.flush()
            
            # Crear items del ticket
            for cart_item in cart_items:
                ticket_item = SaleTicketItem(
                    ticket_id=ticket.id,
                    product_id=cart_item.product_id,
                    product_code=selected_products[0].Code,  # Simplificado
                    product_name=cart_item.product_name,
                    unit_price=cart_item.price,
                    quantity=cart_item.quantity,
                    subtotal=cart_item.subtotal
                )
                db.add(ticket_item)
            
            tickets_created += 1
    
    db.commit()
    print(f"✅ {tickets_created} ventas creadas (últimos 7 días)")


def seed_open_carts(db: Session, users: list, products: list):
    """Crea algunos carritos abiertos"""
    print("\n🛒 Creando carritos abiertos...")
    
    cashiers = [u for u in users if u.Role == "cashier"]
    carts_created = 0
    
    for cashier in cashiers[:2]:  # Solo para 2 cajeros
        cart = Cart(
            user_id=cashier.ID,
            status="open",
            created_at=datetime.utcnow()
        )
        db.add(cart)
        db.flush()
        
        # Agregar algunos productos
        num_items = random.randint(2, 4)
        selected_products = random.sample(products, num_items)
        
        for product in selected_products:
            quantity = random.randint(1, 2)
            cart_item = CartItem(
                cart_id=cart.id,
                product_id=product.Id,
                product_name=product.Product,
                price=product.Price,
                quantity=quantity,
                subtotal=product.Price * quantity
            )
            db.add(cart_item)
        
        carts_created += 1
    
    db.commit()
    print(f"✅ {carts_created} carritos abiertos creados")


def main():
    """Función principal"""
    print("=" * 60)
    print("🌱 SEED DATABASE - Carga de Datos de Prueba")
    print("=" * 60)
    
    # Confirmar antes de continuar
    response = input("\n⚠️  Esto eliminará TODOS los datos actuales. ¿Continuar? (yes/no): ")
    
    if response.lower() != "yes":
        print("❌ Operación cancelada")
        return
    
    db = SessionLocal()
    
    try:
        # Crear tablas si no existen
        print("\n📋 Verificando tablas...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tablas verificadas")
        
        # Limpiar base de datos
        clear_database(db)
        
        # Cargar datos
        users = seed_users(db)
        products = seed_products(db)
        seed_sample_sales(db, users, products)
        seed_open_carts(db, users, products)
        
        print("\n" + "=" * 60)
        print("✅ ¡BASE DE DATOS CARGADA EXITOSAMENTE!")
        print("=" * 60)
        print("\n📊 Resumen:")
        print(f"   - {len(users)} usuarios")
        print(f"   - {len(products)} productos")
        print(f"   - ~70-100 ventas de los últimos 7 días")
        print(f"   - 2 carritos abiertos")
        
        print("\n🔑 Credenciales de acceso:")
        print("   Admin:    admin / admin123")
        print("   Manager:  manager1 / manager123")
        print("   Cajeros:  cajero1, cajero2, cajero3 / cajero123")
        
        print("\n🚀 ¡Listo para probar los endpoints!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()