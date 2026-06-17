import cv2
import numpy as np
from picamera2 import Picamera2

# --- CONSTANTES ---
RESOLUCION_ANCHO  = 640
RESOLUCION_ALTO   = 480
COLOR_VERDE       = (0, 255, 0)
COLOR_ROJO        = (0, 0, 255)
GROSOR            = 2


# --- FUNCIONES ---
def iniciar_camara():
    """
    Inicializa la Raspberry Pi Camera Module usando Picamera2.
    Configura la resolucion y el formato BGR para OpenCV.
    Devuelve el objeto Picamera2 listo para usar, o None si falla.
    """
    try:
        camara = Picamera2()

        config = camara.create_preview_configuration(
            main={
                "format": "BGR888",
                "size": (RESOLUCION_ANCHO, RESOLUCION_ALTO)
            }
        )
        camara.configure(config)
        camara.start()

        print("Camara Raspberry Pi iniciada correctamente")
        return camara

    except Exception as e:
        print(f"Error: no se pudo abrir la camara -> {e}")
        return None


def cargar_detector():
    """
    Carga el detector de rostros de OpenCV.
    Devuelve el clasificador listo para usar.
    """
    detector = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    print("Detector de rostros cargado")
    return detector


def capturar_frame(camara):
    """
    Captura un frame desde la Picamera2.
    Devuelve el frame como array numpy en formato BGR (compatible con OpenCV).
    """
    frame = camara.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return frame


def detectar_rostro(frame, detector):
    """
    Analiza un frame y detecta rostros.
    Devuelve lista de rostros y frame en escala de grises.
    """
    gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rostros = detector.detectMultiScale(
        gris,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(80, 80)
    )
    return rostros, gris


def dibujar_rostros(frame, rostros):
    """
    Dibuja rectangulo verde alrededor de cada rostro detectado.
    Devuelve el frame con los rectangulos dibujados.
    """
    for (x, y, ancho, alto) in rostros:
        cv2.rectangle(
            frame,
            (x, y),
            (x + ancho, y + alto),
            COLOR_VERDE,
            GROSOR
        )
        cv2.putText(
            frame,
            "Conductor detectado",
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            COLOR_VERDE,
            2
        )
    return frame


def mostrar_estado(frame, hay_rostro):
    """
    Muestra el estado del sistema en la esquina superior izquierda.
    """
    if hay_rostro:
        texto = "SMIC: Conductor presente"
        color = COLOR_VERDE
    else:
        texto = "SMIC: Sin conductor"
        color = COLOR_ROJO

    cv2.putText(
        frame,
        texto,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2
    )
    return frame


def cerrar_camara(camara):
    """Detiene la Picamera2 y cierra todas las ventanas de OpenCV."""
    camara.stop()
    cv2.destroyAllWindows()
    print("Camara cerrada correctamente")


# --- PROGRAMA PRINCIPAL ---
if __name__ == "__main__":
    print("=" * 45)
    print("  SMIC - Deteccion de rostro")
    print("  Presiona Q para salir")
    print("=" * 45)

    camara   = iniciar_camara()
    detector = cargar_detector()

    if camara is None:
        print("No se pudo iniciar el sistema")
    else:
        while True:
            frame = capturar_frame(camara)

            rostros, gris = detectar_rostro(frame, detector)
            hay_rostro    = len(rostros) > 0

            frame = dibujar_rostros(frame, rostros)
            frame = mostrar_estado(frame, hay_rostro)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cerrar_camara(camara)
