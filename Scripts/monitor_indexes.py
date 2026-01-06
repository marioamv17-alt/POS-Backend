"""
Script para monitorear el rendimiento y uso de índices.
Ejecutar con: python scripts/monitor_indexes.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text
from database import engine
from tabulate import tabulate


def show_index_usage():
    """Muestra el uso de índices"""
    
    query = text("""
        SELECT
            schemaname,
            relname AS tablename,
            indexrelname AS indexname,
            idx_scan as scans,
            idx_tup_read as tuples_read,
            idx_tup_fetch as tuples_fetched,
            pg_size_pretty(pg_relation_size(indexrelid)) as size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        ORDER BY idx_scan DESC
        LIMIT 20
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
    
    if rows:
        print("\n📊 ÍNDICES MÁS USADOS")
        print("=" * 100)
        print(tabulate(rows, headers="keys", tablefmt="grid"))
    else:
        print("No hay datos de uso de índices")


def show_unused_indexes():
    """Muestra índices no utilizados (candidatos para eliminar)"""
    
    query = text("""
        SELECT
            schemaname,
            relname AS tablename,
            indexrelname AS indexname,
            pg_size_pretty(pg_relation_size(indexrelid)) as size
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
        AND idx_scan = 0
        AND indexrelname NOT LIKE '%_pkey'
        ORDER BY pg_relation_size(indexrelid) DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
    
    if rows:
        print("\n⚠️  ÍNDICES NO UTILIZADOS")
        print("=" * 100)
        print("Estos índices nunca se han usado. Considera eliminarlos:")
        print(tabulate(rows, headers="keys", tablefmt="grid"))
    else:
        print("\n✅ Todos los índices están siendo utilizados")


def show_missing_indexes():
    """Sugiere índices faltantes basado en queries lentos"""
    
    query = text("""
        SELECT
            schemaname,
            relname AS tablename,
            attname,
            n_distinct,
            correlation
        FROM pg_stats
        WHERE schemaname = 'public'
        AND n_distinct > 100
        ORDER BY n_distinct DESC
        LIMIT 10
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
    
    if rows:
        print("\n💡 COLUMNAS CANDIDATAS PARA ÍNDICES")
        print("=" * 100)
        print("Columnas con alta cardinalidad que podrían beneficiarse de índices:")
        print(tabulate(rows, headers="keys", tablefmt="grid"))


def show_table_stats():
    """Muestra estadísticas de tablas"""
    
    query = text("""
        SELECT
            schemaname,
            relname AS tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
            pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples,
            n_dead_tup as dead_tuples
        FROM pg_stat_user_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        rows = [dict(row._mapping) for row in result]
    
    if rows:
        print("\n📈 ESTADÍSTICAS DE TABLAS")
        print("=" * 150)
        print(tabulate(rows, headers="keys", tablefmt="grid"))


def show_slow_queries():
    """Muestra las queries más lentas (requiere pg_stat_statements)"""
    
    query = text("""
        SELECT
            LEFT(query, 80) as query_preview,
            calls,
            ROUND(total_exec_time::numeric, 2) as total_time_ms,
            ROUND(mean_exec_time::numeric, 2) as mean_time_ms,
            ROUND((100 * total_exec_time / SUM(total_exec_time) OVER ())::numeric, 2) as percentage
        FROM pg_stat_statements
        WHERE query NOT LIKE '%pg_stat%'
        ORDER BY total_exec_time DESC
        LIMIT 10
    """)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = [dict(row._mapping) for row in result]
        
        if rows:
            print("\n🐌 QUERIES MÁS LENTAS")
            print("=" * 150)
            print("Nota: Requiere extensión pg_stat_statements activada")
            print(tabulate(rows, headers="keys", tablefmt="grid"))
    except Exception as e:
        print(f"\n⚠️  pg_stat_statements no disponible: {e}")
        print("   Para activarlo: CREATE EXTENSION pg_stat_statements;")


def main():
    """Función principal"""
    print("\n🔍 MONITOREO DE ÍNDICES Y RENDIMIENTO\n")
    
    try:
        show_index_usage()
        show_unused_indexes()
        show_missing_indexes()
        show_table_stats()
        show_slow_queries()
        
        print("\n" + "=" * 100)
        print("✅ Análisis completado")
        print("\n💡 Recomendaciones:")
        print("   1. Revisa los índices no utilizados y considera eliminarlos")
        print("   2. Ejecuta VACUUM ANALYZE regularmente")
        print("   3. Monitorea las queries lentas y optimízalas")
        print("   4. Considera agregar índices para columnas con alta cardinalidad")
        print("=" * 100)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0