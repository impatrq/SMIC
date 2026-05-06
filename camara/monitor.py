import cv2
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from camara.somnolencia  import DetectorSomnolencia
from camara.distraccion  import DetectorDistraccion
from camara.deteccion    import iniciar_camara, cerrar_camara
from alertas.local       import alerta_somnolencia, alerta_distraccion

# --- CONSTANTES ---
COOLDOWN_SOMNOLENCIA  = 3
COOLDOWN_DISTRACCION  = 4
COLOR_VERDE           = (0, 255, 0)
COLOR_ROJO            = (0, 0, 255)
COLOR_AMARILLO        = (0, 255, 255)
COLOR_BLANCO          = (255, 255, 255)
COLOR_NEGRO           = (0, 0, 0)


# --- FUNCIONES DE DISPLAY ---
def dibujar_panel_estado(frame, dormido, distraido, direccion, ear_info):
    """
    Dibuja un panel de estado unificado en la parte superior.
    Evita que los textos de distintos modulos se superpongan.
    """
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

    cv2.putText(frame, f"SMIC: {estado_texto}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, estado_color, 2)

    if ear_info is not None:
        cv2.putText(frame, f"EAR: {ear_info:.2f}",
                    (10, 65), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, COLOR_BLANCO, 1)

    cv2.putText(frame, f"Direccion: {direccion}",
                (10, 95), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, COLOR_BLANCO, 1)

    if dormido:
        cv2.putText(frame, ">>> ACTIVAR ALERTA <<<",
                    (10, 130), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, COLOR_ROJO, 2)
    elif distraido:
        cv2.putText(frame, ">>> ACTIVAR ALERTA <<<",
                    (10, 130), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, COLOR_AMARILLO, 2)

    return frame


# --- CLASE PRINCIPAL ---
class MonitorConductor:
    """
    Une la deteccion de somnolencia y distraccion
    con el sistema de alertas en un solo monitor.
    """

    def __init__(self):
        self.detector_somnolencia  = DetectorSomnolencia()
        self.detector_distraccion  = DetectorDistraccion()
        self.ultima_alerta_somno   = 0
        self.ultima_alerta_distrac = 0
        print("Monitor de conductor iniciado")

    def puede_alertar_somnolencia(self):
        return (time.time() - self.ultima_alerta_somno) > COOLDOWN_SOMNOLENCIA

    def puede_alertar_distraccion(self):
        return (time.time() - self.ultima_alerta_distrac) > COOLDOWN_DISTRACCION

    def procesar_frame(self, frame):
        """
        Procesa un frame con ambos detectores.
        Devuelve el frame anotado con panel unificado.
        """
        frame_somno, dormido = self.detector_somnolencia.analizar(
            frame, dibujar=False
        )
        frame_final, distraido, direccion = self.detector_distraccion.analizar(
            frame_somno, dibujar=False
        )

        ear_info = None
        try:
            ear_info = self.detector_somnolencia.ultimo_ear
        except:
            pass

        frame_final = dibujar_panel_estado(
            frame_final, dormido, distraido, direccion, ear_info
        )

        if dormido and self.puede_alertar_somnolencia():
            alerta_somnolencia()
            self.ultima_alerta_somno   = time.time()
            self.ultima_alerta_distrac = time.time()

        elif distraido and self.puede_alertar_distraccion():
            alerta_distraccion()
            self.ultima_alerta_distrac = time.time()
            self.ultima_alerta_somno   = time.time()

        return frame_final, dormido, distraido


# --- PROGRAMA PRINCIPAL ---
if __name__ == "__main__":
    print("=" * 45)
    print("  SMIC - Monitor principal")
    print("  Presiona Q para salir")
    print("=" * 45)

    camara  = iniciar_camara()
    monitor = MonitorConductor()

    if camara is None:
        print("No se pudo iniciar la camara")
    else:
        while True:
            ret, frame = camara.read()
            if not ret:
                break

            frame, dormido, distraido = monitor.procesar_frame(frame)

            cv2.imshow("SMIC - Monitor conductor", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cerrar_camara(camara)