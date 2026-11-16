from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import requests
import qrcode
import os

# Modelo para recibir el problema desde el celular
class TicketData(BaseModel):
    id_equipo: int
    falla: str
    
app = FastAPI()

# Permite que el frontend (puerto 3000) se comunique con este backend (puerto 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración GLPI
GLPI_API_URL = "http://glpi/apirest.php"
GLPI_WEB_URL = "http://localhost:8080" # URL base de GLPI

# Configuración de Red para QR (Cambia 'localhost' por la IP de tu PC en Wi-Fi, ej: 192.168.1.15)
SERVER_IP = "10.250.204.107"

# Tokens y Credenciales GLPI
APP_TOKEN = "3vnvdFlfoPyx38yIClnyN4kTJ084yZslZcJYK5bX"
GLPI_USER = "glpi" 
GLPI_PASS = "glpi" 

# Configuración Bot de Telegram
TELEGRAM_TOKEN = "9063884850:AAHY2Rel9NhE4pIxONx8W6bo4wG3GCPscRs"
TELEGRAM_CHAT_ID = "6491267113"

HEADERS = {
    "App-Token": APP_TOKEN,
    "Content-Type": "application/json"
}

def iniciar_sesion():
    url = f"{GLPI_API_URL}/initSession"
    res = requests.get(url, headers=HEADERS, auth=(GLPI_USER, GLPI_PASS))
    
    if res.status_code != 200:
        print(f"Error iniciando sesión: {res.text}")
        return None
    return res.json()["session_token"]

def cerrar_sesion(session_token):
    h = HEADERS.copy()
    h["Session-Token"] = session_token
    requests.get(f"{GLPI_API_URL}/killSession", headers=h)

def enviar_alerta_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

@app.post("/sincronizar")
def sincronizar_inventario():
    session_token = iniciar_sesion()
    if not session_token:
        return {"status": "error", "message": "No se pudo conectar a GLPI. Verifica los tokens y la URL."}
    
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
            
            # Apunta a la pantalla móvil usando la variable SERVER_IP
            url_activo = f"http://{SERVER_IP}:8000/reportar/{id_glpi}"
            
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

# ==========================================
# ENDPOINTS: REPORTE POR QR Y ALERTAS
# ==========================================

@app.get("/reportar/{id_equipo}", response_class=HTMLResponse)
def pantalla_reporte(id_equipo: int):
    html_content = f"""
    <html>
        <head>
            <title>Soporte TI</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
        </head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px; background-color: #f4f4f9;">
            <h2 style="color: #333;">Reportar falla en Equipo #{id_equipo}</h2>
            <p>Toca el problema que presenta el equipo:</p>
            
            <button onclick="enviarFalla('No enciende / No da video')" style="width: 100%; padding: 20px; margin: 10px 0; background: #e74c3c; color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold;">🚨 No enciende</button>
            <button onclick="enviarFalla('Error de red / Sin internet')" style="width: 100%; padding: 20px; margin: 10px 0; background: #f39c12; color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold;">🌐 Sin red</button>
            <button onclick="enviarFalla('Falla física / Atasco / Daño')" style="width: 100%; padding: 20px; margin: 10px 0; background: #3498db; color: white; border: none; border-radius: 8px; font-size: 18px; font-weight: bold;">⚙️ Daño físico</button>
            
            <script>
                function enviarFalla(problema) {{
                    fetch('/crear_ticket', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{id_equipo: {id_equipo}, falla: problema}})
                    }}).then(res => res.json())
                      .then(data => {{
                          alert('✅ ¡Ticket creado con éxito! El equipo de TI va en camino.');
                          document.body.innerHTML = "<h2 style='color:green; margin-top:50px;'>Ticket Reportado. Gracias.</h2>";
                      }});
                }}
            </script>
        </body>
    </html>
    """
    return html_content

@app.post("/crear_ticket")
def crear_ticket(data: TicketData):
    session_token = iniciar_sesion()
    if not session_token:
        return {"status": "error"}
        
    h = HEADERS.copy()
    h["Session-Token"] = session_token
    
    # Estructura del Ticket en GLPI
    payload = {
        "input": {
            "name": f"¡URGENTE! Falla reportada vía QR: {data.falla}",
            "content": f"El gerente escaneó el QR y reportó el problema: <b>{data.falla}</b>.<br><br>Por favor, revisar el <b>Equipo con ID GLPI: {data.id_equipo}</b> de inmediato.",
            "status": 1, # 1 = Nuevo
            "urgency": 4 # 4 = Urgencia Alta
        }
    }
    
    # Llamada POST a GLPI para inyectar el ticket
    res = requests.post(f"{GLPI_API_URL}/Ticket", headers=h, json=payload)
    cerrar_sesion(session_token)
    
    # Enviar notificación push a Telegram si el ticket se creó en GLPI
    if res.status_code == 201:
        id_ticket_glpi = res.json().get("id", "Desconocido")
        mensaje_alerta = (
            f"🚨 <b>¡NUEVA INCIDENCIA REPORTADA!</b>\n\n"
            f"<b>Equipo ID:</b> {data.id_equipo}\n"
            f"<b>Falla:</b> {data.falla}\n"
            f"<b>Ticket GLPI:</b> #{id_ticket_glpi}\n\n"
            f"Atender de inmediato."
        )
        enviar_alerta_telegram(mensaje_alerta)
    
    return {"status": "success", "data": res.json()}