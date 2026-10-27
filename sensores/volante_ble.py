import asyncio
import json
import threading
import time
import os
import requests
from bleak import BleakClient, BleakScanner

SERVER              = os.environ.get("SMIC_SERVER_URL", "https://smic-henna.vercel.app")
API_KEY             = os.environ.get("SMIC_API_KEY", "")
NOMBRE_ESP32        = "SMIC-Volante"
CHARACTERISTIC_UUID = "abcdefab-cdef-abcd-efab-cdefabcdefab"

ultimo_dato = {
    "valor":    0,
    "contacto": False
}

def _post(url, datos):
    try:
        headers = {"X-API-Key": API_KEY} if API_KEY else {}
        requests.post(url, json=datos, headers=headers, timeout=10)
    except Exception as e:
        print(f"[SERVER] Error: {e}")

INTERVALO_POST_S = 5          # reenvio periodico si no cambia el contacto (WiFi)
_ultimo_post = {"t": 0.0, "contacto": None}


def _por_ppp():
    """True si la salida a internet es ppp0 (datos moviles)."""
    try:
        import subprocess
        out = subprocess.run(["ip", "route", "get", "1.1.1.1"],
                             capture_output=True, text=True, timeout=3).stdout
        return " dev ppp" in out
    except Exception:
        return False


def _debe_enviar(contacto):
    """Evita mandar un POST por cada notificacion (~5 por segundo).
    Siempre manda cuando cambia el contacto; por WiFi ademas cada INTERVALO_POST_S.
    Por datos moviles solo cuando cambia (para no ocupar el enlace de las alertas)."""
    ahora = time.time()
    cambio = _ultimo_post["contacto"] != contacto
    if cambio or (not _por_ppp() and ahora - _ultimo_post["t"] >= INTERVALO_POST_S):
        _ultimo_post["t"] = ahora
        _ultimo_post["contacto"] = contacto
        return True
    return False


def recibir_datos(sender, data: bytearray):
    texto = data.decode("utf-8")
    try:
        datos = json.loads(texto)
        ultimo_dato["valor"]    = datos.get("valor", 0)
        ultimo_dato["contacto"] = bool(datos.get("contacto", 0))

        estado = "TOCANDO" if ultimo_dato["contacto"] else "SIN CONTACTO"
        print(f"[BLE] Valor: {ultimo_dato['valor']} → {estado}")

        sin_contacto = not ultimo_dato["contacto"]
        payload = {
            "dispositivo": "SMIC-Volante",
            "tipo":        "contacto_volante",
            "valor":       int(ultimo_dato["contacto"]),
            "unidad":      "",
            "alerta":      sin_contacto,
            "mensaje":     "Sin contacto con el volante" if sin_contacto else ""
        }
        if _debe_enviar(ultimo_dato["contacto"]):
            threading.Thread(target=_post, args=(f"{SERVER}/api/sensor", payload), daemon=True).start()

    except json.JSONDecodeError:
        print(f"[BLE] Error parseando: {texto}")

async def buscar_esp32():
    while True:
        print("[BLE] Escaneando...")
        dispositivos = await BleakScanner.discover(timeout=5.0)

        for d in dispositivos:
            if d.name == NOMBRE_ESP32:
                print(f"[BLE] Encontrado en {d.address}")
                return d.address

        print("[BLE] No encontrado, reintentando en 3s...")
        await asyncio.sleep(3)

async def conectar():
    while True:
        direccion = await buscar_esp32()
        try:
            async with BleakClient(direccion) as client:
                print("[BLE] Conectado correctamente")
                await client.start_notify(CHARACTERISTIC_UUID, recibir_datos)

                while client.is_connected:
                    await asyncio.sleep(1.0)

        except Exception as e:
            print(f"[BLE] Conexion perdida: {e}")
            print("[BLE] Reconectando en 2s...")
            await asyncio.sleep(2)

def iniciar_ble():
    asyncio.run(conectar())

def _hilo_ble():
    while True:
        try:
            iniciar_ble()
        except Exception as e:
            print(f"[BLE] Error: {e} -- reintentando en 10s")
            time.sleep(10)


def iniciar_volante():
    """Lanza el receptor BLE del volante en un hilo daemon (no bloquea el monitor)."""
    threading.Thread(target=_hilo_ble, daemon=True, name="volante-ble").start()
    print("[BLE] Receptor del volante iniciado")


if __name__ == "__main__":
    iniciar_ble()

