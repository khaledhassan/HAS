#include <ESP8266WiFi.h>
#include <SimpleDHT.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "DearGod";
const char* password = "1123581321";
const char* mqtt_server = "192.168.1.118";
const char* REPORT_TOPIC = "up/ac";
const char* command_TOPIC = "down/ac";
const char* JOIN_LEAVE_TOPIC = "join_leave";
const char* NODE_NAME = "AC_NODE";
// Predefine handlers
WiFiClient espClient;
PubSubClient mqtt(espClient);
SimpleDHT11 dht11;
StaticJsonBuffer<256> jsonBuffer;
// Prepare joind and will json obj
JsonObject& will = jsonBuffer.createObject();
JsonObject& join_event = jsonBuffer.createObject();

//Predefine pins
const int dhtPin = 5;
const int fanPin = 4;

//Predefine
String mac; //Official Arduino String Class. 
JsonObject& data_up = jsonBuffer.createObject(); // generate string, quote
char data_up_char[256];
char join_buffer[128];
char will_buffer[128];

void connectWifi(){
  Serial.print("Connecting to ");
  Serial.println(ssid);
  /* Explicitly set the ESP8266 to be a WiFi-client, otherwise, it by default,
     would try to act as both a client and an access-point and could cause
     network-issues with your other WiFi-devices on your WiFi-network. */
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    digitalWrite(LED_BUILTIN, !digitalRead(BUILTIN_LED));
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.println("MAC address: ");
  Serial.println(WiFi.macAddress());
  mac = WiFi.macAddress();// return String
  // data_up["id"] = mac; // tell python who I am
}
void reconnect() {
  // Loop until we're reconnected
  bool connect_result;
  
  //Prepare mqtt will
  will["id"] = mac;
  will["type"] = "AC";
  will["o"] = "LEAVE";
  will.printTo(will_buffer);
  // Prepare join event 
  join_event["id"] = mac;
  join_event["type"] = "AC";
  join_event["o"] = "JOIN";
  
  join_event.printTo(join_buffer);

  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    connect_result = mqtt.connect(NODE_NAME, JOIN_LEAVE_TOPIC, 2, false, will_buffer);
    if (connect_result == true) {
      Serial.println("connected");
      // ... and subscribe to topic
      mqtt.subscribe(command_TOPIC);
      // report node join event
      mqtt.publish(JOIN_LEAVE_TOPIC, join_buffer);
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}

void onMsg(char* topic, byte* payload, unsigned int length) { //only command msg, like whoru, or settemperature
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.println("] ");
  
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
  StaticJsonBuffer<256> jB;
  JsonObject& root = jB.parseObject(payload);

  if (!root.success()) {
    Serial.println("JSON parsing failed!");
  }
  
  if (root["type"] == "whoru")
  {// receive whoru query, re-publish join event
    Serial.println("WHO r u request received, republish join event. ");
    mqtt.publish(JOIN_LEAVE_TOPIC, join_buffer);
    delay(1000);
  }
  // if (root["id"] == mac)

  // if (root["led"] == 0) {
  //   digitalWrite(LED_BUILTIN, HIGH);
  // } else if (root["led"] == 1) {
  //   digitalWrite(LED_BUILTIN, LOW);
  // }

  Serial.println();
}

void report()
{                        
  byte temperature = 0;
  byte humidity = 0;
  int err = SimpleDHTErrSuccess;
  if ((err = dht11.read(dhtPin, &temperature, &humidity, NULL)) != SimpleDHTErrSuccess) {
    Serial.print("Communication error with Sensor 1, err="); Serial.println(err);delay(1000);
    return;
  }
   // converting Celsius to Fahrenheit

  byte f = temperature * 1.8 + 32;  

  data_up["id"] = mac; // tell python who I am
  data_up["type"] = "AC"; // tell python who I am
  data_up["t"] = f;
  data_up["h"] = humidity;
  String output = ""; //String class is from ArduinoJSON library
  data_up.printTo(output); //dump json to output
  output.toCharArray(data_up_char, 128);
  mqtt.publish(REPORT_TOPIC, data_up_char);
}

void setup(void) {
  // pinMode(LED_BUILTIN, OUTPUT); // WIFI indicator
  // digitalWrite(LED_BUILTIN, LOW);

  Serial.begin(9600);
  Serial.println();
  Serial.println();
  Serial.println("System booting...");
  connectWifi();
  

  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(onMsg);
}

void loop()
{
  if (!mqtt.connected()) {
    reconnect();
  }
  mqtt.loop();
  report();
  delay(1000);
}

