import os
import time
import threading
import requests
from datetime import datetime

SERVER        = "http://192.168.137.1:5000"
CARPETA_CLIPS = os.path.expanduser("~/SMIC/eventos")
MAX_CLIPS     = 50
INTERVALO     = 30  # segundos entre intentos de sincronización

# Extensiones de clip que maneja el sistema, con el content-type
# correcto para cada una (la dashcam guarda .mp4, la camara del
# conductor guarda .avi -- ver dashcam.py y monitor.py).
CONTENT_TYPE_POR_EXTENSION = {
    ".avi": "video/x-msvideo",
    ".mp4": "video/mp4",
}


def es_clip(nombre_archivo):
    """True si el archivo es un clip de video que el sincronizador
    debe manejar (de cualquiera de las 2 camaras)."""
    return os.path.splitext(nombre_archivo)[1].lower() in CONTENT_TYPE_POR_EXTENSION


def listar_clips():
    """Lista todos los clips pendientes en la carpeta de eventos,
    de ambas camaras (antes solo se listaban los .avi de la camara
    del conductor -- los .mp4 de la dashcam quedaban afuera y nunca
    se subian ni se limpiaban)."""
    return sorted([
        os.path.join(CARPETA_CLIPS, f)
        for f in os.listdir(CARPETA_CLIPS)
        if es_clip(f)
    ])


def hay_conexion():
    """Verifica si el servidor está accesible."""
    try:
        requests.get(f"{SERVER}/api/resumen", timeout=3)
        return True
    except:
        return False


def _info_clip(ruta_clip):
    """
    Deduce fuente/tipo/timestamp a partir del nombre del archivo.

    Nombres esperados (ver monitor.py y dashcam.py):
      - Camara del conductor: "{TIPO}_{timestamp}.avi"
        p.ej. "SOMNOLENCIA_20260714_162938.avi"
      - Dashcam:               "dashcam_{TIPO}_{timestamp}.mp4"
        p.ej. "dashcam_SOMNOLENCIA_20260714_162927.mp4"

    Devuelve (fuente, tipo, timestamp, content_type).
    """
    nombre     = os.path.basename(ruta_clip)
    base, ext  = os.path.splitext(nombre)
    ext        = ext.lower()

    if base.lower().startswith("dashcam_"):
        fuente = "dashcam"
        base   = base[len("dashcam_"):]
    else:
        fuente = "conductor"

    partes    = base.split("_")
    tipo      = partes[0].lower()
    timestamp = "_".join(partes[1:])

    content_type = CONTENT_TYPE_POR_EXTENSION.get(ext, "application/octet-stream")

    return fuente, tipo, timestamp, content_type


def enviar_clip(ruta_clip):
    """Envía un clip al servidor (de cualquiera de las 2 camaras).
    Devuelve True si fue exitoso."""
    nombre = os.path.basename(ruta_clip)
    try:
        fuente, tipo, timestamp, content_type = _info_clip(ruta_clip)

        with open(ruta_clip, "rb") as f:
            r = requests.post(
                f"{SERVER}/api/video",
                files={"video": (nombre, f, content_type)},
                data={
                    "tipo":        tipo,
                    "fuente":      fuente,
                    "descripcion": f"Clip {tipo} ({fuente}) — {timestamp}"
                },
                timeout=60
            )

        if r.status_code == 201:
            print(f"[SYNC] Enviado: {nombre} (fuente={fuente})")
            return True
        else:
            print(f"[SYNC] Error servidor: {r.status_code}")
            return False

    except Exception as e:
        print(f"[SYNC] Error enviando {nombre}: {e}")
        return False


def limpiar_clips_viejos():
    """Si hay más de MAX_CLIPS (contando las 2 camaras juntas), borra
    los más antiguos."""
    clips = listar_clips()

    while len(clips) > MAX_CLIPS:
        clip_viejo = clips.pop(0)
        os.remove(clip_viejo)
        print(f"[SYNC] Borrado por límite: {os.path.basename(clip_viejo)}")


def sincronizar():
    """Intenta enviar todos los clips pendientes de ambas camaras."""
    os.makedirs(CARPETA_CLIPS, exist_ok=True)

    clips = listar_clips()

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
