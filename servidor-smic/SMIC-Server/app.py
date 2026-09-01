import os
from flask import Flask, request, Response, send_file
from models import db
from routes.api import api_bp
from routes.panel import panel_bp


def _migrar_columnas_nuevas(app):
    """db.create_all() crea tablas que faltan, pero no agrega columnas
    nuevas a una tabla que ya existe. eventos_camara puede venir de una
    base vieja sin 'fuente' ni 'evento_id' (agregadas para poder
    emparejar los clips de conductor y dashcam), asi que se agregan acá
    a mano si hace falta. Idempotente: no hace nada si ya están."""
    import sqlite3

    ruta_db = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    if not os.path.isabs(ruta_db):
        # SQLAlchemy resuelve las rutas relativas de sqlite:/// contra
        # app.instance_path (la carpeta "instance/"), no contra el cwd.
        ruta_db = os.path.join(app.instance_path, ruta_db)

    if not os.path.exists(ruta_db):
        return  # base nueva: create_all() ya la crea con las columnas al día

    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()
    cursor.execute("PRAGMA table_info(eventos_camara)")
    columnas = [fila[1] for fila in cursor.fetchall()]

    if "fuente" not in columnas:
        cursor.execute(
            "ALTER TABLE eventos_camara ADD COLUMN fuente VARCHAR(32) DEFAULT 'conductor'"
        )
        print("[MIGRACION] Columna 'fuente' agregada a eventos_camara")

    if "evento_id" not in columnas:
        cursor.execute("ALTER TABLE eventos_camara ADD COLUMN evento_id VARCHAR(64)")
        print("[MIGRACION] Columna 'evento_id' agregada a eventos_camara")

    conexion.commit()
    conexion.close()


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smic.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "smic-secret-key-2026"
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

    db.init_app(app)

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(panel_bp, url_prefix="/panel")

    with app.app_context():
        _migrar_columnas_nuevas(app)
        db.create_all()

    # ── STREAMING DE VIDEO CON RANGE REQUESTS ──
    @app.route("/static/videos/<path:filename>")
    def stream_video(filename):
        ruta = os.path.join(app.static_folder, "videos", filename)
        if not os.path.exists(ruta):
            return Response("Not found", status=404)

        tamanio = os.path.getsize(ruta)
        rango   = request.headers.get("Range")

        if not rango:
            return send_file(ruta, mimetype="video/mp4")

        # Parsear Range: bytes=inicio-fin
        bytes_rango = rango.replace("bytes=", "")
        inicio, *fin = bytes_rango.split("-")
        inicio = int(inicio)
        fin    = int(fin[0]) if fin and fin[0] else tamanio - 1
        largo  = fin - inicio + 1

        with open(ruta, "rb") as f:
            f.seek(inicio)
            datos = f.read(largo)

        headers = {
            "Content-Range":  f"bytes {inicio}-{fin}/{tamanio}",
            "Accept-Ranges":  "bytes",
            "Content-Length": str(largo),
            "Content-Type":   "video/mp4",
        }
        return Response(datos, status=206, headers=headers)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
