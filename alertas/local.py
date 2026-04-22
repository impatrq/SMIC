import time
import threading
import winsound    # solo funciona en Windows, en RPi se reemplaza

# --- CONSTANTES ---
DURACION_BEEP    = 500     # milisegundos
FRECUENCIA_BEEP  = 1000    # Hz

# Tipos de alerta
ALERTA_SOMNOLENCIA  = "SOMNOLENCIA"
ALERTA_DISTRACCION  = "DISTRACCION"
ALERTA_EMERGENCIA   = "EMERGENCIA"


# --- FUNCIONES DE SONIDO ---
def beep_simple():
    """Un beep corto. Para alertas leves."""
    winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)


def beep_doble():
    """Dos beeps. Para distraccion."""
    winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)
    time.sleep(0.1)
    winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)


def beep_continuo():
    """Cinco beeps rapidos. Para somnolencia severa."""
    for _ in range(5):
        winsound.Beep(FRECUENCIA_BEEP, 200)
        time.sleep(0.05)


# --- FUNCIONES DE ALERTA ---
def activar_alerta(tipo):
    """
    Activa la alerta segun el tipo de evento detectado.
    El sonido se ejecuta en un hilo separado para no
    bloquear el procesamiento de la camara.
    """
    if tipo == ALERTA_SOMNOLENCIA:
        hilo = threading.Thread(target=beep_continuo)
        mensaje = "ALERTA SOMNOLENCIA: Conductor adormecido"

    elif tipo == ALERTA_DISTRACCION:
        hilo = threading.Thread(target=beep_doble)
        mensaje = "ALERTA DISTRACCION: Conductor distraido"

    elif tipo == ALERTA_EMERGENCIA:
        hilo = threading.Thread(target=beep_continuo)
        mensaje = "EMERGENCIA: Intervencion inmediata requerida"

    else:
        return

    hilo.daemon = True
    hilo.start()
    print(f"\n{'='*45}")
    print(f"  {mensaje}")
    print(f"  Hora: {time.strftime('%H:%M:%S')}")
    print(f"{'='*45}\n")


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
    print("  SMIC - Prueba de alertas locales")
    print("=" * 45)

    print("\nProbando alerta de distraccion...")
    alerta_distraccion()
    time.sleep(2)

    print("Probando alerta de somnolencia...")
    alerta_somnolencia()
    time.sleep(2)

    print("Probando alerta de emergencia...")
    alerta_emergencia()
    time.sleep(2)

    print("\nPrueba completada.")