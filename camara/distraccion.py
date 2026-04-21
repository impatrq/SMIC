import cv2
import mediapipe as mp
import time

# --- CONSTANTES ---
# Estos valores se pueden ajustar segun la posicion de la camara
UMBRAL_HORIZONTAL  = 0.15   # cuanto se puede mover la nariz a los lados
UMBRAL_VERTICAL    = 0.12   # cuanto se puede mover la nariz arriba/abajo
SEGUNDOS_ALERTA    = 2.0
COLOR_VERDE        = (0, 255, 0)
COLOR_ROJO         = (0, 0, 255)
COLOR_AMARILLO     = (0, 255, 255)

# Puntos de referencia
NARIZ        = 1
FRENTE       = 10
MENTON       = 152
MEJILLA_IZQ  = 234
MEJILLA_DER  = 454


# --- FUNCIONES ---
def obtener_punto(landmark, indice, ancho, alto):
    """Devuelve las coordenadas de un punto en pixeles."""
    lm = landmark[indice]
    return int(lm.x * ancho), int(lm.y * alto)


def calcular_posicion_nariz(landmarks, ancho, alto):
    """
    Calcula la posicion normalizada de la nariz
    respecto al centro del rostro.
    Devuelve (offset_x, offset_y) entre -1 y 1.
    offset_x negativo = mira izquierda
    offset_x positivo = mira derecha
    offset_y negativo = mira arriba
    offset_y positivo = mira abajo (celular)
    """
    nariz       = obtener_punto(landmarks, NARIZ,       ancho, alto)
    mejilla_izq = obtener_punto(landmarks, MEJILLA_IZQ, ancho, alto)
    mejilla_der = obtener_punto(landmarks, MEJILLA_DER, ancho, alto)
    frente      = obtener_punto(landmarks, FRENTE,      ancho, alto)
    menton      = obtener_punto(landmarks, MENTON,      ancho, alto)

    # Centro horizontal del rostro
    centro_x = (mejilla_izq[0] + mejilla_der[0]) / 2
    ancho_rostro = mejilla_der[0] - mejilla_izq[0]

    # Centro vertical del rostro
    centro_y = (frente[1] + menton[1]) / 2
    alto_rostro = menton[1] - frente[1]

    # Offset normalizado (-1 a 1)
    if ancho_rostro == 0 or alto_rostro == 0:
        return 0, 0

    offset_x = (nariz[0] - centro_x) / ancho_rostro
    offset_y = (nariz[1] - centro_y) / alto_rostro

    return offset_x, offset_y


def determinar_direccion(offset_x, offset_y):
    """
    Determina hacia donde mira el conductor.
    Devuelve (direccion, es_distraccion).
    """
    if abs(offset_x) > UMBRAL_HORIZONTAL:
        if offset_x > 0:
            return "Mirando a la derecha", True
        else:
            return "Mirando a la izquierda", True
    elif offset_y > UMBRAL_VERTICAL:
        return "Mirando hacia abajo (celular)", True
    else:
        return "Al frente", False


def dibujar_puntos(frame, landmarks, ancho, alto):
    """Dibuja los puntos de referencia en el frame."""
    puntos = [NARIZ, FRENTE, MENTON, MEJILLA_IZQ, MEJILLA_DER]
    for indice in puntos:
        x, y = obtener_punto(landmarks, indice, ancho, alto)
        cv2.circle(frame, (x, y), 4, COLOR_AMARILLO, -1)
    return frame


def mostrar_info(frame, offset_x, offset_y, direccion, distraido):
    """Muestra el estado en el frame."""
    color = COLOR_ROJO if distraido else COLOR_VERDE

    cv2.putText(frame, f"Horizontal: {offset_x:.2f}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"Vertical:   {offset_y:.2f}",
                (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    cv2.putText(frame, f"Dir: {direccion}",
                (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    if distraido:
        cv2.putText(frame, "ALERTA: DISTRACCION DETECTADA",
                    (10, 145), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, COLOR_ROJO, 2)
    return frame


# --- CLASE PRINCIPAL ---
class DetectorDistraccion:
    """
    Detecta distraccion analizando la posicion
    relativa de la nariz respecto al centro del rostro.
    Funciona con cualquier angulo de camara.
    """

    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.tiempo_distraido = None
        self.distraido        = False
        print("Detector de distraccion iniciado")

    def analizar(self, frame):
        """
        Analiza un frame y detecta distraccion.
        Devuelve (frame_anotado, esta_distraido, direccion).
        """
        alto, ancho = frame.shape[:2]
        rgb         = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado   = self.face_mesh.process(rgb)

        if not resultado.multi_face_landmarks:
            self.tiempo_distraido = None
            self.distraido        = False
            return frame, False, "Sin rostro"

        landmarks = resultado.multi_face_landmarks[0].landmark

        offset_x, offset_y = calcular_posicion_nariz(
            landmarks, ancho, alto
        )

        direccion, es_distraccion = determinar_direccion(
            offset_x, offset_y
        )

        if es_distraccion:
            if self.tiempo_distraido is None:
                self.tiempo_distraido = time.time()
            else:
                tiempo = time.time() - self.tiempo_distraido
                if tiempo >= SEGUNDOS_ALERTA:
                    self.distraido = True
        else:
            self.tiempo_distraido = None
            self.distraido        = False

        frame = dibujar_puntos(frame, landmarks, ancho, alto)
        frame = mostrar_info(
            frame, offset_x, offset_y, direccion, self.distraido
        )

        return frame, self.distraido, direccion


# --- PROGRAMA DE PRUEBA ---
if __name__ == "__main__":
    print("=" * 45)
    print("  SMIC - Deteccion de distraccion")
    print("  Presiona Q para salir")
    print("=" * 45)

    camara   = cv2.VideoCapture(0)
    detector = DetectorDistraccion()
    alertas  = 0

    while True:
        ret, frame = camara.read()
        if not ret:
            break

        frame, distraido, direccion = detector.analizar(frame)

        if distraido:
            alertas += 1
            print(f"ALERTA #{alertas}: {direccion}")

        cv2.imshow("SMIC - Distraccion", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camara.release()
    cv2.destroyAllWindows()