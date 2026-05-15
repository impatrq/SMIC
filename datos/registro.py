import cv2
import cloudinary
import cloudinary.uploader
from collections import deque
from datetime import datetime
from datos.modelos import db, Evento

cloudinary.config(
    cloud_name = "dvg5ueuud",
    api_key    = "571683145839348",
    api_secret = "NLarQvbRL4_XPsKjXBOl_keQzpI"
)

FPS              = 20
SEGUNDOS_ANTES   = 10
SEGUNDOS_DESPUES = 10
FRAMES_BUFFER    = FPS * SEGUNDOS_ANTES

class BufferVideo:
    def __init__(self):
        self.frames = deque(maxlen=FRAMES_BUFFER)

    def agregar_frame(self, frame):
        self.frames.append(frame.copy())

    def obtener_frames_anteriores(self):
        return list(self.frames)

def grabar_clip(camara, buffer, duracion_seg=SEGUNDOS_DESPUES):
    nombre = f"smic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(nombre, fourcc, float(FPS), (640, 480))

    for frame in buffer.obtener_frames_anteriores():
        writer.write(frame)

    for _ in range(FPS * duracion_seg):
        ret, frame = camara.read()
        if ret:
            writer.write(frame)

    writer.release()
    return nombre

def subir_video(ruta_archivo):
    try:
        resultado = cloudinary.uploader.upload(
            ruta_archivo,
            resource_type = "video",
            folder        = "smic_eventos"
        )
        return resultado["secure_url"]
    except Exception as e:
        print(f"Error subiendo video: {e}")
        return None

def guardar_evento(tipo, camara, buffer, duracion,
                   volante=True, latitud=-34.7204, longitud=-58.2538):
    archivo = grabar_clip(camara, buffer)
    url     = subir_video(archivo)
    evento  = Evento(
        tipo     = tipo,
        duracion = duracion,
        clip_url = url,
        latitud  = latitud,
        longitud = longitud,
        volante  = volante
    )
    db.session.add(evento)
    db.session.commit()
    print(f"Evento guardado: {tipo} — {url}")
    return evento