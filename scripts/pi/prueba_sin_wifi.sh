#!/bin/bash
# Apaga el WiFi, manda una alerta de prueba por PPP y vuelve a prender el WiFi.
# El SSH se va a cortar ~1-2 min. Reconectar despues y leer ~/prueba_sin_wifi.log
# Uso:  sudo nohup bash ~/ppp_smic/prueba_sin_wifi.sh >/dev/null 2>&1 &
# (Desenchufar el cable ethernet si hubiera uno.)
LOG=/home/proyecto-smic/prueba_sin_wifi.log
exec > "$LOG" 2>&1
trap 'nmcli radio wifi on' EXIT
echo "inicio $(date)"
echo "gprs: $(systemctl is-active gprs)"
echo "--- rutas con wifi"; ip route
nmcli radio wifi off
sleep 10
echo "--- rutas SIN wifi"; ip route
echo "--- resolv.conf"; cat /etc/resolv.conf
echo "--- DNS"; getent hosts smic-henna.vercel.app || echo "SIN DNS"
echo "--- alerta de prueba"
cd /home/proyecto-smic/ppp_smic
/home/proyecto-smic/SMIC/venv/bin/python alerta_ppp.py prueba
echo "--- fin alerta $(date)"
nmcli radio wifi on
sleep 20
echo "--- rutas con wifi de nuevo"; ip route
echo "fin $(date)"
