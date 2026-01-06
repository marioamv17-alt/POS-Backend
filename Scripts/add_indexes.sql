-- Índices optimizados para mejorar el rendimiento de queries comunes
-- Ejecutar con: psql -U postgres -d POS -f scripts/add_indexes.sql

-- ============================================================================
-- ÍNDICES PARA SALE_TICKETS (Tickets de Venta)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ticket_date_status 
ON sale_tickets (created_at DESC, status) 
WHERE status IN ('completed', 'cancelled');

CREATE INDEX IF NOT EXISTS idx_ticket_created_at_brin 
ON sale_tickets USING BRIN (created_at);

CREATE INDEX IF NOT EXISTS idx_ticket_date_payment 
ON sale_tickets (created_at DESC, payment_method);

CREATE INDEX IF NOT EXISTS idx_ticket_user_date 
ON sale_tickets (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ticket_cash_register 
ON sale_tickets (cash_register_id, created_at DESC) 
WHERE cash_register_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ticket_number_covering 
ON sale_tickets (ticket_number) 
INCLUDE (total, status, created_at);

CREATE INDEX IF NOT EXISTS idx_ticket_completed 
ON sale_tickets (created_at DESC, total) 
WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS idx_ticket_total 
ON sale_tickets (total DESC, created_at DESC) 
WHERE status = 'completed';

-- ============================================================================
-- ÍNDICES PARA SALE_TICKET_ITEMS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ticket_items_ticket_id 
ON sale_ticket_items (ticket_id);

CREATE INDEX IF NOT EXISTS idx_ticket_items_product 
ON sale_ticket_items (product_id, quantity, subtotal);

-- ============================================================================
-- ÍNDICES PARA CART
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_cart_user_open 
ON cart (user_id, status, created_at DESC) 
WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_cart_completed 
ON cart (completed_at DESC) 
WHERE status = 'completed';

CREATE INDEX IF NOT EXISTS idx_cart_created_at 
ON cart (created_at DESC);

-- ============================================================================
-- ÍNDICES PARA CART_ITEMS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id 
ON cart_items (cart_id);

CREATE INDEX IF NOT EXISTS idx_cart_items_product 
ON cart_items (product_id);

-- ============================================================================
-- ÍNDICES PARA MASTER_DATA
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_product_name_trgm 
ON "Master_Data" USING gin (to_tsvector('spanish', "Product"));

CREATE INDEX IF NOT EXISTS idx_product_active_category 
ON "Master_Data" ("Category", "Activo") 
WHERE "Activo" = 1;

CREATE INDEX IF NOT EXISTS idx_product_low_stock 
ON "Master_Data" ("Stock", "Min_Stock") 
WHERE "Activo" = 1 AND "Stock" <= "Min_Stock";

CREATE INDEX IF NOT EXISTS idx_product_price 
ON "Master_Data" ("Price" DESC) 
WHERE "Activo" = 1;

-- ============================================================================
-- ÍNDICES PARA CASH_REGISTER
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_register_user_open 
ON cash_register (user_id, status, opened_at DESC) 
WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_register_date_range 
ON cash_register (opened_at DESC, closed_at DESC);

CREATE INDEX IF NOT EXISTS idx_register_sales 
ON cash_register (total_sales DESC, opened_at DESC) 
WHERE status = 'closed';

-- ============================================================================
-- ÍNDICES PARA CASH_WITHDRAWALS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_withdrawal_register_date 
ON cash_withdrawals (cash_register_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_withdrawal_user_date 
ON cash_withdrawals (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_withdrawal_reason 
ON cash_withdrawals (reason, created_at DESC);

-- ============================================================================
-- ÍNDICES PARA PRICE_HISTORY
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_price_history_product 
ON price_history (product_id, changed_at DESC);

-- ============================================================================
-- ÍNDICES PARA USERS
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_users_role 
ON "Users" ("Role");

-- ============================================================================
-- ESTADÍSTICAS Y MANTENIMIENTO
-- ============================================================================
ANALYZE "sale_tickets";
ANALYZE "sale_ticket_items";
ANALYZE "cart";
ANALYZE "cart_items";
ANALYZE "Master_Data";
ANALYZE "cash_register";
ANALYZE "cash_withdrawals";
ANALYZE "price_history";
ANALYZE "Users";

-- ============================================================================
-- INFORMACIÓN DE ÍNDICES
-- ============================================================================
-- Mostrar información sobre los índices creados
SELECT
    schemaname,
    relname AS tablename,
    indexrelname AS indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;

-- Mostrar tamaño de los índices
SELECT
    relname AS tablename,
    indexrelname AS indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Fin del script de creación de índices