"""Cambia la banda del SIM800L para bajar el pico de transmision y escucha si deja de reiniciarse.
Uso en la Pi (con el servicio gprs detenido):
    sudo systemctl stop gprs
    ~/SMIC/venv/bin/python ~/ppp_smic/banda_sim.py pcs        # solo 1900 MHz (menor potencia)
    ~/SMIC/venv/bin/python ~/ppp_smic/banda_sim.py 850pcs     # 850 + 1900
    ~/SMIC/venv/bin/python ~/ppp_smic/banda_sim.py all        # volver a todas las bandas
"""
import serial, sys, time

MODOS = {"pcs": "PCS_MODE", "850pcs": "GSM850_PCS_MODE", "all": "ALL_BAND"}
modo = MODOS.get(sys.argv[1] if len(sys.argv) > 1 else "pcs")
if not modo:
    print("Modo invalido. Usar: pcs | 850pcs | all"); sys.exit(2)

s = serial.Serial("/dev/serial0", 115200, timeout=1)


def leer(seg):
    fin = time.time() + seg
    out = []
    while time.time() < fin:
        l = s.readline().decode(errors="ignore").strip()
        if l:
            out.append(l)
    return out


def at(c, espera=1.5):
    s.reset_input_buffer()
    s.write((c + "\r").encode())
    return " | ".join(leer(espera))


print("Esperando 'SMS Ready' (hasta 60 s)...")
t0 = time.time(); listo = False
while time.time() - t0 < 60:
    l = s.readline().decode(errors="ignore").strip()
    if l:
        print("  ", l)
    if "SMS Ready" in l:
        listo = True; break
if not listo:
    print("No vi 'SMS Ready'; sigo igual.")

print(f'AT+CBAND="{modo}" ->', at(f'AT+CBAND="{modo}"', 3))
print("AT+CBAND?        ->", at("AT+CBAND?"))

print("\nEscuchando 60 s para ver si se reinicia...")
reinicios = 0
t1 = time.time()
while time.time() - t1 < 60:
    l = s.readline().decode(errors="ignore").strip()
    if l:
        print(f"[{time.time()-t1:5.1f}s] {l}")
        if l == "RDY":
            reinicios += 1
print(f"\nReinicios en 60 s: {reinicios}")
if reinicios == 0:
    print("=> Estable. Estado:")
    for c in ("AT+CSQ", "AT+CREG?", "AT+COPS?", "AT+CBC", "AT+CBAND?"):
        print(f"{c:10s} -> {at(c)}")
else:
    print("=> Sigue reiniciandose con esta banda.")
