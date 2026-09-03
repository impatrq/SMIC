# AVISO: este script quedó obsoleto/en desuso. El programa que corre de
# verdad en la RPi4 es camara/monitor.py (python -m camara.monitor):
# tiene hilo de captura separado, dashcam sincronizada, cooldowns por tipo
# de alerta, y ya llama a mandar_alerta_sim() en disparar_evento() para
# mandar la alerta + ubicación por el SIM800L en el momento del evento.
# Este main.py además tiene un bug sin arreglar: iniciar_camara() (de
# camara/deteccion.py) devuelve un Picamera2, que no tiene método .read()
# (esa es la API de cv2.VideoCapture) -- el loop de abajo rompe con
# AttributeError apenas arranca. También sube el clip a Cloudinary en el
# momento del evento (datos/registro.py), que es justo lo que NO se quiere
# mientras se maneja con datos móviles -- el clip tiene que quedar guardado
# en la RPi4 y subirse recién cuando el sistema detecta conexión a la red
# local (eso ya lo hace sensores/sincronizador.py, usado por monitor.py).
# Se deja este archivo sin borrar por las dudas, pero no usar para correr
# el sistema.

from flask import Flask
from datos.modelos import db
from datos.registro import guardar_evento, BufferVideo
from camara.monitor import MonitorConductor
from camara.deteccion import iniciar_camara, cerrar_camara
from comunicacion.sim800l import mandar_alerta_sim
import cv2
import threading

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smic.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

camara  = iniciar_camara()
monitor = MonitorConductor()
buffer  = BufferVideo()

while True:
    ret, frame = camara.read()
    if not ret:
        break

    # agregamos el frame al buffer en cada iteracion
    buffer.agregar_frame(frame)

    frame, dormido, distraido = monitor.procesar_frame(frame)

    if dormido:
        with app.app_context():
            guardar_evento("somnolencia", camara, buffer, duracion=4.0, volante=False)
        # Alerta + ubicacion por el SIM800L, en un hilo aparte para no
        # trabar el loop de la camara mientras se mandan los comandos AT.
        # No manda video ni nada mas -- eso ya lo hizo guardar_evento()
        # arriba via Cloudinary.
        threading.Thread(target=mandar_alerta_sim, args=("somnolencia",), daemon=True).start()

    if distraido:
        with app.app_context():
            guardar_evento("distraccion", camara, buffer, duracion=3.0, volante=True)
        threading.Thread(target=mandar_alerta_sim, args=("distraccion",), daemon=True).start()

    cv2.imshow("SMIC", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cerrar_camara(camara)
print("SMIC cerrado correctamente")
