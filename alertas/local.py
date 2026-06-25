import time
import threading

ALERTA_SOMNOLENCIA = "SOMNOLENCIA"
ALERTA_DISTRACCION = "DISTRACCION"
ALERTA_EMERGENCIA  = "EMERGENCIA"


def beep_simple():
    """Un beep corto simulado por terminal."""
    print("\a", end="", flush=True)
    time.sleep(0.5)


def beep_doble():
    """Dos beeps para distraccion."""
    print("\a", end="", flush=True)
    time.sleep(0.5)
    print("\a", end="", flush=True)


def beep_continuo():
    """Cinco beeps rapidos para somnolencia."""
    for _ in range(5):
        print("\a", end="", flush=True)
        time.sleep(0.2)


def activar_alerta(tipo):
    if tipo == ALERTA_SOMNOLENCIA:
        hilo   = threading.Thread(target=beep_continuo)
        mensaje = "ALERTA SOMNOLENCIA: Conductor adormecido"
    elif tipo == ALERTA_DISTRACCION:
        hilo   = threading.Thread(target=beep_doble)
        mensaje = "ALERTA DISTRACCION: Conductor distraido"
    elif tipo == ALERTA_EMERGENCIA:
        hilo   = threading.Thread(target=beep_continuo)
        mensaje = "EMERGENCIA: Intervencion inmediata requerida"
    else:
        return

    hilo.daemon = True
    hilo.start()
    print(f"\n{'='*45}")
    print(f" {mensaje}")
    print(f" Hora: {time.strftime('%H:%M:%S')}")
    print(f"{'='*45}\n")


def alerta_somnolencia():
    activar_alerta(ALERTA_SOMNOLENCIA)


def alerta_distraccion():
    activar_alerta(ALERTA_DISTRACCION)


def alerta_emergencia():
    activar_alerta(ALERTA_EMERGENCIA)
