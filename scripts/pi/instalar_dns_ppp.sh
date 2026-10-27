#!/bin/bash
# Mantiene un DNS de respaldo cuando NetworkManager reescribe resolv.conf (p. ej. al caerse el WiFi).
# Uso:  sudo bash instalar_dns_ppp.sh
# Deshacer:  sudo rm /etc/NetworkManager/dispatcher.d/90-smic-dns
set -e
[ "$EUID" -ne 0 ] && { echo "Corre con sudo"; exit 1; }

DEST=/etc/NetworkManager/dispatcher.d/90-smic-dns
mkdir -p /etc/NetworkManager/dispatcher.d
cat > "$DEST" <<'DISP'
#!/bin/sh
# SMIC: si existe ppp0, asegurar un DNS de respaldo despues de que NetworkManager reescriba resolv.conf.
ip link show ppp0 >/dev/null 2>&1 || exit 0
(
  sleep 3
  grep -q '^nameserver 8.8.8.8' /etc/resolv.conf 2>/dev/null || echo 'nameserver 8.8.8.8' >> /etc/resolv.conf
) &
exit 0
DISP
chown root:root "$DEST"
chmod 755 "$DEST"
echo "Instalado: $DEST"
