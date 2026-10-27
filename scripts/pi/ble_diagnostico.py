"""Diagnostico BLE del volante: lista servicios/caracteristicas, lee el valor y escucha notificaciones.
Uso en la Pi:
    cd ~/SMIC && ./venv/bin/python -u ~/ppp_smic/ble_diagnostico.py
Durante la escucha (30 s) toca y suelta el sensor del volante.
"""
import asyncio
from bleak import BleakClient, BleakScanner

NOMBRE = "SMIC-Volante"
UUID = "abcdefab-cdef-abcd-efab-cdefabcdefab"
ESCUCHA = 30


def al_recibir(_, data):
    print("  [NOTIFY]", bytes(data))


async def main():
    print("Buscando", NOMBRE, "...")
    d = await BleakScanner.find_device_by_name(NOMBRE, timeout=15)
    if not d:
        print("No encontrado."); return
    print("Encontrado:", d.address)
    async with BleakClient(d) as c:
        print("Conectado. Servicios:")
        for s in c.services:
            print(" servicio", s.uuid)
            for ch in s.characteristics:
                print("   caracteristica", ch.uuid, ch.properties)
                if ch.uuid.lower() == UUID:
                    if "read" in ch.properties:
                        try:
                            print("   valor leido:", bytes(await c.read_gatt_char(ch)))
                        except Exception as e:
                            print("   error leyendo:", e)
        print(f"\nSuscribiendo a {UUID} y escuchando {ESCUCHA} s (toca el sensor)...")
        await c.start_notify(UUID, al_recibir)
        await asyncio.sleep(ESCUCHA)
        print("Fin.")


asyncio.run(main())
