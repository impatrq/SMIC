import cv2
import mediapipe as mp
import time
from math import dist

# --- CONSTANTES ---
EAR_UMBRAL      = 0.25
SEGUNDOS_ALERTA = 2.0
COLOR_VERDE     = (0, 255, 0)
COLOR_ROJO      = (0, 0, 255)

OJO_DER = [362, 385, 387, 263, 373, 380]
OJO_IZQ = [33,  160, 158, 133, 153, 144]

def calcular_ear(puntos_ojo):
    vertical_1 = dist(puntos_ojo[1], puntos_ojo[5])
    vertical_2 = dist(puntos_ojo[2], puntos_ojo[4])
    horizontal = dist(puntos_ojo[0], puntos_ojo[3])
    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear

def obtener_puntos_ojo(landmarks, indices, ancho, alto):
    puntos = []
    for i in indices:
        punto = landmarks[i]
        x = int(punto.x * ancho)
        y = int(punto.y * alto)
        puntos.append((x, y))
    return puntos

def dibujar_ojos(frame, puntos_izq, puntos_der):
    for punto in puntos_izq + puntos_der:
        cv2.circle(frame, punto, 2, COLOR_VERDE, -1)
    return frame

def mostrar_ear(frame, ear_izq, ear_der, dormido):
    ear_promedio = (ear_izq + ear_der) / 2.0
    color = COLOR_ROJO if dormido else COLOR_VERDE
    cv2.putText(frame, f"EAR: {ear_promedio:.2f}",
                (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    if dormido:
        cv2.putText(frame, "ALERTA: SOMNOLENCIA DETECTADA",
                    (10, 100), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, COLOR_ROJO, 2)
    return frame

class DetectorSomnolencia:
    def __init__(self):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.tiempo_ojos_cerrados = None
        self.dormido              = False
        self.ultimo_ear           = None
        print("Detector de somnolencia iniciado")

    def analizar(self, frame, dibujar=True):
        alto, ancho = frame.shape[:2]
        rgb         = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado   = self.face_mesh.process(rgb)

        if not resultado.multi_face_landmarks:
            self.tiempo_ojos_cerrados = None
            self.dormido              = False
            self.ultimo_ear           = None
            return frame, False

        landmarks = resultado.multi_face_landmarks[0].landmark
        puntos_izq = obtener_puntos_ojo(landmarks, OJO_IZQ, ancho, alto)
        puntos_der = obtener_puntos_ojo(landmarks, OJO_DER, ancho, alto)
        ear_izq = calcular_ear(puntos_izq)
        ear_der = calcular_ear(puntos_der)
        ear_avg = (ear_izq + ear_der) / 2.0
        self.ultimo_ear = ear_avg

        if ear_avg < EAR_UMBRAL:
            if self.tiempo_ojos_cerrados is None:
                self.tiempo_ojos_cerrados = time.time()
            else:
                tiempo_cerrado = time.time() - self.tiempo_ojos_cerrados
                if tiempo_cerrado >= SEGUNDOS_ALERTA:
                    self.dormido = True
        else:
            self.tiempo_ojos_cerrados = None
            self.dormido              = False

        frame = dibujar_ojos(frame, puntos_izq, puntos_der)
        if dibujar:
            frame = mostrar_ear(frame, ear_izq, ear_der, self.dormido)

        return frame, self.dormido

if __name__ == "__main__":
    camara   = cv2.VideoCapture(0)
    detector = DetectorSomnolencia()
    alertas  = 0

    while True:
        ret, frame = camara.read()
        if not ret:
            break
        frame, dormido = detector.analizar(frame)
        if dormido:
            alertas += 1
            print(f"ALERTA #{alertas}: Somnolencia detectada")
        cv2.imshow("SMIC - Somnolencia", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camara.release()
    cv2.destroyAllWindows()