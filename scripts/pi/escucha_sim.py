"""Escucha el SIM800L 90 s, cuenta reinicios y, si esta estable, consulta el registro.
Uso en la Pi:
    sudo systemctl stop gprs
    ~/SMIC/venv/bin/python ~/ppp_smic/escucha_sim.py
"""
import serial, time, sys

PUERTO = "/dev/serial0"
BAUD = 115200
DURACION = 90

s = serial.Serial(PUERTO, BAUD, timeout=1)
t0 = time.time()
reinicios = 0
print(f"Escuchando {DURACION} s (cualquier linea que aparezca sola = el modulo se reinicio)...")
sys.stdout.flush()
while time.time() - t0 < DURACION:
    l = s.readline().decode(errors="ignore").strip()
    if l:
        print(f"[{time.time()-t0:5.1f}s] {l}")
        sys.stdout.flush()
        if l == "RDY":
            reinicios += 1

print(f"\nReinicios detectados: {reinicios}")
if reinicios > 1:
    print("=> Sigue reiniciandose. Revisar alimentacion del modulo.")
    sys.exit(1)

print("=> Estable. Consultando estado...\n")


def at(c):
    s.reset_input_buffer()
    s.write((c + "\r").encode())
    time.sleep(1)
    return s.read(s.in_waiting or 1).decode(errors="ignore").replace("\r\n", " | ").strip()


for c in ("AT", "AT+CPIN?", "AT+CSQ", "AT+CREG?", "AT+COPS?", "AT+CBC"):
    print(f"{c:10s} -> {at(c)}")
