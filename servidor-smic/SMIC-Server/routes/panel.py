from flask import Blueprint, render_template
from models import EventoGPS, EventoSensor, EventoCamara, EventoSistema

panel_bp = Blueprint("panel", __name__)

CANTIDAD_EVENTOS_CAMARA = 12

# Cuantos EventoCamara traemos de la base antes de agrupar por
# evento_id. Cada evento genera hasta 2 filas (conductor + dashcam),
# asi que con margen de sobra alcanza para completar
# CANTIDAD_EVENTOS_CAMARA pares aunque algun clip haya llegado suelto
# (por ejemplo si la dashcam no estaba conectada).
LIMITE_CONSULTA_CAMARA = CANTIDAD_EVENTOS_CAMARA * 4


def _agrupar_por_evento(eventos):
    """Agrupa clips de EventoCamara en pares conductor/dashcam usando
    evento_id (compartido entre las 2 camaras de un mismo evento, ver
    camara/monitor.py). Clips sin evento_id (subidos por versiones
    viejas del sincronizador) quedan cada uno en su propio par, con el
    otro lado vacio.

    Devuelve una lista de dicts, mas reciente primero:
      {"evento_id", "tipo", "timestamp", "conductor": EventoCamara|None,
       "dashcam": EventoCamara|None}
    """
    pares = {}
    orden = []

    for e in eventos:
        clave = e.evento_id or f"suelto-{e.id}"
        if clave not in pares:
            pares[clave] = {
                "evento_id": e.evento_id,
                "tipo": e.tipo,
                "timestamp": e.timestamp,
                "conductor": None,
                "dashcam": None,
            }
            orden.append(clave)

        lado = e.fuente if e.fuente == "dashcam" else "conductor"
        pares[clave][lado] = e

        # Nos quedamos con el timestamp mas viejo de los 2 lados: es el
        # que mejor representa el momento real del evento.
        if e.timestamp < pares[clave]["timestamp"]:
            pares[clave]["timestamp"] = e.timestamp

    return [pares[clave] for clave in orden]


@panel_bp.route("/")
@panel_bp.route("/inicio")
def inicio():
    ultimo_gps = EventoGPS.query.order_by(EventoGPS.timestamp.desc()).first()
    alertas = (
        EventoSensor.query.filter_by(alerta=True)
        .order_by(EventoSensor.timestamp.desc())
        .limit(5)
        .all()
    )
    ultimos_sensores = (
        EventoSensor.query.order_by(EventoSensor.timestamp.desc()).limit(10).all()
    )
    eventos_camara_recientes = (
        EventoCamara.query.order_by(EventoCamara.timestamp.desc())
        .limit(LIMITE_CONSULTA_CAMARA)
        .all()
    )
    pares_camara = _agrupar_por_evento(eventos_camara_recientes)[:CANTIDAD_EVENTOS_CAMARA]
    ultimos_logs = (
        EventoSistema.query.order_by(EventoSistema.timestamp.desc()).limit(10).all()
    )

    resumen = {
        "total_gps": EventoGPS.query.count(),
        "total_sensores": EventoSensor.query.count(),
        "alertas_activas": EventoSensor.query.filter_by(alerta=True).count(),
        "total_detecciones": EventoCamara.query.count(),
        "errores_sistema": EventoSistema.query.filter_by(nivel="error").count(),
    }

    return render_template(
        "panel.html",
        ultimo_gps=ultimo_gps,
        alertas=alertas,
        ultimos_sensores=ultimos_sensores,
        pares_camara=pares_camara,
        ultimos_logs=ultimos_logs,
        resumen=resumen,
    )
