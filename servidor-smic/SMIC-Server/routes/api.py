import os
from functools import wraps
from flask import Blueprint, request, jsonify
from flask_login import login_required
from models import db, EventoGPS, EventoSensor, EventoCamara, EventoSistema, EventoAlerta
from datetime import datetime
from routes.almacenamiento import guardar_archivo

api_bp = Blueprint("api", __name__)


def requiere_api_key(vista):
    """Protege los endpoints que reciben datos de los dispositivos (RPi,
    ESP32, cámara) para que una vez expuesto el servidor a internet no
    cualquiera pueda mandar datos falsos o llenar el almacenamiento.
    /api/alerta queda afuera a propósito: la manda el SIM800L, que no
    conviene tocar (ver comunicacion/sim800l.py)."""

    @wraps(vista)
    def envoltura(*args, **kwargs):
        clave_esperada = os.environ.get("SMIC_API_KEY")
        if clave_esperada and request.headers.get("X-API-Key") != clave_esperada:
            return jsonify({"error": "API key inválida o faltante"}), 401
        return vista(*args, **kwargs)

    return envoltura


# ── GPS ──────────────────────────────────────────────────────────────────────

@api_bp.route("/gps", methods=["POST"])
@requiere_api_key
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
@login_required
def ultimo_gps():
    evento = EventoGPS.query.order_by(EventoGPS.timestamp.desc()).first()
    if not evento:
        return jsonify({"error": "sin datos"}), 404
    return jsonify(evento.to_dict())


@api_bp.route("/gps", methods=["GET"])
@login_required
def listar_gps():
    limit = min(int(request.args.get("limit", 100)), 500)
    eventos = EventoGPS.query.order_by(EventoGPS.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── SENSORES ESP32 ────────────────────────────────────────────────────────────

@api_bp.route("/sensor", methods=["POST"])
@requiere_api_key
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
@login_required
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
@login_required
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
@requiere_api_key
def recibir_camara():
    tipo = request.form.get("tipo") or (request.get_json(silent=True) or {}).get("tipo")
    if not tipo:
        return jsonify({"error": "tipo es requerido"}), 400

    imagen_path = None
    if "imagen" in request.files:
        archivo = request.files["imagen"]
        nombre = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}_{archivo.filename}"
        imagen_path = guardar_archivo(archivo.read(), nombre, "uploads")

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
@login_required
def listar_camara():
    tipo = request.args.get("tipo")
    limit = min(int(request.args.get("limit", 50)), 200)

    query = EventoCamara.query
    if tipo:
        query = query.filter_by(tipo=tipo)

    eventos = query.order_by(EventoCamara.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── CLIPS DE VIDEO (conductor + dashcam) ──────────────────────────────────────
# Dos formas de llegar acá:
#  - multipart con archivo "video": flujo local/dev, el servidor guarda el
#    archivo tal cual llega (sin recodificar -- eso ahora lo hace la RPi
#    antes de subir, ver sensores/sincronizador.py).
#  - JSON con "video_url": el dispositivo ya subió el clip directo a Vercel
#    Blob (así se evita el límite de 4.5 MB por request de Vercel
#    Functions) y solo avisa acá para registrar el evento en la base.

@api_bp.route("/video", methods=["POST"])
@requiere_api_key
def recibir_video():
    es_json = request.content_type and "application/json" in request.content_type

    if es_json:
        data = request.get_json(silent=True) or {}
        video_url = data.get("video_url")
        if not video_url:
            return jsonify({"error": "video_url es requerido"}), 400

        evento = EventoCamara(
            tipo=data.get("tipo", "evento"),
            fuente=data.get("fuente", "conductor"),
            evento_id=data.get("evento_id"),
            etiqueta=data.get("nombre_archivo"),
            imagen_path=video_url,
            descripcion=data.get("descripcion", ""),
        )
        db.session.add(evento)
        db.session.commit()
        return jsonify({"ok": True, "id": evento.id}), 201

    if "video" not in request.files:
        return jsonify({"error": "archivo video requerido"}), 400

    archivo   = request.files["video"]
    tipo      = request.form.get("tipo", "evento")
    desc      = request.form.get("descripcion", "")
    fuente    = request.form.get("fuente", "conductor")
    evento_id = request.form.get("evento_id")

    ts     = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    nombre = f"{ts}_{archivo.filename}"
    ruta_final = guardar_archivo(archivo.read(), nombre, "videos")

    evento = EventoCamara(
        tipo=tipo,
        fuente=fuente,
        evento_id=evento_id,
        etiqueta=archivo.filename,
        imagen_path=ruta_final,
        descripcion=desc,
    )
    db.session.add(evento)
    db.session.commit()

    return jsonify({"ok": True, "id": evento.id, "archivo": nombre}), 201


@api_bp.route("/video", methods=["GET"])
@login_required
def listar_videos():
    limit = min(int(request.args.get("limit", 20)), 100)
    tipo  = request.args.get("tipo")

    query = EventoCamara.query.filter(EventoCamara.imagen_path.like("videos/%"))
    if tipo:
        query = query.filter_by(tipo=tipo)

    eventos = query.order_by(EventoCamara.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── ALERTAS (SIM800L: tipo + ubicación mandados en el momento del evento) ─────
# El clip de video NO llega por acá -- eso sigue el camino de /api/video
# (sensores/sincronizador.py), que recién sube el clip cuando detecta
# conexión a la red local. Acá solo entra tipo/lat/lon/fuente_ubicacion,
# para poder dibujar cada evento como un marcador en el mapa del panel.
#
# A propósito sin @requiere_api_key: lo manda comunicacion/sim800l.py desde
# el módulo SIM800L por comandos AT, y no conviene tocar ese código (no
# soporta bien headers custom ni HTTPS -- ver el comentario en ese archivo).

@api_bp.route("/alerta", methods=["POST"])
def recibir_alerta():
    data = request.get_json(silent=True)
    if not data or "tipo" not in data:
        return jsonify({"error": "tipo es requerido"}), 400

    evento = EventoAlerta(
        tipo=data["tipo"],
        latitud=data.get("lat"),
        longitud=data.get("lon"),
        fuente_ubicacion=data.get("fuente_ubicacion"),
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({"ok": True, "id": evento.id}), 201


@api_bp.route("/alerta", methods=["GET"])
@login_required
def listar_alertas():
    limit = min(int(request.args.get("limit", 100)), 500)
    eventos = (
        EventoAlerta.query.order_by(EventoAlerta.timestamp.desc()).limit(limit).all()
    )
    return jsonify([e.to_dict() for e in eventos])


# ── SISTEMA / LOGS ────────────────────────────────────────────────────────────

@api_bp.route("/sistema", methods=["POST"])
@requiere_api_key
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
@login_required
def listar_sistema():
    nivel = request.args.get("nivel")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = EventoSistema.query
    if nivel:
        query = query.filter_by(nivel=nivel)

    eventos = query.order_by(EventoSistema.timestamp.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in eventos])


# ── RESUMEN GENERAL ───────────────────────────────────────────────────────────
# Con API key en vez de login: sensores/sincronizador.py lo usa como simple
# chequeo de conectividad (hay_conexion()) desde la RPi, no hay una sesión
# de navegador ahí.

@api_bp.route("/resumen", methods=["GET"])
@requiere_api_key
def resumen():
    return jsonify({
        "gps": EventoGPS.query.count(),
        "sensores": EventoSensor.query.count(),
        "alertas_sensor": EventoSensor.query.filter_by(alerta=True).count(),
        "camara": EventoCamara.query.count(),
        "sistema": EventoSistema.query.count(),
        "errores": EventoSistema.query.filter_by(nivel="error").count(),
    })
