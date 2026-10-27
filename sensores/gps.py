"""
Lectura del GPS GY-NEO6MV2 (u-blox NEO-6M) por la UART3 de la RPi4
(GPIO4 = TXD3, GPIO5 = RXD3 -> /dev/ttyAMA3) y envío de la posición al
servidor SMIC (POST /api/gps).

Uso:
    python -m sensores.gps                 # corre solo, para probar
o desde otro módulo:
    from sensores.gps import iniciar_gps, ultima_posicion
    iniciar_gps()                          # arranca el hilo en segundo plano
    pos = ultima_posicion()                # dict o None si no hay fix

Requiere en /boot/firmware/config.txt:  dtoverlay=uart3
No hace falta hacer export: el servidor (Vercel) ya queda configurado
abajo. Si en Vercel esta cargada la variable SMIC_API_KEY, poner ese mismo
valor en API_KEY (abajo). Las dos cosas se pueden pisar igual con las
variables de entorno SMIC_SERVER_URL / SMIC_API_KEY.
"""

import os
import time
import threading
from collections import deque

import requests

try:
    import serial
    _PYSERIAL_DISPONIBLE = True
except ImportError:
    _PYSERIAL_DISPONIBLE = False
    print("[GPS] Falta 'pyserial' (pip install pyserial). El GPS queda deshabilitado.")

# --- Configuración ---
PUERTO = os.environ.get("SMIC_GPS_PUERTO", "/dev/ttyAMA3")
BAUD = 9600
# Servidor desplegado en Vercel (mismo que usa sensores/sincronizador.py).
SERVER = os.environ.get("SMIC_SERVER_URL", "https://smic-henna.vercel.app")
# Solo hace falta si en Vercel (Settings > Environment Variables) esta
# cargada SMIC_API_KEY. Si no esta, dejar vacio.
API_KEY = os.environ.get("SMIC_API_KEY", "")

INTERVALO_ENVIO = 10     # segundos entre envíos al servidor
MAX_PENDIENTES = 500     # posiciones guardadas si no hay internet
# El NEO-6M no informa la precisión en metros, solo el HDOP. Se estima
# multiplicando el HDOP por el error típico del receptor (~2,5 m).
ERROR_BASE_M = 2.5

_ultima = None                         # última posición válida
_ultima_ts = 0                         # cuándo se recibió (time.time())
_lock = threading.Lock()
_pendientes = deque(maxlen=MAX_PENDIENTES)


# ── Parseo NMEA ──────────────────────────────────────────────────────────────

def _checksum_ok(linea):
    """Verifica el checksum '*XX' del final de la trama NMEA."""
    if not linea.startswith("$") or "*" not in linea:
        return False
    cuerpo, _, chk = linea[1:].partition("*")
    calculado = 0
    for c in cuerpo:
        calculado ^= ord(c)
    try:
        return calculado == int(chk[:2], 16)
    except ValueError:
        return False


def _a_decimal(valor, hemisferio):
    """Convierte 'ggmm.mmmm' / 'gggmm.mmmm' + N/S/E/W a grados decimales."""
    if not valor or not hemisferio:
        return None
    punto = valor.index(".")
    grados = float(valor[:punto - 2])
    minutos = float(valor[punto - 2:])
    decimal = grados + minutos / 60
    return -decimal if hemisferio in ("S", "W") else decimal


def _float(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


class ParserNMEA:
    """Junta los datos de $GPGGA (posición, altitud, satélites, HDOP) y
    $GPRMC (validez y velocidad) en una sola posición."""

    def __init__(self):
        self.velocidad_kmh = None
        self.rmc_valido = False

    def procesar(self, linea):
        """Devuelve un dict con la posición cuando llega un GGA con fix,
        o None en cualquier otro caso."""
        linea = linea.strip()
        if not _checksum_ok(linea):
            return None
        campos = linea.split("*")[0].split(",")
        tipo = campos[0][3:]          # GPGGA -> GGA, GNRMC -> RMC

        if tipo == "RMC" and len(campos) >= 8:
            self.rmc_valido = campos[2] == "A"
            nudos = _float(campos[7])
            self.velocidad_kmh = round(nudos * 1.852, 1) if nudos is not None else None
            return None

        if tipo == "GGA" and len(campos) >= 10:
            calidad = int(campos[6] or 0)
            if calidad == 0:
                return None           # sin fix
            lat = _a_decimal(campos[2], campos[3])
            lon = _a_decimal(campos[4], campos[5])
            if lat is None or lon is None:
                return None
            hdop = _float(campos[8])
            return {
                "latitud": round(lat, 6),
                "longitud": round(lon, 6),
                "altitud": _float(campos[9]),
                "velocidad": self.velocidad_kmh if self.rmc_valido else None,
                "satelites": int(campos[7] or 0),
                "precision": round(hdop * ERROR_BASE_M, 1) if hdop else None,
            }
        return None


# ── Envío al servidor ────────────────────────────────────────────────────────

def _enviar(posicion):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    r = requests.post(f"{SERVER}/api/gps", json=posicion, headers=headers, timeout=15)
    r.raise_for_status()


def _vaciar_pendientes():
    """Manda las posiciones acumuladas. Si falla una, corta y reintenta
    en el próximo ciclo (no se pierde nada, queda en la cola)."""
    while _pendientes:
        try:
            _enviar(_pendientes[0])
            _pendientes.popleft()
        except Exception as e:
            print(f"[GPS] Sin conexión con el servidor ({len(_pendientes)} pendientes): {e}")
            return


# ── Loop principal ───────────────────────────────────────────────────────────

def ultima_posicion(max_edad=None):
    """Última posición válida del GPS (dict) o None si todavía no hubo fix.

    Si se pasa max_edad (segundos), devuelve None cuando la última posición
    es más vieja que eso (por ejemplo, si se perdió el fix)."""
    with _lock:
        if not _ultima:
            return None
        if max_edad is not None and time.time() - _ultima_ts > max_edad:
            return None
        return dict(_ultima)


def _loop(enviar=True):
    global _ultima, _ultima_ts
    parser = ParserNMEA()
    ultimo_envio = 0

    while True:
        try:
            with serial.Serial(PUERTO, BAUD, timeout=2) as ser:
                print(f"[GPS] Leyendo {PUERTO} a {BAUD} baudios")
                while True:
                    linea = ser.readline().decode("ascii", errors="ignore")
                    pos = parser.procesar(linea)
                    if not pos:
                        continue
                    with _lock:
                        _ultima = pos
                        _ultima_ts = time.time()
                    if enviar and time.time() - ultimo_envio >= INTERVALO_ENVIO:
                        ultimo_envio = time.time()
                        _pendientes.append(pos)
                        _vaciar_pendientes()
        except serial.SerialException as e:
            print(f"[GPS] Error en {PUERTO}: {e}. Reintento en 5 s")
            time.sleep(5)


def iniciar_gps(enviar=True):
    """Arranca la lectura del GPS en un hilo en segundo plano."""
    if not _PYSERIAL_DISPONIBLE:
        return None
    hilo = threading.Thread(target=_loop, args=(enviar,), daemon=True, name="gps")
    hilo.start()
    return hilo


if __name__ == "__main__":
    iniciar_gps()
    try:
        while True:
            time.sleep(INTERVALO_ENVIO)
            p = ultima_posicion()
            if p:
                print(f"[GPS] {p['latitud']}, {p['longitud']} | "
                      f"{p['satelites']} sat | {p['velocidad']} km/h | ±{p['precision']} m")
            else:
                print("[GPS] Esperando fix...")
    except KeyboardInterrupt:
        print("[GPS] Cerrado")
