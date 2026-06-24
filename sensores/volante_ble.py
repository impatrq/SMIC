import asyncio
import json
import threading
import requests
from bleak import BleakClient, BleakScanner

SERVER              = "http://192.168.137.1:5000"
NOMBRE_ESP32        = "SMIC-Volante"
CHARACTERISTIC_UUID = "abcdefab-cdef-abcd-efab-cdefabcdefab"

ultimo_dato = {
    "valor":    0,
    "contacto": False
}

def _post(url, datos):
    try:
        requests.post(url, json=datos, timeout=2)
    except Exception as e:
        print(f"[SERVER] Error: {e}")

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

if __name__ == "__main__":
    iniciar_ble()

