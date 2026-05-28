# ============================================================
# SMIC - Sistema de Monitoreo Inteligente del Conductor
# Archivo: alertas/local.py
# Descripcion: Sistema de alertas locales con audio personalizado
# Autor: Przybylski, Facundo
# ============================================================

import time
import threading
import winsound
import os

# --- RUTAS DE AUDIO ---
BASE_DIR          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONIDO_ALERTA     = os.path.join(BASE_DIR, "assets", "alerta.wav")

# --- CONSTANTES ---
ALERTA_SOMNOLENCIA  = "SOMNOLENCIA"
ALERTA_DISTRACCION  = "DISTRACCION"
ALERTA_EMERGENCIA   = "EMERGENCIA"


# --- FUNCIONES DE SONIDO ---
def reproducir_sonido():
    """Reproduce el audio personalizado de alerta."""
    if os.path.exists(SONIDO_ALERTA):
        winsound.PlaySound(
            SONIDO_ALERTA,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    else:
        print(f"Archivo no encontrado: {SONIDO_ALERTA}")
        winsound.Beep(1000, 500)


def reproducir_doble():
    """Reproduce el audio dos veces para distraccion."""
    if os.path.exists(SONIDO_ALERTA):
        winsound.PlaySound(
            SONIDO_ALERTA,
            winsound.SND_FILENAME
        )
        time.sleep(0.3)
        winsound.PlaySound(
            SONIDO_ALERTA,
            winsound.SND_FILENAME | winsound.SND_ASYNC
        )
    else:
        winsound.Beep(1000, 500)
        time.sleep(0.1)
        winsound.Beep(1000, 500)


# --- FUNCION ACTIVAR ALERTA ---
def activar_alerta(tipo):
    """
    Activa la alerta segun el tipo de evento detectado.
    El sonido se ejecuta en un hilo separado para no
    bloquear el procesamiento de la camara.
    """
    if tipo == ALERTA_SOMNOLENCIA:
        hilo    = threading.Thread(target=reproducir_doble)
        mensaje = "ALERTA SOMNOLENCIA: Conductor adormecido"

    elif tipo == ALERTA_DISTRACCION:
        hilo    = threading.Thread(target=reproducir_sonido)
        mensaje = "ALERTA DISTRACCION: Conductor distraido"

    elif tipo == ALERTA_EMERGENCIA:
        hilo    = threading.Thread(target=reproducir_doble)
        mensaje = "EMERGENCIA: Intervencion inmediata requerida"

    else:
        return

    hilo.daemon = True
    hilo.start()

    print(f"\n{'='*45}")
    print(f"  {mensaje}")
    print(f"  Hora: {time.strftime('%H:%M:%S')}")
    print(f"{'='*45}\n")


# --- FUNCIONES ATAJO ---
def alerta_somnolencia():
    """Atajo para activar alerta de somnolencia."""
    activar_alerta(ALERTA_SOMNOLENCIA)


def alerta_distraccion():
    """Atajo para activar alerta de distraccion."""
    activar_alerta(ALERTA_DISTRACCION)


def alerta_emergencia():
    """Atajo para activar alerta de emergencia."""
    activar_alerta(ALERTA_EMERGENCIA)


# --- PROGRAMA DE PRUEBA ---
if __name__ == "__main__":
    print("=" * 45)
    print("  SMIC - Prueba de alertas con audio")
    print("=" * 45)

    print("\nProbando alerta de distraccion...")
    alerta_distraccion()
    time.sleep(3)

    print("Probando alerta de somnolencia...")
    alerta_somnolencia()
    time.sleep(3)

    print("Probando alerta de emergencia...")
    alerta_emergencia()
    time.sleep(3)

    print("\nPrueba completada.")