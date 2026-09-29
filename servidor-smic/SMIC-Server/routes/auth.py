import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, logout_user, login_required
from werkzeug.security import check_password_hash

auth_bp = Blueprint("auth", __name__)

ADMIN_ID = "admin"


class Admin(UserMixin):
    """Un solo usuario admin, credenciales por variable de entorno -- no
    hace falta una tabla en la base para esto."""

    def __init__(self, user_id):
        self.id = user_id

    @staticmethod
    def cargar(user_id):
        if user_id == ADMIN_ID:
            return Admin(user_id)
        return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        clave = request.form.get("clave", "")

        usuario_esperado = os.environ.get("SMIC_ADMIN_USER", "admin")
        hash_esperado = os.environ.get("SMIC_ADMIN_PASSWORD_HASH")

        if (
            hash_esperado
            and usuario == usuario_esperado
            and check_password_hash(hash_esperado, clave)
        ):
            login_user(Admin(ADMIN_ID))
            return redirect(url_for("panel.inicio"))

        flash("Usuario o contraseña incorrectos")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
