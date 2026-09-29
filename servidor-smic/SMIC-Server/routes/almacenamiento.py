"""Guarda archivos subidos (snapshots de cámara, clips de video) en Vercel
Blob si está configurado (BLOB_READ_WRITE_TOKEN presente -- el caso en
Vercel), o en disco local si no (el caso en desarrollo con `python app.py`).

Mismo patrón que ya usaba routes/api.py para las carpetas locales, solo que
ahora decide el destino según el entorno en vez de tener siempre disco
local: en Vercel el filesystem no persiste entre invocaciones, así que
guardar en static/uploads o static/videos ahí no serviría de nada."""

import os

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "videos")


def _usa_blob():
    return bool(os.environ.get("BLOB_READ_WRITE_TOKEN"))


def guardar_archivo(datos, nombre, carpeta):
    """datos: bytes del archivo. nombre: nombre de archivo final (ya único).
    carpeta: "uploads" o "videos".

    Devuelve la URL pública (Blob, en Vercel) o la ruta relativa dentro de
    static/ (disco local, en desarrollo) -- lo que se guarda en
    EventoCamara.imagen_path."""
    if _usa_blob():
        from vercel.blob import BlobClient

        with BlobClient() as cliente:
            blob = cliente.put(f"{carpeta}/{nombre}", datos, access="public")
        return blob.url

    destino_dir = UPLOADS_DIR if carpeta == "uploads" else VIDEOS_DIR
    os.makedirs(destino_dir, exist_ok=True)
    ruta_completa = os.path.join(destino_dir, nombre)
    with open(ruta_completa, "wb") as f:
        f.write(datos)
    return f"{carpeta}/{nombre}"
