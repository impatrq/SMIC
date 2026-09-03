import time
import re
import json

try:
    import serial
    _PYSERIAL_DISPONIBLE = True
except ImportError:
    _PYSERIAL_DISPONIBLE = False
    print(
        "[SIM800L] La libreria 'pyserial' no esta instalada "
        "(agregala con: pip install pyserial). "
        "Las alertas por SIM800L quedan deshabilitadas, el resto de SMIC sigue funcionando normal."
    )

# --- Configuración ---
PUERTO = "/dev/serial0"
BAUD = 9600
APN = "igprs.claro.com.ar"  # chip prepago Claro

# URL pública del servidor (Flask local expuesto por ngrok con subdominio
# reservado). IMPORTANTE: el SIM800L NO soporta el handshake SSL/TLS que
# exige el endpoint https:// de ngrok (falla con error de modulo 606), asi
# que esto tiene que ser HTTP plano. Para eso ngrok se levanta con:
#   ngrok http 5000 --scheme http
# (si se usa el esquema https normal, ngrok redirige el HTTP a HTTPS y el
# modulo tampoco puede seguir ese redirect).
SERVER_URL = "http://enticing-squeamish-cornea.ngrok-free.dev/api/alerta"


def _at(ser, comando, espera=1.5):
    ser.reset_input_buffer()
    ser.write((comando + "\r").encode())
    time.sleep(espera)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore")


def _esperar_urc(ser, prefijo, timeout=30):
    """Espera activamente una respuesta asincronica (URC) del modulo, tipo
    '+HTTPACTION: ...'. OJO: hay que buscar el prefijo con los dos puntos
    (ej. '\\n+HTTPACTION:') y no solo '+HTTPACTION', porque el eco del
    comando 'AT+HTTPACTION=1' tambien contiene esa substring y corta la
    espera antes de tiempo."""
    fin = time.time() + timeout
    buffer = ""
    while time.time() < fin:
        if ser.in_waiting:
            buffer += ser.read(ser.in_waiting).decode(errors="ignore")
            if prefijo in buffer:
                time.sleep(0.5)
                if ser.in_waiting:
                    buffer += ser.read(ser.in_waiting).decode(errors="ignore")
                return buffer
        time.sleep(0.3)
    return buffer


def _abrir_bearer(ser, apn=APN):
    _at(ser, 'AT+SAPBR=3,1,"Contype","GPRS"')
    _at(ser, f'AT+SAPBR=3,1,"APN","{apn}"')
    resp = _at(ser, "AT+SAPBR=1,1", espera=3)
    return "ERROR" not in resp


def _cerrar_bearer(ser):
    _at(ser, "AT+SAPBR=0,1")


def _obtener_ubicacion(ser):
    """Ubicación aproximada por triangulación de antenas GSM (no hay GPS
    todavía). Reutiliza la sesión de datos que ya abrió _abrir_bearer."""
    salida = _at(ser, "AT+CIPGSMLOC=1,1", espera=4)
    m = re.search(r"\+CIPGSMLOC:\s*(\d+),([\-\d.]+),([\-\d.]+)", salida)
    if m and m.group(1) == "0":
        return {"lon": float(m.group(2)), "lat": float(m.group(3))}
    return None


def mandar_alerta_sim(tipo_evento):
    """Manda SOLO el tipo de evento + la ubicación aproximada al servidor,
    por la conexión de datos del SIM800L (independiente del WiFi/Ethernet
    local). No manda el clip ni ningún otro dato del evento -- el clip se
    graba y queda guardado en la RPi4 (ver camara/monitor.py y
    sensores/sincronizador.py), y se sube recién cuando el sistema detecta
    conexión a la red local (por ejemplo al conectarse a una computadora),
    no en el momento del evento.

    Manda tipo/timestamp/lat/lon como campos separados (no como un mensaje
    de texto armado) al endpoint /api/alerta del servidor (routes/api.py),
    para que el panel pueda dibujar cada evento como un marcador propio en
    el mapa, con su tipo y ubicación.
    """
    if not _PYSERIAL_DISPONIBLE:
        return False

    try:
        ser = serial.Serial(PUERTO, BAUD, timeout=2)
    except Exception as e:
        print(f"[SIM800L] No se pudo abrir el puerto serie: {e}")
        return False

    # Por si quedo una sesion HTTP colgada de un intento anterior
    _at(ser, "AT+HTTPTERM", espera=2)
    _at(ser, "AT+SAPBR=0,1", espera=2)

    if not _abrir_bearer(ser):
        ser.close()
        print("[SIM800L] Sin GPRS en este momento, no se pudo mandar la alerta")
        return False

    ubicacion = _obtener_ubicacion(ser)

    payload = {
        "tipo": tipo_evento.lower(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "lat": ubicacion["lat"] if ubicacion else None,
        "lon": ubicacion["lon"] if ubicacion else None,
        "fuente_ubicacion": "GSM" if ubicacion else None,
    }
    body = json.dumps(payload)

    _at(ser, "AT+HTTPINIT", espera=2)
    _at(ser, 'AT+HTTPPARA="CID",1', espera=1)
    _at(ser, "AT+HTTPSSL=0", espera=1)  # el modulo no soporta el TLS de ngrok, HTTP plano
    _at(ser, f'AT+HTTPPARA="URL","{SERVER_URL}"', espera=1)
    _at(ser, 'AT+HTTPPARA="CONTENT","application/json"', espera=1)

    ser.write(f"AT+HTTPDATA={len(body)},10000\r".encode())
    time.sleep(1)
    ser.write(body.encode())
    time.sleep(2)

    ser.reset_input_buffer()
    ser.write(b"AT+HTTPACTION=1\r")  # 1 = POST
    resp_action = _esperar_urc(ser, "\n+HTTPACTION:", timeout=30)

    _at(ser, "AT+HTTPREAD", espera=2)
    _at(ser, "AT+HTTPTERM", espera=2)
    _cerrar_bearer(ser)
    ser.close()

    # Codigo de resultado viene como "+HTTPACTION: <metodo>,<status>,<largo>"
    m = re.search(r"\+HTTPACTION:\s*\d+,(\d+),", resp_action)
    codigo = int(m.group(1)) if m else None
    exito = codigo is not None and 200 <= codigo < 300

    print(f"[SIM800L] Alerta {'enviada' if exito else 'fallida'} (codigo {codigo}): {payload}")
    return exito


if __name__ == "__main__":
    # Prueba manual: python -m comunicacion.sim800l
    mandar_alerta_sim("prueba")
