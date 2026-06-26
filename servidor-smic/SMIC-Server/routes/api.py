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


# ── VIDEO ─────────────────────────────────────────────────────────────────────

VIDEOS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)

FFMPEG = r"C:\Users\fnmov\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"

@api_bp.route("/video", methods=["POST"])
def recibir_video():
    import subprocess

    if "video" not in request.files:
        return jsonify({"error": "archivo video requerido"}), 400

    archivo = request.files["video"]
    tipo    = request.form.get("tipo", "evento")
    desc    = request.form.get("descripcion", "")

    # Guardar .avi temporal
    ts         = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    nombre_avi = f"{ts}_{archivo.filename}"
    ruta_avi   = os.path.join(VIDEOS_DIR, nombre_avi)
    archivo.save(ruta_avi)

    # Convertir a .mp4
    nombre_mp4 = nombre_avi.replace(".avi", ".mp4")
    ruta_mp4   = os.path.join(VIDEOS_DIR, nombre_mp4)

    try:
        subprocess.run(
            [FFMPEG, "-i", ruta_avi, "-c:v", "libx264", "-preset", "fast",
             "-crf", "28", "-c:a", "aac", "-y", ruta_mp4],
            capture_output=True, timeout=120, check=True
        )
        os.remove(ruta_avi)
        ruta_final   = f"videos/{nombre_mp4}"
        nombre_final = nombre_mp4
    except Exception as e:
        print(f"[VIDEO] ffmpeg falló: {e}")
        ruta_final   = f"videos/{nombre_avi}"
        nombre_final = nombre_avi

    evento = EventoCamara(
        tipo=tipo,
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
