from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class EventoGPS(db.Model):
    __tablename__ = "eventos_gps"

    id = db.Column(db.Integer, primary_key=True)
    latitud = db.Column(db.Float, nullable=False)
    longitud = db.Column(db.Float, nullable=False)
    altitud = db.Column(db.Float)
    velocidad = db.Column(db.Float)
    satelites = db.Column(db.Integer)
    precision = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "latitud": self.latitud,
            "longitud": self.longitud,
            "altitud": self.altitud,
            "velocidad": self.velocidad,
            "satelites": self.satelites,
            "precision": self.precision,
            "timestamp": self.timestamp.isoformat(),
        }


class EventoSensor(db.Model):
    __tablename__ = "eventos_sensor"

    id = db.Column(db.Integer, primary_key=True)
    dispositivo = db.Column(db.String(64), nullable=False)  # ID del ESP32
    tipo = db.Column(db.String(64), nullable=False)         # temperatura, humedad, movimiento, etc.
    valor = db.Column(db.Float)
    unidad = db.Column(db.String(16))
    alerta = db.Column(db.Boolean, default=False)
    mensaje = db.Column(db.String(256))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "dispositivo": self.dispositivo,
            "tipo": self.tipo,
            "valor": self.valor,
            "unidad": self.unidad,
            "alerta": self.alerta,
            "mensaje": self.mensaje,
            "timestamp": self.timestamp.isoformat(),
        }


class EventoCamara(db.Model):
    __tablename__ = "eventos_camara"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(64), nullable=False)   # deteccion, snapshot, alerta
    confianza = db.Column(db.Float)
    etiqueta = db.Column(db.String(128))              # persona, vehiculo, objeto
    imagen_path = db.Column(db.String(256))           # ruta relativa al archivo guardado
    resolucion = db.Column(db.String(32))
    descripcion = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "confianza": self.confianza,
            "etiqueta": self.etiqueta,
            "imagen_path": self.imagen_path,
            "resolucion": self.resolucion,
            "descripcion": self.descripcion,
            "timestamp": self.timestamp.isoformat(),
        }


class EventoSistema(db.Model):
    __tablename__ = "eventos_sistema"

    id = db.Column(db.Integer, primary_key=True)
    nivel = db.Column(db.String(16), nullable=False)  # info, warning, error, critico
    fuente = db.Column(db.String(64))                 # rpi, esp32, camara, gps
    mensaje = db.Column(db.String(512), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "nivel": self.nivel,
            "fuente": self.fuente,
            "mensaje": self.mensaje,
            "timestamp": self.timestamp.isoformat(),
        }
