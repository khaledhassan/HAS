#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include <WiFiClient.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>

const char* ssid = "TPLINK";
const char* password = "1123581321";
const char* mqtt_server = "192.168.1.122";

WiFiClient espClient;
PubSubClient client(espClient);

const int ledPin = 16;
int LED_status = LOW;

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    if (client.connect("ESP8266 Client")) {
      Serial.println("connected");
      // ... and subscribe to topic
      client.subscribe("LED");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  
  DynamicJsonBuffer jsonBuffer(100); // TODO/XXX: make this a stack variable/static allocation

  JsonObject& root = jsonBuffer.parseObject(payload);

  if (!root.success()) {
    Serial.println("JSON parsing failed!");
  }

  if (root["led"] == 0) {
    digitalWrite(ledPin, HIGH);
  } else if (root["led"] == 1) {
    digitalWrite(ledPin, LOW);
  }

  Serial.println();
}

void setup(void) {
  Serial.begin(9600);

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);

  pinMode(ledPin, OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT); 
}

void loop()
{
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}
