CREATE INDEX idx_sale_tickets_date_status ON sale_tickets(created_at, status);
CREATE INDEX idx_cart_items_cart_product ON cart_items(cart_id, product_id);
CREATE INDEX idx_products_category_active ON Master_Data(Category, Activo);