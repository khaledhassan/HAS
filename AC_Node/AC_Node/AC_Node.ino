#include <ESP8266WiFi.h>
//#include <WiFiClient.h>
#include <SimpleDHT.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "TPLINK";
const char* password = "1123581321";
const char* mqtt_server = "192.168.1.118";

// Predefine handlers
WiFiClient espClient;
PubSubClient mqtt(espClient);
SimpleDHT11 dht11;
StaticJsonBuffer<200> jsonBuffer;

//Predefine pins
const int dhtPin = 16;
const int fanPin = 5;

//Predefine
String mac;
JsonObject& data_up = jsonBuffer.createObject(); // generate string
char data_up_char[128];

void reconnect() {
  // Loop until we're reconnected
  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    if (mqtt.connect("AC_NODE")) {
      Serial.println("connected");
      // ... and subscribe to topic
      mqtt.subscribe("LED");
      // ... and start timer
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
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
 
  JsonObject& root = jsonBuffer.parseObject(payload);

  if (!root.success()) {
    Serial.println("JSON parsing failed!");
  }

  if (root["led"] == 0) {
    digitalWrite(LED_BUILTIN, HIGH);
  } else if (root["led"] == 1) {
    digitalWrite(LED_BUILTIN, LOW);
  }

  Serial.println();
}

void setup(void) {
  
  Serial.begin(9600);
  Serial.println();
  Serial.println();
  Serial.println("System booting...");
  Serial.print("Connecting to ");
  Serial.println(ssid);

  /* Explicitly set the ESP8266 to be a WiFi-client, otherwise, it by default,
     would try to act as both a client and an access-point and could cause
     network-issues with your other WiFi-devices on your WiFi-network. */
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.println("MAC address: ");
  Serial.println(WiFi.macAddress());
  mac = "";
  mac = WiFi.macAddress();// return string
  data_up["mac"] = mac;
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(callback);
  
  pinMode(LED_BUILTIN, OUTPUT); 
}

void loop()
{
  if (!mqtt.connected()) {
    reconnect();
  }
  mqtt.loop();
  delay(500);
  report();
}

void report()
{                        
  String output = "";
  data_up.printTo(output);
  output.toCharArray(data_up_char, 128);
  mqtt.publish("test", data_up_char);
}

