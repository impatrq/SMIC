from flask import Flask, request, Response, send_file
from models import db
from routes.api import api_bp
from routes.panel import panel_bp
import os

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///smic.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "smic-secret-key-2026"
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024  # 500 MB max upload

    db.init_app(app)

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(panel_bp, url_prefix="/panel")

    with app.app_context():
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
