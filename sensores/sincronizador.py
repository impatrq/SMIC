import os
import subprocess
import time
import threading
import requests
from datetime import datetime

# URL pública del servidor en Vercel. Antes era la IP del hotspot de la PC
# (http://192.168.137.1:5000), que solo funcionaba mientras la RPi estaba
# enganchada a ese hotspot -- con esto sincroniza apenas tenga cualquier
# conexión a internet (WiFi de casa, etc).
SERVER = os.environ.get("SMIC_SERVER_URL", "https://CAMBIAR-por-tu-url.vercel.app")

# Mismo header que exige routes/api.py (@requiere_api_key) en /api/video,
# /api/resumen, etc. Configurar como variable de entorno en la RPi, mismo
# valor que SMIC_API_KEY en las Environment Variables de Vercel.
API_KEY = os.environ.get("SMIC_API_KEY", "")

CARPETA_CLIPS = os.path.expanduser("~/SMIC/eventos")
MAX_CLIPS     = 50
INTERVALO     = 30  # segundos entre intentos de sincronización

# Se puede pisar con la variable de entorno SMIC_FFMPEG si el binario no
# está en el PATH (en Raspberry Pi OS: sudo apt install ffmpeg).
FFMPEG = os.environ.get("SMIC_FFMPEG", "ffmpeg")

# Extensiones de clip que maneja el sistema, con el content-type
# correcto para cada una (la dashcam guarda .mp4, la camara del
# conductor guarda .avi -- ver dashcam.py y monitor.py).
CONTENT_TYPE_POR_EXTENSION = {
    ".avi": "video/x-msvideo",
    ".mp4": "video/mp4",
}


def _headers_api():
    return {"X-API-Key": API_KEY} if API_KEY else {}


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
        requests.get(f"{SERVER}/api/resumen", headers=_headers_api(), timeout=3)
        return True
    except Exception:
        return False


def _info_clip(ruta_clip):
    """
    Deduce fuente/tipo/evento_id a partir del nombre del archivo.

    Nombres esperados (ver monitor.py y dashcam.py):
      - Camara del conductor: "{TIPO}_{evento_id}.avi"
        p.ej. "SOMNOLENCIA_20260714_162938_123456.avi"
      - Dashcam:               "dashcam_{TIPO}_{evento_id}.mp4"
        p.ej. "dashcam_SOMNOLENCIA_20260714_162938_123456.mp4"

    evento_id es el mismo string para el clip del conductor y el de la
    dashcam de un mismo evento (lo genera monitor.py una sola vez en
    disparar_evento y se lo pasa a las 2 camaras), así que sirve para
    que el servidor los empareje sin depender de a qué hora exacta
    terminó de escribirse cada archivo.

    Devuelve (fuente, tipo, evento_id).
    """
    nombre    = os.path.basename(ruta_clip)
    base, ext = os.path.splitext(nombre)

    if base.lower().startswith("dashcam_"):
        fuente = "dashcam"
        base   = base[len("dashcam_"):]
    else:
        fuente = "conductor"

    partes    = base.split("_")
    tipo      = partes[0].lower()
    evento_id = "_".join(partes[1:])

    return fuente, tipo, evento_id


def _recodificar_a_mp4(ruta_clip):
    """Recodifica el clip a H.264/mp4 con ffmpeg antes de subirlo, para que
    se pueda reproducir en el navegador (el .avi XVID de la camara del
    conductor y el .mp4 con codec mp4v de la dashcam no se reproducen bien
    en Chrome/Firefox sin recodificar).

    Antes este paso lo hacia el servidor (routes/api.py) al recibir el
    clip. Se movio aca porque en Vercel no hay binario de ffmpeg
    disponible -- y de paso, al recodificar en la RPi antes de subir, el
    archivo que viaja a Blob ya sale liviano.

    Devuelve la ruta del archivo recodificado, o la ruta original si
    ffmpeg no esta disponible o falla (se sube el clip crudo antes que no
    subir nada)."""
    base, _  = os.path.splitext(ruta_clip)
    ruta_mp4 = base + "_h264.mp4"

    try:
        subprocess.run(
            [FFMPEG, "-i", ruta_clip, "-c:v", "libx264", "-preset", "fast",
             "-crf", "28", "-c:a", "aac", "-y", ruta_mp4],
            capture_output=True, timeout=120, check=True
        )
        return ruta_mp4
    except Exception as e:
        print(f"[SYNC] ffmpeg falló, se sube el clip sin recodificar: {e}")
        return ruta_clip


def enviar_clip(ruta_clip):
    """Sube un clip directo a Vercel Blob y avisa al servidor con un JSON
    chico para que quede registrado el evento. Devuelve True si fue
    exitoso.

    Subir directo a Blob (en vez de mandar el archivo por POST a
    /api/video como antes) evita el limite de 4.5 MB por request que
    tienen las Vercel Functions -- ese limite aplica a lo que recibe
    app.py, no a Blob."""
    nombre = os.path.basename(ruta_clip)
    ruta_recodificada = None

    try:
        from vercel.blob import BlobClient

        fuente, tipo, evento_id = _info_clip(ruta_clip)

        ruta_subida = _recodificar_a_mp4(ruta_clip)
        if ruta_subida != ruta_clip:
            ruta_recodificada = ruta_subida

        nombre_subida = os.path.basename(ruta_subida)
        with open(ruta_subida, "rb") as f:
            datos = f.read()

        with BlobClient() as cliente:
            blob = cliente.put(f"videos/{nombre_subida}", datos, access="public")

        r = requests.post(
            f"{SERVER}/api/video",
            json={
                "tipo":          tipo,
                "fuente":        fuente,
                "evento_id":     evento_id,
                "video_url":     blob.url,
                "nombre_archivo": nombre_subida,
                "descripcion":   f"Clip {tipo} ({fuente}) — {evento_id}",
            },
            headers=_headers_api(),
            timeout=30,
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
    finally:
        if ruta_recodificada and os.path.exists(ruta_recodificada):
            os.remove(ruta_recodificada)


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
        print("[SYNC] Sin conexión al servidor — esperando internet")
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
    print(f"[SYNC] Sincronizador iniciado — revisa cada {INTERVALO}s — servidor: {SERVER}")
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
