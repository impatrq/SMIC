#include <Arduino.h>
#include "esp_sleep.h"

#define PIN_TOUCH 4
#define UMBRAL_TOUCH 20
#define SLEEP_US 500000 // 500ms en microsegundos

void setup()
{
  Serial.begin(115200);
  delay(100);

  // Leer el sensor
  int valor = touchRead(PIN_TOUCH);
  bool tocando = valor < UMBRAL_TOUCH;

  // Mostrar resultado
  Serial.print("Valor: ");
  Serial.print(valor);
  if (tocando)
  {
    Serial.println(" → TOCANDO");
  }
  else
  {
    Serial.println(" → SIN CONTACTO");
  }

  // Volver a deep sleep por 500ms
  esp_sleep_enable_timer_wakeup(SLEEP_US);
  Serial.println("Entrando a deep sleep...");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop()
{
  // No se usa - deep sleep reinicia desde setup()
}