import cv2
import sys
import os
import time
import threading
import collections
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camara.somnolencia import DetectorSomnolencia
from camara.distraccion import DetectorDistraccion
from alertas.local      import alerta_somnolencia, alerta_distraccion

# --- CONSTANTES ---
RESOLUCION_ANCHO     = 640
RESOLUCION_ALTO      = 480
FPS                  = 20
SEGUNDOS_ANTES       = 10
SEGUNDOS_DESPUES     = 10
COOLDOWN_SOMNOLENCIA = 5
COOLDOWN_DISTRACCION = 5
CARPETA_EVENTOS      = os.path.expanduser("~/SMIC/eventos")


# --- FUNCIONES ---
def iniciar_camara():
    """
    Inicializa la Raspberry Pi Camera Module usando Picamera2.
    Devuelve el objeto Picamera2 o None si falla.
    """
    try:
        from picamera2 import Picamera2
        camara = Picamera2()
        config = camara.create_preview_configuration(
            main={
                "format": "BGR888",
                "size": (RESOLUCION_ANCHO, RESOLUCION_ALTO)
            }
        )
        camara.configure(config)
        camara.start()
        time.sleep(2)
        print("Camara iniciada correctamente")
        return camara
    except Exception as e:
        print(f"Error al iniciar camara: {e}")
        return None


def cerrar_camara(camara):
    """Detiene la Picamera2."""
    camara.stop()
    print("Camara cerrada correctamente")


def capturar_frame(camara):
    """Captura un frame BGR desde la Picamera2."""
    frame = camara.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame


def crear_carpeta_eventos():
    """Crea la carpeta donde se guardan los clips si no existe."""
    os.makedirs(CARPETA_EVENTOS, exist_ok=True)
    print(f"Carpeta de eventos: {CARPETA_EVENTOS}")


def guardar_clip(buffer_frames, frames_despues, tipo_evento):
    """
    Guarda un clip de video con los frames del buffer (antes)
    mas los frames posteriores al evento.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre    = f"{CARPETA_EVENTOS}/{tipo_evento}_{timestamp}.avi"

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    writer = cv2.VideoWriter(
        nombre,
        fourcc,
        FPS,
        (RESOLUCION_ANCHO, RESOLUCION_ALTO)
    )

    for frame in buffer_frames:
        writer.write(frame)

    for frame in frames_despues:
        writer.write(frame)

    writer.release()
    print(f"Clip guardado: {nombre}")
    return nombre


def registrar_evento(tipo, dormido, distraido, direccion, ear):
    """Imprime un log del evento en la terminal."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"  EVENTO DETECTADO: {tipo}")
    print(f"  Hora: {timestamp}")
    if ear is not None:
        print(f"  EAR: {ear:.3f}")
    if direccion:
        print(f"  Direccion: {direccion}")
    print(f"{'='*50}\n")


# --- CLASE PRINCIPAL ---
class MonitorConductor:
    def __init__(self):
        self.detector_somnolencia  = DetectorSomnolencia()
        self.detector_distraccion  = DetectorDistraccion()
        self.ultima_alerta_somno   = 0
        self.ultima_alerta_distrac = 0

        capacidad_buffer = FPS * SEGUNDOS_ANTES
        self.buffer = collections.deque(maxlen=capacidad_buffer)

        self.grabando_post_evento   = False
        self.frames_post_evento     = []
        self.tipo_evento_actual     = ""
        self.contador_post_evento   = 0
        self.frames_post_necesarios = FPS * SEGUNDOS_DESPUES

        print("Monitor de conductor iniciado (modo produccion)")
        print(f"Buffer: {SEGUNDOS_ANTES}s antes | {SEGUNDOS_DESPUES}s despues")

    def puede_alertar_somnolencia(self):
        return (time.time() - self.ultima_alerta_somno) > COOLDOWN_SOMNOLENCIA

    def puede_alertar_distraccion(self):
        return (time.time() - self.ultima_alerta_distrac) > COOLDOWN_DISTRACCION

    def disparar_evento(self, tipo, dormido, distraido, direccion, ear):
        """Inicia la grabacion del clip cuando ocurre un evento."""
        if not self.grabando_post_evento:
            self.grabando_post_evento = True
            self.frames_post_evento   = []
            self.contador_post_evento = 0
            self.tipo_evento_actual   = tipo
            self.buffer_al_evento     = list(self.buffer)

            registrar_evento(tipo, dormido, distraido, direccion, ear)

            if tipo == "SOMNOLENCIA":
                threading.Thread(
                    target=alerta_somnolencia, daemon=True
                ).start()
                self.ultima_alerta_somno   = time.time()
                self.ultima_alerta_distrac = time.time()
            elif tipo == "DISTRACCION":
                threading.Thread(
                    target=alerta_distraccion, daemon=True
                ).start()
                self.ultima_alerta_distrac = time.time()
                self.ultima_alerta_somno   = time.time()

    def procesar_frame(self, frame):
        """
        Analiza un frame, actualiza el buffer y gestiona
        la grabacion de eventos.
        """
        frame_somno, dormido = self.detector_somnolencia.analizar(
            frame, dibujar=False
        )
        frame_final, distraido, direccion = self.detector_distraccion.analizar(
            frame_somno, dibujar=False
        )

        ear_info = self.detector_somnolencia.ultimo_ear

        frame_final = self._dibujar_estado(
            frame_final, dormido, distraido, direccion, ear_info
        )

        self.buffer.append(frame_final.copy())

        if dormido and self.puede_alertar_somnolencia():
            self.disparar_evento(
                "SOMNOLENCIA", dormido, distraido, direccion, ear_info
            )
        elif distraido and self.puede_alertar_distraccion():
            self.disparar_evento(
                "DISTRACCION", dormido, distraido, direccion, ear_info
            )

        if self.grabando_post_evento:
            self.frames_post_evento.append(frame_final.copy())
            self.contador_post_evento += 1

            segundos_grabados = self.contador_post_evento / FPS
            print(
                f"\rGrabando post-evento: {segundos_grabados:.1f}s / "
                f"{SEGUNDOS_DESPUES}s",
                end=""
            )

            if self.contador_post_evento >= self.frames_post_necesarios:
                print()
                guardar_clip(
                    self.buffer_al_evento,
                    self.frames_post_evento,
                    self.tipo_evento_actual
                )
                self.grabando_post_evento = False
                self.frames_post_evento   = []

        return frame_final, dormido, distraido

    def _dibujar_estado(self, frame, dormido, distraido, direccion, ear):
        """Dibuja el panel de estado en el frame."""
        COLOR_VERDE    = (0, 255, 0)
        COLOR_ROJO     = (0, 0, 255)
        COLOR_AMARILLO = (0, 255, 255)
        COLOR_BLANCO   = (255, 255, 255)
        COLOR_NEGRO    = (0, 0, 0)

        alto, ancho = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (ancho, 160), COLOR_NEGRO, -1)
        cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)

        if dormido:
            estado_texto = "SOMNOLENCIA DETECTADA"
            estado_color = COLOR_ROJO
        elif distraido:
            estado_texto = f"DISTRACCION: {direccion}"
            estado_color = COLOR_AMARILLO
        else:
            estado_texto = "Conductor atento"
            estado_color = COLOR_VERDE

        cv2.putText(
            frame, f"SMIC: {estado_texto}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, estado_color, 2
        )

        if ear is not None:
            cv2.putText(
                frame, f"EAR: {ear:.2f}",
                (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_BLANCO, 1
            )

        cv2.putText(
            frame, f"Dir: {direccion}",
            (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_BLANCO, 1
        )

        if self.grabando_post_evento:
            cv2.circle(frame, (ancho - 20, 20), 8, COLOR_ROJO, -1)
            cv2.putText(
                frame, "REC",
                (ancho - 55, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_ROJO, 2
            )

        return frame


# --- PROGRAMA PRINCIPAL ---
if __name__ == "__main__":
    print("=" * 50)
    print("  SMIC - Monitor de conductor")
    print("  Modo: Produccion (sin pantalla)")
    print("  Presiona Ctrl+C para salir")
    print("=" * 50)

    crear_carpeta_eventos()

    camara  = iniciar_camara()
    monitor = MonitorConductor()

    if camara is None:
        print("No se pudo iniciar la camara")
        sys.exit(1)

    frame_count   = 0
    tiempo_inicio = time.time()

    try:
        while True:
            frame = capturar_frame(camara)
            frame, dormido, distraido = monitor.procesar_frame(frame)

            frame_count += 1

            if frame_count % (FPS * 5) == 0:
                tiempo_transcurrido = time.time() - tiempo_inicio
                fps_real = frame_count / tiempo_transcurrido
                print(f"FPS real: {fps_real:.1f} | Frames: {frame_count}")

    except KeyboardInterrupt:
        print("\nSistema detenido por el usuario")

    finally:
        cerrar_camara(camara)
        print("Sistema cerrado correctamente")
