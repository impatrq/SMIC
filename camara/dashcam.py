"""
SMIC - Modulo Dashcam (camara delantera, webcam USB)

Esta camara graba todo el tiempo en un buffer circular en memoria (RAM),
no en disco. Cuando monitor.py detecta un evento (somnolencia, distraccion,
etc), le avisa a este modulo, y este guarda un clip que incluye los
segundos ANTES del evento (que ya estaban en el buffer) mas los segundos
DESPUES del evento (que sigue capturando en tiempo real).

Funciona en paralelo a camara/monitor.py, cada una maneja su propia camara:
- monitor.py -> webcam USB (puerto CAMARA_CONDUCTOR) -> camara del conductor
- dashcam.py -> webcam USB (puerto DASHCAM_CAMARA)   -> camara del camino
"""

import cv2
import time
import threading
import os
import sys
from collections import deque
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camara.usb_cam import abrir_webcam, liberar_webcam

# ==================== CONFIGURACION ====================

# Webcam USB del camino. Antes se probaban los indices [1, 0] porque era
# la unica webcam, pero ahora hay DOS webcams USB (conductor + camino) y
# los numeros /dev/videoN cambian segun el orden de deteccion al arrancar:
# probar indices podia terminar grabando al conductor en vez del camino.
#
# Ahora se identifica por el PUERTO USB, con el link estable de
# /dev/v4l/by-path/ (ver camara/usb_cam.py). Para saber que valor poner:
#     python3 ~/SMIC/camara/usb_cam.py
# y pegar aca la ruta de la camara que mira al camino.
#
# Con None se usa la primera webcam USB que este libre. Como monitor.py
# abre la camara del conductor ANTES que la dashcam, la dashcam se queda
# con la otra -- pero cual es "la primera" depende del puerto, asi que
# conviene fijar las dos.
DASHCAM_CAMARA = None

RESOLUCION_ANCHO = 640
RESOLUCION_ALTO = 480
FPS = 15

# Cuantos segundos guarda ANTES de que ocurra el evento (ya en buffer)
SEGUNDOS_PRE_EVENTO = 10

# Cuantos segundos sigue grabando DESPUES de que ocurre el evento
SEGUNDOS_POST_EVENTO = 10

# Misma carpeta que usa el resto del sistema para guardar clips
CARPETA_EVENTOS = os.path.expanduser("~/SMIC/eventos")

# Subcarpeta oculta donde se escriben los clips MIENTRAS se estan
# grabando. sensores/sincronizador.py solo mira los archivos directos
# de CARPETA_EVENTOS (no entra a subcarpetas), asi que nunca ve un
# clip a medio escribir -- recien aparece con os.replace() cuando ya
# esta completo. Se usa una subcarpeta en vez de, por ejemplo, un
# sufijo ".tmp" en el nombre, porque cv2.VideoWriter elige el
# codec/contenedor segun la extension final del archivo: un nombre
# como "clip.mp4.tmp" hace que ni siquiera pueda abrir el archivo.
CARPETA_TEMPORAL = os.path.join(CARPETA_EVENTOS, ".en_progreso")


# ==================== CLASE DASHCAM ====================

class Dashcam:
    """Maneja la webcam delantera con un buffer circular en memoria."""

    def __init__(self, dispositivo=None):
        # Si se pasa un dispositivo explicito (ruta by-path, /dev/videoN
        # o int), se respeta tal cual. Si no, se usa DASHCAM_CAMARA.
        if dispositivo is None:
            dispositivo = DASHCAM_CAMARA

        self.camara, self.ruta_real = abrir_webcam(
            dispositivo, RESOLUCION_ANCHO, RESOLUCION_ALTO, FPS, etiqueta="DASHCAM"
        )

        if self.camara is None:
            raise RuntimeError(
                f"No se pudo abrir la dashcam ({dispositivo or 'deteccion automatica'})"
            )

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
        os.makedirs(CARPETA_TEMPORAL, exist_ok=True)

        # Hilo que llena el buffer sin parar, en paralelo a todo lo demas
        self.hilo_captura = threading.Thread(target=self._capturar_loop, daemon=True)
        self.hilo_captura.start()

        print(f"Dashcam iniciada correctamente ({self.ruta_real})")

    def _capturar_loop(self):
        """Corre en un hilo aparte. Lee frames de la webcam sin parar
        y los va guardando en el buffer circular."""
        while self.activo:
            ret, frame = self.camara.read()
            if ret:
                # El VideoWriter necesita exactamente este tamaño; si la
                # webcam no respeto la resolucion pedida, se ajusta aca.
                if frame.shape[1] != RESOLUCION_ANCHO or frame.shape[0] != RESOLUCION_ALTO:
                    frame = cv2.resize(frame, (RESOLUCION_ANCHO, RESOLUCION_ALTO))
                with self.lock:
                    self.buffer.append(frame.copy())
                    self.contador_frames += 1
            else:
                # Si por algun motivo falla una lectura, esperamos un
                # instante en vez de saturar el CPU en un loop vacio
                time.sleep(0.05)

    def guardar_clip(self, tipo_evento, evento_id):
        """Llamar a esta funcion desde monitor.py cuando ocurre un evento.
        No bloquea: dispara un hilo aparte que arma el clip y lo guarda,
        mientras el resto del sistema sigue funcionando normalmente.

        evento_id: mismo identificador que MonitorConductor le pasa a
        guardar_clip() para el clip de la camara del conductor de este
        mismo evento (ver camara/monitor.py disparar_evento). Va en el
        nombre del archivo para poder emparejar los 2 clips en el panel
        del servidor."""
        hilo = threading.Thread(
            target=self._guardar_clip_worker,
            args=(tipo_evento, evento_id),
            daemon=True
        )
        hilo.start()

    def _guardar_clip_worker(self, tipo_evento, evento_id):
        """Arma y escribe el archivo de video: primero los frames que ya
        estaban en el buffer (pre-evento), despues los que van llegando
        en tiempo real (post-evento)."""
        nombre_archivo = f"dashcam_{tipo_evento}_{evento_id}.mp4"
        ruta = os.path.join(CARPETA_EVENTOS, nombre_archivo)

        # Se escribe primero en CARPETA_TEMPORAL y recien se mueve a
        # CARPETA_EVENTOS (su nombre final) cuando el archivo ya esta
        # completo. cv2.VideoWriter crea el archivo en el disco apenas
        # arranca, no cuando termina de escribir -- si escribieramos
        # directo en la carpeta final, sensores/sincronizador.py (que
        # revisa esa carpeta cada 30s) podria agarrar el archivo a
        # mitad de escritura, subirlo casi vacio y borrarlo, mucho antes
        # de que termine de grabar los 10s post-evento. Un os.replace()
        # es atomico a nivel de sistema de archivos: el sincronizador
        # nunca puede ver un estado intermedio.
        ruta_temporal = os.path.join(CARPETA_TEMPORAL, nombre_archivo)

        # Copiamos el buffer actual (pre-evento) y anotamos el contador
        # en este instante, para saber a partir de donde son frames nuevos
        with self.lock:
            frames_pre = list(self.buffer)
            ultimo_contador = self.contador_frames

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(ruta_temporal, fourcc, FPS, (RESOLUCION_ANCHO, RESOLUCION_ALTO))

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

        # Recien ahora el archivo esta completo -- lo hacemos visible
        # con su nombre final de un solo paso atomico.
        os.replace(ruta_temporal, ruta)

        print(f"Clip dashcam guardado: {ruta}")

    def cerrar(self):
        """Frena el hilo de captura y libera la camara. Llamar al
        apagar el sistema."""
        self.activo = False
        self.hilo_captura.join(timeout=2)
        liberar_webcam(self.camara, self.ruta_real)
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
        evento_id_prueba = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dash.guardar_clip("PRUEBA", evento_id_prueba)

        # Esperamos a que termine de escribir el clip antes de cerrar
        time.sleep(SEGUNDOS_POST_EVENTO + 2)

    except KeyboardInterrupt:
        pass
    finally:
        dash.cerrar()
