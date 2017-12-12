// DOOR_Node MAC: A0:20:A6:17:F4:25(Which is AC Node)
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#define LOCKED HIGH
 
const char* ssid = "TP-LINK_PocketAP_287C0A";
const char* password = "";
const char* mqtt_server = "10.42.0.114"; //Khaled's computer, will be chanded to 

const char* NODE_NAME = "DOOR_NODE";

// Predefine handlers
WiFiClient espClient;
PubSubClient mqtt(espClient);

//Predefine pins
const int door_pin = 5;

//Predefine
String mac; //Official Arduino String Class. 

char data_up_char[256];
int lock_status = LOCKED; // High means locked
int last_report_time = 0; //initialize last report time in millisecond
int recent_unlock_time = 0; //milliseconds, will be compared each loop. If diff is larger than 15000(15s), then set it to 0 to it again. 

//Predefine MSG to MQTT
char JLT[32]; //join_leave_topic
char SENSOR_TOPIC[32]; // Like: sensor/<macaddress>
char ACTUATOR_TOPIC[32]; // Like: actuator/<macaddress>

void connectWifi(){
  delay(1000); //debug
  Serial.print("Connecting to ");
  Serial.println(ssid);
  /* Explicitly set the ESP8266 to be a WiFi-client, otherwise, it by default,
     would try to act as both a client and an access-point and could cause
     network-issues with your other WiFi-devices on your WiFi-network. */
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    digitalWrite(LED_BUILTIN, !digitalRead(BUILTIN_LED)); //blink for connecting
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());

  mac = WiFi.macAddress();// return String
  mac.replace(String(':'), String()); // Remove All :
  String JOIN_LEAVE_TOPIC = "join_leave/"; //only be used locally
  JOIN_LEAVE_TOPIC.concat(mac);
  JOIN_LEAVE_TOPIC.toCharArray(JLT, 32);
  Serial.print("MAC address: ");
  Serial.println(mac);

  //Updating sensor and actuator topic
  String t = "sensor/";
  t.concat(mac);
  t.toCharArray(SENSOR_TOPIC, 32);

  String m = "actuator/";
  m.concat(mac);
  m.toCharArray(ACTUATOR_TOPIC, 32);
}

void reconnect() {
  // Loop until we're reconnected
  bool connect_result;

  // Prepare join event 


  StaticJsonBuffer<256> jsonBuffer; //only local 
  char join_buffer[128];
  JsonObject& join_event = jsonBuffer.createObject();
  join_event["mac"] = mac;
  join_event["type"] = "door";
  join_event["status"] = "join";

  // Prepare joind and will json obj
  char will_buffer[128];
  JsonObject& will = jsonBuffer.createObject();
  will["mac"] = mac;
  will["type"] = "door";
  will["status"] = "leave";

  will.printTo(will_buffer);
  join_event.printTo(join_buffer);

  Serial.print("Join Event:");
  Serial.println(join_buffer);
  Serial.print("Will Event:");
  Serial.println(will_buffer);

  while (!mqtt.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Attempt to connect
    connect_result = mqtt.connect(NODE_NAME, JLT, 2, true, will_buffer);
    if (connect_result == true) {
      Serial.println("connected");
      // ... and subscribe to topic
      mqtt.subscribe(ACTUATOR_TOPIC);
      Serial.print("Subscribe to ");
      Serial.println(ACTUATOR_TOPIC);
      // report node join event
      mqtt.publish(JLT, join_buffer, true);
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}
void set_lock(void){
    digitalWrite(door_pin, lock_status);
}
void onMsg(char* topic, byte* payload, unsigned int length) { //only command msg, like whoru, or settemperature
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.println("] ");
  
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
  StaticJsonBuffer<256> msgBuffer;
  JsonObject& root = msgBuffer.parseObject(payload);

  if (!root.success()) {
    Serial.println("JSON parsing failed!");
  }
  
  // No switch support.         
  if(root["action"] == "unlock")
  {
    lock_status = !LOCKED;
    recent_unlock_time = millis();
    Serial.println("Door Unlocked");
  }else{
    Serial.println("Unknown event received.");
  }
  set_lock();
}

void report()
{                        

  StaticJsonBuffer<256> jsonBuffer; //only local 
  JsonObject& data_up = jsonBuffer.createObject(); // generate string, quote
  data_up["mac"] = mac; // tell python who I am
  data_up["type"] = "door"; // tell python what node I am
  data_up["status"] =  lock_status == LOCKED? "locked":"unlocked";
  data_up.printTo(data_up_char); //dump json to output
  // output.toCharArray(data_up_char, 128);
  mqtt.publish(SENSOR_TOPIC, data_up_char);
}

void setup(void) {
  // pinMode(LED_BUILTIN, OUTPUT); // WIFI indicator
  // digitalWrite(LED_BUILTIN, LOW);

  pinMode(door_pin, OUTPUT); // control the fan
  Serial.begin(9600);
  Serial.println();
  Serial.println();
  Serial.println("System booting...");
  connectWifi();
  mqtt.setServer(mqtt_server, 1883);
  mqtt.setCallback(onMsg);
  lock_status = LOCKED;
  set_lock();
}

void loop()
{
  if (!mqtt.connected()) {
    reconnect();
  }

  mqtt.loop();

  if(millis() - last_report_time > 1000){
    report();
    last_report_time = millis(); // update last report time
  }

  if(lock_status != LOCKED){//unlocking
    delay(1000);
    int diff = millis() - recent_unlock_time;
    Serial.println(diff/1000);
    if(diff > 15000){
      lock_status = LOCKED;
      Serial.println("Lock Again");
      set_lock();
    }
  }
}