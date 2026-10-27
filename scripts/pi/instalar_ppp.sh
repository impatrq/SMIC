#!/bin/bash
# Instala PPP sobre SIM800L (Claro). Ejecutar en la Pi:  sudo bash instalar_ppp.sh
# Es idempotente: se puede correr varias veces.
set -e
[ "$EUID" -ne 0 ] && { echo "Corré con sudo"; exit 1; }

APN="igprs.claro.com.ar"
PUERTO="/dev/serial0"
BAUD=115200

apt-get update -y
apt-get install -y ppp

mkdir -p /etc/chatscripts

cat > /etc/chatscripts/gprs-connect <<CHAT
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'NO DIALTONE'
ABORT 'ERROR'
TIMEOUT 20
'' ATZ
OK ATE0
OK "AT+CGDCONT=1,\"IP\",\"$APN\""
OK ATD*99#
CONNECT ''
CHAT

cat > /etc/chatscripts/gprs-disconnect <<'CHAT'
ABORT 'ERROR'
TIMEOUT 5
'' +++
'' ATH
CHAT

cat > /etc/ppp/peers/gprs <<PEER
$PUERTO
$BAUD
nocrtscts
lock
noauth
noipdefault
defaultroute
# metrica alta: WiFi/Ethernet (100-600) siempre tienen prioridad sobre ppp0
defaultroute-metric 700
persist
maxfail 0
holdoff 20
nodetach
noccp
novj
lcp-echo-interval 30
lcp-echo-failure 4
connect "/usr/sbin/chat -v -f /etc/chatscripts/gprs-connect"
disconnect "/usr/sbin/chat -v -f /etc/chatscripts/gprs-disconnect"
PEER

# DNS de respaldo cuando ppp0 sube sin WiFi
cat > /etc/ppp/ip-up.d/smic-dns <<'UP'
#!/bin/sh
[ "$PPP_IFACE" = "ppp0" ] || exit 0
grep -q '^nameserver 8.8.8.8' /etc/resolv.conf 2>/dev/null || echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
UP
chmod +x /etc/ppp/ip-up.d/smic-dns

cat > /etc/systemd/system/gprs.service <<'SVC'
[Unit]
Description=SMIC - PPP por SIM800L
After=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/pppd call gprs
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
echo
echo "Listo. NO está habilitado todavía. Probalo con:"
echo "  sudo systemctl start gprs ; sleep 40 ; ip addr show ppp0"
echo "  curl --interface ppp0 -m 60 -s -o /dev/null -w '%{http_code} %{time_total}s\n' https://smic-henna.vercel.app/api/resumen"
echo "Si funciona:  sudo systemctl enable gprs"
