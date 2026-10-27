"""Deja el SIM800L fijo a 115200 baudios (AT+IPR) para PPP.
Uso (con la fuente de 4V conectada y el servicio gprs detenido):
    sudo systemctl stop gprs
    ~/SMIC/venv/bin/python configurar_baud_sim800l.py
"""
import serial, time, sys
PUERTO = "/dev/serial0"

def at(ser, cmd, espera=1.0):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(espera)
    return ser.read(ser.in_waiting or 1).decode(errors="ignore").strip()

for baud in (115200, 9600, 57600):
    ser = serial.Serial(PUERTO, baud, timeout=1)
    r = at(ser, "AT")
    print(f"{baud}: {r!r}")
    if "OK" in r:
        print("CSQ :", at(ser, "AT+CSQ"))
        print("REG :", at(ser, "AT+CREG?"))
        print("IPR :", at(ser, "AT+IPR=115200"))
        print("SAVE:", at(ser, "AT&W"))
        ser.close()
        print("Listo: SIM800L fijado a 115200.")
        sys.exit(0)
    ser.close()
print("El SIM800L no respondió a ningún baud. Revisá fuente 4V y cableado TX/RX.")
sys.exit(1)
