"""
SMIC - fix_servidor.py
Agrega soporte para los clips de la dashcam en el servidor Flask.

Que hace:
1. Backup de los 4 archivos antes de tocar nada
2. models.py: agrega la columna 'fuente' a EventoCamara
3. routes/api.py: el endpoint /video generaliza el manejo de extension
   de archivo (antes asumia siempre .avi) y agrega el campo 'fuente'
4. routes/panel.py: sube el limite de detecciones mostradas de 6 a 12
5. templates/panel.html: agrega un badge CONDUCTOR / DASHCAM en cada card
6. Migra la base de datos smic.db existente agregando la columna nueva
   (db.create_all() no altera tablas que ya existen)

Correr desde la carpeta SMIC-Server (donde esta app.py):
    python fix_servidor.py

Despues de correrlo, hay que reiniciar el servidor Flask para que
tome los cambios de models.py.
"""

import os
import shutil
import sqlite3

RUTA_MODELS   = "models.py"
RUTA_API      = os.path.join("routes", "api.py")
RUTA_PANEL_PY = os.path.join("routes", "panel.py")
RUTA_PANEL_HTML = os.path.join("templates", "panel.html")


def reemplazar_unico(contenido, viejo, nuevo, descripcion):
    """Reemplaza 'viejo' por 'nuevo' solo si aparece exactamente una vez.
    Si no aparece, o aparece mas de una vez, frena todo sin tocar el
    archivo, para no arriesgarse a romper algo que ya funciona."""
    apariciones = contenido.count(viejo)

    if apariciones == 0:
        raise RuntimeError(
            f"No se encontro el bloque esperado para: {descripcion}\n"
            f"El archivo puede haber cambiado. No se modifico nada."
        )
    if apariciones > 1:
        raise RuntimeError(
            f"El bloque para '{descripcion}' aparece {apariciones} veces, "
            f"deberia aparecer una sola. No se modifico nada."
        )

    return contenido.replace(viejo, nuevo)


def patchear_archivo(ruta, reemplazos):
    """Aplica una lista de (viejo, nuevo, descripcion) a un archivo,
    con backup previo."""
    if not os.path.exists(ruta):
        print(f"No se encontro el archivo: {ruta}")
        return False

    with open(ruta, "r", encoding="utf-8") as f:
        contenido = f.read()

    ruta_backup = ruta + ".bak"
    shutil.copy2(ruta, ruta_backup)
    print(f"Backup creado en: {ruta_backup}")

    for viejo, nuevo, descripcion in reemplazos:
        contenido = reemplazar_unico(contenido, viejo, nuevo, descripcion)

    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"{ruta} actualizado correctamente.")
    return True


def migrar_base_de_datos():
    """Agrega la columna 'fuente' a la tabla eventos_camara si no existe."""
    posibles_rutas = [
        "smic.db",
        os.path.join("instance", "smic.db"),
    ]

    ruta_db = None
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            ruta_db = ruta
            break

    if ruta_db is None:
        print(
            "No se encontro smic.db en este momento (se creara con la "
            "columna nueva la primera vez que arranque el servidor con "
            "el models.py actualizado, no hace falta migrar)."
        )
        return

    conexion = sqlite3.connect(ruta_db)
    cursor = conexion.cursor()

    cursor.execute("PRAGMA table_info(eventos_camara)")
    columnas = [fila[1] for fila in cursor.fetchall()]

    if "fuente" in columnas:
        print(f"La columna 'fuente' ya existe en {ruta_db}, no hace falta migrar.")
    else:
        cursor.execute(
            "ALTER TABLE eventos_camara ADD COLUMN fuente VARCHAR(32) DEFAULT 'conductor'"
        )
        conexion.commit()
        print(f"Columna 'fuente' agregada a {ruta_db}.")

    conexion.close()


def main():
    # ---------- models.py ----------
    reemplazos_models = [
        (
            'class EventoCamara(db.Model):\n'
            '    __tablename__ = "eventos_camara"\n'
            '\n'
            '    id = db.Column(db.Integer, primary_key=True)\n'
            '    tipo = db.Column(db.String(64), nullable=False)   # deteccion, snapshot, alerta\n'
            '    confianza = db.Column(db.Float)\n'
            '    etiqueta = db.Column(db.String(128))              # persona, vehiculo, objeto\n'
            '    imagen_path = db.Column(db.String(256))           # ruta relativa al archivo guardado\n'
            '    resolucion = db.Column(db.String(32))\n'
            '    descripcion = db.Column(db.String(512))\n'
            '    timestamp = db.Column(db.DateTime, default=datetime.utcnow)\n'
            '\n'
            '    def to_dict(self):\n'
            '        return {\n'
            '            "id": self.id,\n'
            '            "tipo": self.tipo,\n'
            '            "confianza": self.confianza,\n'
            '            "etiqueta": self.etiqueta,\n'
            '            "imagen_path": self.imagen_path,\n'
            '            "resolucion": self.resolucion,\n'
            '            "descripcion": self.descripcion,\n'
            '            "timestamp": self.timestamp.isoformat(),\n'
            '        }\n',

            'class EventoCamara(db.Model):\n'
            '    __tablename__ = "eventos_camara"\n'
            '\n'
            '    id = db.Column(db.Integer, primary_key=True)\n'
            '    tipo = db.Column(db.String(64), nullable=False)   # deteccion, snapshot, alerta\n'
            '    fuente = db.Column(db.String(32), default="conductor")  # conductor o dashcam\n'
            '    confianza = db.Column(db.Float)\n'
            '    etiqueta = db.Column(db.String(128))              # persona, vehiculo, objeto\n'
            '    imagen_path = db.Column(db.String(256))           # ruta relativa al archivo guardado\n'
            '    resolucion = db.Column(db.String(32))\n'
            '    descripcion = db.Column(db.String(512))\n'
            '    timestamp = db.Column(db.DateTime, default=datetime.utcnow)\n'
            '\n'
            '    def to_dict(self):\n'
            '        return {\n'
            '            "id": self.id,\n'
            '            "tipo": self.tipo,\n'
            '            "fuente": self.fuente,\n'
            '            "confianza": self.confianza,\n'
            '            "etiqueta": self.etiqueta,\n'
            '            "imagen_path": self.imagen_path,\n'
            '            "resolucion": self.resolucion,\n'
            '            "descripcion": self.descripcion,\n'
            '            "timestamp": self.timestamp.isoformat(),\n'
            '        }\n',

            "columna fuente en EventoCamara"
        ),
    ]

    # ---------- routes/api.py ----------
    reemplazos_api = [
        (
            '@api_bp.route("/video", methods=["POST"])\n'
            'def recibir_video():\n'
            '    import subprocess\n'
            '\n'
            '    if "video" not in request.files:\n'
            '        return jsonify({"error": "archivo video requerido"}), 400\n'
            '\n'
            '    archivo = request.files["video"]\n'
            '    tipo    = request.form.get("tipo", "evento")\n'
            '    desc    = request.form.get("descripcion", "")\n'
            '\n'
            '    # Guardar .avi temporal\n'
            '    ts         = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")\n'
            '    nombre_avi = f"{ts}_{archivo.filename}"\n'
            '    ruta_avi   = os.path.join(VIDEOS_DIR, nombre_avi)\n'
            '    archivo.save(ruta_avi)\n'
            '\n'
            '    # Convertir a .mp4\n'
            '    nombre_mp4 = nombre_avi.replace(".avi", ".mp4")\n'
            '    ruta_mp4   = os.path.join(VIDEOS_DIR, nombre_mp4)\n'
            '\n'
            '    try:\n'
            '        subprocess.run(\n'
            '            [FFMPEG, "-i", ruta_avi, "-c:v", "libx264", "-preset", "fast",\n'
            '             "-crf", "28", "-c:a", "aac", "-y", ruta_mp4],\n'
            '            capture_output=True, timeout=120, check=True\n'
            '        )\n'
            '        os.remove(ruta_avi)\n'
            '        ruta_final   = f"videos/{nombre_mp4}"\n'
            '        nombre_final = nombre_mp4\n'
            '    except Exception as e:\n'
            '        print(f"[VIDEO] ffmpeg falló: {e}")\n'
            '        ruta_final   = f"videos/{nombre_avi}"\n'
            '        nombre_final = nombre_avi\n'
            '\n'
            '    evento = EventoCamara(\n'
            '        tipo=tipo,\n'
            '        etiqueta=archivo.filename,\n'
            '        imagen_path=ruta_final,\n'
            '        descripcion=desc,\n'
            '    )\n'
            '    db.session.add(evento)\n'
            '    db.session.commit()\n'
            '\n'
            '    return jsonify({"ok": True, "id": evento.id, "archivo": nombre_final}), 201\n',

            '@api_bp.route("/video", methods=["POST"])\n'
            'def recibir_video():\n'
            '    import subprocess\n'
            '\n'
            '    if "video" not in request.files:\n'
            '        return jsonify({"error": "archivo video requerido"}), 400\n'
            '\n'
            '    archivo = request.files["video"]\n'
            '    tipo    = request.form.get("tipo", "evento")\n'
            '    desc    = request.form.get("descripcion", "")\n'
            '    fuente  = request.form.get("fuente", "conductor")\n'
            '\n'
            '    # Guardar el archivo tal cual llega (.avi de la camara principal\n'
            '    # o .mp4 de la dashcam)\n'
            '    ts              = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")\n'
            '    nombre_original = f"{ts}_{archivo.filename}"\n'
            '    ruta_original   = os.path.join(VIDEOS_DIR, nombre_original)\n'
            '    archivo.save(ruta_original)\n'
            '\n'
            '    # Convertir siempre a .mp4 con H.264: el .avi de la camara\n'
            '    # principal y el .mp4 crudo de la dashcam (codec mp4v) no se\n'
            '    # reproducen bien en el navegador sin re-codificar\n'
            '    base_nombre, _ = os.path.splitext(nombre_original)\n'
            '    nombre_mp4     = f"{base_nombre}.mp4"\n'
            '    ruta_mp4       = os.path.join(VIDEOS_DIR, nombre_mp4)\n'
            '\n'
            '    # Si el original ya se llama igual que el destino (dashcam ya\n'
            '    # manda .mp4), usamos un archivo temporal para que ffmpeg no\n'
            '    # lea y escriba el mismo archivo a la vez\n'
            '    if ruta_original == ruta_mp4:\n'
            '        ruta_salida_ffmpeg = ruta_original + ".tmp.mp4"\n'
            '    else:\n'
            '        ruta_salida_ffmpeg = ruta_mp4\n'
            '\n'
            '    try:\n'
            '        subprocess.run(\n'
            '            [FFMPEG, "-i", ruta_original, "-c:v", "libx264", "-preset", "fast",\n'
            '             "-crf", "28", "-c:a", "aac", "-y", ruta_salida_ffmpeg],\n'
            '            capture_output=True, timeout=120, check=True\n'
            '        )\n'
            '        os.remove(ruta_original)\n'
            '        if ruta_salida_ffmpeg != ruta_mp4:\n'
            '            os.replace(ruta_salida_ffmpeg, ruta_mp4)\n'
            '        ruta_final   = f"videos/{nombre_mp4}"\n'
            '        nombre_final = nombre_mp4\n'
            '    except Exception as e:\n'
            '        print(f"[VIDEO] ffmpeg falló: {e}")\n'
            '        ruta_final   = f"videos/{nombre_original}"\n'
            '        nombre_final = nombre_original\n'
            '\n'
            '    evento = EventoCamara(\n'
            '        tipo=tipo,\n'
            '        fuente=fuente,\n'
            '        etiqueta=archivo.filename,\n'
            '        imagen_path=ruta_final,\n'
            '        descripcion=desc,\n'
            '    )\n'
            '    db.session.add(evento)\n'
            '    db.session.commit()\n'
            '\n'
            '    return jsonify({"ok": True, "id": evento.id, "archivo": nombre_final}), 201\n',

            "endpoint /video generalizado para .avi y .mp4 con campo fuente"
        ),
    ]

    # ---------- routes/panel.py ----------
    reemplazos_panel_py = [
        (
            '    ultimas_detecciones = (\n'
            '        EventoCamara.query.order_by(EventoCamara.timestamp.desc()).limit(6).all()\n'
            '    )\n',

            '    ultimas_detecciones = (\n'
            '        EventoCamara.query.order_by(EventoCamara.timestamp.desc()).limit(12).all()\n'
            '    )\n',

            "limite de detecciones mostradas de 6 a 12"
        ),
    ]

    # ---------- templates/panel.html ----------
    reemplazos_panel_html = [
        (
            '            <div class="det-label">\n'
            '              {{ d.etiqueta or d.tipo }}\n'
            '              {% if d.confianza %}<span style="color:var(--muted);font-size:11px"> {{ "%.0f"|format(d.confianza * 100) }}%</span>{% endif %}\n'
            '            </div>\n',

            '            <div class="det-label">\n'
            '              {{ d.etiqueta or d.tipo }}\n'
            '              {% if d.confianza %}<span style="color:var(--muted);font-size:11px"> {{ "%.0f"|format(d.confianza * 100) }}%</span>{% endif %}\n'
            '              {% if d.fuente == \'dashcam\' %}\n'
            '                <span class="badge badge-info" style="margin-left:6px">DASHCAM</span>\n'
            '              {% elif d.fuente == \'conductor\' %}\n'
            '                <span class="badge badge-warn" style="margin-left:6px">CONDUCTOR</span>\n'
            '              {% endif %}\n'
            '            </div>\n',

            "badge CONDUCTOR/DASHCAM en panel.html"
        ),
    ]

    exito = True
    exito &= patchear_archivo(RUTA_MODELS, reemplazos_models)
    exito &= patchear_archivo(RUTA_API, reemplazos_api)
    exito &= patchear_archivo(RUTA_PANEL_PY, reemplazos_panel_py)
    exito &= patchear_archivo(RUTA_PANEL_HTML, reemplazos_panel_html)

    if exito:
        print("\nArchivos actualizados. Migrando base de datos...")
        migrar_base_de_datos()
        print("\nListo. Reiniciar el servidor Flask (Ctrl+C y volver a correr app.py)")
        print("para que tome los cambios de models.py.")


if __name__ == "__main__":
    main()
