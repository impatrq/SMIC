#include <Arduino.h>

#define PIN_TOUCH 4

void setup() {
  Serial.begin(115200);
  Serial.println("Test touch capacitivo");
  Serial.println("Tocá el cable conectado al GPIO4");
  Serial.println("-----------------------------------");
}

void loop() {
  int valor = touchRead(PIN_TOUCH);
  
  if (valor < 20) {
    Serial.print("Valor: ");
    Serial.print(valor);
    Serial.println(" → TOCANDO");
  } else {
    Serial.print("Valor: ");
    Serial.print(valor);
    Serial.println(" → SIN CONTACTO");
  }
  
  delay(200);
}