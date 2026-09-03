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
    fuente = db.Column(db.String(32), default="conductor")  # conductor o dashcam
    evento_id = db.Column(db.String(64), index=True)  # comparten valor el clip del
                                                        # conductor y el de la dashcam
                                                        # de un mismo evento (ver
                                                        # camara/monitor.py disparar_evento)
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
            "fuente": self.fuente,
            "evento_id": self.evento_id,
            "confianza": self.confianza,
            "etiqueta": self.etiqueta,
            "imagen_path": self.imagen_path,
            "resolucion": self.resolucion,
            "descripcion": self.descripcion,
            "timestamp": self.timestamp.isoformat(),
        }


class EventoAlerta(db.Model):
    """Alerta mandada en el momento del evento por el SIM800L (mientras se
    esta manejando, con datos moviles). Solo tipo + ubicacion aproximada --
    el clip de video NO viaja por aca, se graba y queda en la RPi4 y llega
    despues por /api/video cuando sensores/sincronizador.py detecta
    conexion a la red local (ver camara/monitor.py disparar_evento)."""
    __tablename__ = "eventos_alerta"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(64), nullable=False)   # somnolencia, distraccion
    latitud = db.Column(db.Float)                      # puede faltar si no hubo fix
    longitud = db.Column(db.Float)
    fuente_ubicacion = db.Column(db.String(16))        # "GSM" (antenas) o "GPS"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "tipo": self.tipo,
            "latitud": self.latitud,
            "longitud": self.longitud,
            "fuente_ubicacion": self.fuente_ubicacion,
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
