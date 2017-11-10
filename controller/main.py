import paho.mqtt.client as mqtt
import json
import pprint

online_list = {}
mqttServer = "mqtt" # Handled by docker-compose link


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("up/+")
    client.subscribe("join_leave")


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    j = json.loads(msg.payload)

    if msg.topic == "join_leave":#device join or leavethe network

        if j['o'] == "LEAVE":
            online_list.pop(j['id'], None)
        else: # JOIN
            j.pop('o', None)
            online_list[j['id']] = j

    else:#data up report

        if j["id"] in online_list: # known node, report sensor data
            print(msg.payload)
        else: # unknown node
            client.publish(msg.topic.replace("up", "down"), "{\"id\":\""+j["id"]+"\",\"type\":\"whoru\"}")
    print(online_list)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(mqttServer, 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("Program end")
