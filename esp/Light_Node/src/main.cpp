#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "TPLINK";
const char* password = "1123581321";
const char* mqtt_server = "10.42.0.1";

WiFiClient espClient;
PubSubClient mqtt(espClient);

String mac;
char JOIN_LEAVE_TOPIC[32];
char SENSOR_TOPIC[32]; // Like: sensor/<macaddress>
char ACTUATOR_TOPIC[32]; // Like: sensor/<macaddress>

bool light_on = false;
bool motion_detected = false;

const int motion_pin = 5;
const int light_pin = 4;

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
      digitalWrite(LED_BUILTIN, !digitalRead(BUILTIN_LED));
      Serial.print(".");
    }
  
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
  
    mac = WiFi.macAddress();// return String
    mac.replace(String(':'), String()); // Remove All :
    Serial.print("MAC address: ");
    Serial.println(mac);
  
    //Updating sensor and actuator topic
    String j = "join_leave/";
    j.concat(mac);
    j.toCharArray(JOIN_LEAVE_TOPIC, 32);

    String t = "sensor/";
    t.concat(mac);
    t.toCharArray(SENSOR_TOPIC, 32);
  
    String m = "actuator/";
    m.concat(mac);
    m.toCharArray(ACTUATOR_TOPIC, 32);
  }

void reconnect() {
    StaticJsonBuffer<256> jsonBuffer;    
    // Loop until we're reconnected
    bool connect_result;
  
    // Prepare join event 
    char join_buffer[128];
    JsonObject& join_event = jsonBuffer.createObject();
    join_event["mac"] = mac;
    join_event["status"] = "JOIN";
  
    // Prepare joind and will json obj
    char will_buffer[128];
    JsonObject& will = jsonBuffer.createObject();
    will["mac"] = mac;
    will["status"] = "LEAVE";
  
    will.printTo(will_buffer);
    join_event.printTo(join_buffer);
    
    Serial.print("Join Event:");
    Serial.println(join_buffer);
    Serial.print("Will Event:");
    Serial.println(will_buffer);

    while (!mqtt.connected()) {
        Serial.print("Attempting MQTT connection...");
        // Attempt to connect
        char mac2[13];
        mac.toCharArray(mac2, 13);
        connect_result = mqtt.connect(mac2, JOIN_LEAVE_TOPIC, 2, true, will_buffer);
        if (connect_result == true) {
            Serial.println("connected");
            // ... and subscribe to topic
            mqtt.subscribe(ACTUATOR_TOPIC);
            Serial.print("Subscribe to ");
            Serial.println(ACTUATOR_TOPIC);
            // report node join event
            mqtt.publish(JOIN_LEAVE_TOPIC, join_buffer, true);
        } else {
            Serial.print("failed, rc=");
            Serial.print(mqtt.state());
            Serial.println(" try again in 5 seconds");
            // Wait 5 seconds before retrying
            delay(5000);
        }
    }
}
  


void publish_state(){
    StaticJsonBuffer<256> jsonBuffer;    
    char state_buffer[128];
    JsonObject& state_msg = jsonBuffer.createObject();
    state_msg["mac"] = mac;
    state_msg["state"] = light_on;
    state_msg.printTo(state_buffer);
    mqtt.publish(SENSOR_TOPIC, state_buffer);
}

void publish_motion(){
    StaticJsonBuffer<256> jsonBuffer;    
    char motion_buffer[128];
    JsonObject& motion_msg = jsonBuffer.createObject();
    motion_msg["mac"] = mac;
    motion_msg["motion"] = String("detected");
    motion_msg.printTo(motion_buffer);
    mqtt.publish(SENSOR_TOPIC, motion_buffer);
}


void change_state(bool want_on){
    if (want_on) {
        digitalWrite(light_pin, HIGH);
    } else {
        digitalWrite(light_pin, LOW);
    }
    light_on = want_on;
}

void motion_ISR(){
    Serial.println("Motion Detected");
    motion_detected = true;
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
    if(root["cmd"] == "state") {
        publish_state();
    } else if(root["cmd"] == "light_on")  {
        change_state(true);
    } else if(root["cmd"] == "light_off") {
        change_state(false);
    } else {
      Serial.println("Unknown event received.");
    }
    Serial.println();
}

void setup(){
    pinMode(light_pin, OUTPUT);
    pinMode(motion_pin, INPUT);
    attachInterrupt(motion_pin, motion_ISR, RISING);

    Serial.begin(9600);
    Serial.println();
    Serial.println();
    Serial.println("System booting...");
    connectWifi();

    mqtt.setServer(mqtt_server, 1883);
    mqtt.setCallback(onMsg);
}

void loop(){
    if (!mqtt.connected()) {
        reconnect();
    }
    mqtt.loop();

    if (motion_detected) {
        motion_detected = false;
        publish_motion();
    }

    delay(1000);
}