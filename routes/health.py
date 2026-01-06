from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from datetime import datetime, UTC
from app.core.health_checks import (
    check_database,
    check_redis,
    check_external_api
) 

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
def health_check():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/db")
def database_health(db: Session = Depends(get_db)):
    try:
        # Test DB connection
        db.execute("SELECT 1")
        return {
            "database": "healthy",
            "connection": "ok"
        }
    except Exception as e:
        return {
            "database": "unhealthy",
            "error": str(e)
        }

@router.get("/dependencies")
def dependencies_health():
    checks = {
        "database": check_database(),
        "redis": check_redis(),  # Si usas Redis
        "external_api": check_external_api()  # Si usas APIs externas
    }
    
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks
    }