"""
SMIC - Utilidades para webcams USB (camara del conductor y dashcam)

Ahora que el sistema tiene DOS webcams USB (conductor + camino), ya no
sirve elegirlas por numero de indice (/dev/video0, /dev/video1, ...):
Linux asigna esos numeros segun el orden en que detecta cada camara al
arrancar, y ese orden puede cambiar entre reinicios. Ademas cada webcam
crea 2 nodos (uno de captura real y otro de metadata que "abre" pero
nunca entrega un frame), asi que con 2 webcams hay 4 nodos y es muy facil
que el conductor termine viendo el camino o al reves.

Solucion: identificar cada camara por el PUERTO USB fisico donde esta
enchufada, usando los links estables que crea Linux en /dev/v4l/by-path/.
Ese nombre depende solo del puerto, no del orden de deteccion:

  /dev/v4l/by-path/platform-fd500000.pcie-pci-0000:01:00.0-usb-0:1.3:1.0-video-index0
                                                               ^^^ puerto USB

Los que terminan en "-video-index0" son siempre el nodo de captura real
(los "-video-index1" son los de metadata), asi que tambien se elimina el
problema del nodo de metadata que tenia la dashcam.

Para ver que camara quedo en cada puerto, correr en la Raspberry:

    source ~/SMIC/venv/bin/activate
    python3 ~/SMIC/camara/usb_cam.py

Eso lista las webcams, saca una foto de prueba de cada una en
~/SMIC/prueba_camaras/ y muestra el texto exacto para pegar en
CAMARA_CONDUCTOR (monitor.py) y DASHCAM_CAMARA (dashcam.py).
"""

import os
import re
import glob
import threading

import cv2

CARPETA_BY_PATH = "/dev/v4l/by-path"

# Dispositivos que ya abrio alguna parte del programa, para que la
# dashcam nunca intente abrir la misma webcam que ya tiene el monitor
# del conductor (y viceversa) cuando se usa la deteccion automatica.
_en_uso = set()
_lock_en_uso = threading.Lock()


def listar_webcams_usb():
    """
    Devuelve la lista (ordenada) de webcams USB conectadas, como links
    estables de /dev/v4l/by-path/ que apuntan al nodo de CAPTURA de cada
    camara (los de metadata se descartan). Lista vacia si no hay ninguna.
    """
    patron = os.path.join(CARPETA_BY_PATH, "*usb*-video-index0")
    # Las versiones nuevas de udev crean DOS links por camara para el
    # mismo puerto ("...-usb-0:1.4:1.0-..." y "...-usbv2-0:1.4:1.0-..."),
    # los dos apuntando al mismo /dev/videoN. Se deja uno solo por
    # dispositivo real, prefiriendo el nombre "usb-" (el clasico).
    por_dispositivo = {}
    for ruta in sorted(glob.glob(patron), key=lambda r: ("usbv2-" in r, r)):
        real = os.path.realpath(ruta)
        por_dispositivo.setdefault(real, ruta)
    return sorted(por_dispositivo.values())


def _a_indice(dispositivo):
    """
    Convierte lo que se configure (int, '/dev/videoN' o un link de
    /dev/v4l/by-path/...) al numero N de /dev/videoN, que es lo que
    cv2.VideoCapture acepta con seguridad en cualquier version de OpenCV.
    Devuelve (indice, ruta_real) o (None, None) si no existe.
    """
    if isinstance(dispositivo, int):
        return dispositivo, f"/dev/video{dispositivo}"

    if not os.path.exists(dispositivo):
        return None, None

    real = os.path.realpath(dispositivo)
    m = re.search(r"/dev/video(\d+)$", real)
    if not m:
        return None, None
    return int(m.group(1)), real


def abrir_webcam(dispositivo, ancho, alto, fps, etiqueta="CAMARA"):
    """
    Abre una webcam USB y verifica que realmente entregue un frame.

    dispositivo: link de /dev/v4l/by-path/... (recomendado), '/dev/videoN',
                 un int, o None para elegir automaticamente la primera
                 webcam USB que todavia no este en uso.

    Devuelve (camara, ruta_real) o (None, None) si no se pudo.
    """
    if dispositivo is None:
        candidatos = listar_webcams_usb()
        if not candidatos:
            print(f"[{etiqueta}] No se encontro ninguna webcam USB en {CARPETA_BY_PATH}")
            return None, None
        print(f"[{etiqueta}] Sin camara configurada, se prueba la primera libre "
              f"(conviene fijarla, ver camara/usb_cam.py)")
    else:
        candidatos = [dispositivo]

    for cand in candidatos:
        indice, real = _a_indice(cand)
        if indice is None:
            print(f"[{etiqueta}] No existe el dispositivo {cand} (esta enchufada en ese puerto?)")
            continue

        with _lock_en_uso:
            if real in _en_uso:
                continue

        camara = cv2.VideoCapture(indice, cv2.CAP_V4L2)
        if not camara.isOpened():
            camara.release()
            continue

        # MJPG en vez de YUYV: con 2 webcams en el mismo bus USB, YUYV sin
        # comprimir a 640x480 reserva tanto ancho de banda que la segunda
        # camara suele fallar al arrancar ("No space left on device").
        # MJPG va comprimido y deja lugar para las dos.
        camara.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        camara.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
        camara.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
        camara.set(cv2.CAP_PROP_FPS, fps)
        # Buffer interno minimo: queremos siempre el frame mas nuevo, no
        # uno viejo que quedo encolado en el driver.
        camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ret, frame = camara.read()
        if ret and frame is not None:
            with _lock_en_uso:
                _en_uso.add(real)
            ancho_real = int(camara.get(cv2.CAP_PROP_FRAME_WIDTH))
            alto_real = int(camara.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"[{etiqueta}] Webcam abierta: {cand} -> {real} "
                  f"({ancho_real}x{alto_real})")
            return camara, real

        camara.release()

    return None, None


def liberar_webcam(camara, ruta_real):
    """Cierra la webcam y la marca como libre."""
    if camara is not None:
        camara.release()
    with _lock_en_uso:
        _en_uso.discard(ruta_real)


# ==================== DIAGNOSTICO ====================
# python3 ~/SMIC/camara/usb_cam.py
if __name__ == "__main__":
    carpeta_fotos = os.path.expanduser("~/SMIC/prueba_camaras")
    os.makedirs(carpeta_fotos, exist_ok=True)

    webcams = listar_webcams_usb()
    print("=" * 60)
    print(f" Webcams USB encontradas: {len(webcams)}")
    print("=" * 60)

    if not webcams:
        print("Ninguna. Revisar con: ls -l /dev/v4l/by-path/  y  v4l2-ctl --list-devices")

    for n, ruta in enumerate(webcams, start=1):
        cam, real = abrir_webcam(ruta, 640, 480, 15, etiqueta=f"CAM {n}")
        if cam is None:
            print(f"\n[{n}] {ruta}\n    -> NO entrego frame")
            continue
        # Descartar algunos frames para que se ajuste la exposicion
        for _ in range(10):
            ret, frame = cam.read()
        foto = os.path.join(carpeta_fotos, f"camara_{n}.jpg")
        if ret:
            cv2.imwrite(foto, frame)
        liberar_webcam(cam, real)
        brillo = frame.mean() if ret else 0
        print(f"\n[{n}] {ruta}")
        print(f"    -> {real} | foto: {foto} | brillo medio: {brillo:.0f}")
        print(f"    Para usarla, pegar:  \"{ruta}\"")

    print("\nTip: tapa una camara con la mano y volve a correr esto; la que")
    print("tenga el brillo mas bajo es la que tapaste.")
