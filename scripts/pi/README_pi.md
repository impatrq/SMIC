# Configuración de la Raspberry Pi (PPP, arranque automático, Bluetooth)

Scripts que se usaron para dejar la Pi 4 funcionando con SMIC. Se corren **en la Pi**
(copiados con `scp` a `~/ppp_smic/`). Los `.sh` tienen que tener finales de línea LF;
si Git los convierte a CRLF, en la Pi: `sed -i 's/\r$//' archivo.sh`.

## Orden con el que se armó la Pi actual

1. `configurar_baud_sim800l.py` — deja el SIM800L a 115200 baudios (`AT+IPR=115200`, `AT&W`).
2. `instalar_ppp.sh` — instala `ppp` y crea `gprs.service`, el peer y el chat script.
   **Ojo:** este instalador trae el chat script viejo y las líneas `lcp-echo` activas.
   La configuración que anda es la de los pasos 3 y 4.
3. `fix_chat_ppp.sh` — chat script correcto (`AT+CGATT=1`, `ATD*99***1#`).
4. En `/etc/ppp/peers/gprs` hay que dejar **comentadas** las líneas `lcp-echo-*`
   (la red no responde al LCP echo y el enlace se caía):
   `sudo sed -i 's/^lcp-echo/#lcp-echo/' /etc/ppp/peers/gprs`
5. `instalar_dns_ppp.sh` — script de `NetworkManager` que repone el DNS cuando cae el WiFi.
6. `instalar_arranque.sh` — servicio `smic.service`: arranca `camara.monitor` al encender
   y habilita `gprs`.
7. Bluetooth interno: en `/boot/firmware/config.txt` cambiar `dtoverlay=disable-bt`
   por `dtoverlay=miniuart-bt` (hace falta para el volante BLE; el SIM800L sigue en `ttyAMA0`).
   Se hizo con copia previa `config.txt.bak_bt`.

## Herramientas de diagnóstico

- `escucha_sim.py` — escucha el SIM800L 90 s y cuenta reinicios (`RDY`).
- `banda_sim.py [pcs|850pcs|all]` — cambia la banda GSM (`AT+CBAND`). Queda en `850pcs`.
- `gprs_estado.py` — estado de datos GPRS del módulo.
- `prueba_sin_wifi.sh` — apaga el WiFi, manda una alerta de prueba por PPP y restaura el WiFi.
- `ble_diagnostico.py` — lista servicios BLE del volante y escucha notificaciones.

## Notas

- Alimentación: la Pi dio `undervoltage` con el stepdown; el SIM800L necesita un
  stepdown propio (4,0–4,2 V) con capacitores de 1000–4700 µF cerca del módulo.
- Las alertas viajan por SIM (PPP) y los clips solo por WiFi: `sincronizador.hay_conexion()`
  devuelve `False` cuando la salida es `ppp0`.
- Firmware del volante: `esp32/esp32-prueba/esp32_smic/src/main.cpp` (BLE `SMIC-Volante`,
  deep sleep con ventana de anuncio).
