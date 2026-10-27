#!/bin/bash
# Hace que SMIC (camara.monitor) arranque solo al encender la Pi, y se reinicie si se cae.
# Uso:  sudo bash instalar_arranque.sh
# Deshacer:  sudo systemctl disable --now smic && sudo rm /etc/systemd/system/smic.service && sudo systemctl daemon-reload
set -e
[ "$EUID" -ne 0 ] && { echo "Corre con sudo"; exit 1; }

USUARIO=proyecto-smic
DIR=/home/$USUARIO/SMIC
PY=$DIR/venv/bin/python

[ -x "$PY" ] || { echo "No encuentro $PY"; exit 1; }
[ -f "$DIR/camara/monitor.py" ] || { echo "No encuentro $DIR/camara/monitor.py"; exit 1; }

cat > /etc/systemd/system/smic.service <<EOF
[Unit]
Description=SMIC - Monitor de conductor
# gprs.service da la salida por SIM800L; si falla, el monitor igual arranca.
After=gprs.service
Wants=gprs.service

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$PY -u -m camara.monitor
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gprs smic
echo
echo "Listo. Estado de arranque:"
systemctl is-enabled gprs smic
echo
echo "Para probarlo ya:      sudo systemctl start smic"
echo "Ver el log en vivo:    journalctl -u smic -f"
echo "Detenerlo:             sudo systemctl stop smic"
