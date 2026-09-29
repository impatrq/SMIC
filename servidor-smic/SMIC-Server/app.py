import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_login import LoginManager
from models import db
from routes.api import api_bp
from routes.panel import panel_bp
from routes.auth import auth_bp, Admin


def _normalizar_url_db(url):
    """Algunos proveedores (Heroku-style, Neon incluido a veces) todavía dan
    el prefijo viejo 'postgres://', que SQLAlchemy 2.x rechaza -- tiene que
    ser 'postgresql://'."""
    if url and url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def _migrar_columnas_nuevas(app):
    """db.create_all() crea tablas que faltan, pero no agrega columnas
    nuevas a una tabla que ya existe. eventos_camara puede venir de una
    base vieja sin 'fuente' ni 'evento_id' (agregadas para poder
    emparejar los clips de conductor y dashcam), asi que se agregan acá
    a mano si hace falta. Idempotente: no hace nada si ya están.

    Solo aplica a SQLite (desarrollo local) -- una base Postgres nueva en
    Vercel ya arranca con create_all() al día, y esta migración a mano
    está escrita en sqlite3, no sirve para Postgres."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        return

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

    database_url = _normalizar_url_db(os.environ.get("DATABASE_URL"))
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///smic.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "smic-dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Iniciá sesión para ver esta página"
    login_manager.init_app(app)

    @login_manager.user_loader
    def cargar_usuario(user_id):
        return Admin.cargar(user_id)

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(panel_bp, url_prefix="/panel")

    with app.app_context():
        _migrar_columnas_nuevas(app)
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
