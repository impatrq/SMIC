import os
from flask import Blueprint, request, jsonify
from models import db, EventoGPS, EventoSensor, EventoCamara, EventoSistema
from datetime import datetime

api_bp = Blueprint("api", __name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# ── GPS ──────────────────────────────────────────────────────────────────────

@api_bp.route("/gps", methods=["POST"])
def recibir_gps():
    data = request.get_json(silent=True)
    if not data or "latitud" not in data or "longitud" not in data:
        return jsonify({"error": "latitud y longitud son requeridos"}), 400

    evento = EventoGPS(
        latitud=data["latitud"],
        longitud=data["longitud"],
        altitud=data.get("altitud"),
        velocidad=data.get("velocidad"),
        satelites=data.get("satelites"),
        precision=data.get("precision"),
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({"ok": True, "id": evento.id}), 201


@api_bp.route("/gps/ultimo", methods=["GET"])
def ultimo_gps():
    evento = EventoGPS.query.order_by(EventoGPS.timestamp.desc()).first()
    if not evento:
        return jsonify({"error": "sin datos"}), 404
    return jsonify(evento.to_dict())


@api_bp.route("/gps", methods=["GET"])
def listar_gps():
    limit = min(int(request.args.get("limit", 100)), 500)
    eventos = EventoGPS.query.order_by(EventoGPS.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── SENSORES ESP32 ────────────────────────────────────────────────────────────

@api_bp.route("/sensor", methods=["POST"])
def recibir_sensor():
    data = request.get_json(silent=True)
    if not data or "dispositivo" not in data or "tipo" not in data:
        return jsonify({"error": "dispositivo y tipo son requeridos"}), 400

    evento = EventoSensor(
        dispositivo=data["dispositivo"],
        tipo=data["tipo"],
        valor=data.get("valor"),
        unidad=data.get("unidad", ""),
        alerta=bool(data.get("alerta", False)),
        mensaje=data.get("mensaje", ""),
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({"ok": True, "id": evento.id}), 201


@api_bp.route("/sensor", methods=["GET"])
def listar_sensores():
    dispositivo = request.args.get("dispositivo")
    tipo = request.args.get("tipo")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = EventoSensor.query
    if dispositivo:
        query = query.filter_by(dispositivo=dispositivo)
    if tipo:
        query = query.filter_by(tipo=tipo)

    eventos = query.order_by(EventoSensor.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


@api_bp.route("/sensor/alertas", methods=["GET"])
def alertas_sensor():
    eventos = (
        EventoSensor.query.filter_by(alerta=True)
        .order_by(EventoSensor.timestamp.desc())
        .limit(50)
        .all()
    )
    return jsonify([e.to_dict() for e in eventos])


# ── CÁMARA ────────────────────────────────────────────────────────────────────

@api_bp.route("/camara", methods=["POST"])
def recibir_camara():
    tipo = request.form.get("tipo") or (request.get_json(silent=True) or {}).get("tipo")
    if not tipo:
        return jsonify({"error": "tipo es requerido"}), 400

    imagen_path = None
    if "imagen" in request.files:
        archivo = request.files["imagen"]
        nombre = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{archivo.filename}"
        ruta_completa = os.path.join(UPLOADS_DIR, nombre)
        archivo.save(ruta_completa)
        imagen_path = f"uploads/{nombre}"

    # Acepta tanto multipart/form-data como JSON puro
    if request.content_type and "multipart" in request.content_type:
        data = request.form
        get = lambda k: data.get(k)
    else:
        data = request.get_json(silent=True) or {}
        get = lambda k: data.get(k)

    evento = EventoCamara(
        tipo=tipo,
        confianza=float(get("confianza")) if get("confianza") else None,
        etiqueta=get("etiqueta"),
        imagen_path=imagen_path,
        resolucion=get("resolucion"),
        descripcion=get("descripcion"),
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({"ok": True, "id": evento.id}), 201


@api_bp.route("/camara", methods=["GET"])
def listar_camara():
    tipo = request.args.get("tipo")
    limit = min(int(request.args.get("limit", 50)), 200)

    query = EventoCamara.query
    if tipo:
        query = query.filter_by(tipo=tipo)

    eventos = query.order_by(EventoCamara.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── SISTEMA / LOGS ────────────────────────────────────────────────────────────

@api_bp.route("/sistema", methods=["POST"])
def recibir_sistema():
    data = request.get_json(silent=True)
    if not data or "nivel" not in data or "mensaje" not in data:
        return jsonify({"error": "nivel y mensaje son requeridos"}), 400

    evento = EventoSistema(
        nivel=data["nivel"],
        fuente=data.get("fuente", "rpi"),
        mensaje=data["mensaje"],
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({"ok": True, "id": evento.id}), 201


@api_bp.route("/sistema", methods=["GET"])
def listar_sistema():
    nivel = request.args.get("nivel")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = EventoSistema.query
    if nivel:
        query = query.filter_by(nivel=nivel)

    eventos = query.order_by(EventoSistema.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── RESUMEN GENERAL ───────────────────────────────────────────────────────────

@api_bp.route("/resumen", methods=["GET"])
def resumen():
    return jsonify({
        "gps": EventoGPS.query.count(),
        "sensores": EventoSensor.query.count(),
        "alertas_sensor": EventoSensor.query.filter_by(alerta=True).count(),
        "camara": EventoCamara.query.count(),
        "sistema": EventoSistema.query.count(),
        "errores": EventoSistema.query.filter_by(nivel="error").count(),
    })
