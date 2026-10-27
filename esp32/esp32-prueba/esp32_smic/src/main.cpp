#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "esp_sleep.h"

// ─────────────────────────────────────────
// SMIC - Modulo Volante (1 sensor capacitivo, papel aluminio)
// GPIO4 = T0, no es strapping pin
//
// Deep sleep CONSERVADO, pero con ventana de anuncio:
//  - Al despertar, el chip se queda despierto y anunciando BLE durante
//    VENTANA_ANUNCIO_MS, para que la Raspberry tenga tiempo de verlo y conectarse.
//  - Si nadie se conecta en esa ventana, vuelve a deep sleep TIEMPO_SLEEP_US.
//  - Mientras haya una Raspberry conectada NO duerme (dormir cortaria el enlace)
//    y notifica cada INTERVALO_MS.
//  - Si la Raspberry se desconecta, se abre una nueva ventana de anuncio.
// ─────────────────────────────────────────
#define PIN_TOUCH 4

#define UMBRAL_CONTACTO     20
#define INTERVALO_MS        200      // periodo de notificacion con conexion activa
#define VENTANA_ANUNCIO_MS  4000     // despierto y anunciando antes de dormir
#define TIEMPO_SLEEP_US     1000000  // 1 s de deep sleep (ajustable: mas = menos consumo)

#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcdefab-cdef-abcd-efab-cdefabcdefab"

BLECharacteristic *pCaracteristica;
volatile bool dispositivoConectado = false;
volatile unsigned long t_ventana = 0;   // inicio de la ventana de anuncio (millis)

class CallbacksServidor : public BLEServerCallbacks {
    void onConnect(BLEServer *pServer) {
        dispositivoConectado = true;
        Serial.println("[BLE] Raspberry Pi conectada");
    }
    void onDisconnect(BLEServer *pServer) {
        dispositivoConectado = false;
        t_ventana = millis();               // nueva ventana de anuncio
        Serial.println("[BLE] Raspberry Pi desconectada, anunciando de nuevo...");
        delay(300);
        BLEDevice::startAdvertising();
    }
};

void setup() {
    Serial.begin(115200);
    Serial.println("SMIC - Modulo Volante ESP32 (deep sleep con ventana de anuncio)");
    Serial.println("-----------------------------------");

    BLEDevice::init("SMIC-Volante");

    BLEServer *pServidor = BLEDevice::createServer();
    pServidor->setCallbacks(new CallbacksServidor());

    BLEService *pServicio = pServidor->createService(SERVICE_UUID);

    pCaracteristica = pServicio->createCharacteristic(
        CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_READ |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pCaracteristica->addDescriptor(new BLE2902());

    pServicio->start();

    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    BLEDevice::startAdvertising();

    t_ventana = millis();
    Serial.println("[BLE] Advertising activo, esperando RPi...");
}

void loop() {
    int valor = touchRead(PIN_TOUCH);
    bool hayContacto = (valor < UMBRAL_CONTACTO);

    Serial.print("Valor: ");
    Serial.print(valor);
    Serial.println(hayContacto ? " -> TOCANDO" : " -> SIN CONTACTO");

    if (dispositivoConectado) {
        String datos = "{\"valor\":" + String(valor) +
                       ",\"contacto\":" + String(hayContacto ? 1 : 0) + "}";
        pCaracteristica->setValue(datos.c_str());
        pCaracteristica->notify();
        delay(INTERVALO_MS);
        return;
    }

    // Sin conexion: seguir despierto durante la ventana de anuncio
    if (millis() - t_ventana < VENTANA_ANUNCIO_MS) {
        delay(100);
        return;
    }

    // Ventana vencida y nadie conectado -> deep sleep
    Serial.println("[SLEEP] Sin conexion, deep sleep...");
    Serial.flush();
    esp_sleep_enable_timer_wakeup(TIEMPO_SLEEP_US);
    esp_deep_sleep_start();
}
