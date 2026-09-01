import time
import re

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
APN = "internet"  # TODO: reemplazar por el APN real (Conecty M2M o igprs.claro.com.ar)

# TODO: esto tiene que ser una URL PÚBLICA para que el SIM800L la alcance
# por la red celular -- la IP local (192.168.137.1) que usan sincronizador.py
# y volante_ble.py NO sirve acá, porque la conexión de datos del módulo no
# tiene ruta a esa red local. Para probar ya, exponé tu Flask local con
# ngrok (https://ngrok.com) y pegá acá la URL que te da, con /api/sistema
# al final. Ejemplo: "https://algo-random.ngrok-free.app/api/sistema"
SERVER_URL = "http://192.168.137.1:5000/api/sistema"


def _at(ser, comando, espera=1.5):
    ser.write((comando + "\r").encode())
    time.sleep(espera)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore")


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
    local). No manda video ni ningún otro dato del evento -- eso sigue
    yendo por datos/registro.py + Cloudinary tal como ya está armado.

    Reusa el endpoint /api/sistema que ya existe en el servidor
    (routes/api.py), sin necesidad de agregar nada nuevo del lado del
    servidor.
    """
    if not _PYSERIAL_DISPONIBLE:
        return False

    try:
        ser = serial.Serial(PUERTO, BAUD, timeout=2)
    except Exception as e:
        print(f"[SIM800L] No se pudo abrir el puerto serie: {e}")
        return False

    if not _abrir_bearer(ser):
        ser.close()
        print("[SIM800L] Sin GPRS en este momento, no se pudo mandar la alerta")
        return False

    ubicacion = _obtener_ubicacion(ser)
    if ubicacion:
        link = f"https://maps.google.com/?q={ubicacion['lat']},{ubicacion['lon']}"
        mensaje = f"{tipo_evento.upper()} detectado. Ubicacion (GSM aprox.): {link}"
    else:
        mensaje = f"{tipo_evento.upper()} detectado. Ubicacion no disponible"

    body = (
        '{"nivel":"alerta","fuente":"sim800l","mensaje":"'
        + mensaje.replace('"', "'")
        + '"}'
    )

    _at(ser, "AT+HTTPINIT")
    _at(ser, 'AT+HTTPPARA="CID",1')
    _at(ser, f'AT+HTTPPARA="URL","{SERVER_URL}"')
    _at(ser, 'AT+HTTPPARA="CONTENT","application/json"')

    ser.write(f"AT+HTTPDATA={len(body)},10000\r".encode())
    time.sleep(1)
    ser.write(body.encode())
    time.sleep(2)

    resp_action = _at(ser, "AT+HTTPACTION=1", espera=5)  # 1 = POST
    _at(ser, "AT+HTTPREAD", espera=2)
    _at(ser, "AT+HTTPTERM")
    _cerrar_bearer(ser)
    ser.close()

    exito = ",200," in resp_action or resp_action.strip().endswith("200")
    print(f"[SIM800L] Alerta {'enviada' if exito else 'fallida'}: {mensaje}")
    return exito


if __name__ == "__main__":
    # Prueba manual: python -m comunicacion.sim800l
    mandar_alerta_sim("prueba")
