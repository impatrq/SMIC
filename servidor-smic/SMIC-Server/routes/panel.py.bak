from flask import Blueprint, render_template
from models import EventoGPS, EventoSensor, EventoCamara, EventoSistema

panel_bp = Blueprint("panel", __name__)


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
    ultimas_detecciones = (
        EventoCamara.query.order_by(EventoCamara.timestamp.desc()).limit(6).all()
    )
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
        ultimas_detecciones=ultimas_detecciones,
        ultimos_logs=ultimos_logs,
        resumen=resumen,
    )
