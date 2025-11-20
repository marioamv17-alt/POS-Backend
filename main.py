from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

# ----------------------------------------------------------
#  CONFIGURACIÓN DE POSTGRES (usa tu contraseña real)
# ----------------------------------------------------------
DATABASE_URL = "postgresql+psycopg2://postgres:POS123@localhost:5432/POS"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ----------------------------------------------------------
#  MODELO SQLALCHEMY CORRIGIDO PARA POSTGRES
# ----------------------------------------------------------
class User(Base):
    __tablename__ = "Users"

    ID = Column(Integer, primary_key=True, index=True)  # ID autoincrement
    username = Column("Username", String, unique=True, index=True, nullable=False)
    password = Column("Password", String, nullable=False)

# Crear tablas si no existen
Base.metadata.create_all(bind=engine)

# ----------------------------------------------------------
#  CONFIG FASTAPI + CORS
# ----------------------------------------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # puedes restringir después
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------
#  ESQUEMAS Pydantic
# ----------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str


# ----------------------------------------------------------
#  ENDPOINT: Root
# ----------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "API funcionando correctamente"}

# ----------------------------------------------------------
#  ENDPOINT: Login
# ----------------------------------------------------------
@app.post("/api/login")
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == data.username).first()

        if not user or user.password != data.password:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

        return {"username": user.username}

    except Exception as e:
        print("ERROR en /api/login:", e)
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    finally:
        db.close()

# ----------------------------------------------------------
#  ENDPOINT: Registrar Usuario
# ----------------------------------------------------------
@app.post("/api/register")
def register(data: RegisterRequest):
    db = SessionLocal()
    try:
        # Verificar si ya existe
        existing = db.query(User).filter(User.username == data.username).first()
        if existing:
            raise HTTPException(status_code=400, detail="El usuario ya existe")

        # Obtener el siguiente ID consecutivo SIN HUECOS
        last_user = db.query(User).order_by(User.ID.desc()).first()
        next_id = (last_user.ID + 1) if last_user else 1

        # Crear nuevo usuario
        new_user = User(
            ID=next_id,
            username=data.username,
            password=data.password
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {"id": new_user.ID, "username": new_user.username}

    except Exception as e:
        db.rollback()
        print("ERROR en /api/register:", e)
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
    finally:
        db.close()
