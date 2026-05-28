from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Evento(db.Model):
    __tablename__ = "eventos"

    id        = db.Column(db.Integer, primary_key=True)
    tipo      = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    duracion  = db.Column(db.Float, nullable=True)
    clip_url  = db.Column(db.String(300), nullable=True)
    latitud   = db.Column(db.Float, default=-34.7204)
    longitud  = db.Column(db.Float, default=-58.2538)
    volante   = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id":        self.id,
            "tipo":      self.tipo,
            "timestamp": self.timestamp.strftime("%d/%m/%Y %H:%M:%S"),
            "duracion":  self.duracion,
            "clip_url":  self.clip_url,
            "latitud":   self.latitud,
            "longitud":  self.longitud,
            "volante":   self.volante,
        }

    def __repr__(self):
        return f"<Evento {self.tipo} — {self.timestamp}>"