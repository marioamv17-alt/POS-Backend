from decimal import Decimal
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator

# ==================== USUARIOS ====================
class LoginRequest(BaseModel):
    username: str = Field(..., alias="Username")
    password: str = Field(..., alias="Password")
    model_config = ConfigDict(populate_by_name=True)


class RegisterRequest(BaseModel):
    username: str = Field(..., alias="Username", min_length=3, max_length=50)
    password: str = Field(..., alias="Password", min_length=4, max_length=72)
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('password')
    @classmethod
    def validate_password_length(cls, v):
        if len(v.encode('utf-8')) > 72:
            raise ValueError("La contraseña no puede superar los 72 caracteres")
        return v


class UserSchema(BaseModel):
    id: int = Field(..., alias="ID")
    username: str = Field(..., alias="Username")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ==================== PRODUCTOS ====================
class ProductoCreate(BaseModel):
    code: str | int = Field(..., alias="Code")
    barcode: str | int | None = Field(None, alias="Barcode")
    product: str = Field(..., alias="Product")
    category: str = Field(..., alias="Category")
    units: str = Field(..., alias="Units")
    price: Decimal = Field(..., alias="Price")
    stock: int = Field(..., alias="Stock")
    min_stock: int = Field(..., alias="Min_Stock")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('El precio no puede ser negativo')
        return round(v, 2)


class ProductoSchema(BaseModel):
    Id: int = Field(..., alias="Id")
    Code: str | int = Field(..., alias="Code")
    Barcode: str | int | None = Field(None, alias="Barcode")
    Product: str = Field(..., alias="Product")
    Category: str = Field(..., alias="Category")
    Units: str = Field(..., alias="Units")
    Price: Decimal = Field(..., alias="Price")
    Stock: int = Field(..., alias="Stock")
    Min_Stock: int = Field(..., alias="Min_Stock")
    Activo: int = Field(..., alias="Activo")
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ProductoUpdate(BaseModel):
    product: str | None = Field(None, alias="Product")
    code: str | int | None = Field(None, alias="Code")
    barcode: str | int | None = Field(None, alias="Barcode")
    stock: int | None = Field(None, alias="Stock")
    min_stock: int | None = Field(None, alias="Min_Stock")
    activo: int | None = Field(None, alias="Activo")

    model_config = ConfigDict(populate_by_name=True)

# ==================== CARRITO ====================
class CartCreate(BaseModel):
    pass


class AddItemRequest(BaseModel):
    product_id: int | None = None
    code: str | None = None
    barcode: str | None = None
    quantity: Decimal = Decimal('1.0')


class CartItemSchema(BaseModel):
    id: int
    product_id: int
    product_name: str
    price: Decimal
    quantity: Decimal
    subtotal: Decimal
    model_config = ConfigDict(from_attributes=True)


class CartSchema(BaseModel):
    id: int
    status: str
    created_at: Any | None
    items: list[CartItemSchema] = []
    total: Decimal | None = None
    model_config = ConfigDict(from_attributes=True)


class CartUpdateStatus(BaseModel):
    status: str = Field(..., alias="Status")
    model_config = ConfigDict(populate_by_name=True)


class CartUpdateQuantity(BaseModel):
    quantity: Decimal = Field(..., alias="Quantity")
    model_config = ConfigDict(populate_by_name=True)


# ==================== PRECIOS ====================
class PrecioUpdate(BaseModel):
    price: Decimal = Field(..., alias="Price")
    reason: str | None = Field(None, alias="Reason")
    model_config = ConfigDict(populate_by_name=True)


class PrecioBulkItem(BaseModel):
    id: int = Field(..., alias="Id")
    price: Decimal = Field(..., alias="Price")
    reason: str | None = Field(None, alias="Reason")
    model_config = ConfigDict(populate_by_name=True)


class PrecioBulkRequest(BaseModel):
    items: list[PrecioBulkItem] = Field(..., alias="Items")
    model_config = ConfigDict(populate_by_name=True)


class ProductoPrecioSchema(BaseModel):
    Id: int
    Code: int
    Product: str
    Price: Decimal
    Activo: int
    model_config = ConfigDict(from_attributes=True)


class PriceHistorySchema(BaseModel):
    id: int
    product_id: int
    old_price: Decimal
    new_price: Decimal
    reason: str | None
    changed_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ==================== TICKETS DE VENTA ====================
class CreateTicketRequest(BaseModel):
    cart_id: int = Field(..., alias="CartId")
    payment_method: str = Field(..., alias="PaymentMethod")
    payment_reference: str | None = Field(None, alias="PaymentReference")
    amount_paid: Decimal | None = Field(None, alias="AmountPaid")
    tax: Decimal = Field(default=Decimal('0.00'), alias="Tax")
    discount: Decimal = Field(default=Decimal('0.00'), alias="Discount")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('payment_method')
    @classmethod
    def validate_payment_method(cls, v):
        allowed = ['cash', 'card', 'transfer']
        if v.lower() not in allowed:
            raise ValueError(f'Método de pago debe ser: {", ".join(allowed)}')
        return v.lower()


class SaleTicketItemSchema(BaseModel):
    product_code: str
    product_name: str
    unit_price: Decimal
    quantity: Decimal
    subtotal: Decimal
    model_config = ConfigDict(from_attributes=True)


class SaleTicketSchema(BaseModel):
    id: int
    ticket_number: str
    subtotal: Decimal
    tax: Decimal
    discount: Decimal
    total: Decimal
    payment_method: str
    payment_reference: str | None
    amount_paid: Decimal | None
    change_given: Decimal | None
    status: str
    created_at: datetime
    cashier_name: str | None = None
    items: list[SaleTicketItemSchema] = []
    model_config = ConfigDict(from_attributes=True)


class CancelTicketRequest(BaseModel):
    reason: str = Field(..., alias="Reason", min_length=10)
    model_config = ConfigDict(populate_by_name=True)


# ==================== CAJA REGISTRADORA ====================
class OpenCashRegisterRequest(BaseModel):
    initial_cash: Decimal = Field(default=Decimal('0.00'), alias="InitialCash")
    notes: str | None = Field(None, alias="Notes")
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('initial_cash')
    @classmethod
    def validate_initial_cash(cls, v):
        if v < 0:
            raise ValueError('El efectivo inicial no puede ser negativo')
        return v


class CloseCashRegisterRequest(BaseModel):
    final_cash: Decimal = Field(..., alias="FinalCash")
    notes: str | None = Field(None, alias="Notes")
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('final_cash')
    @classmethod
    def validate_final_cash(cls, v):
        if v < 0:
            raise ValueError('El efectivo final no puede ser negativo')
        return v


class CashRegisterSchema(BaseModel):
    id: int
    user_id: int
    opened_at: datetime
    closed_at: datetime | None
    initial_cash: Decimal
    final_cash: Decimal | None
    expected_cash: Decimal | None
    difference: Decimal | None
    total_sales: Decimal
    total_cash: Decimal
    total_card: Decimal
    total_transfer: Decimal
    num_transactions: int
    status: str
    notes: str | None
    model_config = ConfigDict(from_attributes=True)


class CashRegisterSummary(BaseModel):
    register_id: int
    cashier: str
    opened_at: datetime
    closed_at: datetime | None
    status: str
    total_sales: Decimal
    total_cash: Decimal
    total_card: Decimal
    total_transfer: Decimal
    num_transactions: int
    difference: Decimal | None
    
# ==================== RETIROS DE EFECTIVO ====================
class CreateWithdrawalRequest(BaseModel):
    amount: Decimal = Field(..., alias="Amount", gt=0)
    reason: str = Field(..., alias="Reason")
    notes: str | None = Field(None, alias="Notes")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        allowed = ['security_limit', 'end_of_shift', 'deposit', 'other']
        if v not in allowed:
            raise ValueError(f'Razón debe ser: {", ".join(allowed)}')
        return v
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('El monto debe ser mayor a 0')
        if v > 50000:
            raise ValueError('El monto máximo por retiro es $50,000')
        return v


class CashWithdrawalSchema(BaseModel):
    id: int
    cash_register_id: int
    user_id: int
    amount: Decimal
    reason: str
    notes: str | None
    cash_before: Decimal
    cash_after: Decimal
    status: str
    created_at: datetime
    user_name: str | None = None
    approver_name: str | None = None
    
    model_config = ConfigDict(from_attributes=True)


class CashLimitAlert(BaseModel):
    cash_register_id: int
    current_cash: Decimal
    cash_limit: Decimal
    excess: Decimal
    alert_level: str  # "warning", "critical"
    message: str