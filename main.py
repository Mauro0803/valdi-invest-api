import math
import yfinance as yf
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, Field
from typing import Optional

# --- CONFIGURACIÓN BASE ---
DATABASE_URL = "sqlite:///./inversiones.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Transaccion(Base):
    __tablename__ = "transacciones"
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(String)
    entidad = Column(String)
    acciones = Column(Integer)
    precio_compra = Column(Float)
    monto_total_compra = Column(Integer)

Base.metadata.create_all(bind=engine)

class TransaccionCreate(BaseModel):
    fecha: Optional[str] = None
    entidad: str
    acciones: int
    precio_compra: float

def calcular_comision_iva(monto: int):
    if monto <= 0: return 0
    neto = math.floor(2500 + (monto * 0.006))
    return neto + round(neto * 0.19)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- ENDPOINTS ---

@app.post("/transacciones/")
def crear_transaccion(t: TransaccionCreate, db: Session = Depends(get_db)):
    # Si no hay fecha, usamos la de hoy
    fecha_final = t.fecha if t.fecha else datetime.now().strftime("%Y-%m-%d")
    
    inv_compra = round(t.acciones * t.precio_compra)
    total_compra = inv_compra + calcular_comision_iva(inv_compra)
    
    nueva = Transaccion(
        fecha=fecha_final,
        entidad=t.entidad.upper(),
        acciones=t.acciones,
        precio_compra=t.precio_compra,
        monto_total_compra=total_compra
    )
    db.add(nueva)
    db.commit()
    return {"status": "ok"}

@app.get("/transacciones/")
def listar_completo(db: Session = Depends(get_db)):
    transacciones = db.query(Transaccion).all()
    resultado = []

    for t in transacciones:
        # 1. Obtener precio actual (Yahoo Finance)
        try:
            ticker_yf = yf.Ticker(t.entidad)
            precio_actual = ticker_yf.fast_info['lastPrice']
        except:
            precio_actual = 0

        # 2. Monto total si vendo (Ingreso bruto - comisión salida)
        ingreso_bruto_venta = round(t.acciones * precio_actual)
        total_venta_neta = ingreso_bruto_venta - calcular_comision_iva(ingreso_bruto_venta)
        
        # 3. Ganancia final
        ganancia = total_venta_neta - t.monto_total_compra

        resultado.append({
            "id": t.id,
            "fecha": t.fecha,
            "entidad": t.entidad,
            "acciones": t.acciones,
            "precio_compra": t.precio_compra,
            "costo_total": t.monto_total_compra,
            "precio_actual": round(precio_actual, 2),
            "monto_venta_neta": total_venta_neta,
            "ganancia": ganancia
        })
    
    return resultado

@app.delete("/transacciones/{id}")
def eliminar(id: int, db: Session = Depends(get_db)):
    item = db.query(Transaccion).filter(Transaccion.id == id).first()
    db.delete(item)
    db.commit()
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
async def home():
    return FileResponse('static/index.html')