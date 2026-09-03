import os
from flask import Blueprint, request, jsonify
from models import db, EventoGPS, EventoSensor, EventoCamara, EventoSistema, EventoAlerta
from datetime import datetime

api_bp = Blueprint("api", __name__)

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)

# Se puede pisar con la variable de entorno SMIC_FFMPEG si el binario no
# está en el PATH del sistema donde corre el servidor.
FFMPEG = os.environ.get("SMIC_FFMPEG", "ffmpeg")


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


# ── CLIPS DE VIDEO (conductor + dashcam) ──────────────────────────────────────

@api_bp.route("/video", methods=["POST"])
def recibir_video():
    import subprocess

    if "video" not in request.files:
        return jsonify({"error": "archivo video requerido"}), 400

    archivo    = request.files["video"]
    tipo       = request.form.get("tipo", "evento")
    desc       = request.form.get("descripcion", "")
    fuente     = request.form.get("fuente", "conductor")
    evento_id  = request.form.get("evento_id")

    # Guardar el archivo tal cual llega (.avi de la camara del conductor
    # o .mp4 crudo de la dashcam)
    ts              = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    nombre_original = f"{ts}_{archivo.filename}"
    ruta_original   = os.path.join(VIDEOS_DIR, nombre_original)
    archivo.save(ruta_original)

    # Convertir siempre a .mp4 con H.264: el .avi de la camara del
    # conductor y el .mp4 crudo de la dashcam (codec mp4v) no se
    # reproducen bien en el navegador sin re-codificar
    base_nombre, _ = os.path.splitext(nombre_original)
    nombre_mp4     = f"{base_nombre}.mp4"
    ruta_mp4       = os.path.join(VIDEOS_DIR, nombre_mp4)

    # Si el original ya se llama igual que el destino (la dashcam ya
    # manda .mp4), usamos un archivo temporal para que ffmpeg no lea y
    # escriba el mismo archivo a la vez
    if ruta_original == ruta_mp4:
        ruta_salida_ffmpeg = ruta_original + ".tmp.mp4"
    else:
        ruta_salida_ffmpeg = ruta_mp4

    try:
        subprocess.run(
            [FFMPEG, "-i", ruta_original, "-c:v", "libx264", "-preset", "fast",
             "-crf", "28", "-c:a", "aac", "-y", ruta_salida_ffmpeg],
            capture_output=True, timeout=120, check=True
        )
        os.remove(ruta_original)
        if ruta_salida_ffmpeg != ruta_mp4:
            os.replace(ruta_salida_ffmpeg, ruta_mp4)
        ruta_final   = f"videos/{nombre_mp4}"
        nombre_final = nombre_mp4
    except Exception as e:
        print(f"[VIDEO] ffmpeg falló: {e}")
        ruta_final   = f"videos/{nombre_original}"
        nombre_final = nombre_original

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

    return jsonify({"ok": True, "id": evento.id, "archivo": nombre_final}), 201


@api_bp.route("/video", methods=["GET"])
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
def listar_alertas():
    limit = min(int(request.args.get("limit", 100)), 500)
    eventos = (
        EventoAlerta.query.order_by(EventoAlerta.timestamp.desc()).limit(limit).all()
    )
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


# ── SINCRONIZACIÓN DE CLIPS ───────────────────────────────────────────────────

@api_bp.route("/sync", methods=["POST"])
def sync_clips():
    import subprocess

    clips_destino = os.path.join(os.path.expanduser("~"), "Desktop", "SMIC_clips")
    os.makedirs(clips_destino, exist_ok=True)

    try:
        resultado = subprocess.run(
            [
                "scp", "-r",
                "proyecto-smic@SMIC.local:/home/proyecto-smic/SMIC/eventos/.",
                clips_destino
            ],
            capture_output=True,
            text=True,
            timeout=60
        )

        if resultado.returncode == 0:
            return jsonify({"ok": True, "mensaje": "Clips sincronizados correctamente"}), 200
        else:
            return jsonify({"ok": False, "mensaje": resultado.stderr}), 500

    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "mensaje": "Tiempo de espera agotado"}), 504
    except Exception as e:
        return jsonify({"ok": False, "mensaje": str(e)}), 500
