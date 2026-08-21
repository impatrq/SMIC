"""
SMIC - Modulo Dashcam (camara delantera, webcam USB)

Esta camara graba todo el tiempo en un buffer circular en memoria (RAM),
no en disco. Cuando monitor.py detecta un evento (somnolencia, distraccion,
etc), le avisa a este modulo, y este guarda un clip que incluye los
segundos ANTES del evento (que ya estaban en el buffer) mas los segundos
DESPUES del evento (que sigue capturando en tiempo real).

Funciona en paralelo a camara/monitor.py, cada una maneja su propia camara:
- monitor.py -> Picamera2 (CSI) -> camara del conductor
- dashcam.py -> cv2.VideoCapture (USB) -> camara del camino
"""

import cv2
import time
import threading
import os
from collections import deque
from datetime import datetime

# ==================== CONFIGURACION ====================

# Indice del dispositivo de video. Confirmado con v4l2-ctl --list-devices:
# /dev/video1 es "GENERAL WEBCAM" (captura real, tiene formatos MJPG/YUYV).
# /dev/video2 es el nodo de metadata de la misma camara, no sirve para esto.
DASHCAM_INDEX = 1

RESOLUCION_ANCHO = 640
RESOLUCION_ALTO = 480
FPS = 15

# Cuantos segundos guarda ANTES de que ocurra el evento (ya en buffer)
SEGUNDOS_PRE_EVENTO = 10

# Cuantos segundos sigue grabando DESPUES de que ocurre el evento
SEGUNDOS_POST_EVENTO = 10

# Misma carpeta que usa el resto del sistema para guardar clips
CARPETA_EVENTOS = os.path.expanduser("~/SMIC/eventos")


# ==================== CLASE DASHCAM ====================

class Dashcam:
    """Maneja la webcam delantera con un buffer circular en memoria."""

    def __init__(self, index=DASHCAM_INDEX):
        self.camara = cv2.VideoCapture(index)

        if not self.camara.isOpened():
            raise RuntimeError(f"No se pudo abrir la dashcam en el indice {index}")

        self.camara.set(cv2.CAP_PROP_FRAME_WIDTH, RESOLUCION_ANCHO)
        self.camara.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUCION_ALTO)
        self.camara.set(cv2.CAP_PROP_FPS, FPS)

        # deque con maxlen: cuando se llena, cada frame nuevo empuja
        # afuera al mas viejo automaticamente. Asi el buffer siempre
        # tiene los ultimos SEGUNDOS_PRE_EVENTO segundos, ni uno mas
        max_frames_buffer = SEGUNDOS_PRE_EVENTO * FPS
        self.buffer = deque(maxlen=max_frames_buffer)

        # Contador de frames totales capturados. Se usa para saber,
        # durante el guardado de un clip, si ya llego un frame nuevo
        self.contador_frames = 0

        # Lock para que el hilo de captura y el hilo de guardado no
        # accedan al buffer al mismo tiempo y lo corrompan
        self.lock = threading.Lock()

        self.activo = True

        os.makedirs(CARPETA_EVENTOS, exist_ok=True)

        # Hilo que llena el buffer sin parar, en paralelo a todo lo demas
        self.hilo_captura = threading.Thread(target=self._capturar_loop, daemon=True)
        self.hilo_captura.start()

        print("Dashcam iniciada correctamente")

    def _capturar_loop(self):
        """Corre en un hilo aparte. Lee frames de la webcam sin parar
        y los va guardando en el buffer circular."""
        while self.activo:
            ret, frame = self.camara.read()
            if ret:
                with self.lock:
                    self.buffer.append(frame.copy())
                    self.contador_frames += 1
            else:
                # Si por algun motivo falla una lectura, esperamos un
                # instante en vez de saturar el CPU en un loop vacio
                time.sleep(0.05)

    def guardar_clip(self, tipo_evento):
        """Llamar a esta funcion desde monitor.py cuando ocurre un evento.
        No bloquea: dispara un hilo aparte que arma el clip y lo guarda,
        mientras el resto del sistema sigue funcionando normalmente."""
        hilo = threading.Thread(
            target=self._guardar_clip_worker,
            args=(tipo_evento,),
            daemon=True
        )
        hilo.start()

    def _guardar_clip_worker(self, tipo_evento):
        """Arma y escribe el archivo de video: primero los frames que ya
        estaban en el buffer (pre-evento), despues los que van llegando
        en tiempo real (post-evento)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = f"dashcam_{tipo_evento}_{timestamp}.mp4"
        ruta = os.path.join(CARPETA_EVENTOS, nombre_archivo)

        # Copiamos el buffer actual (pre-evento) y anotamos el contador
        # en este instante, para saber a partir de donde son frames nuevos
        with self.lock:
            frames_pre = list(self.buffer)
            ultimo_contador = self.contador_frames

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(ruta, fourcc, FPS, (RESOLUCION_ANCHO, RESOLUCION_ALTO))

        for frame in frames_pre:
            writer.write(frame)

        # Ahora esperamos y escribimos los frames que van llegando
        # despues del evento, hasta juntar los segundos post-evento
        frames_necesarios = SEGUNDOS_POST_EVENTO * FPS
        frames_escritos = 0

        # Margen de seguridad por si la camara va mas lenta que el FPS
        # configurado, para que esto no quede esperando para siempre
        limite_tiempo = time.time() + SEGUNDOS_POST_EVENTO + 3

        while frames_escritos < frames_necesarios and time.time() < limite_tiempo:
            with self.lock:
                hay_frame_nuevo = self.contador_frames > ultimo_contador
                if hay_frame_nuevo:
                    frame_actual = self.buffer[-1]
                    ultimo_contador = self.contador_frames

            if hay_frame_nuevo:
                writer.write(frame_actual)
                frames_escritos += 1
            else:
                time.sleep(0.01)

        writer.release()
        print(f"Clip dashcam guardado: {ruta}")

    def cerrar(self):
        """Frena el hilo de captura y libera la camara. Llamar al
        apagar el sistema."""
        self.activo = False
        self.hilo_captura.join(timeout=2)
        self.camara.release()
        print("Dashcam cerrada correctamente")


# ==================== PRUEBA DIRECTA ====================

if __name__ == "__main__":
    print("=" * 45)
    print(" SMIC - Prueba de dashcam")
    print("=" * 45)

    dash = Dashcam()

    try:
        print("Grabando buffer 3 segundos antes de simular el evento...")
        time.sleep(3)

        print("Simulando evento -> guardando clip...")
        dash.guardar_clip("PRUEBA")

        # Esperamos a que termine de escribir el clip antes de cerrar
        time.sleep(SEGUNDOS_POST_EVENTO + 2)

    except KeyboardInterrupt:
        pass
    finally:
        dash.cerrar()
