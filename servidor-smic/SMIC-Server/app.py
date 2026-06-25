from flask import Flask
from models import db
from routes.api import api_bp
from routes.panel import panel_bp

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
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
