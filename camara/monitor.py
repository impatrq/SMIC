import cv2
import numpy as np
import sys
import os
import time
import threading
import queue
import collections
import mediapipe as mp
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camara.somnolencia import DetectorSomnolencia
from camara.distraccion import DetectorDistraccion
from alertas.local      import alerta_somnolencia, alerta_distraccion
from sensores.sincronizador import iniciar_sincronizador
from camara.dashcam import Dashcam

# --- CONSTANTES ---
RESOLUCION_ANCHO     = 640
RESOLUCION_ALTO      = 480
FPS                  = 20
SEGUNDOS_ANTES       = 10
SEGUNDOS_DESPUES     = 10
COOLDOWN_SOMNOLENCIA = 5
COOLDOWN_DISTRACCION = 5
ALTO_PANEL           = 160
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
            },
            controls={"ScalerCrop": (0, 0, 3280, 2464)}
        )
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
    """
    Captura un frame BGR desde la Picamera2.

    NOTA DE RENDIMIENTO: cv2.cvtColor() siempre devuelve un array
    NUEVO (nunca modifica el original). Eso significa que el frame
    que devuelve esta funcion es, en cada llamada, un bloque de
    memoria recien creado que ningun otro lugar del programa vuelve a
    tocar despues. Mas abajo, en MonitorConductor, esto se aprovecha
    para NO copiar el frame antes de guardarlo en el buffer de video.
    Si el dia de mañana esta funcion cambia para reciclar un mismo
    array, hay que revisar ese supuesto en MonitorConductor.procesar_frame().
    """
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

    Hace I/O de disco y codificacion de video (lento). MonitorConductor
    la corre en un hilo aparte (ver _escritor_clips) en vez de llamarla
    directo desde el loop de captura, para no bloquear la camara del
    conductor justo cuando mas importa no perder frames. La dashcam
    (dashcam.py) ya guardaba sus clips en un hilo propio; esto iguala
    el comportamiento para la camara del conductor.
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


# --- HILO DE CAPTURA ---
class CapturaHilo:
    """
    Hilo de captura de la camara del conductor, separado del hilo
    principal (el que corre MediaPipe y el resto del analisis). Mismo
    patron que ya usa dashcam.py para su propio hilo de captura
    (buffer + lock + contador de frames).

    Por que: antes, capturar_frame() y procesar_frame() se ejecutaban
    en serie, uno atras del otro, en el mismo hilo -> tiempo_por_frame
    = tiempo_captura + tiempo_analisis. Corriendo la captura en un
    hilo aparte, mientras el hilo principal todavia esta analizando el
    frame N (~35-45ms de MediaPipe), este hilo ya esta capturando el
    frame N+1 en paralelo. En el mejor caso tiempo_por_frame pasa a
    ser aproximadamente max(tiempo_captura, tiempo_analisis) en vez de
    la suma de los dos. Esto funciona porque tanto Picamera2.capture_array()
    (espera al hardware/DMA) como el process() de MediaPipe (computo
    pesado en C++/TFLite) liberan el GIL de Python mientras trabajan,
    asi que pueden correr de verdad al mismo tiempo en nucleos
    distintos de la Raspberry Pi.

    Sincronizacion (importante): este hilo expone solo el frame MAS
    RECIENTE, no una cola con todos los frames capturados. El hilo
    principal NUNCA debe analizar el mismo frame dos veces -- si lo
    hiciera, self.buffer (el "video de los N segundos antes del
    evento" en MonitorConductor) quedaria con frames duplicados en vez
    de representar de verdad los ultimos SEGUNDOS_ANTES segundos. Por
    eso cada frame capturado lleva un numero de secuencia, y
    obtener_frame_mas_reciente() solo devuelve un frame cuando su
    numero es mayor al ultimo que el llamador ya proceso.
    """

    def __init__(self, camara):
        self.camara = camara
        self.lock   = threading.Lock()
        self.evento_frame_nuevo = threading.Event()

        self.frame_actual    = None
        self.contador_frames = 0
        self.activo = True

        self.hilo = threading.Thread(target=self._capturar_loop, daemon=True)
        self.hilo.start()

    def _capturar_loop(self):
        """Corre en un hilo aparte. Captura frames sin parar y deja
        siempre el ultimo disponible para quien lo pida."""
        while self.activo:
            frame = capturar_frame(self.camara)
            with self.lock:
                self.frame_actual = frame
                self.contador_frames += 1
            self.evento_frame_nuevo.set()

    def obtener_frame_mas_reciente(self, ultimo_contador, timeout=1.0):
        """
        Bloquea hasta que haya un frame con numero de secuencia mayor
        a `ultimo_contador` (o hasta que se cumpla el timeout).
        Devuelve (frame, contador_del_frame). Si se agota el timeout
        sin frame nuevo (por ejemplo la camara se colgo), devuelve
        (None, ultimo_contador) para que el llamador decida que hacer
        sin quedar bloqueado para siempre.
        """
        limite = time.time() + timeout
        while time.time() < limite:
            with self.lock:
                if self.contador_frames > ultimo_contador:
                    return self.frame_actual, self.contador_frames
            self.evento_frame_nuevo.wait(timeout=0.05)
            self.evento_frame_nuevo.clear()
        return None, ultimo_contador

    def detener(self):
        """Frena el hilo de captura. Llamar antes de cerrar_camara()
        para no cerrar la camara mientras el hilo todavia la esta
        usando."""
        self.activo = False
        self.hilo.join(timeout=2)


# --- CLASE PRINCIPAL ---
class MonitorConductor:
    def __init__(self, dashcam=None):
        # FaceMesh unico, compartido entre somnolencia y
        # distraccion para no duplicar la inferencia mas
        # cara del pipeline en cada frame
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            # No usamos puntos del iris (indices 468-477), asi
            # que desactivamos el modelo extra que los calcula
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.detector_somnolencia  = DetectorSomnolencia()
        self.detector_distraccion  = DetectorDistraccion()
        self.dashcam                = dashcam
        self.ultima_alerta_somno   = 0
        self.ultima_alerta_distrac = 0

        capacidad_buffer = FPS * SEGUNDOS_ANTES
        self.buffer = collections.deque(maxlen=capacidad_buffer)

        self.grabando_post_evento   = False
        self.frames_post_evento     = []
        self.tipo_evento_actual     = ""
        self.contador_post_evento   = 0
        self.frames_post_necesarios = FPS * SEGUNDOS_DESPUES

        # Panel negro semitransparente reutilizado en cada frame para
        # el encabezado de estado, en vez de copiar el frame entero
        # (480 filas) para despues mezclar solo las primeras 160.
        self._panel_negro = np.zeros((ALTO_PANEL, RESOLUCION_ANCHO, 3), dtype=np.uint8)

        # Cola + hilo dedicado a escribir el clip de la camara del
        # conductor en disco, para que grabar un evento no frene el
        # analisis de los frames que siguen llegando de la camara
        # (igual que ya hace dashcam.py con su propio clip).
        self._cola_clips = queue.Queue()
        threading.Thread(target=self._escritor_clips, daemon=True).start()

        print("Monitor de conductor iniciado (modo produccion)")
        print(f"Buffer: {SEGUNDOS_ANTES}s antes | {SEGUNDOS_DESPUES}s despues")

    def _escritor_clips(self):
        """Hilo en segundo plano: guarda clips sin bloquear la camara."""
        while True:
            buffer_frames, frames_despues, tipo_evento = self._cola_clips.get()
            try:
                guardar_clip(buffer_frames, frames_despues, tipo_evento)
            except Exception as e:
                print(f"[CLIP] Error guardando clip: {e}")
            finally:
                self._cola_clips.task_done()

    def esperar_clips_pendientes(self, timeout=20):
        """
        Espera a que el hilo _escritor_clips termine de escribir
        cualquier clip que haya quedado en la cola, con un limite de
        tiempo para no colgar el apagado si algo se traba.

        IMPORTANTE llamar a esto antes de terminar el programa: el
        hilo de escritura es daemon, asi que si el proceso principal
        termina mientras ese hilo esta a mitad de un cv2.VideoWriter,
        Python lo corta de golpe -- interrumpir una llamada nativa de
        OpenCV a mitad de camino puede terminar en un crash del tipo
        "terminate called without an active exception" al cerrar.
        Esperando a que la cola se vacie, el hilo siempre termina por
        su cuenta antes de que el proceso salga.
        """
        pendientes = self._cola_clips.unfinished_tasks
        if pendientes == 0:
            return

        print(f"Esperando a que terminen {pendientes} clip(s) pendiente(s)...")
        inicio = time.time()
        while self._cola_clips.unfinished_tasks > 0 and (time.time() - inicio) < timeout:
            time.sleep(0.2)

        if self._cola_clips.unfinished_tasks > 0:
            print("Aviso: seguia habiendo clips pendientes al cerrar "
                  "(se corto la espera por el limite de tiempo)")

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

            if self.dashcam is not None:
                self.dashcam.guardar_clip(tipo)

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
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Tip de rendimiento documentado por MediaPipe: marcar la
        # imagen como "no escribible" antes de process() evita que la
        # libreria haga una copia interna extra del array.
        rgb.flags.writeable = False
        resultado_mediapipe = self.face_mesh.process(rgb)
        rgb.flags.writeable = True

        frame_somno, dormido = self.detector_somnolencia.analizar(
            frame, dibujar=False, resultado_mediapipe=resultado_mediapipe
        )
        frame_final, distraido, direccion = self.detector_distraccion.analizar(
            frame_somno, dibujar=False, resultado_mediapipe=resultado_mediapipe
        )

        ear_info = self.detector_somnolencia.ultimo_ear

        frame_final = self._dibujar_estado(
            frame_final, dormido, distraido, direccion, ear_info
        )

        # frame_final es el mismo array que devolvio capturar_frame():
        # nadie mas lo va a tocar despues de esta linea (el proximo
        # frame se captura en un array nuevo), asi que no hace falta
        # copiarlo antes de guardarlo. Antes se copiaba el frame
        # entero hasta dos veces por frame sin necesidad.
        self.buffer.append(frame_final)

        if dormido and self.puede_alertar_somnolencia():
            self.disparar_evento(
                "SOMNOLENCIA", dormido, distraido, direccion, ear_info
            )
        elif distraido and self.puede_alertar_distraccion():
            self.disparar_evento(
                "DISTRACCION", dormido, distraido, direccion, ear_info
            )

        if self.grabando_post_evento:
            self.frames_post_evento.append(frame_final)
            self.contador_post_evento += 1

            segundos_grabados = self.contador_post_evento / FPS
            print(
                f"\rGrabando post-evento: {segundos_grabados:.1f}s / "
                f"{SEGUNDOS_DESPUES}s",
                end=""
            )

            if self.contador_post_evento >= self.frames_post_necesarios:
                print()
                # Antes: guardar_clip(...) se llamaba aca mismo y
                # bloqueaba el loop principal mientras codificaba y
                # escribia en disco ~200 frames (se ve clarito en el
                # log real: el FPS caia de 16 a ~12 durante esto).
                # Ahora solo se encola y _escritor_clips lo procesa
                # aparte, igual que ya hace la dashcam.
                self._cola_clips.put((
                    self.buffer_al_evento,
                    self.frames_post_evento,
                    self.tipo_evento_actual
                ))
                self.grabando_post_evento = False
                self.frames_post_evento   = []

        return frame_final, dormido, distraido

    def _dibujar_estado(self, frame, dormido, distraido, direccion, ear):
        """Dibuja el panel de estado en el frame."""
        COLOR_VERDE    = (0, 255, 0)
        COLOR_ROJO     = (0, 0, 255)
        COLOR_AMARILLO = (0, 255, 255)
        COLOR_BLANCO   = (255, 255, 255)

        alto, ancho = frame.shape[:2]

        # Antes se copiaba el frame ENTERO (480 filas) para dibujar un
        # rectangulo negro solo en las primeras 160 y despues se
        # mezclaba sobre las 480 filas completas, aunque las de abajo
        # no cambiaban en nada. Ahora se trabaja solo sobre la franja
        # de 160 filas que realmente se necesita (una "vista" del
        # array, sin copiar memoria), reutilizando el mismo panel
        # negro en vez de crearlo de nuevo cada vez.
        panel = frame[0:ALTO_PANEL, 0:ancho]
        cv2.addWeighted(self._panel_negro[:, :ancho], 0.4, panel, 0.6, 0, panel)

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
    iniciar_sincronizador()

    camara = iniciar_camara()

    try:
        dashcam = Dashcam()
    except Exception as e:
        print(f"Aviso: no se pudo iniciar la dashcam ({e}). "
              f"El sistema sigue sin ella.")
        dashcam = None

    monitor = MonitorConductor(dashcam=dashcam)

    if camara is None:
        print("No se pudo iniciar la camara")
        sys.exit(1)

    frame_count   = 0
    tiempo_inicio = time.time()

    # Hilo de captura de la camara del conductor, separado del hilo
    # principal que hace el analisis (ver CapturaHilo mas arriba).
    captura         = CapturaHilo(camara)
    ultimo_contador = 0

    try:
        while True:
            frame, ultimo_contador = captura.obtener_frame_mas_reciente(
                ultimo_contador, timeout=2.0
            )
            if frame is None:
                # No llego un frame nuevo dentro del timeout (por
                # ejemplo la camara se colgo). No proceso nada este
                # ciclo, pero tampoco me quedo bloqueado para siempre.
                print("Aviso: no llego un frame nuevo de la camara "
                      "a tiempo")
                continue

            frame, dormido, distraido = monitor.procesar_frame(frame)

            frame_count += 1

            if frame_count % (FPS * 5) == 0:
                tiempo_transcurrido = time.time() - tiempo_inicio
                fps_real = frame_count / tiempo_transcurrido
                print(f"FPS real: {fps_real:.1f} | Frames: {frame_count}")

    except KeyboardInterrupt:
        print("\nSistema detenido por el usuario")

    finally:
        # Frenar el hilo de captura ANTES de cerrar la camara: si
        # cerramos la camara mientras ese hilo todavia esta a mitad
        # de un capture_array(), puede tirar un error feo al salir.
        captura.detener()
        cerrar_camara(camara)
        if dashcam is not None:
            dashcam.cerrar()
        # Esperar a que el hilo de clips termine antes de salir, para
        # que Python no lo corte a mitad de un cv2.VideoWriter.
        monitor.esperar_clips_pendientes()
        print("Sistema cerrado correctamente")
