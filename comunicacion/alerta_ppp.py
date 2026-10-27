"""Alertas por HTTPS directo a Vercel (sale por WiFi o por ppp0 si no hay WiFi).
Reemplaza a comunicacion/sim800l.py. Guardar como comunicacion/alerta_ppp.py.
En camara/monitor.py cambiar:
    from comunicacion.sim800l import mandar_alerta_sim
por:
    from comunicacion.alerta_ppp import mandar_alerta_sim
Prueba suelta:  python alerta_ppp.py prueba
"""
import json, os, sys, threading, time
import requests

try:
    from sensores.gps import ultima_posicion
except Exception:
    ultima_posicion = None

SERVER = os.environ.get("SMIC_SERVER_URL", "https://smic-henna.vercel.app")
API_KEY = os.environ.get("SMIC_API_KEY", "")
URL = f"{SERVER}/api/alerta"
TIMEOUT = 90            # 2G + arranque en frio de Vercel (medido: 10-50 s)
REINTENTOS = 2
EDAD_MAX_GPS = 60
COLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cola_alertas.jsonl")
_lock = threading.Lock()


def _ubicacion():
    if ultima_posicion is None:
        return None
    try:
        p = ultima_posicion(max_edad=EDAD_MAX_GPS)
    except Exception:
        return None
    if not p:
        return None
    return {"lat": p.get("latitud"), "lon": p.get("longitud")}


def _post(payload):
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    r = requests.post(URL, json=payload, headers=headers, timeout=TIMEOUT)
    print(f"[ALERTA] respuesta {r.status_code}: {r.text[:200]}")
    return r.status_code < 400


def _guardar(payload):
    with open(COLA, "a") as f:
        f.write(json.dumps(payload) + "\n")


def _vaciar_cola():
    if not os.path.exists(COLA):
        return
    with open(COLA) as f:
        pendientes = [json.loads(l) for l in f if l.strip()]
    restantes = []
    for p in pendientes:
        try:
            if not _post(p):
                restantes.append(p)
        except Exception:
            restantes.append(p)
    with open(COLA, "w") as f:
        for p in restantes:
            f.write(json.dumps(p) + "\n")


def mandar_alerta_sim(tipo):
    """Misma firma que la version AT. Bloqueante: monitor.py ya la llama en un hilo."""
    ub = _ubicacion()
    payload = {"tipo": tipo, "ts_local": time.time()}
    if ub:
        payload.update({"lat": ub["lat"], "lon": ub["lon"], "fuente_ubicacion": "GPS"})
    with _lock:
        for i in range(REINTENTOS):
            try:
                if _post(payload):
                    print(f"[ALERTA] '{tipo}' enviada ({'GPS' if ub else 'sin ubicacion'})")
                    _vaciar_cola()
                    return True
            except Exception as e:
                print(f"[ALERTA] intento {i+1} fallo: {e}")
            time.sleep(5)
        _guardar(payload)
        print("[ALERTA] sin conexion; guardada en cola")
        return False


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "prueba"
    t0 = time.time()
    ok = mandar_alerta_sim(t)
    print(f"resultado: {'OK' if ok else 'FALLO'} en {time.time()-t0:.1f}s")
