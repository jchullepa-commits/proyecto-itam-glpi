from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import qrcode
import os

app = FastAPI()

# Permite que el frontend (puerto 3000) se comunique con este backend (puerto 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración GLPI
# 'glpi' es el nombre del contenedor en la red de Docker
GLPI_API_URL = "http://glpi/apirest.php"
GLPI_WEB_URL = "http://localhost:8080" # URL para los códigos QR

# ¡IMPORTANTE! Reemplaza esto después de configurar GLPI en el Paso 5
APP_TOKEN = "TU_APP_TOKEN"
USER_TOKEN = "TU_USER_TOKEN"

HEADERS = {
    "App-Token": APP_TOKEN,
    "Authorization": f"user_token {USER_TOKEN}",
    "Content-Type": "application/json"
}

def iniciar_sesion():
    res = requests.get(f"{GLPI_API_URL}/initSession", headers=HEADERS)
    if res.status_code != 200:
        return None
    return res.json()["session_token"]

def cerrar_sesion(session_token):
    h = HEADERS.copy()
    h["Session-Token"] = session_token
    requests.get(f"{GLPI_API_URL}/killSession", headers=h)

@app.post("/sincronizar")
def sincronizar_inventario():
    session_token = iniciar_sesion()
    if not session_token:
        return {"status": "error", "message": "No se pudo conectar a GLPI. Verifica los tokens."}
    
    h = HEADERS.copy()
    h["Session-Token"] = session_token
    
    equipos = [
        {"nombre": "POS-CAJA-01", "serie": "SN-998811", "qr": "QR-LIM-01", "sede": "Lima"},
        {"nombre": "KDS-COCINA-01", "serie": "SN-774410", "qr": "QR-LIM-02", "sede": "Lima"}
    ]
    
    resultados = []
    os.makedirs("etiquetas_qr", exist_ok=True)
    
    for eq in equipos:
        payload = {"input": {"name": eq["nombre"], "serial": eq["serie"], "otherserial": eq["qr"], "comment": eq["sede"]}}
        res = requests.post(f"{GLPI_API_URL}/Computer", headers=h, json=payload)
        
        if res.status_code == 201:
            id_glpi = res.json()["id"]
            url_activo = f"{GLPI_WEB_URL}/front/computer.form.php?id={id_glpi}"
            
            # Generar QR
            qr = qrcode.make(url_activo)
            qr.save(f"etiquetas_qr/{eq['qr']}.png")
            resultados.append(f"Registrado: {eq['nombre']} (ID: {id_glpi})")
        else:
            resultados.append(f"Error en {eq['nombre']}: {res.text}")
            
    cerrar_sesion(session_token)
    return {"status": "success", "data": resultados}

@app.get("/resumen")
def obtener_resumen():
    session_token = iniciar_sesion()
    if not session_token:
        return {"status": "error", "total": 0}
        
    h = HEADERS.copy()
    h["Session-Token"] = session_token
    res = requests.get(f"{GLPI_API_URL}/Computer", headers=h)
    cerrar_sesion(session_token)
    
    equipos = res.json() if res.status_code == 200 else []
    return {"status": "success", "total": len(equipos), "equipos": equipos}