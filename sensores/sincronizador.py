import os
import time
import threading
import requests
from datetime import datetime

SERVER        = "http://192.168.137.1:5000"
CARPETA_CLIPS = os.path.expanduser("~/SMIC/eventos")
MAX_CLIPS     = 50
INTERVALO     = 30  # segundos entre intentos de sincronización

def hay_conexion():
    """Verifica si el servidor está accesible."""
    try:
        requests.get(f"{SERVER}/api/resumen", timeout=3)
        return True
    except:
        return False

def enviar_clip(ruta_clip):
    """Envía un clip al servidor. Devuelve True si fue exitoso."""
    try:
        nombre    = os.path.basename(ruta_clip)
        tipo      = nombre.split("_")[0].lower()  # somnolencia o distraccion
        timestamp = "_".join(nombre.split("_")[1:]).replace(".avi", "")

        with open(ruta_clip, "rb") as f:
            r = requests.post(
                f"{SERVER}/api/video",
                files={"video": (nombre, f, "video/x-msvideo")},
                data={
                    "tipo":        tipo,
                    "descripcion": f"Clip {tipo} — {timestamp}"
                },
                timeout=60
            )

        if r.status_code == 201:
            print(f"[SYNC] Enviado: {nombre}")
            return True
        else:
            print(f"[SYNC] Error servidor: {r.status_code}")
            return False

    except Exception as e:
        print(f"[SYNC] Error enviando {nombre}: {e}")
        return False

def limpiar_clips_viejos():
    """Si hay más de MAX_CLIPS, borra los más antiguos."""
    clips = sorted([
        os.path.join(CARPETA_CLIPS, f)
        for f in os.listdir(CARPETA_CLIPS)
        if f.endswith(".avi")
    ])

    while len(clips) > MAX_CLIPS:
        clip_viejo = clips.pop(0)
        os.remove(clip_viejo)
        print(f"[SYNC] Borrado por límite: {os.path.basename(clip_viejo)}")

def sincronizar():
    """Intenta enviar todos los clips pendientes."""
    os.makedirs(CARPETA_CLIPS, exist_ok=True)

    clips = sorted([
        os.path.join(CARPETA_CLIPS, f)
        for f in os.listdir(CARPETA_CLIPS)
        if f.endswith(".avi")
    ])

    if not clips:
        return

    print(f"[SYNC] {len(clips)} clips pendientes")

    if not hay_conexion():
        print("[SYNC] Sin conexión al servidor — esperando WiFi")
        limpiar_clips_viejos()
        return

    for clip in clips:
        if enviar_clip(clip):
            os.remove(clip)
            print(f"[SYNC] Borrado local: {os.path.basename(clip)}")
        else:
            print(f"[SYNC] Reintentará después: {os.path.basename(clip)}")

def bucle_sincronizacion():
    """Corre en segundo plano, sincroniza cada INTERVALO segundos."""
    print(f"[SYNC] Sincronizador iniciado — revisa cada {INTERVALO}s")
    while True:
        try:
            sincronizar()
        except Exception as e:
            print(f"[SYNC] Error inesperado: {e}")
        time.sleep(INTERVALO)

def iniciar_sincronizador():
    """Inicia el sincronizador en un hilo de fondo."""
    hilo = threading.Thread(target=bucle_sincronizacion, daemon=True)
    hilo.start()
    return hilo

if __name__ == "__main__":
    print("=" * 45)
    print("  SMIC - Sincronizador de clips")
    print("=" * 45)
    sincronizar()
