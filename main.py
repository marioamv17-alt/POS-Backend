import schemas
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db

# Importar routers
from routes.health import router as router
from routes.inventory import router as inventory_router
from routes.users import router as usuarios_router
from routes.cart import router as carritos_router
from routes.prices import router as price_router
from routes.tickets import router as tickets_router
from routes.cash_register import router as cash_register_router
from routes.withdrawals import router as withdrawals_router
from app.core.exceptions import AppException
from app.core.config import settings

from app.core.health_checks import (
    check_database,
    check_redis,
    check_external_api
)

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API POS Sistema Completo",
    description="Sistema de Punto de Venta con autenticación, tickets y caja registradora",
    version="3.0.0"
)

origins = [
    os.getenv("FRONTEND_URL", "http://localhost:5173")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Registrar routers
app.include_router(usuarios_router)
app.include_router(inventory_router)
app.include_router(carritos_router)
app.include_router(price_router)
app.include_router(tickets_router)
app.include_router(cash_register_router)
app.include_router(withdrawals_router)

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Manejador global para excepciones personalizadas"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "type": exc.__class__.__name__,
            "path": str(request.url)
        }
    )

@app.get("/")
def read_root():
    return {
        "message": "API POS v3.0 - Sistema Completo",
        "features": [
            "Autenticación JWT con roles",
            "Gestión de inventario",
            "Carritos de compra",
            "Tickets de venta",
            "Control de caja registradora",
            "Reportes de ventas"
        ],
        "docs": "/docs"
    }

@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "3.0.0"}

@router.get("/health")
async def health_system_check(db: Session = Depends(get_db)):
    db_status = check_database(db)
    redis_status = check_redis()
    api_status = await check_external_api()
    
    # Si alguno falla, podrías cambiar el status code a 503
    return {
        "database": db_status,
        "redis": redis_status,
        "external_apis": api_status
    }

@app.get("/debug-routes")
def get_all_routes():
    return [{"path": route.path, "name": route.name} for route in app.routes]