"""Muestra el estado de datos (GPRS) del SIM800L e intenta engancharlo.
Uso en la Pi:
    sudo systemctl stop gprs
    ~/SMIC/venv/bin/python ~/ppp_smic/gprs_estado.py
"""
import serial, time

s = serial.Serial("/dev/serial0", 115200, timeout=1)


def at(c, espera=1.5):
    s.reset_input_buffer()
    s.write((c + "\r").encode())
    fin = time.time() + espera
    out = []
    while time.time() < fin:
        l = s.readline().decode(errors="ignore").strip()
        if l:
            out.append(l)
    return " | ".join(out)


def mostrar(c, espera=1.5):
    print(f"{c:12s} -> {at(c, espera)}")


for c in ("AT", "AT+CSQ", "AT+CREG?", "AT+COPS?", "AT+CGATT?", "AT+CGREG?", "AT+CGACT?"):
    mostrar(c)

print("\nIntentando enganchar datos (hasta 30 s)...")
mostrar("AT+CGATT=1", 30)
for c in ("AT+CGATT?", "AT+CGREG?"):
    mostrar(c)

print("\nContexto de datos:")
mostrar("AT+CGDCONT?")
mostrar("AT+CGACT=1,1", 20)
mostrar("AT+CGACT?")
mostrar("AT+CGPADDR=1")
mostrar("AT+CGACT=0,1", 5)
