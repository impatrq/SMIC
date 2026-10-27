#!/bin/bash
# Mejora la secuencia de marcado PPP: engancha datos y usa el contexto 1 explicitamente.
# Uso:  sudo bash fix_chat_ppp.sh
# Deshacer:  sudo cp /etc/chatscripts/gprs-connect.bak /etc/chatscripts/gprs-connect
set -e
[ "$EUID" -ne 0 ] && { echo "Corre con sudo"; exit 1; }

ARCH=/etc/chatscripts/gprs-connect
[ -f "$ARCH.bak" ] || cp "$ARCH" "$ARCH.bak"

cat > "$ARCH" <<'CHAT'
ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'NO DIALTONE'
ABORT 'ERROR'
TIMEOUT 30
'' ATZ
OK ATE0
OK "AT+CGDCONT=1,\"IP\",\"igprs.claro.com.ar\""
OK AT+CGATT=1
OK ATD*99***1#
CONNECT ''
CHAT

echo "Listo. Respaldo en $ARCH.bak"
cat "$ARCH"
