"""
Script para agregar índices optimizados a PostgreSQL.
Ejecutar con: python scripts/add_indexes.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine
import time


def create_indexes():
    """Crea todos los índices de optimización"""
    
    indexes = [
        # SALE_TICKETS
        {
            "name": "idx_ticket_date_status",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_ticket_date_status 
                ON sale_tickets (created_at DESC, status) 
                WHERE status IN ('completed', 'cancelled')
            """,
            "description": "Índice para filtros por fecha y estado"
        },
        {
            "name": "idx_ticket_date_payment",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_ticket_date_payment 
                ON sale_tickets (created_at DESC, payment_method)
            """,
            "description": "Índice para filtros por fecha y método de pago"
        },
        {
            "name": "idx_ticket_user_date",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_ticket_user_date 
                ON sale_tickets (user_id, created_at DESC)
            """,
            "description": "Índice para filtros por cajero y fecha"
        },
        {
            "name": "idx_ticket_completed",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_ticket_completed 
                ON sale_tickets (created_at DESC, total) 
                WHERE status = 'completed'
            """,
            "description": "Índice parcial para tickets completados"
        },
        
        # CART
        {
            "name": "idx_cart_user_open",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_cart_user_open 
                ON cart (user_id, status, created_at DESC) 
                WHERE status = 'open'
            """,
            "description": "Índice para carritos abiertos por usuario"
        },
        {
            "name": "idx_cart_created_at",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_cart_created_at 
                ON cart (created_at DESC)
            """,
            "description": "Índice para búsquedas por fecha de creación"
        },
        
        # MASTER_DATA (Productos)
        {
            "name": "idx_product_name_trgm",
            "sql": """
                CREATE EXTENSION IF NOT EXISTS pg_trgm;
                CREATE INDEX IF NOT EXISTS idx_product_name_trgm 
                ON "Master_Data" USING gin (to_tsvector('spanish', "Product"))
            """,
            "description": "Índice de texto completo para nombres de productos"
        },
        {
            "name": "idx_product_low_stock",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_product_low_stock 
                ON "Master_Data" ("Stock", "Min_Stock") 
                WHERE "Activo" = 1 AND "Stock" <= "Min_Stock"
            """,
            "description": "Índice para productos con stock bajo"
        },
        
        # CASH_REGISTER
        {
            "name": "idx_register_user_open",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_register_user_open 
                ON cash_register (user_id, status, opened_at DESC) 
                WHERE status = 'open'
            """,
            "description": "Índice para cajas abiertas por usuario"
        },
        {
            "name": "idx_register_date_range",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_register_date_range 
                ON cash_register (opened_at DESC, closed_at DESC)
            """,
            "description": "Índice para rangos de fecha en cajas"
        },
        
        # CASH_WITHDRAWALS
        {
            "name": "idx_withdrawal_register_date",
            "sql": """
                CREATE INDEX IF NOT EXISTS idx_withdrawal_register_date 
                ON cash_withdrawals (cash_register_id, created_at DESC)
            """,
            "description": "Índice para retiros por caja y fecha"
        },
    ]
    
    print("=" * 70)
    print("CREANDO ÍNDICES DE OPTIMIZACIÓN")
    print("=" * 70)
    
    with engine.connect() as conn:
        success_count = 0
        fail_count = 0
        
        for idx in indexes:
            try:
                print(f"\n📊 Creando: {idx['name']}")
                print(f"   {idx['description']}")
                
                start_time = time.time()
                conn.execute(text(idx['sql']))
                conn.commit()
                elapsed = time.time() - start_time
                
                print(f"   ✅ Creado en {elapsed:.2f}s")
                success_count += 1
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                fail_count += 1
                conn.rollback()
        
        # Actualizar estadísticas
        print("\n" + "=" * 70)
        print("ACTUALIZANDO ESTADÍSTICAS")
        print("=" * 70)
        
        tables = [
            "sale_tickets",
            "sale_ticket_items",
            "cart",
            "cart_items",
            '"Master_Data"',
            "cash_register",
            "cash_withdrawals",
            "price_history",
            '"Users"'
        ]
        
        for table in tables:
            try:
                print(f"\n📈 Analizando tabla: {table}")
                conn.execute(text(f"ANALYZE {table}"))
                conn.commit()
                print(f"   ✅ Completado")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                conn.rollback()
    
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)
    print(f"✅ Índices creados exitosamente: {success_count}")
    print(f"❌ Índices fallidos: {fail_count}")
    print("=" * 70)


def show_index_info():
    """Muestra información sobre los índices creados"""
    
    print("\n" + "=" * 70)
    print("INFORMACIÓN DE ÍNDICES")
    print("=" * 70)
    
    query = text("""
        SELECT 
            schemaname,
            relname AS tablename,
            indexrelname AS indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        ORDER BY pg_relation_size(indexrelid) DESC
        LIMIT 20
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        
        print(f"\n{'Tabla':<20} {'Índice':<35} {'Tamaño':<10}")
        print("-" * 70)
        
        for row in result:
            print(f"{row.tablename:<20} {row.indexname:<35} {row.index_size:<10}")


def main():
    """Función principal"""
    print("\n🚀 OPTIMIZACIÓN DE BASE DE DATOS - ÍNDICES\n")
    
    response = input("¿Deseas crear los índices de optimización? (yes/no): ")
    
    if response.lower() != "yes":
        print("❌ Operación cancelada")
        return
    
    try:
        create_indexes()
        show_index_info()
        
        print("\n✅ ¡Índices creados exitosamente!")
        print("\n💡 Recomendaciones:")
        print("   - Ejecuta VACUUM ANALYZE periódicamente")
        print("   - Monitorea el uso de índices con pg_stat_user_indexes")
        print("   - Considera crear índices adicionales basados en queries lentos")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())